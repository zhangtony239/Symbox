"""SVK zero/multiple/mixed argument and identity-equivalence tests."""

from __future__ import annotations

import inspect

from symbox.application.mutations import MutationSnapshot
from symbox.application.relations import RelationState, assert_relation
from symbox.kernel.fake import InMemoryTruthKernel


def _state() -> RelationState:
    return RelationState((), MutationSnapshot({}), InMemoryTruthKernel())


def test_zero_post_argument_self_modification_relation() -> None:
    def refreshes(subject: object) -> bool:
        return subject == "robot"

    asserted = assert_relation(
        _state(),
        signature=inspect.signature(refreshes),
        check=refreshes,
        subject="robot",
        subject_name="robot",
        verb_name="refreshes",
        args=(),
        kwargs=(),
    )

    assert asserted.state.relations[0].relation.args == ()
    assert asserted.state.relations[0].relation.kwargs == ()


def test_multiple_positionals_and_mixed_parameters_reach_check() -> None:
    seen: list[tuple[object, ...]] = []

    def route(subject: object, origin: str, destination: str, *, speed: int = 1) -> bool:
        seen.append((subject, origin, destination, speed))
        return True

    asserted = assert_relation(
        _state(),
        signature=inspect.signature(route),
        check=route,
        subject="robot",
        subject_name="robot",
        verb_name="route",
        args=("dock", "bay"),
        kwargs=(("speed", 2),),
    )

    assert seen == [("robot", "dock", "bay", 2), ("robot", "dock", "bay", 2)]
    assert asserted.state.relations[0].relation.kwargs == (
        ("destination", "bay"),
        ("origin", "dock"),
        ("speed", 2),
    )


def test_keyword_order_is_same_identity_but_any_effective_value_difference_is_not() -> None:
    def moves(subject: object, destination: str, *, speed: int = 1, safe: bool = True) -> bool:
        return True

    signature = inspect.signature(moves)
    first = assert_relation(
        _state(),
        signature=signature,
        check=moves,
        subject="robot",
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(("speed", 2), ("safe", True)),
    ).state
    reordered = assert_relation(
        first,
        signature=signature,
        check=moves,
        subject="robot",
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(("safe", True), ("speed", 2)),
    ).state
    different = assert_relation(
        reordered,
        signature=signature,
        check=moves,
        subject="robot",
        subject_name="robot",
        verb_name="moves",
        args=("dock",),
        kwargs=(("safe", True), ("speed", 3)),
    ).state

    assert len(reordered.relations) == 1
    assert len(different.relations) == 2
    assert different.relations[0].node_key != different.relations[1].node_key
