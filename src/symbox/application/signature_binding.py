"""Normalize parsed now arguments through a Python callable signature."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from symbox.domain.models import DomainInvariantError


class ArgumentBindingError(DomainInvariantError):
    """Raised when a variable argument package violates the bound callable signature."""


@dataclass(frozen=True, slots=True)
class EffectiveArguments:
    """A signature-bound package with defaults expanded and Subject kept explicit."""

    subject: Any
    args: tuple[Any, ...]
    kwargs: tuple[tuple[str, Any], ...]
    parameter_values: tuple[tuple[str, Any], ...]


def bind_effective_arguments(
    signature: inspect.Signature,
    subject: Any,
    args: tuple[Any, ...],
    kwargs: tuple[tuple[str, Any], ...],
) -> EffectiveArguments:
    """Bind Subject first, reject structural errors, and expand all defaults."""
    names = tuple(name for name, _ in kwargs)
    if len(names) != len(set(names)):
        raise ArgumentBindingError("duplicate named arguments")
    keyword_mapping = dict(kwargs)
    try:
        bound = signature.bind(subject, *args, **keyword_mapping)
    except TypeError as error:
        raise ArgumentBindingError(str(error)) from error
    bound.apply_defaults()

    parameters = tuple(signature.parameters.values())
    if not parameters:
        raise ArgumentBindingError("binding signature does not accept Subject")
    subject_name = parameters[0].name
    normalized_args: list[Any] = []
    normalized_kwargs: list[tuple[str, Any]] = []
    parameter_values: list[tuple[str, Any]] = []
    for parameter in parameters:
        value = bound.arguments[parameter.name]
        parameter_values.append((parameter.name, value))
        if parameter.name == subject_name:
            continue
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            normalized_args.append(value)
        elif parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            normalized_args.extend(value)
        elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
            normalized_kwargs.extend(sorted(value.items()))
        else:
            normalized_kwargs.append((parameter.name, value))
    return EffectiveArguments(
        subject=bound.arguments[subject_name],
        args=tuple(normalized_args),
        kwargs=tuple(sorted(normalized_kwargs)),
        parameter_values=tuple(parameter_values),
    )
