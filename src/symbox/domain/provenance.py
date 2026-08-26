"""Immutable, source-aware Adj and tag facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from symbox.domain.models import Adj, DomainInvariantError, Tag, _required_name


class SourceKind(StrEnum):
    """Normative origins visible through state queries."""

    EXPLICIT = "explicit"
    DERIVED = "derived"
    ASSUMPTION = "assumption"


@dataclass(frozen=True, slots=True)
class FactSource:
    """One independently retractable support for a fact."""

    kind: SourceKind
    source_id: str
    justification: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _required_name(self.source_id, "source id"))
        normalized = tuple(
            _required_name(node, "justification node") for node in self.justification
        )
        if len(normalized) != len(set(normalized)):
            raise DomainInvariantError("justification nodes must be unique")
        object.__setattr__(self, "justification", normalized)

    @property
    def identity(self) -> tuple[SourceKind, str]:
        """Identify a source independently of its explanatory metadata."""
        return self.kind, self.source_id


@dataclass(frozen=True, slots=True)
class SourceSet:
    """The complete non-empty support set for one effective fact."""

    sources: frozenset[FactSource]

    def __post_init__(self) -> None:
        if not self.sources:
            raise DomainInvariantError("an effective fact must have at least one source")
        identities = [source.identity for source in self.sources]
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("fact source identities must be unique")

    @classmethod
    def one(cls, source: FactSource) -> SourceSet:
        """Create support from a single source."""
        return cls(frozenset({source}))

    def add(self, source: FactSource) -> SourceSet:
        """Add or idempotently retain an identical source."""
        for existing in self.sources:
            if existing.identity == source.identity and existing != source:
                raise DomainInvariantError("source identity already has different metadata")
        return SourceSet(self.sources | {source})

    def withdraw(self, kind: SourceKind, source_id: str) -> SourceSet | None:
        """Retract exactly one support; return ``None`` when the fact becomes ineffective."""
        identity = kind, _required_name(source_id, "source id")
        remaining = frozenset(source for source in self.sources if source.identity != identity)
        if remaining == self.sources:
            raise DomainInvariantError("cannot withdraw an unknown fact source")
        return SourceSet(remaining) if remaining else None

    def has_kind(self, kind: SourceKind) -> bool:
        """Report whether any support of the requested normative kind remains."""
        return any(source.kind is kind for source in self.sources)


@dataclass(frozen=True, slots=True)
class AdjFact:
    """An effective Adj with one or more independent supports."""

    adj: Adj
    sources: SourceSet

    def withdraw(self, kind: SourceKind, source_id: str) -> AdjFact | None:
        remaining = self.sources.withdraw(kind, source_id)
        return AdjFact(self.adj, remaining) if remaining else None


@dataclass(frozen=True, slots=True)
class TagFact:
    """An effective tag preserving explicit and derived supports separately."""

    tag: Tag
    sources: SourceSet

    def add_source(self, source: FactSource) -> TagFact:
        return TagFact(self.tag, self.sources.add(source))

    def withdraw(self, kind: SourceKind, source_id: str) -> TagFact | None:
        remaining = self.sources.withdraw(kind, source_id)
        return TagFact(self.tag, remaining) if remaining else None
