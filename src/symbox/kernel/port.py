"""Stable truth-maintenance port independent of the current LTMS library."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from symbox.domain.models import DomainInvariantError, _required_name
from symbox.domain.node_keys import NodeKey


class TruthValue(StrEnum):
    """The three observable truth states held by the central kernel."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TruthNode:
    """A registered symbolic fact node."""

    key: NodeKey


@dataclass(frozen=True, slots=True)
class Premise:
    """A node and the polarity required for a justification to fire."""

    node: NodeKey
    expected: TruthValue = TruthValue.TRUE

    def __post_init__(self) -> None:
        if self.expected is TruthValue.UNKNOWN:
            raise DomainInvariantError("a justification premise cannot require unknown")


@dataclass(frozen=True, slots=True)
class Assumption:
    """An independently retractable primitive support."""

    assumption_id: str
    node: NodeKey
    value: TruthValue = TruthValue.TRUE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assumption_id",
            _required_name(self.assumption_id, "assumption id"),
        )
        if self.value is TruthValue.UNKNOWN:
            raise DomainInvariantError("an assumption cannot assert unknown")


@dataclass(frozen=True, slots=True)
class Justification:
    """A Horn-style support from zero or more premises to one polarized conclusion."""

    justification_id: str
    conclusion: NodeKey
    premises: tuple[Premise, ...]
    conclusion_value: TruthValue = TruthValue.TRUE

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "justification_id",
            _required_name(self.justification_id, "justification id"),
        )
        if self.conclusion_value is TruthValue.UNKNOWN:
            raise DomainInvariantError("a justification cannot conclude unknown")
        if len(self.premises) != len(set(self.premises)):
            raise DomainInvariantError("justification premises must be unique")


@dataclass(frozen=True, slots=True)
class SupportRef:
    """One direct assumption or justification supporting an explained value."""

    support_id: str
    kind: str
    premises: tuple[NodeKey, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "support_id", _required_name(self.support_id, "support id"))
        if self.kind not in {"assumption", "justification"}:
            raise DomainInvariantError("support kind must be assumption or justification")


@dataclass(frozen=True, slots=True)
class Explanation:
    """The current value and direct traversable supports for one node."""

    node: NodeKey
    value: TruthValue
    supports: tuple[SupportRef, ...] = ()


@dataclass(frozen=True, slots=True)
class PropagationConflict:
    """A node for which both true and false are propagation-reachable."""

    node: NodeKey
    true_supports: tuple[SupportRef, ...]
    false_supports: tuple[SupportRef, ...]


@dataclass(frozen=True, slots=True)
class PropagationReport:
    """The deterministic result of propagating a candidate kernel to stability."""

    changed: tuple[NodeKey, ...] = ()
    conflicts: tuple[PropagationConflict, ...] = ()

    @property
    def consistent(self) -> bool:
        return not self.conflicts


@runtime_checkable
class TruthKernel(Protocol):
    """Replaceable truth-maintenance boundary used by application services."""

    def clone(self) -> TruthKernel:
        """Return an isolated candidate kernel."""
        ...

    def register_node(self, node: TruthNode) -> None:
        """Idempotently register a symbolic fact node."""
        ...

    def retract_node(self, key: NodeKey) -> None:
        """Remove a node and every support that references it."""
        ...

    def assert_assumption(self, assumption: Assumption) -> None:
        """Add or idempotently retain primitive support."""
        ...

    def retract_assumption(self, assumption_id: str) -> None:
        """Remove primitive support by stable identifier."""
        ...

    def add_justification(self, justification: Justification) -> None:
        """Add or idempotently retain a propagation rule."""
        ...

    def retract_justification(self, justification_id: str) -> None:
        """Remove a propagation rule by stable identifier."""
        ...

    def truth(self, key: NodeKey) -> TruthValue:
        """Read the last propagated three-valued state."""
        ...

    def propagate(self) -> PropagationReport:
        """Reach a stable state and report every reachable conflict."""
        ...

    def explain(self, key: NodeKey) -> Explanation:
        """Return direct supports that callers can recursively traverse."""
        ...
