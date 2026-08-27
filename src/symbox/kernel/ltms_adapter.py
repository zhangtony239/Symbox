"""TruthKernel adapter backed by the installed :mod:`ltms` BCP engine."""

from __future__ import annotations

from typing import Any

from ltms import LTMS, Label

from symbox.domain.models import DomainInvariantError, _required_name
from symbox.domain.node_keys import NodeKey
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import (
    Assumption,
    Explanation,
    Justification,
    PropagationReport,
    TruthNode,
    TruthValue,
)

_LABEL_TO_TRUTH = {
    Label.TRUE: TruthValue.TRUE,
    Label.FALSE: TruthValue.FALSE,
    Label.UNKNOWN: TruthValue.UNKNOWN,
}


class LTMSTruthKernel:
    """Map the stable port onto signed LTMS clauses and assumptions.

    The third-party engine has no public clause-removal operation and stores one
    active support per node.  Stable port metadata is therefore authoritative,
    and a fresh native graph is deterministically rebuilt for each propagation.
    """

    def __init__(self) -> None:
        self._nodes: dict[NodeKey, TruthNode] = {}
        self._assumptions: dict[str, Assumption] = {}
        self._justifications: dict[str, Justification] = {}
        self._model = InMemoryTruthKernel()
        self._native = LTMS("symbox")

    def clone(self) -> LTMSTruthKernel:
        """Rebuild an isolated candidate adapter from stable port metadata."""
        candidate = LTMSTruthKernel()
        for node in self._ordered_nodes():
            candidate.register_node(node)
        for assumption in self._ordered_assumptions():
            candidate.assert_assumption(assumption)
        for justification in self._ordered_justifications():
            candidate.add_justification(justification)
        candidate.propagate()
        return candidate

    def register_node(self, node: TruthNode) -> None:
        self._nodes.setdefault(node.key, node)
        self._model.register_node(node)

    def retract_node(self, key: NodeKey) -> None:
        self._model.retract_node(key)
        self._nodes.pop(key, None)
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

    def assert_assumption(self, assumption: Assumption) -> None:
        self._model.assert_assumption(assumption)
        self._assumptions[assumption.assumption_id] = assumption

    def retract_assumption(self, assumption_id: str) -> None:
        identifier = _required_name(assumption_id, "assumption id")
        self._model.retract_assumption(identifier)
        self._assumptions.pop(identifier)

    def add_justification(self, justification: Justification) -> None:
        self._model.add_justification(justification)
        self._justifications[justification.justification_id] = justification

    def retract_justification(self, justification_id: str) -> None:
        identifier = _required_name(justification_id, "justification id")
        self._model.retract_justification(identifier)
        self._justifications.pop(identifier)

    def truth(self, key: NodeKey) -> TruthValue:
        return self._model.truth(key)

    def explain(self, key: NodeKey) -> Explanation:
        return self._model.explain(key)

    def propagate(self) -> PropagationReport:
        """Rebuild native clauses, run BCP, and verify every consistent label."""
        report = self._model.propagate()
        self._native = LTMS("symbox", node_string=lambda node: str(node.datum))
        native_nodes = {
            key: self._native.create_node(key.encode()) for key in self._ordered_node_keys()
        }

        with self._native.without_contradiction_check():
            for assumption in self._ordered_assumptions():
                token = self._native.create_node(
                    f"Assumption:{assumption.assumption_id}",
                    assumption=True,
                )
                self._native.enable_assumption(token, Label.TRUE)
                self._add_implication(
                    native_nodes,
                    ((token, Label.TRUE),),
                    native_nodes[assumption.node],
                    self._truth_to_label(assumption.value),
                    assumption.assumption_id,
                )
            for justification in self._ordered_justifications():
                premises = tuple(
                    (native_nodes[premise.node], self._truth_to_label(premise.expected))
                    for premise in justification.premises
                )
                self._add_implication(
                    native_nodes,
                    premises,
                    native_nodes[justification.conclusion],
                    self._truth_to_label(justification.conclusion_value),
                    justification.justification_id,
                )

        if report.consistent:
            for key, native_node in native_nodes.items():
                native_value = _LABEL_TO_TRUTH[self._native.label_of(native_node)]
                model_value = self._model.truth(key)
                if native_value is not model_value:
                    raise RuntimeError(
                        f"LTMS label mismatch for {key.encode()}: "
                        f"native={native_value.value}, model={model_value.value}"
                    )
        return report

    def _add_implication(
        self,
        native_nodes: dict[NodeKey, Any],
        premises: tuple[tuple[Any, Label], ...],
        conclusion: Any,
        conclusion_value: Label,
        informant: str,
    ) -> None:
        del native_nodes  # Documents that all referenced nodes belong to this rebuild.
        true_nodes = [node for node, expected in premises if expected is Label.FALSE]
        false_nodes = [node for node, expected in premises if expected is Label.TRUE]
        if conclusion_value is Label.TRUE:
            true_nodes.append(conclusion)
        else:
            false_nodes.append(conclusion)
        self._native.add_clause(true_nodes, false_nodes, informant)

    @staticmethod
    def _truth_to_label(value: TruthValue) -> Label:
        if value is TruthValue.TRUE:
            return Label.TRUE
        if value is TruthValue.FALSE:
            return Label.FALSE
        raise DomainInvariantError("LTMS implications cannot use unknown polarity")

    def _ordered_node_keys(self) -> tuple[NodeKey, ...]:
        return tuple(sorted(self._nodes, key=NodeKey.encode))

    def _ordered_nodes(self) -> tuple[TruthNode, ...]:
        return tuple(self._nodes[key] for key in self._ordered_node_keys())

    def _ordered_assumptions(self) -> tuple[Assumption, ...]:
        return tuple(
            sorted(self._assumptions.values(), key=lambda assumption: assumption.assumption_id)
        )

    def _ordered_justifications(self) -> tuple[Justification, ...]:
        return tuple(sorted(self._justifications.values(), key=lambda rule: rule.justification_id))
