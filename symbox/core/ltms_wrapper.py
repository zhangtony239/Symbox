from typing import Any, Dict, List, Optional, Tuple
import ltms


class ContradictionError(Exception):
    """Raised when LTMS encounters an unresolvable contradiction."""
    pass


class LTMSWrapper:
    """Wrapper managing LTMS truth maintenance, nodes, clauses, and belief revision."""

    def __init__(self, title: str = "symbox_ltms"):
        self.tms = ltms.LTMS(title=title)
        self.nodes: Dict[str, ltms.TmsNode] = {}
        self.assertions: List[Tuple[str, str, str]] = []

    def get_or_create_node(self, key: str, is_assumption: bool = True) -> ltms.TmsNode:
        if key not in self.nodes:
            self.nodes[key] = self.tms.create_node(datum=key, assumption=is_assumption)
        return self.nodes[key]

    def set_node_truth(self, key: str, is_true: bool, force: bool = False) -> None:
        node = self.get_or_create_node(key, is_assumption=True)
        label = ltms.Label.TRUE if is_true else ltms.Label.FALSE

        current = self.tms.label_of(node)
        if current == label:
            return

        if current != ltms.Label.UNKNOWN:
            if force:
                try:
                    for supp in self.tms.assumptions_of_node(node):
                        self.tms.retract_assumption(supp)
                except Exception:
                    pass
                try:
                    self.tms.retract_assumption(node)
                except Exception:
                    pass
            else:
                # Label mismatch
                raise ContradictionError(
                    f"Contradiction: Node '{key}' is already {current.name}, cannot set to {label.name}"
                )

        try:
            self.tms.enable_assumption(node, label)
        except (ltms.LTMSContradiction, ValueError) as e:
            if force:
                try:
                    self.tms.retract_assumption(node)
                except Exception:
                    pass
                self.tms.enable_assumption(node, label)
            else:
                raise ContradictionError(f"LTMS Contradiction on '{key}': {e}")

    def retract_node(self, key: str) -> None:
        if key in self.nodes:
            node = self.nodes[key]
            try:
                self.tms.retract_assumption(node)
            except Exception:
                pass

    def add_veto_clause(self, adj_key: str, svo_key: str) -> None:
        """Add clause: NOT (adj_key AND svo_key) -> (OR (NOT adj_key) (NOT svo_key))."""
        adj_node = self.get_or_create_node(adj_key, is_assumption=True)
        svo_node = self.get_or_create_node(svo_key, is_assumption=True)

        # In LTMS add_clause(true_nodes, false_nodes) represents (OR true_nodes... (NOT false_nodes)...)
        # So for (NOT adj_key OR NOT svo_key), true_nodes=[], false_nodes=[adj_node, svo_node]
        try:
            self.tms.add_clause(true_nodes=[], false_nodes=[adj_node, svo_node])
        except ltms.LTMSContradiction as e:
            raise ContradictionError(f"LTMS Contradiction adding veto rule ({adj_key} vetoes {svo_key}): {e}")

    def add_requires_clause(self, condition_key: str, svo_key: str) -> None:
        """Add clause: svo_key requires condition_key -> (OR condition_key (NOT svo_key)).

        Used for the v0.4 Worry polarity (spec §3.1): an SVO assertion requires
        the Worry health node to be TRUE (healthy). If the node is FALSE
        (contradiction), asserting the SVO raises a contradiction.
        """
        cond_node = self.get_or_create_node(condition_key, is_assumption=True)
        svo_node = self.get_or_create_node(svo_key, is_assumption=True)

        # (OR condition_key (NOT svo_key)): true_nodes=[cond_node], false_nodes=[svo_node]
        try:
            self.tms.add_clause(true_nodes=[cond_node], false_nodes=[svo_node])
        except ltms.LTMSContradiction as e:
            raise ContradictionError(
                f"LTMS Contradiction adding requires rule ({svo_key} requires {condition_key}): {e}"
            )

    def assert_svo(self, svo_key: str, if_force: bool = False) -> None:
        """Assert an SVO relation node as True."""
        svo_node = self.get_or_create_node(svo_key, is_assumption=True)
        try:
            self.set_node_truth(svo_key, is_true=True, force=if_force)
        except ContradictionError as e:
            if if_force:
                # Force assertion by clearing conflicting assumptions
                self.retract_node(svo_key)
                self.set_node_truth(svo_key, is_true=True, force=True)
            else:
                raise e

    def get_node_label(self, key: str) -> str:
        if key in self.nodes:
            lbl = self.tms.label_of(self.nodes[key])
            return lbl.name
        return "UNKNOWN"
