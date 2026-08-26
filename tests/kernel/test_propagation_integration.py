"""Cross-object propagation, retraction, soundness, and atomic conflict tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from symbox.application.transactions import TransactionCoordinator
from symbox.domain.node_keys import NodeKey
from symbox.kernel.ltms_adapter import LTMSTruthKernel
from symbox.kernel.port import (
    Assumption,
    Justification,
    Premise,
    TruthNode,
    TruthValue,
)


def _cross_object_kernel() -> tuple[LTMSTruthKernel, dict[str, NodeKey]]:
    kernel = LTMSTruthKernel()
    nodes = {
        "robot": NodeKey.subject("robot"),
        "battery": NodeKey.adj("robot", "battery-ok"),
        "mission": NodeKey.svk("robot", "can-run", "a" * 64),
        "dock": NodeKey.subject("dock"),
        "available": NodeKey.tag("dock", "available"),
    }
    for key in nodes.values():
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("robot-exists", nodes["robot"]))
    kernel.assert_assumption(Assumption("battery-ok", nodes["battery"]))
    kernel.assert_assumption(Assumption("dock-exists", nodes["dock"]))
    kernel.add_justification(
        Justification(
            "robot-battery-mission",
            nodes["mission"],
            (Premise(nodes["robot"]), Premise(nodes["battery"])),
        )
    )
    kernel.add_justification(
        Justification(
            "mission-dock-available",
            nodes["available"],
            (Premise(nodes["mission"]), Premise(nodes["dock"])),
        )
    )
    return kernel, nodes


def test_cross_object_and_relation_propagation_reaches_target() -> None:
    kernel, nodes = _cross_object_kernel()

    report = kernel.propagate()

    assert report.consistent
    assert kernel.truth(nodes["mission"]) is TruthValue.TRUE
    assert kernel.truth(nodes["available"]) is TruthValue.TRUE


def test_retracting_attribute_support_corrects_all_dependent_facts() -> None:
    kernel, nodes = _cross_object_kernel()
    kernel.propagate()

    kernel.retract_assumption("battery-ok")
    report = kernel.propagate()

    assert report.consistent
    assert kernel.truth(nodes["battery"]) is TruthValue.UNKNOWN
    assert kernel.truth(nodes["mission"]) is TruthValue.UNKNOWN
    assert kernel.truth(nodes["available"]) is TruthValue.UNKNOWN


def test_unregistered_global_constraint_is_not_falsely_claimed_as_conflict() -> None:
    kernel = LTMSTruthKernel()
    first = NodeKey.subject("first")
    second = NodeKey.subject("second")
    for key in (first, second):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("first", first))
    kernel.assert_assumption(Assumption("second", second))

    report = kernel.propagate()

    assert report.consistent
    assert report.conflicts == ()
    assert kernel.truth(first) is TruthValue.TRUE
    assert kernel.truth(second) is TruthValue.TRUE


@dataclass(frozen=True)
class KernelSnapshot:
    kernel: LTMSTruthKernel


class KernelStore:
    def __init__(self, state: KernelSnapshot) -> None:
        self.state = state
        self.save_calls = 0

    def load(self) -> KernelSnapshot:
        return self.state

    def save(self, state: KernelSnapshot) -> None:
        self.save_calls += 1
        self.state = state


def test_reachable_conflict_aborts_candidate_transaction_atomically() -> None:
    committed = LTMSTruthKernel()
    health = NodeKey.worry("battery")
    committed.register_node(TruthNode(health))
    committed.assert_assumption(Assumption("healthy", health, TruthValue.TRUE))
    committed.propagate()
    store = KernelStore(KernelSnapshot(committed))
    coordinator = TransactionCoordinator(store)

    def mutate(snapshot: KernelSnapshot) -> KernelSnapshot:
        candidate = snapshot.kernel.clone()
        candidate.assert_assumption(Assumption("unhealthy", health, TruthValue.FALSE))
        return KernelSnapshot(candidate)

    def reject_conflicts(snapshot: KernelSnapshot) -> None:
        report = snapshot.kernel.propagate()
        if not report.consistent:
            raise RuntimeError("reachable truth conflict")

    with pytest.raises(RuntimeError, match="truth conflict"):
        coordinator.execute(mutate, propagate=reject_conflicts)

    assert store.save_calls == 0
    assert store.state.kernel.truth(health) is TruthValue.TRUE
    assert coordinator.committed.kernel.truth(health) is TruthValue.TRUE
