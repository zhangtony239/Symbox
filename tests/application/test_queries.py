"""Deterministic and read-only state query tests."""

from __future__ import annotations

from dataclasses import asdict

from symbox.application.bindings import BindingEntry, BindingState
from symbox.application.objects import ObjectState, create_object
from symbox.application.queries import QueryState, list_objects
from symbox.domain.models import BindingRef, ObjectCategory
from symbox.kernel.fake import InMemoryTruthKernel


def _objects() -> BindingState:
    state = ObjectState((), InMemoryTruthKernel())
    state = create_object(state, "zeta", ObjectCategory.PHYSICAL)
    state = create_object(state, "alpha", ObjectCategory.ABSTRACT)
    state = create_object(state, "monitor", ObjectCategory.META)
    reference = BindingRef("rules/checks.py", "check", "a" * 64, is_verb=True)
    return BindingState(state, (BindingEntry("zeta", reference),))


def test_list_objects_returns_name_sorted_classification_and_verb_marker() -> None:
    summaries = list_objects(QueryState(_objects()))

    assert tuple(asdict(summary) for summary in summaries) == (
        {"name": "alpha", "category": ObjectCategory.ABSTRACT, "is_verb": False},
        {"name": "monitor", "category": ObjectCategory.META, "is_verb": False},
        {"name": "zeta", "category": ObjectCategory.PHYSICAL, "is_verb": True},
    )


def test_list_objects_returns_empty_success_collection() -> None:
    empty = BindingState(ObjectState((), InMemoryTruthKernel()))

    assert list_objects(QueryState(empty)) == ()
