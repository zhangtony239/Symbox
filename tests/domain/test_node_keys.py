"""Canonical NodeKey codec tests."""

from __future__ import annotations

import pytest

from symbox.domain.models import DomainInvariantError
from symbox.domain.node_keys import NodeKey, NodeNamespace


@pytest.mark.parametrize(
    "node_key",
    [
        NodeKey.subject("robot"),
        NodeKey.subject("robot:arm%1"),
        NodeKey.adj("机器人", "温度 °C"),
        NodeKey.svk("S:1", "V/2", "a" * 64),
        NodeKey.worry("battery-safe"),
        NodeKey.tag("robot", "ready:now"),
    ],
)
def test_node_key_round_trip(node_key: NodeKey) -> None:
    assert NodeKey.parse(node_key.encode()) == node_key


def test_user_colons_cannot_create_namespace_collisions() -> None:
    escaped_subject = NodeKey.subject("robot:arm").encode()
    structured_adj = NodeKey.adj("robot", "arm").encode()

    assert escaped_subject == "Subject:robot%3Aarm"
    assert escaped_subject != structured_adj


def test_namespace_and_component_arity_are_preserved() -> None:
    key = NodeKey.adj("robot", "battery")

    assert key.namespace is NodeNamespace.ADJ
    assert key.components == ("robot", "battery")
    assert key.encode() == "Adj:robot:battery"


@pytest.mark.parametrize(
    "encoded",
    [
        "Unknown:robot",
        "Subject:",
        "Subject:robot:extra",
        "Adj:robot",
        "Subject:robot%3aarm",
        "Subject:%FF",
    ],
)
def test_parser_rejects_unknown_malformed_or_noncanonical_keys(encoded: str) -> None:
    with pytest.raises(DomainInvariantError):
        NodeKey.parse(encoded)
