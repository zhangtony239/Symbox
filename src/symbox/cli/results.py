"""Deterministic JSON result envelopes and process exit codes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

from symbox.application.errors import ErrorCategory


class ResultStatus(StrEnum):
    """Public command outcomes."""

    SUCCESS = "success"
    CONFIRM_NEEDED = "confirm_needed"
    ERROR = "error"
    CONFLICT = "conflict"


class ExitCode(IntEnum):
    """Stable process exit-code classes."""

    SUCCESS = 0
    VALIDATION_ERROR = 2
    CONFLICT = 3
    SYSTEM_ERROR = 4


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A structured, machine-readable command diagnostic."""

    category: ErrorCategory
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Conflict:
    """A conflicting fact and its currently available justification chain."""

    fact: str
    justification: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResultEnvelope:
    """The only JSON document emitted by a normal CLI invocation."""

    status: ResultStatus
    data: Any = None
    diagnostics: tuple[Diagnostic, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    transaction_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation with every public field present."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize canonically for stable agent consumption and golden tests."""
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @property
    def exit_code(self) -> ExitCode:
        """Map the outcome and error category to a stable process exit class."""
        if self.status in {ResultStatus.SUCCESS, ResultStatus.CONFIRM_NEEDED}:
            return ExitCode.SUCCESS
        if self.status is ResultStatus.CONFLICT:
            return ExitCode.CONFLICT
        if self.diagnostics and self.diagnostics[0].category in {
            ErrorCategory.VALIDATION,
            ErrorCategory.NOT_FOUND,
            ErrorCategory.BINDING,
        }:
            return ExitCode.VALIDATION_ERROR
        return ExitCode.SYSTEM_ERROR
