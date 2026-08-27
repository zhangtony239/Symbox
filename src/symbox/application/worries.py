"""Worry registration, dependency indexing, and generic binding lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from symbox.application.binding_ports import BindingLoader, LoadedBinding
from symbox.application.bindings import BindingState, bind_object, unbind_object
from symbox.application.objects import (
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    ObjectState,
    create_object,
    delete_object,
)
from symbox.domain.models import DomainInvariantError, ObjectCategory, Worry
from symbox.domain.node_keys import NodeKey
from symbox.kernel.port import TruthKernel, TruthNode


class WorryAlreadyExistsError(ObjectAlreadyExistsError):
    """Raised when a Worry name is already occupied in the object catalog."""


class WorryNotFoundError(ObjectNotFoundError):
    """Raised when a Worry operation targets an unknown monitor."""


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
    """Remove a Worry binding while retaining its registered dependencies."""
    _require_worry(state, worry_name)
    objects = unbind_object(state.objects, worry_name)
    return WorryState(objects, state.worries, _kernel(state))


def _require_worry(state: WorryState, name: str) -> Worry:
    worry = state.worry_for(name)
    if worry is None:
        raise WorryNotFoundError(f"unknown worry: {name}")
    return worry


def _kernel(state: WorryState) -> TruthKernel:
    assert state.kernel is not None
    return state.kernel
