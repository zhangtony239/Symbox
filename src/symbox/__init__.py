"""Symbox v0.6 package."""

from typing import TYPE_CHECKING, Any

__version__ = "0.6.0"

if TYPE_CHECKING:
    from symbox.integrations.python_bindings import BindingLoadError as BindingLoadError
    from symbox.persistence.backup_repository import BackupError as BackupError
    from symbox.persistence.backup_repository import BackupNotFoundError as BackupNotFoundError
    from symbox.persistence.state_format import StateFormatError as StateFormatError
    from symbox.runtime import CommandRuntime as CommandRuntime


def __getattr__(name: str) -> Any:
    """Lazily expose composition-root types without eager cross-layer imports."""
    if name == "CommandRuntime":
        from symbox.runtime import CommandRuntime

        return CommandRuntime
    if name in {"BackupError", "BackupNotFoundError"}:
        from symbox.persistence.backup_repository import BackupError, BackupNotFoundError

        return {"BackupError": BackupError, "BackupNotFoundError": BackupNotFoundError}[name]
    if name == "BindingLoadError":
        from symbox.integrations.python_bindings import BindingLoadError

        return BindingLoadError
    if name == "StateFormatError":
        from symbox.persistence.state_format import StateFormatError

        return StateFormatError
    raise AttributeError(name)
