"""Immutable core domain values for Symbox v0.6."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DomainInvariantError(ValueError):
    """Raised when an invalid value attempts to cross the domain boundary."""


class CategoryConstraintError(DomainInvariantError):
    """Raised when an object category violates a Verb domain or range."""


class ObjectCategory(StrEnum):
    """The three isolated object categories defined by the public model."""

    PHYSICAL = "physical"
    ABSTRACT = "abstract"
    META = "meta"


def _required_name(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainInvariantError(f"{field_name} must not be empty")
    if any(ord(character) < 32 for character in normalized):
        raise DomainInvariantError(f"{field_name} must not contain control characters")
    return normalized


@dataclass(frozen=True, slots=True)
class Subject:
    """A stable, named object that may occupy the subject position."""

    name: str
    category: ObjectCategory = ObjectCategory.PHYSICAL

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_name(self.name, "subject name"))


@dataclass(frozen=True, slots=True)
class Verb:
    """An explicitly marked relation predicate."""

    name: str
    category: ObjectCategory = ObjectCategory.ABSTRACT
    domain: tuple[ObjectCategory, ...] = (
        ObjectCategory.PHYSICAL,
        ObjectCategory.ABSTRACT,
    )
    ranges: tuple[tuple[ObjectCategory, ...], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_name(self.name, "verb name"))
        if not self.domain:
            raise DomainInvariantError("verb domain must contain at least one category")
        if any(not accepted for accepted in self.ranges):
            raise DomainInvariantError("each verb range position must accept at least one category")

    def validate_categories(
        self,
        subject_category: ObjectCategory,
        argument_categories: tuple[ObjectCategory, ...] = (),
    ) -> None:
        """Validate object-valued positions before invoking the bound check."""
        if subject_category not in self.domain:
            allowed = ", ".join(category.value for category in self.domain)
            raise CategoryConstraintError(
                f"verb {self.name!r} subject requires one of [{allowed}], "
                f"received {subject_category.value!r}"
            )
        if len(argument_categories) != len(self.ranges):
            raise CategoryConstraintError(
                f"verb {self.name!r} requires {len(self.ranges)} classified arguments, "
                f"received {len(argument_categories)}"
            )
        for position, (actual, accepted) in enumerate(
            zip(argument_categories, self.ranges, strict=True),
            start=1,
        ):
            if actual not in accepted:
                allowed = ", ".join(category.value for category in accepted)
                raise CategoryConstraintError(
                    f"verb {self.name!r} argument {position} requires one of [{allowed}], "
                    f"received {actual.value!r}"
                )


@dataclass(frozen=True, slots=True)
class Adj:
    """A named attribute value and the tags it declares as consequences."""

    key: str
    value: Any
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    implies_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _required_name(self.key, "adj key"))
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise DomainInvariantError("adj recorded_at must be timezone-aware")
        normalized_tags = tuple(
            _required_name(tag, "implied tag") for tag in self.implies_tags
        )
        if len(normalized_tags) != len(set(normalized_tags)):
            raise DomainInvariantError("adj implied tags must be unique")
        object.__setattr__(self, "implies_tags", normalized_tags)


@dataclass(frozen=True, slots=True)
class Tag:
    """A named marker whose provenance is tracked separately."""

    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_name(self.name, "tag name"))


@dataclass(frozen=True, slots=True)
class Worry:
    """A meta object that monitors named dependencies."""

    name: str
    dependencies: tuple[str, ...]
    category: ObjectCategory = field(default=ObjectCategory.META, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_name(self.name, "worry name"))
        dependencies = tuple(
            _required_name(dependency, "worry dependency") for dependency in self.dependencies
        )
        if not dependencies:
            raise DomainInvariantError("worry must monitor at least one dependency")
        if len(dependencies) != len(set(dependencies)):
            raise DomainInvariantError("worry dependencies must be unique")
        object.__setattr__(self, "dependencies", dependencies)


@dataclass(frozen=True, slots=True)
class BindingRef:
    """A persistent reference to trusted project-local Python source."""

    source_path: str
    qualified_name: str
    source_digest: str
    is_verb: bool = False

    def __post_init__(self) -> None:
        source_path = self.source_path.replace("\\", "/")
        path = PurePosixPath(source_path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise DomainInvariantError("binding source_path must be project-relative")
        if path.suffix != ".py":
            raise DomainInvariantError("binding source_path must identify a Python file")
        object.__setattr__(self, "source_path", path.as_posix())

        qualified_name = _required_name(self.qualified_name, "binding qualified_name")
        if not all(part.isidentifier() for part in qualified_name.split(".")):
            raise DomainInvariantError("binding qualified_name must be a dotted Python name")
        object.__setattr__(self, "qualified_name", qualified_name)

        if not _SHA256_PATTERN.fullmatch(self.source_digest):
            raise DomainInvariantError("binding source_digest must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class SVK:
    """A subject/verb relation with variable positional and named arguments."""

    subject: str
    verb: str
    args: tuple[Any, ...] = ()
    kwargs: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", _required_name(self.subject, "SVK subject"))
        object.__setattr__(self, "verb", _required_name(self.verb, "SVK verb"))
        names = tuple(_required_name(name, "SVK keyword") for name, _ in self.kwargs)
        if len(names) != len(set(names)):
            raise DomainInvariantError("SVK keyword arguments must be unique")
        object.__setattr__(
            self,
            "kwargs",
            tuple((name, value) for name, (_, value) in zip(names, self.kwargs, strict=True)),
        )
