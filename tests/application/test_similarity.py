"""Strict threshold, confirmation envelope, and force retry tests."""

from __future__ import annotations

from symbox.application.embedding_ports import EmbeddingError
from symbox.application.similarity import (
    assess_similarity,
    find_similar_key,
    similarity_confirmation,
)
from symbox.cli.confirmations import confirmation_envelope
from symbox.cli.results import ExitCode, ResultStatus


class StaticProvider:
    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.vectors = vectors
        self.calls = 0

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        self.calls += 1
        return tuple(self.vectors[text] for text in texts)


class FailingProvider:
    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        raise EmbeddingError("injected timeout")


def test_strictly_greater_score_returns_structured_confirmation() -> None:
    provider = StaticProvider({"temp": (1, 0), "temperature": (0.9, 0.1)})

    request = similarity_confirmation(
        provider,
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.9,
    )

    assert request is not None
    result = confirmation_envelope(request)
    assert result.status is ResultStatus.CONFIRM_NEEDED
    assert result.exit_code is ExitCode.SUCCESS
    assert result.data["subject"] == "robot"
    assert result.data["existing_key"] == "temperature"
    assert result.data["proposed_key"] == "temp"
    assert "question" in result.data


def test_score_equal_to_threshold_does_not_require_confirmation() -> None:
    provider = StaticProvider({"temp": (1, 0), "temperature": (0.8, 0.6)})

    assert find_similar_key(provider, "temp", ("temperature",), 0.8) is None


def test_force_skips_only_similarity_check_without_calling_provider() -> None:
    provider = StaticProvider({})

    result = similarity_confirmation(
        provider,
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.8,
        force=True,
    )

    assert result is None
    assert provider.calls == 0


def test_best_match_is_deterministic_by_score_then_name() -> None:
    provider = StaticProvider(
        {
            "temp": (1, 0),
            "temperature": (1, 0),
            "temper": (1, 0),
        }
    )

    match = find_similar_key(provider, "temp", ("temperature", "temper"), 0.9)

    assert match is not None
    assert match.existing_key == "temper"


def test_unconfigured_provider_degrades_without_blocking_write() -> None:
    assessment = assess_similarity(
        None,
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.9,
    )

    assert assessment.confirmation is None
    assert assessment.diagnostics[0].degraded
    assert assessment.diagnostics[0].code == "embedding_not_configured"


def test_provider_failure_degrades_to_exact_name_semantics() -> None:
    assessment = assess_similarity(
        FailingProvider(),
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.9,
    )

    assert assessment.confirmation is None
    assert assessment.diagnostics[0].code == "embedding_unavailable"
    assert "injected timeout" in assessment.diagnostics[0].message


def test_exact_existing_key_is_detected_without_provider_call() -> None:
    provider = StaticProvider({})

    assessment = assess_similarity(
        provider,
        subject="robot",
        proposed_key="temperature",
        existing_keys=("temperature",),
        threshold=0.9,
    )

    assert assessment.confirmation is None
    assert assessment.diagnostics[0].code == "exact_key_match"
    assert not assessment.diagnostics[0].degraded
    assert provider.calls == 0
