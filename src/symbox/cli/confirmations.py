"""CLI transport adapter for application-level confirmation requests."""

from __future__ import annotations

from dataclasses import asdict

from symbox.application.similarity import ConfirmationRequest
from symbox.cli.results import ResultEnvelope, ResultStatus


def confirmation_envelope(request: ConfirmationRequest) -> ResultEnvelope:
    """Convert a pure application DTO into the public confirm-needed envelope."""
    return ResultEnvelope(ResultStatus.CONFIRM_NEEDED, data=asdict(request))
