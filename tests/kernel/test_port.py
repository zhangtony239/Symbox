"""TruthKernel public value-contract tests."""

from __future__ import annotations

import pytest

from symbox.domain.models import DomainInvariantError
from symbox.domain.node_keys import NodeKey
from symbox.kernel.port import (
    Assumption,
    Justification,
    Premise,
    PropagationReport,
    SupportRef,
    TruthValue,
)


def test_truth_values_are_stable_public_strings() -> None:
    assert [value.value for value in TruthValue] == ["true", "false", "unknown"]


def test_assumptions_and_justifications_preserve_polarity() -> None:
    subject = NodeKey.subject("robot")
    worry = NodeKey.worry("safe")
    assumption = Assumption("subject-exists", subject, TruthValue.TRUE)
    justification = Justification(
        "robot-implies-safe",
        worry,
        (Premise(subject, TruthValue.TRUE),),
        TruthValue.FALSE,
    )

    assert assumption.value is TruthValue.TRUE
    assert justification.conclusion_value is TruthValue.FALSE
    assert justification.premises[0].node == subject


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Assumption("a", NodeKey.subject("robot"), TruthValue.UNKNOWN),
        lambda: Premise(NodeKey.subject("robot"), TruthValue.UNKNOWN),
        lambda: Justification("j", NodeKey.subject("robot"), (), TruthValue.UNKNOWN),
        lambda: Justification(
            "j",
            NodeKey.subject("robot"),
            (Premise(NodeKey.subject("source")), Premise(NodeKey.subject("source"))),
        ),
        lambda: SupportRef("support", "other"),
        lambda: SupportRef("support", "assumption", (NodeKey.subject("robot"),)),
        lambda: SupportRef(
            "support",
            "justification",
            (NodeKey.subject("robot"),),
            (),
        ),
    ],
)
def test_invalid_kernel_values_are_rejected(factory: object) -> None:
    with pytest.raises(DomainInvariantError):
        factory()  # type: ignore[operator]


def test_propagation_report_consistency_is_derived_from_conflicts() -> None:
    assert PropagationReport().consistent
