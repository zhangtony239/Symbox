"""Derived and explicit tag synchronization for effective Adj facts."""

from __future__ import annotations

from dataclasses import dataclass

from symbox.domain.models import DomainInvariantError, Tag
from symbox.domain.node_keys import NodeKey
from symbox.domain.provenance import FactSource, SourceKind, SourceSet, TagFact


@dataclass(frozen=True, slots=True)
class TagEntry:
    """One subject's effective tag and all independent supports."""

    subject: str
    fact: TagFact


def add_explicit_tag(
    tags: tuple[TagEntry, ...],
    subject: str,
    tag_name: str,
) -> tuple[TagEntry, ...]:
    """Add a persistent explicit support without replacing derived supports."""
    return _add_source(
        tags,
        subject,
        tag_name,
        FactSource(SourceKind.EXPLICIT, _explicit_source_id(subject, tag_name)),
    )


def sync_adj_tags(
    tags: tuple[TagEntry, ...],
    subject: str,
    adj_key: str,
    previous: tuple[str, ...],
    current: tuple[str, ...],
) -> tuple[TagEntry, ...]:
    """Apply one Adj's tag delta while preserving every other source."""
    if len(previous) != len(set(previous)) or len(current) != len(set(current)):
        raise DomainInvariantError("implied tag declarations must be unique")
    result = tags
    source_id = _derived_source_id(subject, adj_key)
    for tag_name in sorted(set(previous) - set(current)):
        result = _withdraw_source(result, subject, tag_name, SourceKind.DERIVED, source_id)
    for tag_name in sorted(set(current) - set(previous)):
        result = _add_source(
            result,
            subject,
            tag_name,
            FactSource(
                SourceKind.DERIVED,
                source_id,
                justification=(NodeKey.adj(subject, adj_key).encode(),),
            ),
        )
    return result


def _add_source(
    tags: tuple[TagEntry, ...],
    subject: str,
    tag_name: str,
    source: FactSource,
) -> tuple[TagEntry, ...]:
    entries = {(entry.subject, entry.fact.tag.name): entry for entry in tags}
    identity = subject, Tag(tag_name).name
    existing = entries.get(identity)
    if existing is None:
        entries[identity] = TagEntry(subject, TagFact(Tag(tag_name), SourceSet.one(source)))
    elif source.identity not in {item.identity for item in existing.fact.sources.sources}:
        entries[identity] = TagEntry(subject, existing.fact.add_source(source))
    return tuple(entry for _, entry in sorted(entries.items()))


def _withdraw_source(
    tags: tuple[TagEntry, ...],
    subject: str,
    tag_name: str,
    kind: SourceKind,
    source_id: str,
) -> tuple[TagEntry, ...]:
    entries = {(entry.subject, entry.fact.tag.name): entry for entry in tags}
    identity = subject, tag_name
    existing = entries.get(identity)
    if existing is None:
        raise DomainInvariantError(f"cannot withdraw unknown tag: {subject}:{tag_name}")
    remaining = existing.fact.withdraw(kind, source_id)
    if remaining is None:
        del entries[identity]
    else:
        entries[identity] = TagEntry(subject, remaining)
    return tuple(entry for _, entry in sorted(entries.items()))


def _explicit_source_id(subject: str, tag_name: str) -> str:
    return f"tag-explicit:{NodeKey.tag(subject, tag_name).encode()}"


def _derived_source_id(subject: str, adj_key: str) -> str:
    return f"tag-derived:{NodeKey.adj(subject, adj_key).encode()}"
