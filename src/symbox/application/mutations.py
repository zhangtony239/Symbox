"""Controlled candidate effects for trusted dynamic bindings."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from symbox.domain.models import DomainInvariantError, _required_name

CheckCallable = Callable[..., bool]
EffectCallable = Callable[..., None]


class CheckRejectedError(DomainInvariantError):
    """Raised when a binding check returns False for the candidate operation."""


class BindingExecutionError(DomainInvariantError):
    """Raised when trusted binding execution fails or violates its contract."""


@dataclass(frozen=True, slots=True)
class MutationSnapshot:
    """A simple immutable state container exposed only through controlled methods."""

    values: dict[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", deepcopy(self.values))


class MutationContext:
    """The only write surface available to an optional binding effect."""

    def __init__(self, snapshot: MutationSnapshot) -> None:
        self._values = deepcopy(snapshot.values)

    def get(self, key: str) -> Any:
        """Read a candidate value without exposing the mutable backing mapping."""
        return deepcopy(self._values.get(_required_name(key, "mutation key")))

    def set(self, key: str, value: Any) -> None:
        """Set one candidate value."""
        self._values[_required_name(key, "mutation key")] = deepcopy(value)

    def delete(self, key: str) -> None:
        """Delete one existing candidate value."""
        normalized = _required_name(key, "mutation key")
        if normalized not in self._values:
            raise DomainInvariantError(f"cannot delete unknown candidate value: {normalized}")
        del self._values[normalized]

    def snapshot(self) -> MutationSnapshot:
        """Freeze the current candidate without exposing mutable internals."""
        return MutationSnapshot(self._values)


def execute_binding(
    committed: MutationSnapshot,
    check: CheckCallable,
    subject: Any,
    *args: Any,
    apply_effect: EffectCallable | None = None,
    kwargs: Mapping[str, Any] | None = None,
) -> MutationSnapshot:
    """Run check then optional controlled effect against an isolated candidate."""
    call_kwargs = dict(kwargs or {})
    try:
        accepted = check(subject, *args, **call_kwargs)
    except Exception as error:
        raise BindingExecutionError(f"binding check raised: {error}") from error
    if not isinstance(accepted, bool):
        raise BindingExecutionError("binding check must return bool")
    if not accepted:
        raise CheckRejectedError("binding check rejected the candidate operation")
    if apply_effect is None:
        return MutationSnapshot(committed.values)

    context = MutationContext(committed)
    try:
        effect_result = apply_effect(context, subject, *args, **call_kwargs)
    except Exception as error:
        raise BindingExecutionError(f"binding effect raised: {error}") from error
    if effect_result is not None:
        raise BindingExecutionError("binding effect must return None")
    return context.snapshot()
