"""Deterministic, side-effect-free projections of committed Symbox state."""

from __future__ import annotations

from dataclasses import dataclass

from symbox.application.attributes import AttributeEntry
from symbox.application.bindings import BindingState
from symbox.application.relations import RelationFact
from symbox.application.tags import TagEntry
from symbox.domain.models import ObjectCategory
from symbox.kernel.port import TruthKernel


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
