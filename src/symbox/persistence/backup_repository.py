"""Project-isolated bare-Git storage for canonical Symbox backups."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from symbox.persistence.state_format import StateDocument
from symbox.persistence.state_repository import ProjectScope


class BackupError(RuntimeError):
    """Raised when backup storage cannot complete a Git operation."""


class BackupConflictError(BackupError):
    """Raised when another backup operation holds the project lock."""


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """Stable public metadata for one managed backup commit."""

    commit_id: str
    note: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    """Strictly decoded output from a binary-safe Git subprocess."""

    stdout: str
    stderr: str


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

    def create(
        self,
        state: StateDocument,
        note: str,
        *,
        created_at: datetime | None = None,
    ) -> BackupRecord:
        """Write canonical state as a tree and atomically publish its commit ref."""
        normalized_note = note.strip()
        if not normalized_note:
            raise BackupError("backup note must not be empty")
        if "\x00" in normalized_note:
            raise BackupError("backup note must not contain NUL")
        timestamp = created_at or datetime.now(UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise BackupError("backup created_at must be timezone-aware")
        timestamp = timestamp.astimezone(UTC)

        with self.locked():
            self._ensure_initialized_unlocked()
            blob = self._run(
                "hash-object",
                "-w",
                "--stdin",
                input_bytes=state.to_bytes(),
            ).stdout.strip()
            tree_entry = f"100644 blob {blob}\tstate.json\n".encode()
            tree = self._run("mktree", input_bytes=tree_entry).stdout.strip()
            environment = os.environ.copy()
            environment.update(
                {
                    "GIT_AUTHOR_NAME": "Symbox",
                    "GIT_AUTHOR_EMAIL": "symbox@localhost",
                    "GIT_COMMITTER_NAME": "Symbox",
                    "GIT_COMMITTER_EMAIL": "symbox@localhost",
                    "GIT_AUTHOR_DATE": timestamp.isoformat(),
                    "GIT_COMMITTER_DATE": timestamp.isoformat(),
                }
            )
            commit_id = self._run(
                "commit-tree",
                tree,
                "-m",
                normalized_note,
                environment=environment,
            ).stdout.strip()
            managed_ref = f"refs/symbox/backups/{commit_id}"
            existing = self._try_resolve_ref(managed_ref)
            if existing is None:
                self._run("update-ref", managed_ref, commit_id, "0" * 40)
            elif existing != commit_id:
                raise BackupConflictError("managed backup ref identifies a different commit")
        return BackupRecord(commit_id, normalized_note, timestamp)

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

    def _try_resolve_ref(self, reference: str) -> str | None:
        try:
            return self._run("rev-parse", "--verify", reference).stdout.strip()
        except BackupError:
            return None

    def _run(
        self,
        *arguments: str,
        input_bytes: bytes | None = None,
        use_git_dir: bool = True,
        environment: dict[str, str] | None = None,
    ) -> GitCommandResult:
        command = ["git"]
        if use_git_dir:
            command.append(f"--git-dir={self.git_dir}")
        command.extend(arguments)
        try:
            completed = subprocess.run(
                command,
                input=input_bytes,
                capture_output=True,
                check=True,
                env=environment,
            )
            return GitCommandResult(
                completed.stdout.decode("utf-8", errors="strict"),
                completed.stderr.decode("utf-8", errors="strict"),
            )
        except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
            stderr = (
                error.stderr.decode("utf-8", errors="replace").strip()
                if isinstance(error, subprocess.CalledProcessError)
                else ""
            )
            detail = f": {stderr}" if stderr else ""
            operation = " ".join(arguments)
            raise BackupError(f"git backup operation failed ({operation}){detail}") from error
