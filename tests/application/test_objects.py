"""Object create/delete application command tests."""

from __future__ import annotations

import pytest

from symbox.application.objects import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ObjectState,
    create_object,
    delete_object,
)
from symbox.domain.models import ObjectCategory
from symbox.domain.node_keys import NodeKey
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import Justification, Premise, TruthNode, TruthValue


def test_create_registers_unique_object_and_true_existence_fact() -> None:
    original = ObjectState((), InMemoryTruthKernel())

    created = create_object(original, "robot", ObjectCategory.PHYSICAL)

    assert original.objects == ()
    assert created.objects[0].name == "robot"
    assert created.kernel.truth(NodeKey.subject("robot")) is TruthValue.TRUE


def test_create_rejects_duplicate_without_changing_original() -> None:
    original = create_object(ObjectState((), InMemoryTruthKernel()), "robot")

    with pytest.raises(ObjectAlreadyExistsError, match="already exists"):
        create_object(original, " robot ", ObjectCategory.ABSTRACT)

    assert len(original.objects) == 1
    assert original.kernel.truth(NodeKey.subject("robot")) is TruthValue.TRUE


def test_delete_withdraws_object_and_propagates_dependent_truth() -> None:
    original = create_object(ObjectState((), InMemoryTruthKernel()), "robot")
    candidate_kernel = original.kernel.clone()
    dependent = NodeKey.tag("robot", "active")
    candidate_kernel.register_node(TruthNode(dependent))
    candidate_kernel.add_justification(
        Justification(
            "robot-implies-active",
            dependent,
            (Premise(NodeKey.subject("robot")),),
        )
    )
    candidate_kernel.propagate()
    state = ObjectState(original.objects, candidate_kernel)
    assert state.kernel.truth(dependent) is TruthValue.TRUE

    deleted = delete_object(state, "robot")

    assert deleted.objects == ()
    assert deleted.kernel.truth(dependent) is TruthValue.UNKNOWN
    assert state.kernel.truth(NodeKey.subject("robot")) is TruthValue.TRUE


def test_delete_unknown_object_preserves_original_state() -> None:
    original = create_object(ObjectState((), InMemoryTruthKernel()), "robot")

    with pytest.raises(ObjectNotFoundError, match="unknown object"):
        delete_object(original, "missing")

    assert original.kernel.truth(NodeKey.subject("robot")) is TruthValue.TRUE
