"""Versioned canonical state document tests."""

from __future__ import annotations

import json

import pytest

from symbox.persistence.state_format import StateDocument, StateFormatError


def test_empty_state_has_all_versioned_sections() -> None:
    state = StateDocument()
    decoded = json.loads(state.to_bytes())

    assert decoded["schema_version"] == 1
    assert decoded["revision"] == 0
    assert decoded["objects"] == []
    assert decoded["truth_nodes"] == []
    assert state.to_bytes().endswith(b"\n")


def test_state_serialization_is_canonical_and_round_trips() -> None:
    state = StateDocument(
        revision=7,
        objects=(
            {"name": "机器人", "category": "physical"},
            {"category": "abstract", "name": "moves"},
        ),
        relations=({"key": "SVK:z"}, {"key": "SVK:a"}),
        truth_nodes=({"state": "true", "key": "Subject:机器人"},),
        justifications=({"conclusion": "Subject:机器人", "premises": []},),
    )

    encoded = state.to_bytes()
    restored = StateDocument.from_bytes(encoded)

    assert restored == state
    assert restored.to_bytes() == encoded
    assert restored.relations[0]["key"] == "SVK:a"


@pytest.mark.parametrize(
    "content",
    [
        b"not-json",
        b"[]",
        b'{"schema_version":1}',
        StateDocument().to_bytes().replace(b'"objects":[]', b'"objects":{}'),
        StateDocument().to_bytes().replace(b'"schema_version":1', b'"schema_version":2'),
        StateDocument().to_bytes().replace(b'"revision":0', b'"revision":-1'),
    ],
)
def test_malformed_or_unknown_state_is_rejected(content: bytes) -> None:
    with pytest.raises(StateFormatError):
        StateDocument.from_bytes(content)


def test_state_rejects_non_finite_or_non_json_values() -> None:
    with pytest.raises(StateFormatError):
        StateDocument(objects=({"value": float("nan")},))
    with pytest.raises(StateFormatError):
        StateDocument(objects=({"value": object()},))
