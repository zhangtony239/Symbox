"""Single-commit and failure-rollback tests for every CLI write handler."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from symbox.domain.models import DomainInvariantError
from symbox.integrations.python_bindings import BindingLoadError
from symbox.runtime import CommandRuntime


def _write_rules(root: Path) -> None:
    rules = root / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "checks.py").write_text(
        "def accepts(subject, destination='dock'):\n"
        "    return subject == 'robot' and destination != 'blocked'\n",
        encoding="utf-8",
    )


def _revision(runtime: CommandRuntime) -> int:
    return runtime.states.load().revision


def _assert_single_commit(runtime: CommandRuntime, operation: Callable[[], object]) -> None:
    before = _revision(runtime)
    operation()
    assert _revision(runtime) == before + 1


def _assert_failed_without_disk_change(
    runtime: CommandRuntime,
    operation: Callable[[], object],
    error: type[BaseException],
) -> None:
    before_state = runtime.states.load()
    before_bytes = runtime.scope.state_path.read_bytes()
    with pytest.raises(error):
        operation()
    assert runtime.states.load() == before_state
    assert runtime.scope.state_path.read_bytes() == before_bytes


def test_each_state_write_command_commits_exactly_one_revision(tmp_path: Path) -> None:
    _write_rules(tmp_path)
    runtime = CommandRuntime(tmp_path)

    _assert_single_commit(runtime, lambda: runtime.create("robot", "physical"))
    _assert_single_commit(runtime, lambda: runtime.create("accepts", "abstract"))
    _assert_single_commit(
        runtime,
        lambda: runtime.bind(
            "accepts",
            "rules/checks.py",
            "accepts",
            is_verb=True,
        ),
    )
    _assert_single_commit(runtime, lambda: runtime.set_attributes("robot", ("level=12",)))
    _assert_single_commit(runtime, lambda: runtime.now(("robot", "accepts", "dock")))
    _assert_single_commit(runtime, lambda: runtime.unset_attributes("robot", ("level",)))
    _assert_single_commit(runtime, lambda: runtime.unbind("accepts"))
    _assert_single_commit(runtime, lambda: runtime.delete("accepts"))


def test_each_state_write_failure_preserves_revision_and_exact_disk_bytes(
    tmp_path: Path,
) -> None:
    _write_rules(tmp_path)
    runtime = CommandRuntime(tmp_path)
    runtime.create("robot", "physical")
    runtime.create("accepts", "abstract")
    runtime.bind("accepts", "rules/checks.py", "accepts", is_verb=True)
    runtime.set_attributes("robot", ("level=12",))

    failures: tuple[tuple[Callable[[], object], type[BaseException]], ...] = (
        (lambda: runtime.create("robot", "abstract"), DomainInvariantError),
        (lambda: runtime.delete("missing"), DomainInvariantError),
        (
            lambda: runtime.bind(
                "accepts",
                "missing.py",
                "accepts",
                is_verb=True,
            ),
            BindingLoadError,
        ),
        (lambda: runtime.unbind("robot"), DomainInvariantError),
        (lambda: runtime.set_attributes("robot", ("broken",)), DomainInvariantError),
        (lambda: runtime.unset_attributes("robot", ("missing",)), DomainInvariantError),
        (lambda: runtime.now(("robot", "accepts", "blocked")), DomainInvariantError),
    )

    for operation, error in failures:
        _assert_failed_without_disk_change(runtime, operation, error)


def test_backup_writes_have_single_visible_commit_boundary(tmp_path: Path) -> None:
    runtime = CommandRuntime(tmp_path)
    runtime.create("robot", "physical")
    state_revision = _revision(runtime)

    backup = runtime.backup_create("before")
    assert _revision(runtime) == state_revision
    assert tuple(item.commit_id for item in runtime.backups.list_backups()) == (
        backup["commit_id"],
    )

    runtime.set_attributes("robot", ("level=3",))
    before_rollback = _revision(runtime)
    runtime.backup_rollback(str(backup["commit_id"]))
    assert _revision(runtime) == before_rollback + 1

    runtime.backup_delete((str(backup["commit_id"]),))
    assert runtime.backups.list_backups() == ()
