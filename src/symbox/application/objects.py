"""Object lifecycle use cases over an isolated candidate TruthKernel."""

from __future__ import annotations

from dataclasses import dataclass

from symbox.domain.models import DomainInvariantError, ObjectCategory, Subject
from symbox.domain.node_keys import NodeKey
from symbox.kernel.port import Assumption, TruthKernel, TruthNode


class ObjectAlreadyExistsError(DomainInvariantError):
    """Raised when a project object name is already occupied."""


class ObjectNotFoundError(DomainInvariantError):
    """Raised when an object lifecycle command targets an unknown name."""


class ObjectPropagationError(DomainInvariantError):
    """Raised when a lifecycle candidate reaches a truth conflict."""


@dataclass(frozen=True, slots=True)
class ObjectState:
    """A deterministic object catalog and its central truth kernel."""

    objects: tuple[Subject, ...]
    kernel: TruthKernel

    def __post_init__(self) -> None:
        names = tuple(subject.name for subject in self.objects)
        if len(names) != len(set(names)):
            raise ObjectAlreadyExistsError("object names must be unique")
        if names != tuple(sorted(names)):
            raise DomainInvariantError("object catalog must use deterministic name order")


def create_object(
    state: ObjectState,
    name: str,
    category: ObjectCategory = ObjectCategory.PHYSICAL,
) -> ObjectState:
    """Create one named object and its explicit existence support."""
    subject = Subject(name, category)
    if any(existing.name == subject.name for existing in state.objects):
        raise ObjectAlreadyExistsError(f"object already exists: {subject.name}")
    candidate = state.kernel.clone()
    key = NodeKey.subject(subject.name)
    candidate.register_node(TruthNode(key))
    candidate.assert_assumption(Assumption(_existence_assumption_id(subject.name), key))
    report = candidate.propagate()
    if not report.consistent:
        raise ObjectPropagationError(f"creating object caused a conflict: {subject.name}")
    objects = tuple(sorted((*state.objects, subject), key=lambda item: item.name))
    return ObjectState(objects, candidate)


def delete_object(state: ObjectState, name: str) -> ObjectState:
    """Delete one object and propagate withdrawal through every referencing fact."""
    matches = tuple(subject for subject in state.objects if subject.name == name)
    if not matches:
        raise ObjectNotFoundError(f"unknown object: {name}")
    candidate = state.kernel.clone()
    candidate.retract_node(NodeKey.subject(name))
    report = candidate.propagate()
    if not report.consistent:
        raise ObjectPropagationError(f"deleting object caused a conflict: {name}")
    objects = tuple(subject for subject in state.objects if subject.name != name)
    return ObjectState(objects, candidate)


def _existence_assumption_id(name: str) -> str:
    return f"object-exists:{NodeKey.subject(name).encode()}"
