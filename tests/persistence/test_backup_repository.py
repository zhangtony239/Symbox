"""Project-isolated bare-Git backup repository tests."""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from filelock import FileLock

from symbox.persistence.backup_repository import (
    BackupConflictError,
    BackupError,
    BackupNotFoundError,
    GitBackupRepository,
)
from symbox.persistence.state_format import StateDocument
from symbox.persistence.state_repository import ProjectScope, StateRepository


def _is_bare(path: Path) -> str:
    result = subprocess.run(
        ["git", f"--git-dir={path}", "rev-parse", "--is-bare-repository"],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def test_first_use_initializes_project_local_bare_repository(tmp_path: Path) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))

    repository.ensure_initialized()
    repository.ensure_initialized()

    assert repository.git_dir == tmp_path / ".sbox" / "backups"
    assert _is_bare(repository.git_dir) == "true"


def test_backup_repositories_are_isolated_by_project_scope(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = GitBackupRepository(ProjectScope(first_root))
    second = GitBackupRepository(ProjectScope(second_root))

    first.ensure_initialized()
    second.ensure_initialized()

    assert first.git_dir != second.git_dir
    assert _is_bare(first.git_dir) == "true"
    assert _is_bare(second.git_dir) == "true"


def test_backup_lock_conflict_is_project_local_and_diagnostic(tmp_path: Path) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path), lock_timeout=0)
    repository.scope.state_dir.mkdir()
    external_lock = FileLock(repository.lock_path)

    with external_lock, pytest.raises(BackupConflictError, match="backup lock"):
        repository.ensure_initialized()


def test_create_writes_canonical_state_tree_and_returns_full_stable_commit_id(
    tmp_path: Path,
) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))
    state = StateDocument(revision=3, objects=({"name": "robot"},))
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    first = repository.create(state, "before experiment", created_at=created_at)
    second = repository.create(state, "before experiment", created_at=created_at)

    assert first == second
    assert len(first.commit_id) == 40
    assert first.note == "before experiment"
    assert first.created_at == created_at
    content = subprocess.run(
        ["git", f"--git-dir={repository.git_dir}", "show", f"{first.commit_id}:state.json"],
        capture_output=True,
        check=True,
    ).stdout
    assert content == state.to_bytes()
    resolved = subprocess.run(
        [
            "git",
            f"--git-dir={repository.git_dir}",
            "rev-parse",
            f"refs/symbox/backups/{first.commit_id}",
        ],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    assert resolved == first.commit_id


def test_create_rejects_empty_note_without_initializing_repository(tmp_path: Path) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))

    with pytest.raises(BackupError, match="note must not be empty"):
        repository.create(StateDocument(), "   ")

    assert not repository.git_dir.exists()


def test_log_returns_managed_metadata_newest_first_with_id_tiebreaker(
    tmp_path: Path,
) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))
    older = repository.create(
        StateDocument(revision=1),
        "older",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer_a = repository.create(
        StateDocument(revision=2),
        "newer a",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    newer_b = repository.create(
        StateDocument(revision=3),
        "newer b",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    records = repository.list_backups()

    assert records == tuple(
        sorted(
            (newer_a, newer_b),
            key=lambda record: record.commit_id,
        )
    ) + (older,)


def test_log_of_uninitialized_project_is_empty_and_read_only(tmp_path: Path) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))

    assert repository.list_backups() == ()
    assert not repository.scope.state_dir.exists()


def test_delete_removes_all_requested_managed_refs_atomically(tmp_path: Path) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))
    first = repository.create(StateDocument(revision=1), "first")
    second = repository.create(StateDocument(revision=2), "second")
    retained = repository.create(StateDocument(revision=3), "retained")

    repository.delete((first.commit_id, second.commit_id))

    assert repository.list_backups() == (retained,)


def test_delete_with_unknown_id_preserves_every_requested_backup(tmp_path: Path) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))
    first = repository.create(StateDocument(revision=1), "first")
    second = repository.create(StateDocument(revision=2), "second")
    before = repository.list_backups()

    with pytest.raises(BackupNotFoundError, match="unknown backup ids"):
        repository.delete((first.commit_id, "f" * 40, second.commit_id))

    assert repository.list_backups() == before


