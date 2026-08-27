"""Recursive evidence-chain and conflict-report tests."""

from __future__ import annotations

from symbox.domain.node_keys import NodeKey
from symbox.kernel.explanation import explain_conflict, explain_paths
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import (
    Assumption,
    Justification,
    Premise,
    TruthNode,
    TruthValue,
)


def test_justification_chain_reaches_primitive_assumption() -> None:
    kernel = InMemoryTruthKernel()
    source = NodeKey.subject("source")
    middle = NodeKey.tag("source", "middle")
    target = NodeKey.tag("source", "target")
    for key in (source, middle, target):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("source-assumption", source))
    kernel.add_justification(Justification("source-middle", middle, (Premise(source),)))
    kernel.add_justification(Justification("middle-target", target, (Premise(middle),)))
    kernel.propagate()

    path = explain_paths(kernel, target)[0]

    assert path.support_id == "middle-target"
    assert path.premises[0].support_id == "source-middle"
    assert path.premises[0].premises[0].support_id == "source-assumption"


def test_conflict_report_expands_both_reachable_polarities() -> None:
    kernel = InMemoryTruthKernel()
    source = NodeKey.subject("source")
    health = NodeKey.worry("health")
    for key in (source, health):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("source", source))
    kernel.add_justification(Justification("healthy", health, (Premise(source),), TruthValue.TRUE))
    kernel.add_justification(
        Justification("unhealthy", health, (Premise(source),), TruthValue.FALSE)
    )

    report = kernel.propagate()
    evidence = explain_conflict(kernel, report.conflicts[0])

    assert evidence.true_paths[0].support_id == "healthy"
    assert evidence.false_paths[0].support_id == "unhealthy"
    assert evidence.true_paths[0].premises[0].support_id == "source"
    assert evidence.false_paths[0].premises[0].support_id == "source"


def test_explanation_traversal_marks_cycles_instead_of_recursing_forever() -> None:
    kernel = InMemoryTruthKernel()
    first = NodeKey.subject("first")
    second = NodeKey.subject("second")
    for key in (first, second):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("seed", first))
    kernel.add_justification(Justification("first-second", second, (Premise(first),)))
    kernel.add_justification(Justification("second-first", first, (Premise(second),)))
    kernel.propagate()

    paths = explain_paths(kernel, first)

    cyclic_path = next(path for path in paths if path.support_id == "second-first")
    assert cyclic_path.premises[0].premises[0].cycle
