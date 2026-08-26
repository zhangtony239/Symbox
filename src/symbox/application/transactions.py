"""Single commit boundary for all state-changing application commands."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from typing import Protocol, TypeVar

Snapshot = TypeVar("Snapshot")


class StateStore(Protocol[Snapshot]):
    """Minimal persistence port required by the transaction coordinator."""

    def load(self) -> Snapshot:
        """Return the current committed snapshot."""
        ...

    def save(self, state: Snapshot) -> None:
        """Atomically replace the current committed snapshot."""
        ...


Mutation = Callable[[Snapshot], Snapshot]
CandidateStage = Callable[[Snapshot], None]


class TransactionCoordinator[Snapshot]:
    """Build, verify, propagate, and atomically publish a candidate snapshot."""

    def __init__(self, store: StateStore[Snapshot]) -> None:
        self._store = store
        self._committed: Snapshot | None = None

    @property
    def committed(self) -> Snapshot:
        """Expose the last successfully loaded or committed in-memory snapshot."""
        if self._committed is None:
            self._committed = self._store.load()
        return self._committed

    def execute(
        self,
        mutation: Mutation[Snapshot],
        *,
        validators: Iterable[CandidateStage[Snapshot]] = (),
        synchronize_kernel: CandidateStage[Snapshot] | None = None,
        propagate: CandidateStage[Snapshot] | None = None,
    ) -> Snapshot:
        """Execute all candidate stages and publish exactly once after success."""
        committed = self._store.load()
        self._committed = committed
        isolated = deepcopy(committed)
        candidate = mutation(isolated)
        if candidate is committed:
            raise ValueError("mutation must return an isolated candidate snapshot")
        for validate in validators:
            validate(candidate)
        if synchronize_kernel is not None:
            synchronize_kernel(candidate)
        if propagate is not None:
            propagate(candidate)
        self._store.save(candidate)
        self._committed = candidate
        return candidate
