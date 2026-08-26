"""Atomic SVK relation assertion over checks, effects, and unified propagation."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from symbox.application.mutations import EffectCallable, MutationSnapshot, execute_binding
from symbox.application.signature_binding import bind_effective_arguments
from symbox.application.verb_checks import VerbCheckResult, execute_verb_check
from symbox.domain.models import SVK, DomainInvariantError
from symbox.domain.svk_identity import SVKIdentityRegistry
from symbox.kernel.port import Assumption, TruthKernel, TruthNode


class RelationConflictError(DomainInvariantError):
    """Raised when local validation or unified propagation rejects a relation."""


@dataclass(frozen=True, slots=True)
class RelationFact:
    """A normalized SVK and its full stable node identity."""

    relation: SVK
    node_key: str


@dataclass(frozen=True, slots=True)
class RelationState:
    """Committed relation facts, controlled values, and the central kernel."""

    relations: tuple[RelationFact, ...]
    values: MutationSnapshot
    kernel: TruthKernel

    def __post_init__(self) -> None:
        keys = tuple(fact.node_key for fact in self.relations)
        if len(keys) != len(set(keys)):
            raise DomainInvariantError("relation identities must be unique")
        if keys != tuple(sorted(keys)):
            raise DomainInvariantError("relations must use deterministic identity order")


@dataclass(frozen=True, slots=True)
class RelationAssertion:
    """A successful candidate plus its local Verb check result."""

    state: RelationState
    check: VerbCheckResult


def assert_relation(
    state: RelationState,
    *,
    signature: inspect.Signature,
    check: Callable[..., bool],
    subject: Any,
    subject_name: str,
    verb_name: str,
    args: tuple[Any, ...],
    kwargs: tuple[tuple[str, Any], ...],
    apply_effect: EffectCallable | None = None,
) -> RelationAssertion:
    """Normalize, check, apply controlled effects, propagate, then return a candidate."""
    effective = bind_effective_arguments(signature, subject, args, kwargs)
    check_result = execute_verb_check(
        check,
        effective.subject,
        effective.args,
        effective.kwargs,
    )
    if not check_result.accepted:
        message = check_result.diagnostics[0].message
        raise RelationConflictError(message)
    candidate_values = execute_binding(
        state.values,
        check,
        effective.subject,
        *effective.args,
        kwargs=dict(effective.kwargs),
        apply_effect=apply_effect,
    )
    relation = SVK(subject_name, verb_name, effective.args, effective.kwargs)
    registry = SVKIdentityRegistry()
    for existing in state.relations:
        registry.identify(existing.relation)
    identity = registry.identify(relation)
    encoded_key = identity.key.encode()
    if any(existing.node_key == encoded_key for existing in state.relations):
        return RelationAssertion(state, check_result)

    candidate_kernel = state.kernel.clone()
    candidate_kernel.register_node(TruthNode(identity.key))
    candidate_kernel.assert_assumption(Assumption(f"relation-explicit:{encoded_key}", identity.key))
    report = candidate_kernel.propagate()
    if not report.consistent:
        raise RelationConflictError(f"relation propagation conflict: {encoded_key}")
    relations = tuple(
        sorted(
            (*state.relations, RelationFact(relation, encoded_key)),
            key=lambda fact: fact.node_key,
        )
    )
    candidate_state = RelationState(relations, candidate_values, candidate_kernel)
    return RelationAssertion(candidate_state, check_result)
