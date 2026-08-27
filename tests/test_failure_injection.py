"""Cross-stage failure-injection matrix for atomic command processing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from symbox.application.attributes import parse_assignments
from symbox.application.embedding_ports import EmbeddingError
from symbox.application.mutations import BindingExecutionError, MutationSnapshot, execute_binding
from symbox.application.similarity import assess_similarity
from symbox.application.transactions import TransactionCoordinator
from symbox.integrations.python_bindings import BindingLoadError, ProjectPythonBindingLoader
from symbox.persistence.backup_repository import BackupError, GitBackupRepository
from symbox.persistence.state_format import StateDocument
from symbox.persistence.state_repository import ProjectScope, StateRepository


@dataclass(frozen=True)
class _Snapshot:
    value: int


class _Store:
    def __init__(self) -> None:
        self.state = _Snapshot(1)
        self.save_calls = 0

    def load(self) -> _Snapshot:
        return self.state

    def save(self, state: _Snapshot) -> None:
        self.save_calls += 1
        self.state = state


class _FailingEmbedding:
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise EmbeddingError("injected embedding timeout")


def test_parse_failure_occurs_before_any_persistent_candidate(tmp_path: Path) -> None:
    repository = StateRepository(ProjectScope(tmp_path))
    repository.save(StateDocument(revision=1))
    before = repository.scope.state_path.read_bytes()

    with pytest.raises(ValueError):
        parse_assignments(("broken",))

    assert repository.scope.state_path.read_bytes() == before


def test_binding_load_and_execution_failures_discard_candidates(tmp_path: Path) -> None:
    committed = MutationSnapshot({"level": 12})

    with pytest.raises(BindingLoadError):
        ProjectPythonBindingLoader().load(tmp_path, "missing.py", "check")

    def explode(subject: object) -> bool:
        raise RuntimeError("injected binding failure")

    with pytest.raises(BindingExecutionError, match="injected binding failure"):
        execute_binding(committed, explode, "robot")
    assert committed.values == {"level": 12}


@pytest.mark.parametrize("stage", ["kernel", "propagate"])
def test_kernel_stage_failure_never_commits_candidate(stage: str) -> None:
    store = _Store()
    coordinator = TransactionCoordinator(store)

    def fail(_: _Snapshot) -> None:
        raise RuntimeError(f"injected {stage} failure")

    with pytest.raises(RuntimeError, match=stage):
        coordinator.execute(
            lambda _: _Snapshot(2),
            synchronize_kernel=fail if stage == "kernel" else None,
            propagate=fail if stage == "propagate" else None,
        )

    assert store.save_calls == 0
    assert store.state == _Snapshot(1)
    assert coordinator.committed == _Snapshot(1)


def test_embedding_failure_degrades_without_authorizing_or_blocking_write() -> None:
    assessment = assess_similarity(
        _FailingEmbedding(),
        subject="robot",
        proposed_key="battery-level",
        existing_keys=("battery",),
        threshold=0.9,
    )

    assert assessment.confirmation is None
    assert assessment.diagnostics[0].code == "embedding_unavailable"
    assert assessment.diagnostics[0].degraded


def test_persistence_replace_failure_preserves_old_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = StateRepository(ProjectScope(tmp_path))
    repository.save(StateDocument(revision=1, objects=({"name": "before"},)))
    before = repository.scope.state_path.read_bytes()

    def fail_replace(source: str | Path, destination: str | Path) -> None:
        raise OSError("injected persistence failure")

    monkeypatch.setattr("symbox.persistence.state_repository.os.replace", fail_replace)
    with pytest.raises(ValueError, match="atomically write"):
        repository.save(StateDocument(revision=2, objects=({"name": "after"},)))

    assert repository.scope.state_path.read_bytes() == before
    assert not tuple(repository.scope.state_dir.glob(".state-*.tmp"))


def test_git_ref_failure_leaves_no_visible_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))
    original_run = repository._run

    def fail_ref(*arguments: str, **kwargs: Any) -> Any:
        if arguments and arguments[0] == "update-ref":
            raise BackupError("injected Git ref failure")
        return original_run(*arguments, **kwargs)

    monkeypatch.setattr(repository, "_run", fail_ref)
    with pytest.raises(BackupError, match="injected Git ref failure"):
        repository.create(StateDocument(revision=1), "invisible")

    assert repository.list_backups() == ()
