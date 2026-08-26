"""Atomic batch attribute parsing, provenance, and propagation tests."""

from __future__ import annotations

import pytest

from symbox.application.attributes import (
    AttributeNotFoundError,
    AttributeState,
    parse_assignments,
    set_attributes,
    unset_attributes,
)
from symbox.application.bindings import BindingState
from symbox.application.objects import ObjectState, create_object
from symbox.domain.node_keys import NodeKey
from symbox.domain.provenance import SourceKind
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import TruthValue


def _state() -> AttributeState:
    objects = create_object(ObjectState((), InMemoryTruthKernel()), "robot")
    return AttributeState(BindingState(objects))


def test_parse_assignments_preserves_json_types_and_rejects_duplicates() -> None:
    assert parse_assignments(("count=2", 'name="r2"', "ready=true")) == {
        "count": 2,
        "name": "r2",
        "ready": True,
    }
    with pytest.raises(ValueError, match="duplicate"):
        parse_assignments(("count=1", "count=2"))


def test_batch_set_registers_explicit_sources_and_truth_nodes() -> None:
    state = set_attributes(_state(), "robot", {"battery": 80, "mode": "auto"})

    assert [entry.fact.adj.key for entry in state.attributes] == ["battery", "mode"]
    assert all(entry.fact.sources.has_kind(SourceKind.EXPLICIT) for entry in state.attributes)
    assert state.kernel is not None
    assert state.kernel.truth(NodeKey.adj("robot", "battery")) is TruthValue.TRUE


def test_invalid_batch_keeps_original_state_unchanged() -> None:
    original = set_attributes(_state(), "robot", {"battery": 80})

    with pytest.raises(ValueError):
        set_attributes(original, "robot", {"mode": object(), "battery": 0})

    assert [entry.fact.adj.value for entry in original.attributes] == [80]


def test_unset_withdraws_facts_and_unknown_key_aborts_whole_batch() -> None:
    original = set_attributes(_state(), "robot", {"battery": 80, "mode": "auto"})

    with pytest.raises(AttributeNotFoundError):
        unset_attributes(original, "robot", ("battery", "missing"))
    assert len(original.attributes) == 2

    updated = unset_attributes(original, "robot", ("battery", "mode"))
    assert updated.attributes == ()
