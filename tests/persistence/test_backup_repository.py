"""Project-isolated bare-Git backup repository tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from filelock import FileLock

from symbox.persistence.backup_repository import (
    BackupConflictError,
    GitBackupRepository,
)
from symbox.persistence.state_repository import ProjectScope


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
