"""Application port and process-only configuration for embedding suggestions."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class EmbeddingError(RuntimeError):
    """Raised when a configured embedding provider cannot return a valid vector."""


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """Environment-provided embedding configuration; credentials stay process-local."""

    base_url: str
    model: str
    api_key: str | None = None
    similarity_threshold: float = 0.85
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("embedding base_url must not be empty")
        if not self.model.strip():
            raise ValueError("embedding model must not be empty")
        if not -1.0 <= self.similarity_threshold <= 1.0:
            raise ValueError("embedding similarity threshold must be between -1 and 1")
        if self.timeout_seconds <= 0:
            raise ValueError("embedding timeout must be positive")

    def public_settings(self) -> dict[str, str | float | bool]:
        """Return diagnostics-safe settings that cannot persist the API key."""
        return {
            "base_url": self.base_url,
            "model": self.model,
            "similarity_threshold": self.similarity_threshold,
            "timeout_seconds": self.timeout_seconds,
            "credential_configured": self.api_key is not None,
        }


def load_embedding_config(environment: dict[str, str] | None = None) -> EmbeddingConfig | None:
    """Load an optional provider configuration from the process environment."""
    values = environment if environment is not None else os.environ
    base_url = values.get("SBOX_EMBEDDING_BASE_URL", "").strip()
    model = values.get("SBOX_EMBEDDING_MODEL", "").strip()
    if not base_url or not model:
        return None
    try:
        threshold = float(values.get("SBOX_SIMILARITY_THRESHOLD", "0.85"))
        timeout = float(values.get("SBOX_EMBEDDING_TIMEOUT_SECONDS", "10"))
    except ValueError as error:
        raise ValueError("embedding threshold and timeout must be numeric") from error
    return EmbeddingConfig(
        base_url=base_url,
        model=model,
        api_key=values.get("SBOX_EMBEDDING_API_KEY") or None,
        similarity_threshold=threshold,
        timeout_seconds=timeout,
    )


class EmbeddingProvider(Protocol):
    """A fallible suggestion-only vector provider."""

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one finite, non-empty vector for every input text."""
        ...


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute finite cosine similarity for equal non-zero vectors."""
    if not left or len(left) != len(right):
        raise ValueError("cosine vectors must be non-empty and equal length")
    if not all(math.isfinite(value) for value in (*left, *right)):
        raise ValueError("cosine vectors must contain finite values")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("cosine similarity is undefined for zero vectors")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
