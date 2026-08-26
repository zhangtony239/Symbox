"""Reusable TruthKernel port contract tests."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from symbox.domain.models import DomainInvariantError
from symbox.domain.node_keys import NodeKey
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.ltms_adapter import LTMSTruthKernel
from symbox.kernel.port import (
    Assumption,
    Justification,
    Premise,
    TruthKernel,
    TruthNode,
    TruthValue,
)

KernelFactory = Callable[[], TruthKernel]


@pytest.fixture(params=[InMemoryTruthKernel, LTMSTruthKernel], ids=["fake", "ltms"])
def kernel_factory(request: pytest.FixtureRequest) -> KernelFactory:
    return request.param  # type: ignore[no-any-return]


def test_adapter_satisfies_runtime_port(kernel_factory: KernelFactory) -> None:
    assert isinstance(kernel_factory(), TruthKernel)


def test_assumption_sets_truth_and_retraction_returns_unknown(
    kernel_factory: KernelFactory,
) -> None:
    kernel = kernel_factory()
    robot = NodeKey.subject("robot")
    kernel.register_node(TruthNode(robot))
    kernel.assert_assumption(Assumption("robot-exists", robot))

    report = kernel.propagate()

    assert report.consistent
    assert kernel.truth(robot) is TruthValue.TRUE
    assert kernel.explain(robot).supports[0].support_id == "robot-exists"

    kernel.retract_assumption("robot-exists")
    kernel.propagate()
    assert kernel.truth(robot) is TruthValue.UNKNOWN


def test_justification_propagates_and_retracts(kernel_factory: KernelFactory) -> None:
    kernel = kernel_factory()
    robot = NodeKey.subject("robot")
    safe = NodeKey.tag("robot", "safe")
    for key in (robot, safe):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("robot-exists", robot))
    kernel.add_justification(Justification("robot-is-safe", safe, (Premise(robot),)))

    kernel.propagate()

    assert kernel.truth(safe) is TruthValue.TRUE
    explanation = kernel.explain(safe)
    assert explanation.supports[0].premises == (robot,)
    assert explanation.supports[0].premise_values == (TruthValue.TRUE,)

    kernel.retract_justification("robot-is-safe")
    kernel.propagate()
    assert kernel.truth(safe) is TruthValue.UNKNOWN


def test_negative_health_and_reachable_conflict_are_reported(
    kernel_factory: KernelFactory,
) -> None:
    kernel = kernel_factory()
    health = NodeKey.worry("battery")
    kernel.register_node(TruthNode(health))
    kernel.assert_assumption(Assumption("healthy", health, TruthValue.TRUE))
    kernel.assert_assumption(Assumption("unhealthy", health, TruthValue.FALSE))

    report = kernel.propagate()

    assert not report.consistent
    assert report.conflicts[0].node == health
    assert report.conflicts[0].true_supports[0].support_id == "healthy"
    assert report.conflicts[0].false_supports[0].support_id == "unhealthy"
    assert kernel.truth(health) is TruthValue.UNKNOWN


def test_clone_is_isolated_from_committed_kernel(kernel_factory: KernelFactory) -> None:
    committed = kernel_factory()
    robot = NodeKey.subject("robot")
    committed.register_node(TruthNode(robot))
    candidate = committed.clone()
    candidate.assert_assumption(Assumption("candidate-only", robot))
    candidate.propagate()

    assert candidate.truth(robot) is TruthValue.TRUE
    assert committed.truth(robot) is TruthValue.UNKNOWN


def test_retracting_node_removes_referencing_supports(kernel_factory: KernelFactory) -> None:
    kernel = kernel_factory()
    source = NodeKey.subject("source")
    target = NodeKey.subject("target")
    for key in (source, target):
        kernel.register_node(TruthNode(key))
    kernel.assert_assumption(Assumption("source-exists", source))
    kernel.add_justification(Justification("source-target", target, (Premise(source),)))

    kernel.retract_node(source)
    kernel.propagate()

    assert kernel.truth(target) is TruthValue.UNKNOWN
    with pytest.raises(DomainInvariantError, match="unknown truth node"):
        kernel.truth(source)
