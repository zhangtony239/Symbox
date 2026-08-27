"""Canonical, type-preserving JSON value encoding."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from symbox.domain.models import DomainInvariantError

CanonicalValue = dict[str, Any]


def encode_value(value: Any) -> CanonicalValue:
    """Encode supported values with explicit type tags and deterministic ordering."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainInvariantError("canonical JSON does not support non-finite floats")
        return {"type": "float", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [encode_value(item) for item in value]}
    if isinstance(value, list):
        return {"type": "list", "items": [encode_value(item) for item in value]}
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DomainInvariantError("canonical JSON object keys must be strings")
        return {
            "type": "object",
            "items": [{"key": key, "value": encode_value(value[key])} for key in sorted(value)],
        }
    raise DomainInvariantError(f"unsupported canonical JSON value: {type(value).__name__}")


def decode_value(encoded: Mapping[str, Any]) -> Any:
    """Decode a value produced by :func:`encode_value`."""
    value_type = encoded.get("type")
    if value_type == "null" and set(encoded) == {"type"}:
        return None
    if value_type == "bool" and isinstance(encoded.get("value"), bool):
        return encoded["value"]
    if value_type == "int" and isinstance(encoded.get("value"), str):
        try:
            return int(encoded["value"])
        except ValueError as error:
            raise DomainInvariantError("invalid canonical integer") from error
    if value_type == "float" and isinstance(encoded.get("value"), str):
        try:
            value = float.fromhex(encoded["value"])
        except ValueError as error:
            raise DomainInvariantError("invalid canonical float") from error
        if not math.isfinite(value):
            raise DomainInvariantError("canonical JSON does not support non-finite floats")
        return value
    if value_type == "string" and isinstance(encoded.get("value"), str):
        return encoded["value"]
    if value_type in {"list", "tuple"}:
        items = encoded.get("items")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            raise DomainInvariantError("invalid canonical sequence")
        decoded = [decode_value(_require_mapping(item)) for item in items]
        return tuple(decoded) if value_type == "tuple" else decoded
    if value_type == "object":
        items = encoded.get("items")
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
            raise DomainInvariantError("invalid canonical object")
        result: dict[str, Any] = {}
        for item in items:
            entry = _require_mapping(item)
            key = entry.get("key")
            if not isinstance(key, str) or key in result:
                raise DomainInvariantError("invalid or duplicate canonical object key")
            result[key] = decode_value(_require_mapping(entry.get("value")))
        if list(result) != sorted(result):
            raise DomainInvariantError("canonical object keys must be sorted")
        return result
    raise DomainInvariantError("invalid canonical JSON value envelope")


def _require_mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainInvariantError("canonical JSON envelope must be an object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON bytes for hashing and persistence."""
    return json.dumps(
        encode_value(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
