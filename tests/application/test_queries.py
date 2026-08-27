"""Deterministic and read-only state query tests."""

from __future__ import annotations

from dataclasses import asdict

from symbox.application.bindings import BindingEntry, BindingState
from symbox.application.objects import ObjectState, create_object
from symbox.application.queries import QueryState, list_objects, list_verbs
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


def test_list_verbs_filters_plain_bindings_and_returns_safe_summary() -> None:
    objects = _objects()
    plain = BindingRef("rules/plain.py", "check", "b" * 64)
    state = BindingState(
        objects.objects,
        tuple(
            sorted(
                (*objects.bindings, BindingEntry("alpha", plain)),
                key=lambda item: item.object_name,
            )
        ),
    )

    summaries = list_verbs(QueryState(state))

    assert tuple(asdict(summary) for summary in summaries) == (
        {
            "name": "zeta",
            "category": ObjectCategory.PHYSICAL,
            "binding": {
                "source_path": "rules/checks.py",
                "qualified_name": "check",
                "source_digest": "a" * 64,
            },
        },
    )


def test_list_verbs_returns_empty_collection_when_no_verb_is_marked() -> None:
    plain = BindingRef("rules/plain.py", "check", "b" * 64)
    objects = _objects()
    state = BindingState(objects.objects, (BindingEntry("alpha", plain),))

    assert list_verbs(QueryState(state)) == ()
