"""SVK registration, controlled effects, and unified propagation tests."""

from __future__ import annotations

import inspect

import pytest

from symbox.application.mutations import MutationContext, MutationSnapshot
from symbox.application.relations import RelationConflictError, RelationState, assert_relation
from symbox.domain.node_keys import NodeKey
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import TruthValue


def moves(subject: dict[str, object], destination: str, speed: int = 1) -> bool:
    return speed > 0 and bool(destination) and subject["ready"] is True


def test_passing_svk_registers_one_coarse_truth_node() -> None:
    original = RelationState((), MutationSnapshot({}), InMemoryTruthKernel())

    asserted = assert_relation(
        original,
        signature=inspect.signature(moves),
        check=moves,
        subject={"ready": True},
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(),
    )

    assert original.relations == ()
    assert len(asserted.state.relations) == 1
    fact = asserted.state.relations[0]
    assert fact.node_key.startswith("SVK:robot:moves:")
    assert asserted.state.kernel.truth(fact_node(fact.node_key)) is TruthValue.TRUE


def fact_node(encoded: str) -> NodeKey:
    return NodeKey.parse(encoded)


def test_false_verb_check_does_not_register_relation() -> None:
    original = RelationState((), MutationSnapshot({}), InMemoryTruthKernel())

    with pytest.raises(RelationConflictError, match="contradictory"):
        assert_relation(
            original,
            signature=inspect.signature(moves),
            check=moves,
            subject={"ready": True},
            subject_name="robot",
            verb_name="moves",
            args=("dock",),
            kwargs=(("speed", 0),),
        )

    assert original.relations == ()


def test_controlled_effect_updates_candidate_only_after_check_passes() -> None:
    original = RelationState(
        (),
        MutationSnapshot({"battery": 80}),
        InMemoryTruthKernel(),
    )

    def effect(
        context: MutationContext,
        subject: dict[str, object],
        destination: str,
        speed: int,
    ) -> None:
        context.set("battery", context.get("battery") - speed)

    asserted = assert_relation(
        original,
        signature=inspect.signature(moves),
        check=moves,
        subject={"ready": True},
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(("speed", 5),),
        apply_effect=effect,
    )

    assert asserted.state.values.values["battery"] == 75
    assert original.values.values["battery"] == 80


def test_duplicate_normalized_relation_is_idempotent() -> None:
    original = RelationState((), MutationSnapshot({}), InMemoryTruthKernel())
    first = assert_relation(
        original,
        signature=inspect.signature(moves),
        check=moves,
        subject={"ready": True},
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(),
    ).state

    second = assert_relation(
        first,
        signature=inspect.signature(moves),
        check=moves,
        subject={"ready": True},
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(("speed", 1),),
    ).state

    assert len(second.relations) == 1