def test_rollback_validates_snapshot_and_atomically_restores_canonical_state(
    tmp_path: Path,
) -> None:
    scope = ProjectScope(tmp_path)
    states = StateRepository(scope)
    backups = GitBackupRepository(scope)
    original = StateDocument(revision=1, objects=({"name": "before"},))
    states.save(original)
    backup = backups.create(original, "before experiment")
    current = StateDocument(revision=2, objects=({"name": "after"},))
    states.save(current)

    restored = backups.rollback(backup.commit_id, states)

    assert restored.revision == 3
    assert restored.objects == original.objects
    assert states.load() == restored


def test_rollback_unknown_id_preserves_current_state_bytes(tmp_path: Path) -> None:
    scope = ProjectScope(tmp_path)
    states = StateRepository(scope)
    backups = GitBackupRepository(scope)
    current = StateDocument(revision=1, objects=({"name": "current"},))
    states.save(current)
    before = scope.state_path.read_bytes()

    with pytest.raises(BackupNotFoundError, match="unknown backup id"):
        backups.rollback("f" * 40, states)

    assert scope.state_path.read_bytes() == before
    assert states.load() == current


def test_rollback_rejects_corrupt_snapshot_before_touching_current_state(
    tmp_path: Path,
) -> None:
    scope = ProjectScope(tmp_path)
    states = StateRepository(scope)
    backups = GitBackupRepository(scope)
    current = StateDocument(revision=1, objects=({"name": "current"},))
    states.save(current)
    backups.ensure_initialized()
    blob = (
        subprocess.run(
            ["git", f"--git-dir={backups.git_dir}", "hash-object", "-w", "--stdin"],
            input=b"not-json",
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    tree = (
        subprocess.run(
            ["git", f"--git-dir={backups.git_dir}", "mktree"],
            input=f"100644 blob {blob}\tstate.json\n".encode(),
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    environment = {
        "GIT_AUTHOR_NAME": "Symbox",
        "GIT_AUTHOR_EMAIL": "symbox@localhost",
        "GIT_COMMITTER_NAME": "Symbox",
        "GIT_COMMITTER_EMAIL": "symbox@localhost",
    }
    commit_id = subprocess.run(
        ["git", f"--git-dir={backups.git_dir}", "commit-tree", tree, "-m", "corrupt"],
        capture_output=True,
        check=True,
        text=True,
        env=environment,
    ).stdout.strip()
    subprocess.run(
        [
            "git",
            f"--git-dir={backups.git_dir}",
            "update-ref",
            f"refs/symbox/backups/{commit_id}",
            commit_id,
        ],
        capture_output=True,
        check=True,
    )
    before = scope.state_path.read_bytes()

    with pytest.raises(BackupError, match="snapshot is invalid"):
        backups.rollback(commit_id, states)

    assert scope.state_path.read_bytes() == before
    assert states.load() == current


def test_concurrent_create_serializes_ref_updates_without_losing_backups(
    tmp_path: Path,
) -> None:
    repository = GitBackupRepository(ProjectScope(tmp_path))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(repository.create, StateDocument(revision=1), "first"),
            executor.submit(repository.create, StateDocument(revision=2), "second"),
        )
        created = tuple(future.result() for future in futures)

    assert {record.commit_id for record in repository.list_backups()} == {
        record.commit_id for record in created
    }


def test_backup_content_and_list_exclude_environment_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-never-backup-this"
    monkeypatch.setenv("SBOX_EMBEDDING_API_KEY", secret)
    repository = GitBackupRepository(ProjectScope(tmp_path))

    record = repository.create(StateDocument(revision=1), "safe note")

    content = subprocess.run(
        ["git", f"--git-dir={repository.git_dir}", "show", f"{record.commit_id}:state.json"],
        capture_output=True,
        check=True,
    ).stdout
    commit = subprocess.run(
        ["git", f"--git-dir={repository.git_dir}", "cat-file", "-p", record.commit_id],
        capture_output=True,
        check=True,
    ).stdout
    metadata = repr(repository.list_backups()).encode()

    assert secret.encode() not in content
    assert secret.encode() not in commit
    assert secret.encode() not in metadata
    assert b"SBOX_EMBEDDING_API_KEY" not in content
