"""Project-isolated bare-Git storage for canonical Symbox backups."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from symbox.persistence.state_repository import ProjectScope


class BackupError(RuntimeError):
    """Raised when backup storage cannot complete a Git operation."""


class BackupConflictError(BackupError):
    """Raised when another backup operation holds the project lock."""


class GitBackupRepository:
    """A bare-Git adapter rooted exclusively in one project's ``.sbox`` directory."""

    def __init__(self, scope: ProjectScope, *, lock_timeout: float = 10.0) -> None:
        self.scope = scope
        self.lock_timeout = lock_timeout

    @property
    def git_dir(self) -> Path:
        """Return this project's isolated bare repository path."""
        return self.scope.backups_path

    @property
    def lock_path(self) -> Path:
        """Keep the operation lock outside the bare repository object database."""
        return self.scope.state_dir / "backups.lock"

    def ensure_initialized(self) -> None:
        """Idempotently initialize and validate the project-local bare repository."""
        with self.locked():
            self._ensure_initialized_unlocked()

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize all ref and object operations for this project."""
        try:
            self.scope.state_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise BackupError(
                f"unable to create backup parent directory: {self.scope.state_dir}"
            ) from error
        if self.scope.state_dir.is_symlink():
            raise BackupError("backup parent directory must not be a symlink")
        lock = FileLock(self.lock_path, timeout=self.lock_timeout)
        try:
            with lock:
                yield
        except Timeout as error:
            raise BackupConflictError("timed out waiting for the backup lock") from error

    def _ensure_initialized_unlocked(self) -> None:
        path = self.git_dir
        if path.exists():
            if not path.is_dir() or path.is_symlink():
                raise BackupError("backup repository must be a regular directory")
        else:
            self._run("init", "--bare", str(path), use_git_dir=False)
        result = self._run("rev-parse", "--is-bare-repository")
        if result.stdout.strip() != "true":
            raise BackupError("backup repository is not bare")

    def _run(
        self,
        *arguments: str,
        input_bytes: bytes | None = None,
        use_git_dir: bool = True,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = ["git"]
        if use_git_dir:
            command.append(f"--git-dir={self.git_dir}")
        command.extend(arguments)
        try:
            return subprocess.run(
                command,
                input=input_bytes.decode("utf-8") if input_bytes is not None else None,
                capture_output=True,
                check=True,
                encoding="utf-8",
                errors="strict",
                env=environment,
            )
        except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
            stderr = (
                error.stderr.strip()
                if isinstance(error, subprocess.CalledProcessError)
                else ""
            )
            detail = f": {stderr}" if stderr else ""
            operation = " ".join(arguments)
            raise BackupError(f"git backup operation failed ({operation}){detail}") from error
