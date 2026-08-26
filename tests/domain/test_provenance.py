"""Multi-source fact and retraction rules."""

from __future__ import annotations

import pytest

from symbox.domain.models import Adj, DomainInvariantError, Tag
from symbox.domain.provenance import AdjFact, FactSource, SourceKind, SourceSet, TagFact


def test_adj_remains_effective_until_its_last_source_is_withdrawn() -> None:
    explicit = FactSource(SourceKind.EXPLICIT, "command:1")
    assumption = FactSource(SourceKind.ASSUMPTION, "assumption:temperature")
    fact = AdjFact(Adj("temperature", 20), SourceSet.one(explicit).add(assumption))

    remaining = fact.withdraw(SourceKind.EXPLICIT, "command:1")

    assert remaining is not None
    assert remaining.sources.has_kind(SourceKind.ASSUMPTION)
    assert remaining.withdraw(SourceKind.ASSUMPTION, "assumption:temperature") is None


def test_withdrawing_derived_tag_source_preserves_same_named_explicit_tag() -> None:
    explicit = FactSource(SourceKind.EXPLICIT, "command:tag")
    derived = FactSource(
        SourceKind.DERIVED,
        "adj:temperature",
        justification=("Adj:robot:temperature",),
    )
    tag = TagFact(Tag("safe"), SourceSet.one(explicit).add(derived))

    remaining = tag.withdraw(SourceKind.DERIVED, "adj:temperature")

    assert remaining is not None
    assert remaining.sources.has_kind(SourceKind.EXPLICIT)
    assert not remaining.sources.has_kind(SourceKind.DERIVED)


def test_tag_disappears_when_last_derived_source_is_withdrawn() -> None:
    tag = TagFact(
        Tag("safe"),
        SourceSet.one(FactSource(SourceKind.DERIVED, "adj:temperature")),
    )

    assert tag.withdraw(SourceKind.DERIVED, "adj:temperature") is None


def test_multiple_derived_sources_are_independently_retractable() -> None:
    first = FactSource(SourceKind.DERIVED, "adj:temperature")
    second = FactSource(SourceKind.DERIVED, "adj:pressure")
    tag = TagFact(Tag("safe"), SourceSet.one(first).add(second))

    remaining = tag.withdraw(SourceKind.DERIVED, "adj:temperature")

    assert remaining is not None
    assert {source.source_id for source in remaining.sources.sources} == {"adj:pressure"}


def test_unknown_or_conflicting_source_updates_are_rejected() -> None:
    source = FactSource(SourceKind.EXPLICIT, "command:1")
    sources = SourceSet.one(source)

    with pytest.raises(DomainInvariantError, match="unknown"):
        sources.withdraw(SourceKind.DERIVED, "missing")
    with pytest.raises(DomainInvariantError, match="different metadata"):
        sources.add(
            FactSource(
                SourceKind.EXPLICIT,
                "command:1",
                justification=("Subject:robot",),
            )
        )
