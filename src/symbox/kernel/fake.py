"""Deterministic in-memory TruthKernel used by application and contract tests."""

from __future__ import annotations

from copy import deepcopy

from symbox.domain.models import DomainInvariantError, _required_name
from symbox.domain.node_keys import NodeKey
from symbox.kernel.port import (
    Assumption,
    Explanation,
    Justification,
    PropagationConflict,
    PropagationReport,
    SupportRef,
    TruthNode,
    TruthValue,
)


class InMemoryTruthKernel:
    """A small sound Horn propagator with complete metadata for test use."""

    def __init__(self) -> None:
        self._nodes: dict[NodeKey, TruthNode] = {}
        self._assumptions: dict[str, Assumption] = {}
        self._justifications: dict[str, Justification] = {}
        self._truths: dict[NodeKey, TruthValue] = {}
        self._supports: dict[tuple[NodeKey, TruthValue], tuple[SupportRef, ...]] = {}

    def clone(self) -> InMemoryTruthKernel:
        """Return a fully isolated candidate graph."""
        return deepcopy(self)

    def register_node(self, node: TruthNode) -> None:
        """Register a node idempotently."""
        self._nodes.setdefault(node.key, node)
        self._truths.setdefault(node.key, TruthValue.UNKNOWN)

    def retract_node(self, key: NodeKey) -> None:
        """Remove a node and all assumptions or rules that reference it."""
        if key not in self._nodes:
            raise DomainInvariantError(f"unknown truth node: {key.encode()}")
        del self._nodes[key]
        self._truths.pop(key, None)
        self._assumptions = {
            identifier: assumption
            for identifier, assumption in self._assumptions.items()
            if assumption.node != key
        }
        self._justifications = {
            identifier: justification
            for identifier, justification in self._justifications.items()
            if justification.conclusion != key
            and all(premise.node != key for premise in justification.premises)
        }
        self._supports = {
            identity: supports
            for identity, supports in self._supports.items()
            if identity[0] != key
        }

    def assert_assumption(self, assumption: Assumption) -> None:
        """Add primitive support after validating its target node."""
        self._require_node(assumption.node)
        existing = self._assumptions.get(assumption.assumption_id)
        if existing is not None and existing != assumption:
            raise DomainInvariantError("assumption id already identifies different support")
        self._assumptions[assumption.assumption_id] = assumption

    def retract_assumption(self, assumption_id: str) -> None:
        """Remove primitive support by stable identifier."""
        identifier = _required_name(assumption_id, "assumption id")
        if self._assumptions.pop(identifier, None) is None:
            raise DomainInvariantError(f"unknown assumption: {identifier}")

    def add_justification(self, justification: Justification) -> None:
        """Add a rule only when its conclusion and premises are registered."""
        self._require_node(justification.conclusion)
        for premise in justification.premises:
            self._require_node(premise.node)
        existing = self._justifications.get(justification.justification_id)
        if existing is not None and existing != justification:
            raise DomainInvariantError("justification id already identifies a different rule")
        self._justifications[justification.justification_id] = justification

    def retract_justification(self, justification_id: str) -> None:
        """Remove a rule by stable identifier."""
        identifier = _required_name(justification_id, "justification id")
        if self._justifications.pop(identifier, None) is None:
            raise DomainInvariantError(f"unknown justification: {identifier}")

    def truth(self, key: NodeKey) -> TruthValue:
        """Read the last stable state, rejecting unknown node identities."""
        self._require_node(key)
        return self._truths[key]

    def propagate(self) -> PropagationReport:
        """Recompute all reachable positive and negative supports to a fixed point."""
        previous = dict(self._truths)
        supports: dict[tuple[NodeKey, TruthValue], set[SupportRef]] = {}
        for assumption in self._assumptions.values():
            support = SupportRef(
                assumption.assumption_id,
                "assumption",
                value=assumption.value,
            )
            supports.setdefault((assumption.node, assumption.value), set()).add(support)

        changed = True
        while changed:
            changed = False
            for rule in self._ordered_justifications():
                if all((premise.node, premise.expected) in supports for premise in rule.premises):
                    support = SupportRef(
                        rule.justification_id,
                        "justification",
                        tuple(premise.node for premise in rule.premises),
                        tuple(premise.expected for premise in rule.premises),
                        rule.conclusion_value,
                    )
                    target = supports.setdefault((rule.conclusion, rule.conclusion_value), set())
                    if support not in target:
                        target.add(support)
                        changed = True

        truths: dict[NodeKey, TruthValue] = {}
        conflicts: list[PropagationConflict] = []
        normalized_supports = {
            identity: tuple(sorted(values, key=lambda support: (support.kind, support.support_id)))
            for identity, values in supports.items()
        }
        for key in self._ordered_node_keys():
            true_supports = normalized_supports.get((key, TruthValue.TRUE), ())
            false_supports = normalized_supports.get((key, TruthValue.FALSE), ())
            if true_supports and false_supports:
                truths[key] = TruthValue.UNKNOWN
                conflicts.append(PropagationConflict(key, true_supports, false_supports))
            elif true_supports:
                truths[key] = TruthValue.TRUE
            elif false_supports:
                truths[key] = TruthValue.FALSE
            else:
                truths[key] = TruthValue.UNKNOWN

        self._truths = truths
        self._supports = normalized_supports
        changed_keys = tuple(
            key for key in self._ordered_node_keys() if previous.get(key) != truths[key]
        )
        return PropagationReport(changed_keys, tuple(conflicts))

    def explain(self, key: NodeKey) -> Explanation:
        """Return deterministic direct supports for recursive traversal."""
        value = self.truth(key)
        if value is TruthValue.UNKNOWN:
            supports = (
                *self._supports.get((key, TruthValue.TRUE), ()),
                *self._supports.get((key, TruthValue.FALSE), ()),
            )
        else:
            supports = self._supports.get((key, value), ())
        return Explanation(key, value, tuple(supports))

    def _require_node(self, key: NodeKey) -> None:
        if key not in self._nodes:
            raise DomainInvariantError(f"unknown truth node: {key.encode()}")

    def _ordered_node_keys(self) -> tuple[NodeKey, ...]:
        return tuple(sorted(self._nodes, key=NodeKey.encode))

    def _ordered_justifications(self) -> tuple[Justification, ...]:
        return tuple(
            sorted(self._justifications.values(), key=lambda rule: rule.justification_id)
        )
