"""Recursive justification chains and conflict evidence expansion."""

from __future__ import annotations

from dataclasses import dataclass

from symbox.domain.node_keys import NodeKey
from symbox.kernel.port import PropagationConflict, SupportRef, TruthKernel, TruthValue


@dataclass(frozen=True, slots=True)
class EvidenceStep:
    """One support in a recursively traversable justification path."""

    node: NodeKey
    value: TruthValue
    support_id: str | None
    support_kind: str | None
    premises: tuple[EvidenceStep, ...] = ()
    cycle: bool = False


@dataclass(frozen=True, slots=True)
class ConflictEvidence:
    """Both reachable polarities that make a candidate node contradictory."""

    node: NodeKey
    true_paths: tuple[EvidenceStep, ...]
    false_paths: tuple[EvidenceStep, ...]


def explain_paths(
    kernel: TruthKernel,
    node: NodeKey,
    value: TruthValue | None = None,
) -> tuple[EvidenceStep, ...]:
    """Expand all direct supports to assumptions, retaining shared and cyclic paths."""
    requested = value if value is not None else kernel.truth(node)
    return _expand(kernel, node, requested, frozenset())


def explain_conflict(
    kernel: TruthKernel,
    conflict: PropagationConflict,
) -> ConflictEvidence:
    """Expand the positive and negative support sets from a propagation conflict."""
    true_paths = tuple(
        _expand_support(kernel, conflict.node, support, frozenset())
        for support in conflict.true_supports
    )
    false_paths = tuple(
        _expand_support(kernel, conflict.node, support, frozenset())
        for support in conflict.false_supports
    )
    return ConflictEvidence(conflict.node, true_paths, false_paths)


def _expand(
    kernel: TruthKernel,
    node: NodeKey,
    value: TruthValue,
    visiting: frozenset[tuple[NodeKey, TruthValue]],
) -> tuple[EvidenceStep, ...]:
    identity = node, value
    if identity in visiting:
        return (EvidenceStep(node, value, None, None, cycle=True),)
    supports = tuple(support for support in kernel.explain(node).supports if support.value is value)
    if not supports:
        return (EvidenceStep(node, value, None, None),)
    next_visiting = visiting | {identity}
    return tuple(_expand_support(kernel, node, support, next_visiting) for support in supports)


def _expand_support(
    kernel: TruthKernel,
    node: NodeKey,
    support: SupportRef,
    visiting: frozenset[tuple[NodeKey, TruthValue]],
) -> EvidenceStep:
    premises: list[EvidenceStep] = []
    for premise_node, premise_value in zip(
        support.premises,
        support.premise_values,
        strict=True,
    ):
        premises.extend(_expand(kernel, premise_node, premise_value, visiting))
    return EvidenceStep(
        node,
        support.value,
        support.support_id,
        support.kind,
        tuple(premises),
    )
