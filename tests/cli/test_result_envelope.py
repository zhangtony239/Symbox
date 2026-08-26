"""Golden tests for the public JSON result protocol."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbox.application.errors import ErrorCategory
from symbox.cli.results import (
    Conflict,
    Diagnostic,
    ExitCode,
    ResultEnvelope,
    ResultStatus,
)

GOLDEN_ROOT = Path(__file__).parents[1] / "golden"


@pytest.mark.parametrize(
    ("golden_name", "envelope", "exit_code"),
    [
        (
            "success.json",
            ResultEnvelope(ResultStatus.SUCCESS, data={"objects": []}),
            ExitCode.SUCCESS,
        ),
        (
            "confirm-needed.json",
            ResultEnvelope(
                ResultStatus.CONFIRM_NEEDED,
                data={"existing_key": "temperature", "proposed_key": "temp"},
            ),
            ExitCode.SUCCESS,
        ),
        (
            "validation-error.json",
            ResultEnvelope(
                ResultStatus.ERROR,
                diagnostics=(
                    Diagnostic(
                        ErrorCategory.VALIDATION,
                        "invalid_name",
                        "object name must not be empty",
                        {"name": ""},
                    ),
                ),
            ),
            ExitCode.VALIDATION_ERROR,
        ),
        (
            "conflict.json",
            ResultEnvelope(
                ResultStatus.CONFLICT,
                diagnostics=(
                    Diagnostic(
                        ErrorCategory.CONFLICT,
                        "truth_conflict",
                        "candidate state is inconsistent",
                    ),
                ),
                conflicts=(Conflict("Worry:battery", ("Adj:robot:battery",)),),
                transaction_id="tx-123",
            ),
            ExitCode.CONFLICT,
        ),
    ],
)
def test_result_envelope_golden(
    golden_name: str,
    envelope: ResultEnvelope,
    exit_code: ExitCode,
) -> None:
    assert envelope.to_json() == (GOLDEN_ROOT / golden_name).read_text(encoding="utf-8").strip()
    assert envelope.exit_code is exit_code
