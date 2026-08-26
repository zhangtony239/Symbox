"""SVK now token-structure tests."""

from __future__ import annotations

import pytest

from symbox.cli.now_parser import ParsedNow, parse_now_tokens
from symbox.domain.models import DomainInvariantError


def test_zero_post_arguments_produces_empty_variable_package() -> None:
    assert parse_now_tokens(("robot", "refreshes")) == ParsedNow("robot", "refreshes")


def test_multiple_positionals_preserve_order_and_json_types() -> None:
    parsed = parse_now_tokens(("robot", "moves", "dock", "2", "true"))

    assert parsed.args == ("dock", 2, True)
    assert parsed.kwargs == ()


def test_mixed_positional_and_named_arguments_are_lossless() -> None:
    parsed = parse_now_tokens(
        ("robot", "moves", "dock", "speed=2", "metadata={\"safe\":true}")
    )

    assert parsed.args == ("dock",)
    assert parsed.kwargs == (("speed", 2), ("metadata", {"safe": True}))


@pytest.mark.parametrize(
    "tokens",
    [
        (),
        ("robot",),
        ("robot", "moves", "=2"),
        ("robot", "moves", "speed=1", "speed=2"),
    ],
)
def test_structurally_invalid_now_tokens_are_rejected(tokens: tuple[str, ...]) -> None:
    with pytest.raises(DomainInvariantError):
        parse_now_tokens(tokens)
