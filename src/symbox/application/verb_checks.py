"""Structured True-pass / False-conflict execution for bound Verbs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VerbDiagnostic:
    """A machine-readable outcome from local Verb validation."""

    code: str
    message: str
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VerbCheckResult:
    """A local validation result that controls whether relation staging may proceed."""

    accepted: bool
    conflict: bool
    diagnostics: tuple[VerbDiagnostic, ...] = ()


def execute_verb_check(
    check: Callable[..., bool],
    subject: Any,
    args: tuple[Any, ...],
    kwargs: tuple[tuple[str, Any], ...],
) -> VerbCheckResult:
    """Invoke one trusted Verb check and preserve the normative boolean polarity."""
    try:
        result = check(subject, *args, **dict(kwargs))
    except Exception as error:
        return VerbCheckResult(
            accepted=False,
            conflict=False,
            diagnostics=(
                VerbDiagnostic(
                    "verb_check_error",
                    f"Verb check raised: {error}",
                    {"exception_type": type(error).__name__},
                ),
            ),
        )
    if not isinstance(result, bool):
        return VerbCheckResult(
            accepted=False,
            conflict=False,
            diagnostics=(
                VerbDiagnostic(
                    "invalid_verb_result",
                    "Verb check must return bool",
                    {"result_type": type(result).__name__},
                ),
            ),
        )
    if result:
        return VerbCheckResult(accepted=True, conflict=False)
    return VerbCheckResult(
        accepted=False,
        conflict=True,
        diagnostics=(
            VerbDiagnostic(
                "verb_conflict",
                "Verb check returned False; the relation would be contradictory",
                {"subject": subject, "args": args, "kwargs": dict(kwargs)},
            ),
        ),
    )
