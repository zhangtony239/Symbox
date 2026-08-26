"""Project-scoped state discovery and loading."""

from __future__ import annotations

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
