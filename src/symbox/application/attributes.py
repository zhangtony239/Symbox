"""Atomic attribute parsing, set/unset, provenance, and truth synchronization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from symbox.application.bindings import BindingState
from symbox.application.objects import ObjectNotFoundError
from symbox.domain.models import Adj, DomainInvariantError
from symbox.domain.node_keys import NodeKey
from symbox.domain.provenance import AdjFact, FactSource, SourceKind, SourceSet
from symbox.domain.value_codec import canonical_json_bytes
from symbox.kernel.port import Assumption, TruthKernel, TruthNode


class AttributeNotFoundError(DomainInvariantError):
    """Raised when unset targets a missing explicit attribute source."""


class AttributePropagationError(DomainInvariantError):
    """Raised when an attribute candidate creates a reachable conflict."""


@dataclass(frozen=True, slots=True)
class AttributeEntry:
    """One subject's effective Adj fact."""

    subject: str
    fact: AdjFact


@dataclass(frozen=True, slots=True)
class AttributeState:
    """Deterministically ordered attributes plus the shared truth kernel."""

    objects: BindingState
    attributes: tuple[AttributeEntry, ...] = ()
    kernel: TruthKernel | None = None

    def __post_init__(self) -> None:
        identities = tuple((entry.subject, entry.fact.adj.key) for entry in self.attributes)
        if len(identities) != len(set(identities)):
            raise DomainInvariantError("attribute identities must be unique")
        if identities != tuple(sorted(identities)):
            raise DomainInvariantError("attributes must use deterministic subject/key order")
        known = {subject.name for subject in self.objects.objects.objects}
        unknown = sorted({entry.subject for entry in self.attributes} - known)
        if unknown:
            raise ObjectNotFoundError(f"attributes reference unknown objects: {unknown}")
        if self.kernel is None:
            object.__setattr__(self, "kernel", self.objects.objects.kernel)


def parse_assignments(tokens: tuple[str, ...]) -> dict[str, Any]:
    """Parse unique ``key=JSON`` tokens without accepting ambiguous duplicates."""
    parsed: dict[str, Any] = {}
    for token in tokens:
        if "=" not in token:
            raise DomainInvariantError(f"attribute assignment must contain '=': {token}")
        key, raw_value = token.split("=", 1)
        key = key.strip()
        if not key:
            raise DomainInvariantError("attribute key must not be empty")
        if key in parsed:
            raise DomainInvariantError(f"duplicate attribute key: {key}")
        try:
            parsed[key] = json.loads(raw_value)
        except json.JSONDecodeError as error:
            raise DomainInvariantError(f"attribute value must be valid JSON: {key}") from error
    if not parsed:
        raise DomainInvariantError("at least one attribute assignment is required")
    return parsed


def set_attributes(
    state: AttributeState,
    subject: str,
    values: dict[str, Any],
) -> AttributeState:
    """Validate an entire batch, then update all explicit facts and propagate once."""
    _require_subject(state, subject)
    if not values:
        raise DomainInvariantError("at least one attribute value is required")
    # Validate every key/value before cloning or changing any candidate structure.
    new_facts = {
        Adj(key, value).key: Adj(key, value)
        for key, value in values.items()
        if canonical_json_bytes(value)
    }
    candidate = _kernel(state).clone()
    entries = {(entry.subject, entry.fact.adj.key): entry for entry in state.attributes}
    for key, adj in new_facts.items():
        identity = subject, key
        source = FactSource(SourceKind.EXPLICIT, _source_id(subject, key))
        existing = entries.get(identity)
        sources = existing.fact.sources if existing is not None else SourceSet.one(source)
        if existing is not None and not sources.has_kind(SourceKind.EXPLICIT):
            sources = sources.add(source)
        entries[identity] = AttributeEntry(subject, AdjFact(adj, sources))
        node_key = NodeKey.adj(subject, key)
        if existing is None:
            candidate.register_node(TruthNode(node_key))
            candidate.assert_assumption(Assumption(_source_id(subject, key), node_key))
    report = candidate.propagate()
    if not report.consistent:
        raise AttributePropagationError("attribute batch caused a truth conflict")
    return AttributeState(
        state.objects,
        tuple(entry for _, entry in sorted(entries.items())),
        candidate,
    )


def unset_attributes(
    state: AttributeState,
    subject: str,
    keys: tuple[str, ...],
) -> AttributeState:
    """Withdraw every requested explicit source atomically and propagate once."""
    _require_subject(state, subject)
    normalized = tuple(Adj(key, None).key for key in keys)
    if not normalized or len(normalized) != len(set(normalized)):
        raise DomainInvariantError("unset keys must be non-empty and unique")
    entries = {(entry.subject, entry.fact.adj.key): entry for entry in state.attributes}
    missing = [key for key in normalized if (subject, key) not in entries]
    if missing:
        raise AttributeNotFoundError(f"unknown attributes: {sorted(missing)}")
    for key in normalized:
        if not entries[(subject, key)].fact.sources.has_kind(SourceKind.EXPLICIT):
            raise AttributeNotFoundError(f"attribute has no explicit source: {key}")

    candidate = _kernel(state).clone()
    for key in normalized:
        identity = subject, key
        entry = entries[identity]
        remaining = entry.fact.withdraw(SourceKind.EXPLICIT, _source_id(subject, key))
        if remaining is None:
            del entries[identity]
            candidate.retract_node(NodeKey.adj(subject, key))
        else:
            entries[identity] = AttributeEntry(subject, remaining)
    report = candidate.propagate()
    if not report.consistent:
        raise AttributePropagationError("attribute withdrawal caused a truth conflict")
    return AttributeState(
        state.objects,
        tuple(entry for _, entry in sorted(entries.items())),
        candidate,
    )


def _require_subject(state: AttributeState, subject: str) -> None:
    if not any(item.name == subject for item in state.objects.objects.objects):
        raise ObjectNotFoundError(f"unknown object: {subject}")


def _kernel(state: AttributeState) -> TruthKernel:
    assert state.kernel is not None
    return state.kernel


def _source_id(subject: str, key: str) -> str:
    return f"adj-explicit:{NodeKey.adj(subject, key).encode()}"
