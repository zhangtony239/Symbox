"""Deterministic, side-effect-free projections of committed Symbox state."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from symbox.application.attributes import AttributeEntry
from symbox.application.bindings import BindingState
from symbox.application.objects import ObjectNotFoundError
from symbox.application.relations import RelationFact
from symbox.application.tags import TagEntry
from symbox.domain.models import DomainInvariantError, ObjectCategory
from symbox.domain.node_keys import NodeKey
from symbox.domain.provenance import SourceSet
from symbox.kernel.port import Explanation, TruthKernel, TruthValue


@dataclass(frozen=True, slots=True)
class QueryState:
    """Committed records available to read-only list operations."""

    objects: BindingState
    attributes: tuple[AttributeEntry, ...] = ()
    tags: tuple[TagEntry, ...] = ()
    relations: tuple[RelationFact, ...] = ()
    kernel: TruthKernel | None = None

    def __post_init__(self) -> None:
        if self.kernel is None:
            object.__setattr__(self, "kernel", self.objects.objects.kernel)


@dataclass(frozen=True, slots=True)
class ObjectSummary:
    """Stable machine-readable object catalog entry."""

    name: str
    category: ObjectCategory
    is_verb: bool


@dataclass(frozen=True, slots=True)
class BindingSummary:
    """Persistence-safe binding metadata that never resolves the callable."""

    source_path: str
    qualified_name: str
    source_digest: str


@dataclass(frozen=True, slots=True)
class VerbSummary:
    """One explicitly marked Verb and its currently available binding."""

    name: str
    category: ObjectCategory
    binding: BindingSummary


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """One visible explicit, derived, or assumption fact source."""

    kind: str
    source_id: str
    justification: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AttributeSummary:
    """One effective Adj and all of its independent sources."""

    key: str
    value: Any
    recorded_at: str
    sources: tuple[SourceSummary, ...]


@dataclass(frozen=True, slots=True)
class TagSummary:
    """One effective tag and all of its independent sources."""

    name: str
    sources: tuple[SourceSummary, ...]


@dataclass(frozen=True, slots=True)
class RelationSummary:
    """One normalized relation involving the queried object."""

    node_key: str
    subject: str
    verb: str
    args: tuple[Any, ...]
    kwargs: tuple[tuple[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SupportSummary:
    """One direct assumption or justification behind a truth value."""

    support_id: str
    kind: str
    premises: tuple[str, ...]
    premise_values: tuple[TruthValue, ...]
    value: TruthValue


@dataclass(frozen=True, slots=True)
class TruthSummary:
    """One related fact's three-valued state and direct justification metadata."""

    node_key: str
    value: TruthValue
    supports: tuple[SupportSummary, ...]


@dataclass(frozen=True, slots=True)
class ObjectDetail:
    """Complete currently observable state for one named object."""

    name: str
    category: ObjectCategory
    is_verb: bool
    attributes: tuple[AttributeSummary, ...]
    tags: tuple[TagSummary, ...]
    binding: BindingSummary | None
    relations: tuple[RelationSummary, ...]
    truths: tuple[TruthSummary, ...]


class BackupMetadata(Protocol):
    """Minimal metadata boundary supplied by a backup infrastructure adapter."""

    commit_id: str
    note: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BackupSummary:
    """Stable machine-readable backup list entry."""

    commit_id: str
    note: str
    created_at: str


def list_objects(state: QueryState) -> tuple[ObjectSummary, ...]:
    """Return all object handles in deterministic name order."""
    return tuple(
        ObjectSummary(
            name=subject.name,
            category=subject.category,
            is_verb=state.objects.is_verb(subject.name),
        )
        for subject in state.objects.objects.objects
    )


def list_verbs(state: QueryState) -> tuple[VerbSummary, ...]:
    """Return only explicitly marked Verb objects without loading their callables."""
    categories = {
        subject.name: subject.category for subject in state.objects.objects.objects
    }
    return tuple(
        VerbSummary(
            name=entry.object_name,
            category=categories[entry.object_name],
            binding=BindingSummary(
                source_path=entry.reference.source_path,
                qualified_name=entry.reference.qualified_name,
                source_digest=entry.reference.source_digest,
            ),
        )
        for entry in state.objects.bindings
        if entry.reference.is_verb
    )


def list_backups(records: Iterable[BackupMetadata]) -> tuple[BackupSummary, ...]:
    """Project backup metadata into the unified list-query representation."""
    return tuple(
        BackupSummary(record.commit_id, record.note, record.created_at.isoformat())
        for record in records
    )


def get_object_detail(state: QueryState, name: str) -> ObjectDetail:
    """Project one object's complete observable state without executing bindings."""
    subject = next(
        (item for item in state.objects.objects.objects if item.name == name),
        None,
    )
    if subject is None:
        raise ObjectNotFoundError(f"unknown object: {name}")

    binding_entry = state.objects.binding_for(name)
    binding = (
        BindingSummary(
            binding_entry.reference.source_path,
            binding_entry.reference.qualified_name,
            binding_entry.reference.source_digest,
        )
        if binding_entry is not None
        else None
    )
    attributes = tuple(
        AttributeSummary(
            entry.fact.adj.key,
            entry.fact.adj.value,
            entry.fact.adj.recorded_at.isoformat(),
            _source_summaries(entry.fact.sources),
        )
        for entry in state.attributes
        if entry.subject == name
    )
    tags = tuple(
        TagSummary(entry.fact.tag.name, _source_summaries(entry.fact.sources))
        for entry in state.tags
        if entry.subject == name
    )
    relations = tuple(
        _relation_summary(fact)
        for fact in state.relations
        if _relation_involves(fact, name)
    )
    truth_keys = {
        NodeKey.subject(name),
        *(NodeKey.adj(name, item.key) for item in attributes),
        *(NodeKey.tag(name, item.name) for item in tags),
        *(NodeKey.parse(item.node_key) for item in relations),
    }
    kernel = _kernel(state)
    truths = tuple(
        _truth_summary(kernel, key)
        for key in sorted(truth_keys, key=NodeKey.encode)
    )
    return ObjectDetail(
        name=subject.name,
        category=subject.category,
        is_verb=state.objects.is_verb(name),
        attributes=attributes,
        tags=tags,
        binding=binding,
        relations=relations,
        truths=truths,
    )


def _source_summaries(sources: SourceSet) -> tuple[SourceSummary, ...]:
    return tuple(
        SourceSummary(source.kind.value, source.source_id, source.justification)
        for source in sorted(
            sources.sources,
            key=lambda item: (item.kind.value, item.source_id),
        )
    )


def _relation_summary(fact: RelationFact) -> RelationSummary:
    relation = fact.relation
    return RelationSummary(
        fact.node_key,
        relation.subject,
        relation.verb,
        relation.args,
        relation.kwargs,
    )


def _relation_involves(fact: RelationFact, name: str) -> bool:
    relation = fact.relation
    return (
        relation.subject == name
        or relation.verb == name
        or name in relation.args
        or any(value == name for _, value in relation.kwargs)
    )


def _truth_summary(kernel: TruthKernel, key: NodeKey) -> TruthSummary:
    try:
        explanation = kernel.explain(key)
    except DomainInvariantError:
        explanation = Explanation(key, TruthValue.UNKNOWN)
    supports = tuple(
        SupportSummary(
            support.support_id,
            support.kind,
            tuple(premise.encode() for premise in support.premises),
            support.premise_values,
            support.value,
        )
        for support in explanation.supports
    )
    return TruthSummary(key.encode(), explanation.value, supports)


def _kernel(state: QueryState) -> TruthKernel:
    assert state.kernel is not None
    return state.kernel
