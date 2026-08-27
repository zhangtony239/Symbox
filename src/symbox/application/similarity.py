"""Similarity confirmation policy for new attribute keys."""

from __future__ import annotations

from dataclasses import dataclass

from symbox.application.embedding_ports import (
    EmbeddingError,
    EmbeddingProvider,
    cosine_similarity,
)


@dataclass(frozen=True, slots=True)
class SimilarKey:
    """The highest-scoring existing key that exceeds the configured threshold."""

    existing_key: str
    proposed_key: str
    score: float
    threshold: float


@dataclass(frozen=True, slots=True)
class ConfirmationRequest:
    """Application-level confirmation details independent of CLI transport."""

    subject: str
    existing_key: str
    proposed_key: str
    score: float
    threshold: float
    question: str


@dataclass(frozen=True, slots=True)
class SimilarityDiagnostic:
    """Non-fatal machine-readable information about suggestion quality."""

    code: str
    message: str
    degraded: bool


@dataclass(frozen=True, slots=True)
class SimilarityAssessment:
    """A confirmation decision plus diagnostics that never authorize a write."""

    confirmation: ConfirmationRequest | None = None
    diagnostics: tuple[SimilarityDiagnostic, ...] = ()


def find_similar_key(
    provider: EmbeddingProvider,
    proposed_key: str,
    existing_keys: tuple[str, ...],
    threshold: float,
) -> SimilarKey | None:
    """Return the deterministic best strict-threshold match, if any."""
    if not existing_keys:
        return None
    ordered_existing = tuple(sorted(set(existing_keys)))
    vectors = provider.embed((proposed_key, *ordered_existing))
    proposed_vector = vectors[0]
    matches = [
        SimilarKey(existing, proposed_key, cosine_similarity(proposed_vector, vector), threshold)
        for existing, vector in zip(ordered_existing, vectors[1:], strict=True)
    ]
    over_threshold = [match for match in matches if match.score > threshold]
    if not over_threshold:
        return None
    return min(over_threshold, key=lambda match: (-match.score, match.existing_key))


def similarity_confirmation(
    provider: EmbeddingProvider,
    *,
    subject: str,
    proposed_key: str,
    existing_keys: tuple[str, ...],
    threshold: float,
    force: bool = False,
) -> ConfirmationRequest | None:
    """Return confirmation details unless this exact retry is explicitly forced."""
    if force:
        return None
    match = find_similar_key(provider, proposed_key, existing_keys, threshold)
    if match is None:
        return None
    return ConfirmationRequest(
        subject=subject,
        existing_key=match.existing_key,
        proposed_key=match.proposed_key,
        score=match.score,
        threshold=match.threshold,
        question=(
            f"Should {match.proposed_key!r} be added alongside similar key {match.existing_key!r}?"
        ),
    )


def assess_similarity(
    provider: EmbeddingProvider | None,
    *,
    subject: str,
    proposed_key: str,
    existing_keys: tuple[str, ...],
    threshold: float,
    force: bool = False,
) -> SimilarityAssessment:
    """Use embeddings when available, otherwise continue with exact-name semantics."""
    if proposed_key in existing_keys:
        return SimilarityAssessment(
            diagnostics=(
                SimilarityDiagnostic(
                    "exact_key_match",
                    f"attribute key already exists exactly: {proposed_key}",
                    False,
                ),
            )
        )
    if force:
        return SimilarityAssessment()
    if provider is None:
        return SimilarityAssessment(
            diagnostics=(
                SimilarityDiagnostic(
                    "embedding_not_configured",
                    "similarity detection degraded to exact key matching",
                    True,
                ),
            )
        )
    try:
        confirmation = similarity_confirmation(
            provider,
            subject=subject,
            proposed_key=proposed_key,
            existing_keys=existing_keys,
            threshold=threshold,
        )
    except EmbeddingError as error:
        return SimilarityAssessment(
            diagnostics=(
                SimilarityDiagnostic(
                    "embedding_unavailable",
                    f"similarity detection degraded to exact key matching: {error}",
                    True,
                ),
            )
        )
    return SimilarityAssessment(confirmation=confirmation)
