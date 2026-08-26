"""Versioned, canonical JSON format for ``.sbox/state.json``."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

CURRENT_SCHEMA_VERSION = 1
_COLLECTION_NAMES = (
    "objects",
    "adj_facts",
    "tag_facts",
    "bindings",
    "relations",
    "truth_nodes",
    "justifications",
)


class StateFormatError(ValueError):
    """Raised when persisted state is malformed or unsupported."""


def _canonical_record(record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        serialized = json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise StateFormatError("state records must contain finite JSON values") from error
    decoded = json.loads(serialized)
    if not isinstance(decoded, dict):  # pragma: no cover - guaranteed by Mapping input
        raise StateFormatError("state record must be a JSON object")
    return decoded


def _canonical_collection(records: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    canonical = [_canonical_record(record) for record in records]
    canonical.sort(
        key=lambda record: json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return tuple(canonical)


@dataclass(frozen=True, slots=True)
class StateDocument:
    """A complete committed domain and truth snapshot."""

    revision: int = 0
    objects: tuple[dict[str, Any], ...] = ()
    adj_facts: tuple[dict[str, Any], ...] = ()
    tag_facts: tuple[dict[str, Any], ...] = ()
    bindings: tuple[dict[str, Any], ...] = ()
    relations: tuple[dict[str, Any], ...] = ()
    truth_nodes: tuple[dict[str, Any], ...] = ()
    justifications: tuple[dict[str, Any], ...] = ()
    schema_version: int = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise StateFormatError(f"unsupported state schema version: {self.schema_version}")
        if isinstance(self.revision, bool) or self.revision < 0:
            raise StateFormatError("state revision must be a non-negative integer")
        for name in _COLLECTION_NAMES:
            records = getattr(self, name)
            object.__setattr__(self, name, _canonical_collection(records))

    def to_mapping(self) -> dict[str, Any]:
        """Return a detached JSON-ready state mapping."""
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            **{name: deepcopy(list(getattr(self, name))) for name in _COLLECTION_NAMES},
        }

    def to_bytes(self) -> bytes:
        """Serialize to deterministic UTF-8 JSON with one trailing newline."""
        text = json.dumps(
            self.to_mapping(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"{text}\n".encode()

    @classmethod
    def from_bytes(cls, content: bytes) -> StateDocument:
        """Parse and structurally validate a complete state document."""
        try:
            decoded = json.loads(content.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise StateFormatError("state file is not valid UTF-8 JSON") from error
        if not isinstance(decoded, dict):
            raise StateFormatError("state document must be a JSON object")
        expected = {"schema_version", "revision", *_COLLECTION_NAMES}
        if set(decoded) != expected:
            missing = sorted(expected - set(decoded))
            unknown = sorted(set(decoded) - expected)
            raise StateFormatError(f"invalid state fields; missing={missing}, unknown={unknown}")
        version = decoded["schema_version"]
        revision = decoded["revision"]
        if not isinstance(version, int) or isinstance(version, bool):
            raise StateFormatError("schema_version must be an integer")
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise StateFormatError("revision must be an integer")
        collections: dict[str, tuple[dict[str, Any], ...]] = {}
        for name in _COLLECTION_NAMES:
            value = decoded[name]
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise StateFormatError(f"{name} must be an array of objects")
            collections[name] = tuple(value)
        return cls(
            schema_version=version,
            revision=revision,
            **collections,
        )
