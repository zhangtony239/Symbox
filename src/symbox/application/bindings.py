"""Generic bind/unbind lifecycle and persisted-source revalidation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from symbox.application.binding_ports import BindingLoader, LoadedBinding
from symbox.application.objects import ObjectNotFoundError, ObjectState
from symbox.domain.models import BindingRef, DomainInvariantError


class BindingNotFoundError(DomainInvariantError):
    """Raised when unbind targets an object without a binding."""


class BindingSourceChangedError(DomainInvariantError):
    """Raised when persisted source metadata no longer matches project code."""


@dataclass(frozen=True, slots=True)
class BindingEntry:
    """One object's persistent callable reference."""

    object_name: str
    reference: BindingRef


@dataclass(frozen=True, slots=True)
class BindingState:
    """Object state plus a deterministic set of generic callable bindings."""

    objects: ObjectState
    bindings: tuple[BindingEntry, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(entry.object_name for entry in self.bindings)
        if len(names) != len(set(names)):
            raise DomainInvariantError("each object may have at most one binding")
        if names != tuple(sorted(names)):
            raise DomainInvariantError("bindings must use deterministic object-name order")
        known_objects = {subject.name for subject in self.objects.objects}
        unknown = sorted(set(names) - known_objects)
        if unknown:
            raise ObjectNotFoundError(f"bindings reference unknown objects: {unknown}")

    def binding_for(self, object_name: str) -> BindingEntry | None:
        """Return one binding without executing its callable."""
        return next(
            (entry for entry in self.bindings if entry.object_name == object_name),
            None,
        )

    def is_verb(self, object_name: str) -> bool:
        """Return the explicit persisted Verb marker."""
        entry = self.binding_for(object_name)
        return entry is not None and entry.reference.is_verb


def bind_object(
    state: BindingState,
    loader: BindingLoader,
    project_root: Path,
    object_name: str,
    source_path: str,
    qualified_name: str,
    *,
    is_verb: bool = False,
) -> tuple[BindingState, LoadedBinding]:
    """Validate first, then atomically add or replace one object's binding."""
    if not any(subject.name == object_name for subject in state.objects.objects):
        raise ObjectNotFoundError(f"unknown object: {object_name}")
    loaded = loader.load(
        project_root,
        source_path,
        qualified_name,
        is_verb=is_verb,
    )
    entries = [entry for entry in state.bindings if entry.object_name != object_name]
    entries.append(BindingEntry(object_name, loaded.reference))
    ordered_entries = tuple(sorted(entries, key=lambda entry: entry.object_name))
    candidate = BindingState(state.objects, ordered_entries)
    return candidate, loaded


def unbind_object(state: BindingState, object_name: str) -> BindingState:
    """Remove one generic binding and its Verb marker if present."""
    if state.binding_for(object_name) is None:
        raise BindingNotFoundError(f"object has no binding: {object_name}")
    entries = tuple(entry for entry in state.bindings if entry.object_name != object_name)
    return BindingState(state.objects, entries)


def revalidate_bindings(
    state: BindingState,
    loader: BindingLoader,
    project_root: Path,
) -> tuple[LoadedBinding, ...]:
    """Reload all persisted references and reject source or signature drift."""
    loaded_bindings: list[LoadedBinding] = []
    for entry in state.bindings:
        reference = entry.reference
        loaded = loader.load(
            project_root,
            reference.source_path,
            reference.qualified_name,
            is_verb=reference.is_verb,
        )
        if loaded.reference.source_digest != reference.source_digest:
            raise BindingSourceChangedError(
                f"binding source changed for object {entry.object_name}: {reference.source_path}"
            )
        loaded_bindings.append(loaded)
    return tuple(loaded_bindings)
