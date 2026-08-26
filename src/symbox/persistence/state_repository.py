"""Project-scoped state discovery and loading."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from symbox.persistence.state_format import StateDocument, StateFormatError

_PROJECT_MARKERS = (".sbox", "pyproject.toml", ".git")


class ProjectScopeError(ValueError):
    """Raised when a safe project scope cannot be established."""


@dataclass(frozen=True, slots=True)
class ProjectScope:
    """All Symbox state locations derived from one isolated project root."""

    root: Path

    def __post_init__(self) -> None:
        root = self.root.resolve()
        if not root.is_dir():
            raise ProjectScopeError(f"project root is not a directory: {root}")
        object.__setattr__(self, "root", root)

    @property
    def state_dir(self) -> Path:
        return self.root / ".sbox"

    @property
    def state_path(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def backups_path(self) -> Path:
        return self.state_dir / "backups"


def discover_project_scope(start: Path | None = None) -> ProjectScope:
    """Find the nearest project marker, falling back to the supplied directory."""
    candidate = (start or Path.cwd()).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    if not candidate.is_dir():
        raise ProjectScopeError(f"scope start is not a directory: {candidate}")
    for directory in (candidate, *candidate.parents):
        if any((directory / marker).exists() for marker in _PROJECT_MARKERS):
            return ProjectScope(directory)
    return ProjectScope(candidate)


class StateRepository:
    """Load committed state exclusively from one discovered project scope."""

    def __init__(self, scope: ProjectScope) -> None:
        self.scope = scope

    def load(self) -> StateDocument:
        """Load and validate state; a project with no state starts empty."""
        path = self.scope.state_path
        if not path.exists():
            return StateDocument()
        if not path.is_file() or path.is_symlink():
            raise StateFormatError("state path must be a regular non-symlink file")
        try:
            content = path.read_bytes()
        except OSError as error:
            raise StateFormatError(f"unable to read state file: {path}") from error
        return StateDocument.from_bytes(content)

    def save(self, state: StateDocument) -> None:
        """Publish a complete state document through a same-directory atomic replace."""
        state_dir = self.scope.state_dir
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise StateFormatError(f"unable to create state directory: {state_dir}") from error
        if state_dir.is_symlink():
            raise StateFormatError("state directory must not be a symlink")

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".state-",
                suffix=".tmp",
                dir=state_dir,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(state.to_bytes())
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.scope.state_path)
            temporary_path = None
        except (OSError, StateFormatError) as error:
            message = f"unable to atomically write state: {self.scope.state_path}"
            raise StateFormatError(message) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
