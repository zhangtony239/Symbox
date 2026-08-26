"""Native LTMS mapping details beyond the shared port contract."""

from __future__ import annotations

from symbox.domain.node_keys import NodeKey
from symbox.kernel.ltms_adapter import LTMSTruthKernel
from symbox.kernel.port import (
    Assumption,
    Justification,
    Premise,
    TruthNode,
    TruthValue,
)


def test_signed_false_premise_maps_to_native_clause() -> None:
    kernel = LTMSTruthKernel()
    health = NodeKey.worry("battery")
    alarm = NodeKey.tag("robot", "alarm")
    for key in (health, alarm):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("battery-low", health, TruthValue.FALSE))
    kernel.add_justification(
        Justification(
            "low-battery-implies-alarm",
            alarm,
            (Premise(health, TruthValue.FALSE),),
        )
    )

    report = kernel.propagate()

    assert report.consistent
    assert kernel.truth(health) is TruthValue.FALSE
    assert kernel.truth(alarm) is TruthValue.TRUE


def test_justification_retraction_rebuilds_native_graph() -> None:
    kernel = LTMSTruthKernel()
    source = NodeKey.subject("source")
    target = NodeKey.subject("target")
    for key in (source, target):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("source", source))
    kernel.add_justification(Justification("source-target", target, (Premise(source),)))
    kernel.propagate()
    assert kernel.truth(target) is TruthValue.TRUE

    kernel.retract_justification("source-target")
    kernel.propagate()

    assert kernel.truth(target) is TruthValue.UNKNOWN


def test_clone_deterministically_rebuilds_an_isolated_native_kernel() -> None:
    committed = LTMSTruthKernel()
    source = NodeKey.subject("source")
    target = NodeKey.subject("target")
    for key in (target, source):  # Deliberately register out of canonical order.
        committed.register_node(TruthNode(key))
    committed.assert_assumption(Assumption("source", source))
    committed.add_justification(Justification("source-target", target, (Premise(source),)))
    committed.propagate()

    candidate = committed.clone()
    candidate.retract_assumption("source")
    candidate.propagate()

    assert candidate.truth(source) is TruthValue.UNKNOWN
    assert candidate.truth(target) is TruthValue.UNKNOWN
    assert committed.truth(source) is TruthValue.TRUE
    assert committed.truth(target) is TruthValue.TRUE


def test_repeated_native_rebuilds_have_stable_truth_and_explanation() -> None:
    kernel = LTMSTruthKernel()
    source = NodeKey.subject("source")
    target = NodeKey.subject("target")
    for key in (source, target):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("source", source))
    kernel.add_justification(Justification("source-target", target, (Premise(source),)))

    first_report = kernel.propagate()
    first_explanation = kernel.explain(target)
    second_report = kernel.propagate()

    assert first_report.consistent
    assert second_report.consistent
    assert second_report.changed == ()
    assert kernel.explain(target) == first_explanation
