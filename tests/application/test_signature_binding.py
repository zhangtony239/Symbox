"""Subject-first Python signature binding and default normalization tests."""

from __future__ import annotations

import inspect

import pytest

from symbox.application.signature_binding import ArgumentBindingError, bind_effective_arguments


def check(subject: object, destination: str, speed: int = 2, *, safe: bool = True) -> bool:
    return True


def test_subject_is_explicit_first_argument_and_defaults_are_expanded() -> None:
    effective = bind_effective_arguments(
        inspect.signature(check),
        "robot",
        ("dock",),
        (),
    )

    assert effective.subject == "robot"
    assert effective.kwargs == (("destination", "dock"), ("safe", True), ("speed", 2))
    assert effective.parameter_values == (
        ("subject", "robot"),
        ("destination", "dock"),
        ("speed", 2),
        ("safe", True),
    )


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        ((), (), "missing a required argument"),
        (("dock",), (("destination", "bay"),), "multiple values"),
        (("dock",), (("unknown", 1),), "unexpected keyword"),
        (("dock",), (("speed", 1), ("speed", 2)), "duplicate named"),
    ],
)
def test_missing_duplicate_or_unknown_arguments_are_rejected(
    args: tuple[object, ...],
    kwargs: tuple[tuple[str, object], ...],
    message: str,
) -> None:
    with pytest.raises(ArgumentBindingError, match=message):
        bind_effective_arguments(inspect.signature(check), "robot", args, kwargs)


def test_varargs_and_varkw_are_normalized_deterministically() -> None:
    def flexible(subject: object, *targets: str, **options: int) -> bool:
        return True

    effective = bind_effective_arguments(
        inspect.signature(flexible),
        "robot",
        ("dock", "bay"),
        (("speed", 2), ("priority", 1)),
    )

    assert effective.args == ("dock", "bay")
    assert effective.kwargs == (("priority", 1), ("speed", 2))
