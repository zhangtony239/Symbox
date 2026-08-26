"""Candidate transaction atomicity and commit-count tests."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from symbox.application.transactions import TransactionCoordinator


@dataclass(frozen=True)
class Snapshot:
    revision: int
    values: tuple[str, ...] = ()


class FakeStore:
    def __init__(self, state: Snapshot) -> None:
        self.state = state
        self.save_calls = 0
        self.fail_save = False

    def load(self) -> Snapshot:
        return self.state

    def save(self, state: Snapshot) -> None:
        self.save_calls += 1
        if self.fail_save:
            raise OSError("injected persistence failure")
        self.state = state


def _mutate(state: Snapshot) -> Snapshot:
    return replace(state, revision=state.revision + 1, values=(*state.values, "candidate"))


def test_successful_transaction_runs_stages_then_commits_once() -> None:
    store = FakeStore(Snapshot(0))
    coordinator = TransactionCoordinator(store)
    stages: list[str] = []

    result = coordinator.execute(
        _mutate,
        validators=(lambda _: stages.append("validate"),),
        synchronize_kernel=lambda _: stages.append("kernel"),
        propagate=lambda _: stages.append("propagate"),
    )

    assert stages == ["validate", "kernel", "propagate"]
    assert result == Snapshot(1, ("candidate",))
    assert store.state == result
    assert coordinator.committed == result
    assert store.save_calls == 1


@pytest.mark.parametrize("failing_stage", ["mutation", "validate", "kernel", "propagate"])
def test_any_candidate_stage_failure_preserves_memory_and_disk(failing_stage: str) -> None:
    original = Snapshot(0, ("committed",))
    store = FakeStore(original)
    coordinator = TransactionCoordinator(store)

    def fail(_: Snapshot) -> None:
        raise RuntimeError(f"injected {failing_stage} failure")

    def mutation(state: Snapshot) -> Snapshot:
        if failing_stage == "mutation":
            fail(state)
        return _mutate(state)

    with pytest.raises(RuntimeError, match=failing_stage):
        coordinator.execute(
            mutation,
            validators=(fail,) if failing_stage == "validate" else (),
            synchronize_kernel=fail if failing_stage == "kernel" else None,
            propagate=fail if failing_stage == "propagate" else None,
        )

    assert store.state == original
    assert coordinator.committed == original
    assert store.save_calls == 0


def test_persistence_failure_preserves_committed_memory_and_disk() -> None:
    original = Snapshot(0)
    store = FakeStore(original)
    store.fail_save = True
    coordinator = TransactionCoordinator(store)

    with pytest.raises(OSError, match="persistence"):
        coordinator.execute(_mutate)

    assert store.state == original
    assert coordinator.committed == original
    assert store.save_calls == 1


def test_returning_committed_object_is_rejected_before_save() -> None:
    store = FakeStore(Snapshot(0))
    coordinator = TransactionCoordinator(store)

    with pytest.raises(ValueError, match="isolated candidate"):
        coordinator.execute(lambda _: store.state)

    assert store.save_calls == 0
