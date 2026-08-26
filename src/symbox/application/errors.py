"""Stable error taxonomy shared by application use cases and CLI adapters."""

from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    """Machine-readable failure categories exposed by the public CLI."""

    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    BINDING = "binding"
    PERSISTENCE = "persistence"
    EXTERNAL = "external"
    INTERNAL = "internal"
