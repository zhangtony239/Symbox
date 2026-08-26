"""Adj implies_tags derivation and multi-source retraction tests."""

from __future__ import annotations

from symbox.application.tags import add_explicit_tag, sync_adj_tags
from symbox.domain.provenance import SourceKind


def test_effective_adj_derives_declared_tags() -> None:
    tags = sync_adj_tags((), "robot", "temperature", (), ("safe", "ready"))

    assert [entry.fact.tag.name for entry in tags] == ["ready", "safe"]
    assert all(entry.fact.sources.has_kind(SourceKind.DERIVED) for entry in tags)


def test_last_derived_source_retraction_removes_tag() -> None:
    tags = sync_adj_tags((), "robot", "temperature", (), ("safe",))

    tags = sync_adj_tags(tags, "robot", "temperature", ("safe",), ())

    assert tags == ()


def test_multiple_adj_sources_are_retracted_independently() -> None:
    tags = sync_adj_tags((), "robot", "temperature", (), ("safe",))
    tags = sync_adj_tags(tags, "robot", "pressure", (), ("safe",))

    remaining = sync_adj_tags(tags, "robot", "temperature", ("safe",), ())

    assert len(remaining) == 1
    sources = remaining[0].fact.sources.sources
    assert {source.source_id for source in sources} == {"tag-derived:Adj:robot:pressure"}


def test_retracting_derived_source_preserves_same_named_explicit_tag() -> None:
    tags = add_explicit_tag((), "robot", "safe")
    tags = sync_adj_tags(tags, "robot", "temperature", (), ("safe",))

    remaining = sync_adj_tags(tags, "robot", "temperature", ("safe",), ())

    assert len(remaining) == 1
    assert remaining[0].fact.sources.has_kind(SourceKind.EXPLICIT)
    assert not remaining[0].fact.sources.has_kind(SourceKind.DERIVED)
