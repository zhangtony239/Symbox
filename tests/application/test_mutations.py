"""Controlled binding check/effect and rollback tests."""

from __future__ import annotations

import pytest

from symbox.application.mutations import (
    BindingExecutionError,
    CheckRejectedError,
    MutationContext,
    MutationSnapshot,
    execute_binding,
)


def test_successful_check_applies_effect_only_to_candidate() -> None:
    committed = MutationSnapshot({"battery": 80})

    def effect(context: MutationContext, subject: str, amount: int) -> None:
        assert subject == "robot"
        context.set("battery", context.get("battery") - amount)
        context.set("last_action", "move")

    candidate = execute_binding(
        committed,
        lambda subject, amount: subject == "robot" and amount <= 20,
        "robot",
        10,
        apply_effect=effect,
    )

    assert candidate.values == {"battery": 70, "last_action": "move"}
    assert committed.values == {"battery": 80}


def test_false_check_does_not_run_effect_or_change_committed_state() -> None:
    committed = MutationSnapshot({"battery": 5})
    effect_calls = 0

    def effect(context: MutationContext, subject: str) -> None:
        nonlocal effect_calls
        effect_calls += 1
        context.set("battery", 0)

    with pytest.raises(CheckRejectedError):
        execute_binding(committed, lambda subject: False, "robot", apply_effect=effect)

    assert effect_calls == 0
    assert committed.values == {"battery": 5}


@pytest.mark.parametrize("stage", ["check", "effect"])
def test_check_or_effect_exception_discards_candidate(stage: str) -> None:
    committed = MutationSnapshot({"battery": 80})

    def check(subject: str) -> bool:
        if stage == "check":
            raise RuntimeError("boom")
        return True

    def effect(context: MutationContext, subject: str) -> None:
        context.set("battery", 0)
        if stage == "effect":
            raise RuntimeError("boom")

    with pytest.raises(BindingExecutionError, match=stage):
        execute_binding(committed, check, "robot", apply_effect=effect)

    assert committed.values == {"battery": 80}


def test_non_boolean_check_and_non_none_effect_are_rejected() -> None:
    committed = MutationSnapshot({})

    with pytest.raises(BindingExecutionError, match="return bool"):
        execute_binding(committed, lambda subject: "yes", "robot")  # type: ignore[arg-type]

    with pytest.raises(BindingExecutionError, match="return None"):
        execute_binding(
            committed,
            lambda subject: True,
            "robot",
            apply_effect=lambda context, subject: "unexpected",  # type: ignore[arg-type]
        )


def test_context_rejects_deleting_unknown_candidate_value() -> None:
    context = MutationContext(MutationSnapshot({}))

    with pytest.raises(ValueError, match="unknown candidate"):
        context.delete("missing")
