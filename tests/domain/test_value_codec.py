"""Canonical value and SVK identity tests."""

from __future__ import annotations

import json

import pytest

from symbox.domain.models import SVK, DomainInvariantError
from symbox.domain.svk_identity import SVKIdentityRegistry, identify_svk
from symbox.domain.value_codec import canonical_json_bytes, decode_value, encode_value


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        -10,
        1.25,
        "机器人",
        [1, "two", False],
        ("position", 2),
        {"z": 1, "a": [None]},
    ],
)
def test_canonical_value_round_trip(value: object) -> None:
    assert decode_value(encode_value(value)) == value


def test_canonical_encoding_is_order_independent_for_objects() -> None:
    first = canonical_json_bytes({"b": 2, "a": 1})
    second = canonical_json_bytes({"a": 1, "b": 2})

    assert first == second
    assert json.loads(first)["type"] == "object"


def test_type_tags_prevent_python_value_aliases() -> None:
    assert canonical_json_bytes(True) != canonical_json_bytes(1)
    assert canonical_json_bytes(1) != canonical_json_bytes(1.0)
    assert canonical_json_bytes([1]) != canonical_json_bytes((1,))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "not-string"}, object()])
def test_unsupported_values_are_rejected(value: object) -> None:
    with pytest.raises(DomainInvariantError):
        canonical_json_bytes(value)


def test_svk_keyword_order_and_effective_defaults_have_stable_identity() -> None:
    first = SVK("robot", "moves", ("dock",), (("speed", 2), ("safe", True)))
    reordered = SVK("robot", "moves", ("dock",), (("safe", True), ("speed", 2)))
    default_expanded = SVK("robot", "moves", ("dock",), (("safe", True), ("speed", 2)))

    assert identify_svk(first).key == identify_svk(reordered).key
    assert identify_svk(reordered).key == identify_svk(default_expanded).key


def test_svk_complete_argument_package_changes_identity() -> None:
    base = identify_svk(SVK("robot", "moves", ("dock",), (("speed", 2),))).key

    assert identify_svk(SVK("other", "moves", ("dock",), (("speed", 2),))).key != base
    assert identify_svk(SVK("robot", "stops", ("dock",), (("speed", 2),))).key != base
    assert identify_svk(SVK("robot", "moves", ("bay",), (("speed", 2),))).key != base
    assert identify_svk(SVK("robot", "moves", ("dock",), (("speed", 3),))).key != base


def test_svk_digest_collision_is_rejected() -> None:
    registry = SVKIdentityRegistry(lambda _: "0" * 64)
    registry.identify(SVK("robot", "moves", (1,)))

    with pytest.raises(DomainInvariantError, match="collision"):
        registry.identify(SVK("robot", "moves", (2,)))
