"""Attribute atomicity, similarity boundary, degradation, force, and tag sources."""

from __future__ import annotations

import pytest

from symbox.application.attributes import AttributeState, set_attributes
from symbox.application.bindings import BindingState
from symbox.application.embedding_ports import EmbeddingError
from symbox.application.objects import ObjectState, create_object
from symbox.application.similarity import assess_similarity
from symbox.application.tags import add_explicit_tag, sync_adj_tags
from symbox.domain.provenance import SourceKind
from symbox.kernel.fake import InMemoryTruthKernel


class VectorProvider:
    def __init__(self, vectors: dict[str, tuple[float, ...]], *, fail: bool = False) -> None:
        self.vectors = vectors
        self.fail = fail

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if self.fail:
            raise EmbeddingError("provider down")
        return tuple(self.vectors[text] for text in texts)


def _state() -> AttributeState:
    objects = create_object(ObjectState((), InMemoryTruthKernel()), "robot")
    return AttributeState(BindingState(objects))


def test_batch_partial_failure_does_not_apply_any_valid_member() -> None:
    original = set_attributes(_state(), "robot", {"battery": 80})

    with pytest.raises(ValueError):
        set_attributes(original, "robot", {"mode": "auto", "invalid": float("nan")})

    assert [(entry.fact.adj.key, entry.fact.adj.value) for entry in original.attributes] == [
        ("battery", 80)
    ]


def test_threshold_equality_passes_but_strictly_greater_confirms() -> None:
    equal = assess_similarity(
        VectorProvider({"temp": (1, 0), "temperature": (0.8, 0.6)}),
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.8,
    )
    greater = assess_similarity(
        VectorProvider({"temp": (1, 0), "temperature": (0.81, 0.59)}),
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.8,
    )

    assert equal.confirmation is None
    assert greater.confirmation is not None


def test_provider_failure_degrades_and_force_bypasses_similarity_only() -> None:
    degraded = assess_similarity(
        VectorProvider({}, fail=True),
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.8,
    )
    forced = assess_similarity(
        VectorProvider({}, fail=True),
        subject="robot",
        proposed_key="temp",
        existing_keys=("temperature",),
        threshold=0.8,
        force=True,
    )

    assert degraded.diagnostics[0].degraded
    assert forced.confirmation is None
    assert forced.diagnostics == ()


def test_explicit_and_multiple_derived_tag_sources_survive_independent_retraction() -> None:
    tags = add_explicit_tag((), "robot", "safe")
    tags = sync_adj_tags(tags, "robot", "temperature", (), ("safe",))
    tags = sync_adj_tags(tags, "robot", "pressure", (), ("safe",))

    tags = sync_adj_tags(tags, "robot", "temperature", ("safe",), ())
    tags = sync_adj_tags(tags, "robot", "pressure", ("safe",), ())

    assert len(tags) == 1
    assert tags[0].fact.sources.has_kind(SourceKind.EXPLICIT)
    assert not tags[0].fact.sources.has_kind(SourceKind.DERIVED)
