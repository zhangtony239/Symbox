"""Similarity confirmation policy for new attribute keys."""

from __future__ import annotations

from dataclasses import dataclass

from symbox.application.embedding_ports import EmbeddingProvider, cosine_similarity


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
            f"Should {match.proposed_key!r} be added alongside "
            f"similar key {match.existing_key!r}?"
        ),
    )
