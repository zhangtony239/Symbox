"""Core model invariant tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from symbox.domain.models import (
    SVK,
    Adj,
    BindingRef,
    CategoryConstraintError,
    DomainInvariantError,
    ObjectCategory,
    Subject,
    Tag,
    Verb,
    Worry,
)

DIGEST = "a" * 64


def test_domain_models_accept_valid_inputs() -> None:
    assert Subject(" robot ").name == "robot"
    assert Verb("moves").category is ObjectCategory.ABSTRACT
    assert Tag(" mobile ").name == "mobile"
    assert Worry("battery-safe", ("robot.battery",)).category is ObjectCategory.META
    binding = BindingRef("rules\\checks.py", "Checks.is_safe", DIGEST, is_verb=True)
    assert binding.source_path == "rules/checks.py"
    relation = SVK("robot", "moves", ("dock",), (("speed", 2),))
    assert relation.kwargs == (("speed", 2),)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Subject(" "),
        lambda: Verb("\x00bad"),
        lambda: Tag(""),
        lambda: Worry("health", ()),
        lambda: BindingRef("../outside.py", "check", DIGEST),
        lambda: BindingRef("rules.txt", "check", DIGEST),
        lambda: BindingRef("rules.py", "not-valid", DIGEST),
        lambda: BindingRef("rules.py", "check", "not-a-digest"),
        lambda: SVK("robot", "moves", kwargs=(("speed", 1), ("speed", 2))),
    ],
)
def test_invalid_domain_inputs_are_rejected(factory: object) -> None:
    with pytest.raises(DomainInvariantError):
        factory()  # type: ignore[operator]


def test_adj_requires_an_aware_timestamp_and_unique_tags() -> None:
    with pytest.raises(DomainInvariantError, match="timezone-aware"):
        Adj("temperature", 20, recorded_at=datetime(2026, 1, 1))
    with pytest.raises(DomainInvariantError, match="unique"):
        Adj("temperature", 20, implies_tags=("safe", "safe"))


def test_verb_accepts_declared_domain_and_range_categories() -> None:
    verb = Verb(
        "contains",
        domain=(ObjectCategory.PHYSICAL,),
        ranges=((ObjectCategory.PHYSICAL, ObjectCategory.ABSTRACT),),
    )

    verb.validate_categories(ObjectCategory.PHYSICAL, (ObjectCategory.ABSTRACT,))


@pytest.mark.parametrize(
    ("subject_category", "argument_categories", "message"),
    [
        (ObjectCategory.META, (ObjectCategory.PHYSICAL,), "subject requires"),
        (ObjectCategory.PHYSICAL, (), "requires 1 classified arguments"),
        (ObjectCategory.PHYSICAL, (ObjectCategory.META,), "argument 1 requires"),
    ],
)
def test_verb_rejects_categories_outside_declared_domain_and_ranges(
    subject_category: ObjectCategory,
    argument_categories: tuple[ObjectCategory, ...],
    message: str,
) -> None:
    verb = Verb(
        "contains",
        domain=(ObjectCategory.PHYSICAL,),
        ranges=((ObjectCategory.PHYSICAL,),),
    )

    with pytest.raises(CategoryConstraintError, match=message):
        verb.validate_categories(subject_category, argument_categories)


def test_verb_must_explicitly_allow_meta_objects() -> None:
    ordinary = Verb("monitors")
    meta_aware = Verb(
        "monitors-meta",
        domain=(ObjectCategory.PHYSICAL, ObjectCategory.META),
    )

    with pytest.raises(CategoryConstraintError):
        ordinary.validate_categories(ObjectCategory.META)
    meta_aware.validate_categories(ObjectCategory.META)
