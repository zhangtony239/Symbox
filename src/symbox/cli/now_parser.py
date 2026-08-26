"""Token parser for the public variable-arity ``sbox now`` command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from symbox.domain.models import DomainInvariantError, _required_name


@dataclass(frozen=True, slots=True)
class ParsedNow:
    """Lossless structural parse before Python signature binding."""

    subject: str
    verb: str
    args: tuple[Any, ...] = ()
    kwargs: tuple[tuple[str, Any], ...] = ()


def parse_now_tokens(tokens: tuple[str, ...]) -> ParsedNow:
    """Split required S/V slots from ordered positional and named arguments."""
    if len(tokens) < 2:
        raise DomainInvariantError("now requires a Subject and Verb")
    subject = _required_name(tokens[0], "now subject")
    verb = _required_name(tokens[1], "now verb")
    args: list[Any] = []
    kwargs: list[tuple[str, Any]] = []
    keyword_names: set[str] = set()
    for token in tokens[2:]:
        if "=" not in token:
            args.append(_parse_token_value(token))
            continue
        name, raw_value = token.split("=", 1)
        name = _required_name(name, "now keyword")
        if name in keyword_names:
            raise DomainInvariantError(f"duplicate now keyword: {name}")
        keyword_names.add(name)
        kwargs.append((name, _parse_token_value(raw_value)))
    return ParsedNow(subject, verb, tuple(args), tuple(kwargs))


def _parse_token_value(token: str) -> Any:
    try:
        return json.loads(token)
    except json.JSONDecodeError:
        return token
