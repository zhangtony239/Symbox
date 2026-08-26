"""Verb boolean polarity and structured diagnostic tests."""

from __future__ import annotations

from symbox.application.verb_checks import execute_verb_check


def test_true_means_relation_check_passes() -> None:
    result = execute_verb_check(
        lambda subject, destination, speed=1: subject == "robot" and speed > 0,
        "robot",
        ("dock",),
        (("speed", 2),),
    )

    assert result.accepted
    assert not result.conflict
    assert result.diagnostics == ()


def test_false_means_structured_conflict() -> None:
    result = execute_verb_check(lambda subject: False, "robot", (), ())

    assert not result.accepted
    assert result.conflict
    assert result.diagnostics[0].code == "verb_conflict"
    assert result.diagnostics[0].details["subject"] == "robot"


def test_exception_and_non_bool_are_diagnostic_validation_failures() -> None:
    def failing(subject: str) -> bool:
        raise RuntimeError("boom")

    error = execute_verb_check(failing, "robot", (), ())
    invalid = execute_verb_check(lambda subject: "yes", "robot", (), ())  # type: ignore[arg-type]

    assert not error.conflict
    assert error.diagnostics[0].code == "verb_check_error"
    assert error.diagnostics[0].details["exception_type"] == "RuntimeError"
    assert invalid.diagnostics[0].code == "invalid_verb_result"
