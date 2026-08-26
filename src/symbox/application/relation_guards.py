"""Pre-invocation object and Verb guards shared by relation use cases."""

from __future__ import annotations

from symbox.application.bindings import BindingState
from symbox.application.objects import ObjectNotFoundError
from symbox.domain.models import CategoryConstraintError, ObjectCategory, Verb


class NotAVerbError(ValueError):
    """Raised when an unmarked object is used in the ``now`` Verb position."""


def validate_relation_objects(
    state: BindingState,
    subject_name: str,
    verb_name: str,
    argument_names: tuple[str, ...] = (),
) -> Verb:
    """Resolve object categories and reject invalid Verb positions before invocation."""
    objects = {subject.name: subject for subject in state.objects.objects}
    missing = sorted({subject_name, verb_name, *argument_names} - set(objects))
    if missing:
        raise ObjectNotFoundError(f"unknown relation objects: {missing}")
    if not state.is_verb(verb_name):
        raise NotAVerbError(f"object is not marked as a Verb: {verb_name}")
    verb_subject = objects[verb_name]
    if verb_subject.category is ObjectCategory.META:
        raise CategoryConstraintError("a meta object cannot serve as a relation Verb")
    verb = Verb(verb_name, category=verb_subject.category)
    verb.validate_categories(
        objects[subject_name].category,
        tuple(objects[name].category for name in argument_names),
    )
    return verb
