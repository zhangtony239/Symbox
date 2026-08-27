"""Worry registration and generic binding lifecycle tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbox.application.bindings import BindingState
from symbox.application.objects import ObjectState, create_object
from symbox.application.worries import (
    WorryAlreadyExistsError,
    WorryState,
    bind_worry,
    create_worry,
    delete_worry,
    unbind_worry,
)
from symbox.domain.models import ObjectCategory
from symbox.domain.node_keys import NodeKey
from symbox.integrations.python_bindings import ProjectPythonBindingLoader
from symbox.kernel.fake import InMemoryTruthKernel
from symbox.kernel.port import TruthValue


def _state(*names: str) -> WorryState:
    objects = ObjectState((), InMemoryTruthKernel())
    for name in names:
        objects = create_object(objects, name)
    return WorryState(BindingState(objects))


def _write_check(project: Path) -> None:
    rules = project / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def healthy(subject, threshold=10):\n"
        "    return subject['level'] >= threshold\n",
        encoding="utf-8",
    )


def test_create_worry_registers_meta_object_dependencies_and_health_node() -> None:
    state = create_worry(_state("tank"), "level-ok", ("tank.level", "tank.mode"))

    worry = state.worry_for("level-ok")
    meta_object = next(item for item in state.objects.objects.objects if item.name == "level-ok")

    assert worry is not None
    assert worry.dependencies == ("tank.level", "tank.mode")
    assert meta_object.category is ObjectCategory.META
    assert state.kernel is not None
    assert state.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.UNKNOWN


def test_dependency_index_returns_affected_worries_in_name_order() -> None:
    state = create_worry(_state("tank"), "z-pressure", ("tank.pressure",))
    state = create_worry(state, "a-level", ("tank.level", "tank.pressure"))

    affected = state.affected_by(("tank.pressure",))

    assert tuple(worry.name for worry in affected) == ("a-level", "z-pressure")


def test_create_worry_rejects_any_occupied_object_name() -> None:
    with pytest.raises(WorryAlreadyExistsError, match="already exists"):
        create_worry(_state("occupied"), "occupied", ("tank.level",))


def test_worry_uses_generic_bind_and_unbind_lifecycle(tmp_path: Path) -> None:
    _write_check(tmp_path)
    state = create_worry(_state("tank"), "level-ok", ("tank.level",))

    bound, loaded = bind_worry(
        state,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "healthy",
    )

    entry = bound.objects.binding_for("level-ok")
    assert entry is not None
    assert entry.reference == loaded.reference
    assert not entry.reference.is_verb
    assert loaded.callable({"level": 12}) is True

    unbound = unbind_worry(bound, "level-ok")
    assert unbound.objects.binding_for("level-ok") is None
    assert unbound.worry_for("level-ok") is not None


def test_delete_worry_removes_meta_object_binding_and_health_node(tmp_path: Path) -> None:
    _write_check(tmp_path)
    state = create_worry(_state("tank"), "level-ok", ("tank.level",))
    bound, _ = bind_worry(
        state,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "healthy",
    )

    deleted = delete_worry(bound, "level-ok")

    assert deleted.worry_for("level-ok") is None
    assert deleted.objects.binding_for("level-ok") is None
    assert all(item.name != "level-ok" for item in deleted.objects.objects.objects)
    assert deleted.kernel is not None
    with pytest.raises(ValueError, match="unknown truth node"):
        deleted.kernel.truth(NodeKey.worry("level-ok"))
