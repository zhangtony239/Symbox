"""Project-isolated bare-Git storage for canonical Symbox backups."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from symbox.persistence.state_format import StateDocument
from symbox.persistence.state_repository import ProjectScope, StateRepository


class BackupError(RuntimeError):
    """Raised when backup storage cannot complete a Git operation."""


class BackupConflictError(BackupError):
    """Raised when another backup operation holds the project lock."""


class BackupNotFoundError(BackupError):
    """Raised when a managed backup identifier does not exist."""


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
        timestamp = timestamp.astimezone(UTC).replace(microsecond=0)

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

    def list_backups(self) -> tuple[BackupRecord, ...]:
        """List managed backups newest-first without creating storage on read."""
        if not self.git_dir.exists():
            return ()
        with self.locked():
            self._ensure_initialized_unlocked()
            output = self._run(
                "for-each-ref",
                "--format=%(objectname)%00%(creatordate:iso-strict)%00%(contents)%00",
                "refs/symbox/backups/",
            ).stdout
        fields = output.split("\x00")
        records: list[BackupRecord] = []
        for offset in range(0, len(fields) - 1, 3):
            commit_id = fields[offset].strip()
            if not commit_id:
                continue
            raw_timestamp = fields[offset + 1].strip()
            note = fields[offset + 2].strip()
            try:
                created_at = datetime.fromisoformat(raw_timestamp).astimezone(UTC)
            except ValueError as error:
                raise BackupError(
                    f"backup commit has invalid timestamp: {commit_id}"
                ) from error
            records.append(BackupRecord(commit_id, note, created_at))
        return tuple(
            sorted(
                records,
                key=lambda record: (
                    -record.created_at.timestamp(),
                    record.commit_id,
                ),
            )
        )

    def delete(self, commit_ids: tuple[str, ...]) -> None:
        """Validate every target, then delete all managed refs in one Git transaction."""
        normalized = tuple(identifier.strip().lower() for identifier in commit_ids)
        if not normalized:
            raise BackupError("at least one backup id is required")
        if len(normalized) != len(set(normalized)):
            raise BackupError("backup ids must be unique")
        invalid = tuple(
            identifier
            for identifier in normalized
            if not re.fullmatch(r"[0-9a-f]{40}", identifier)
        )
        if invalid:
            raise BackupError(f"backup ids must be full commit ids: {invalid}")

        with self.locked():
            if not self.git_dir.exists():
                raise BackupNotFoundError(f"unknown backup ids: {normalized}")
            self._ensure_initialized_unlocked()
            resolved: list[tuple[str, str]] = []
            unknown: list[str] = []
            for commit_id in normalized:
                reference = self._managed_ref(commit_id)
                current = self._try_resolve_ref(reference)
                if current != commit_id:
                    unknown.append(commit_id)
                else:
                    resolved.append((reference, current))
            if unknown:
                raise BackupNotFoundError(f"unknown backup ids: {tuple(unknown)}")

            commands = ["start"]
            commands.extend(
                f"delete {reference} {current}"
                for reference, current in resolved
            )
            commands.extend(("prepare", "commit"))
            payload = ("\n".join(commands) + "\n").encode()
            self._run("update-ref", "--stdin", input_bytes=payload)

    def rollback(self, commit_id: str, state_repository: StateRepository) -> StateDocument:
        """Validate a managed snapshot before atomically publishing it as current state."""
        normalized = self._normalize_commit_id(commit_id)
        if state_repository.scope.root != self.scope.root:
            raise BackupError("backup and state repositories must use the same project scope")

        with self.locked():
            if not self.git_dir.exists():
                raise BackupNotFoundError(f"unknown backup id: {normalized}")
            self._ensure_initialized_unlocked()
            reference = self._managed_ref(normalized)
            if self._try_resolve_ref(reference) != normalized:
                raise BackupNotFoundError(f"unknown backup id: {normalized}")
            content = self._run_bytes("show", f"{normalized}:state.json")
            try:
                snapshot = StateDocument.from_bytes(content)
            except ValueError as error:
                raise BackupError(f"backup snapshot is invalid: {normalized}") from error

        committed = state_repository.load()
        candidate = replace(snapshot, revision=committed.revision + 1)
        state_repository.save(candidate)
        return candidate

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

    @staticmethod
    def _managed_ref(commit_id: str) -> str:
        return f"refs/symbox/backups/{commit_id}"

    @staticmethod
    def _normalize_commit_id(commit_id: str) -> str:
        normalized = commit_id.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", normalized):
            raise BackupError("backup id must be a full commit id")
        return normalized

    def _run_bytes(self, *arguments: str) -> bytes:
        command = ["git", f"--git-dir={self.git_dir}", *arguments]
        try:
            return subprocess.run(
                command,
                capture_output=True,
                check=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            stderr = (
                error.stderr.decode("utf-8", errors="replace").strip()
                if isinstance(error, subprocess.CalledProcessError)
                else ""
            )
            detail = f": {stderr}" if stderr else ""
            operation = " ".join(arguments)
            raise BackupError(f"git backup operation failed ({operation}){detail}") from error

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
