"""Worry registration, dependency indexing, and generic binding lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from symbox.application.attributes import AttributeEntry, AttributeState, set_attributes
from symbox.application.binding_ports import BindingLoader, LoadedBinding
from symbox.application.bindings import BindingState, bind_object, unbind_object
from symbox.application.mutations import BindingExecutionError
from symbox.application.objects import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ObjectState,
    create_object,
    delete_object,
)
from symbox.domain.models import DomainInvariantError, ObjectCategory, Worry
from symbox.domain.node_keys import NodeKey
from symbox.kernel.port import Assumption, TruthKernel, TruthNode, TruthValue


class WorryAlreadyExistsError(ObjectAlreadyExistsError):
    """Raised when a Worry name is already occupied in the object catalog."""


class WorryNotFoundError(ObjectNotFoundError):
    """Raised when a Worry operation targets an unknown monitor."""


class WorryConvergenceError(DomainInvariantError):
    """Raised when Worry tail evaluation repeats or exceeds its safety boundary."""

    def __init__(self, message: str, *, iterations: int, signature: str) -> None:
        super().__init__(message)
        self.iterations = iterations
        self.signature = signature


@dataclass(frozen=True, slots=True)
class WorryState:
    """Generic object bindings plus deterministic Worry dependency metadata."""

    objects: BindingState
    worries: tuple[Worry, ...] = ()
    kernel: TruthKernel | None = None

    def __post_init__(self) -> None:
        names = tuple(worry.name for worry in self.worries)
        if len(names) != len(set(names)):
            raise WorryAlreadyExistsError("worry names must be unique")
        if names != tuple(sorted(names)):
            raise DomainInvariantError("worries must use deterministic name order")

        catalog = {subject.name: subject for subject in self.objects.objects.objects}
        unknown = sorted(set(names) - set(catalog))
        if unknown:
            raise WorryNotFoundError(f"worries reference unknown objects: {unknown}")
        non_meta = sorted(
            name for name in names if catalog[name].category is not ObjectCategory.META
        )
        if non_meta:
            raise DomainInvariantError(f"worries must reference meta objects: {non_meta}")
        if self.kernel is None:
            object.__setattr__(self, "kernel", self.objects.objects.kernel)

    def worry_for(self, name: str) -> Worry | None:
        """Return one monitor without loading or executing its binding."""
        return next((worry for worry in self.worries if worry.name == name), None)

    def affected_by(self, dependencies: tuple[str, ...]) -> tuple[Worry, ...]:
        """Return monitors subscribed to any changed dependency in stable order."""
        changed = frozenset(dependencies)
        return tuple(
            worry
            for worry in self.worries
            if changed.intersection(worry.dependencies)
        )


@dataclass(frozen=True, slots=True)
class WorryMonitoringState:
    """Attributes and Worry metadata sharing one authoritative candidate kernel."""

    worries: WorryState
    attributes: tuple[AttributeEntry, ...] = ()
    kernel: TruthKernel | None = None

    def __post_init__(self) -> None:
        if self.kernel is None:
            object.__setattr__(self, "kernel", _kernel(self.worries))
        # Reuse AttributeState's ordering and referential-integrity invariants.
        AttributeState(self.worries.objects, self.attributes, self.kernel)


def create_worry(state: WorryState, name: str, dependencies: tuple[str, ...]) -> WorryState:
    """Create one meta object and register its initially unknown health node."""
    worry = Worry(name, dependencies)
    if any(subject.name == worry.name for subject in state.objects.objects.objects):
        raise WorryAlreadyExistsError(f"object already exists: {worry.name}")

    base_objects = ObjectState(state.objects.objects.objects, _kernel(state))
    object_state = create_object(base_objects, worry.name, ObjectCategory.META)
    candidate = object_state.kernel
    candidate.register_node(TruthNode(NodeKey.worry(worry.name)))
    report = candidate.propagate()
    if not report.consistent:
        raise DomainInvariantError(f"creating worry caused a conflict: {worry.name}")

    objects = BindingState(ObjectState(object_state.objects, candidate), state.objects.bindings)
    worries = tuple(sorted((*state.worries, worry), key=lambda item: item.name))
    return WorryState(objects, worries, candidate)


def delete_worry(state: WorryState, name: str) -> WorryState:
    """Remove a Worry, its generic binding, and all health-node supports atomically."""
    if state.worry_for(name) is None:
        raise WorryNotFoundError(f"unknown worry: {name}")

    bindings = tuple(entry for entry in state.objects.bindings if entry.object_name != name)
    base_objects = ObjectState(state.objects.objects.objects, _kernel(state))
    object_state = delete_object(base_objects, name)
    candidate = object_state.kernel
    candidate.retract_node(NodeKey.worry(name))
    report = candidate.propagate()
    if not report.consistent:
        raise DomainInvariantError(f"deleting worry caused a conflict: {name}")

    objects = BindingState(ObjectState(object_state.objects, candidate), bindings)
    worries = tuple(worry for worry in state.worries if worry.name != name)
    return WorryState(objects, worries, candidate)


def bind_worry(
    state: WorryState,
    loader: BindingLoader,
    project_root: Path,
    worry_name: str,
    source_path: str,
    qualified_name: str,
) -> tuple[WorryState, LoadedBinding]:
    """Bind a Worry through the same generic lifecycle used by every object."""
    _require_worry(state, worry_name)
    objects, loaded = bind_object(
        state.objects,
        loader,
        project_root,
        worry_name,
        source_path,
        qualified_name,
    )
    return WorryState(objects, state.worries, _kernel(state)), loaded


def unbind_worry(state: WorryState, worry_name: str) -> WorryState:
    """Remove a Worry binding and withdraw its health support."""
    _require_worry(state, worry_name)
    objects = unbind_object(state.objects, worry_name)
    candidate = _kernel(state).clone()
    _retract_health_support(candidate, worry_name)
    report = candidate.propagate()
    if not report.consistent:
        raise DomainInvariantError(f"unbinding worry caused a conflict: {worry_name}")
    synchronized = BindingState(ObjectState(objects.objects.objects, candidate), objects.bindings)
    return WorryState(synchronized, state.worries, candidate)


def set_monitored_attributes(
    state: WorryMonitoringState,
    subject: str,
    values: dict[str, Any],
    loaded_bindings: Mapping[str, LoadedBinding],
    *,
    max_iterations: int = 32,
) -> WorryMonitoringState:
    """Set attributes and immediately evaluate affected bound Worries atomically."""
    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or max_iterations <= 0
    ):
        raise DomainInvariantError("worry max_iterations must be a positive integer")
    kernel = _monitoring_kernel(state)
    object_state = ObjectState(state.worries.objects.objects.objects, kernel)
    bindings = BindingState(object_state, state.worries.objects.bindings)
    attributes = AttributeState(bindings, state.attributes, kernel)
    candidate_attributes = set_attributes(attributes, subject, values)
    changed = tuple(attribute_dependency(subject, key) for key in values)
    candidate = _evaluate_affected(
        WorryState(
            candidate_attributes.objects,
            state.worries.worries,
            candidate_attributes.kernel,
        ),
        candidate_attributes.attributes,
        changed,
        loaded_bindings,
        max_iterations,
    )
    return WorryMonitoringState(candidate, candidate_attributes.attributes, _kernel(candidate))


def attribute_dependency(subject: str, key: str) -> str:
    """Return the canonical dependency identity for one monitored attribute."""
    return NodeKey.adj(subject, key).encode()


def _evaluate_affected(
    state: WorryState,
    attributes: tuple[AttributeEntry, ...],
    changed: tuple[str, ...],
    loaded_bindings: Mapping[str, LoadedBinding],
    max_iterations: int,
) -> WorryState:
    candidate = _kernel(state).clone()
    pending = tuple(sorted(set(changed)))
    seen: set[str] = set()
    iterations = 0
    while pending:
        iterations += 1
        if iterations > max_iterations:
            signature = _state_signature(candidate, state.worries, pending)
            raise WorryConvergenceError(
                f"worry evaluation exceeded {max_iterations} iterations",
                iterations=iterations - 1,
                signature=signature,
            )
        snapshots = _dependency_snapshots(attributes, candidate, state.worries)
        for worry in state.affected_by(pending):
            _evaluate_worry(state, worry, snapshots, loaded_bindings, candidate)

        report = candidate.propagate()
        if not report.consistent:
            conflicts = ", ".join(conflict.node.encode() for conflict in report.conflicts)
            raise DomainInvariantError(f"worry propagation conflict: {conflicts}")
        pending = tuple(key.encode() for key in report.changed)
        if pending:
            signature = _state_signature(candidate, state.worries, pending)
            if signature in seen:
                raise WorryConvergenceError(
                    "worry evaluation repeated a state before reaching stability",
                    iterations=iterations,
                    signature=signature,
                )
            seen.add(signature)

    objects = BindingState(
        ObjectState(state.objects.objects.objects, candidate),
        state.objects.bindings,
    )
    return WorryState(objects, state.worries, candidate)


def _evaluate_worry(
    state: WorryState,
    worry: Worry,
    snapshots: Mapping[str, Any],
    loaded_bindings: Mapping[str, LoadedBinding],
    candidate: TruthKernel,
) -> None:
    entry = state.objects.binding_for(worry.name)
    if entry is None:
        return
    loaded = loaded_bindings.get(worry.name)
    if loaded is None or loaded.reference != entry.reference:
        raise BindingExecutionError(f"loaded binding unavailable for worry: {worry.name}")
    subject_state = {name: snapshots.get(name) for name in worry.dependencies}
    for dependency in worry.dependencies:
        key = NodeKey.parse(dependency).components[-1]
        subject_state.setdefault(key, snapshots.get(dependency))
    try:
        healthy = loaded.callable(subject_state)
    except Exception as error:
        raise BindingExecutionError(f"worry check raised for {worry.name}: {error}") from error
    if not isinstance(healthy, bool):
        raise BindingExecutionError(f"worry check must return bool: {worry.name}")
    _replace_health_support(candidate, worry.name, healthy)


def _dependency_snapshots(
    attributes: tuple[AttributeEntry, ...],
    kernel: TruthKernel,
    worries: tuple[Worry, ...],
) -> dict[str, Any]:
    snapshots = {
        attribute_dependency(entry.subject, entry.fact.adj.key): entry.fact.adj.value
        for entry in attributes
    }
    for dependency in {
        dependency
        for worry in worries
        for dependency in worry.dependencies
    }:
        snapshots.setdefault(dependency, _truth_snapshot(kernel, dependency))
    return snapshots


def _truth_snapshot(kernel: TruthKernel, dependency: str) -> str | None:
    try:
        return kernel.truth(NodeKey.parse(dependency)).value
    except DomainInvariantError:
        return None


def _state_signature(
    kernel: TruthKernel,
    worries: tuple[Worry, ...],
    pending: tuple[str, ...],
) -> str:
    truths = ",".join(
        f"{worry.name}={kernel.truth(NodeKey.worry(worry.name)).value}"
        for worry in worries
    )
    return f"truths[{truths}];pending[{','.join(sorted(pending))}]"


def _replace_health_support(kernel: TruthKernel, worry_name: str, healthy: bool) -> None:
    _retract_health_support(kernel, worry_name)
    kernel.assert_assumption(
        Assumption(
            _health_assumption_id(worry_name),
            NodeKey.worry(worry_name),
            TruthValue.TRUE if healthy else TruthValue.FALSE,
        )
    )


def _retract_health_support(kernel: TruthKernel, worry_name: str) -> None:
    identifier = _health_assumption_id(worry_name)
    explanation = kernel.explain(NodeKey.worry(worry_name))
    if any(support.support_id == identifier for support in explanation.supports):
        kernel.retract_assumption(identifier)


def _health_assumption_id(worry_name: str) -> str:
    return f"worry-health:{NodeKey.worry(worry_name).encode()}"


def _require_worry(state: WorryState, name: str) -> Worry:
    worry = state.worry_for(name)
    if worry is None:
        raise WorryNotFoundError(f"unknown worry: {name}")
    return worry


def _kernel(state: WorryState) -> TruthKernel:
    assert state.kernel is not None
    return state.kernel


def _monitoring_kernel(state: WorryMonitoringState) -> TruthKernel:
    assert state.kernel is not None
    return state.kernel
