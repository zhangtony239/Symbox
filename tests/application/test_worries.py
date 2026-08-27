"""Worry registration and generic binding lifecycle tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbox.application.bindings import BindingState
from symbox.application.mutations import BindingExecutionError
from symbox.application.objects import ObjectState, create_object
from symbox.application.worries import (
    WorryAlreadyExistsError,
    WorryConvergenceError,
    WorryMonitoringState,
    WorryState,
    attribute_dependency,
    bind_worry,
    create_worry,
    delete_worry,
    set_monitored_attributes,
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
        "def healthy(subject, threshold=10):\n    return subject['level'] >= threshold\n",
        encoding="utf-8",
    )


def test_create_worry_registers_meta_object_dependencies_and_health_node() -> None:
    dependencies = (
        attribute_dependency("tank", "level"),
        attribute_dependency("tank", "mode"),
    )
    state = create_worry(_state("tank"), "level-ok", dependencies)

    worry = state.worry_for("level-ok")
    meta_object = next(item for item in state.objects.objects.objects if item.name == "level-ok")

    assert worry is not None
    assert worry.dependencies == dependencies
    assert meta_object.category is ObjectCategory.META
    assert state.kernel is not None
    assert state.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.UNKNOWN


def test_dependency_index_returns_affected_worries_in_name_order() -> None:
    pressure = attribute_dependency("tank", "pressure")
    state = create_worry(_state("tank"), "z-pressure", (pressure,))
    state = create_worry(
        state,
        "a-level",
        (attribute_dependency("tank", "level"), pressure),
    )

    affected = state.affected_by((pressure,))

    assert tuple(worry.name for worry in affected) == ("a-level", "z-pressure")


def test_create_worry_rejects_any_occupied_object_name() -> None:
    with pytest.raises(WorryAlreadyExistsError, match="already exists"):
        create_worry(
            _state("occupied"),
            "occupied",
            (attribute_dependency("tank", "level"),),
        )


def test_worry_uses_generic_bind_and_unbind_lifecycle(tmp_path: Path) -> None:
    _write_check(tmp_path)
    state = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )

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
    state = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )
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


def test_attribute_candidate_maps_worry_bool_directly_to_health_node(tmp_path: Path) -> None:
    _write_check(tmp_path)
    registered = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )
    bound, loaded = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "healthy",
    )
    state = WorryMonitoringState(bound)

    healthy = set_monitored_attributes(state, "tank", {"level": 12}, {"level-ok": loaded})
    assert healthy.kernel is not None
    assert healthy.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.TRUE

    unhealthy = set_monitored_attributes(
        healthy,
        "tank",
        {"level": 3},
        {"level-ok": loaded},
    )
    assert unhealthy.kernel is not None
    assert unhealthy.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.FALSE


def test_unaffected_worry_is_not_executed(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def explode(subject):\n    raise RuntimeError('must not run')\n",
        encoding="utf-8",
    )
    registered = create_worry(
        _state("tank"),
        "pressure-ok",
        (attribute_dependency("tank", "pressure"),),
    )
    bound, loaded = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "pressure-ok",
        "rules/checks.py",
        "explode",
    )

    updated = set_monitored_attributes(
        WorryMonitoringState(bound),
        "tank",
        {"level": 12},
        {"pressure-ok": loaded},
    )

    assert updated.kernel is not None
    assert updated.kernel.truth(NodeKey.worry("pressure-ok")) is TruthValue.UNKNOWN


def test_worry_exception_discards_attribute_and_health_candidates(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def explode(subject):\n    raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    registered = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )
    bound, loaded = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "explode",
    )
    committed = WorryMonitoringState(bound)

    with pytest.raises(BindingExecutionError, match="boom"):
        set_monitored_attributes(
            committed,
            "tank",
            {"level": 12},
            {"level-ok": loaded},
        )

    assert committed.attributes == ()
    assert committed.kernel is not None
    assert committed.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.UNKNOWN


def test_unbind_withdraws_existing_health_support(tmp_path: Path) -> None:
    _write_check(tmp_path)
    registered = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )
    bound, loaded = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "healthy",
    )
    monitored = set_monitored_attributes(
        WorryMonitoringState(bound),
        "tank",
        {"level": 12},
        {"level-ok": loaded},
    )
    synchronized = WorryState(
        monitored.worries.objects,
        monitored.worries.worries,
        monitored.kernel,
    )

    unbound = unbind_worry(synchronized, "level-ok")

    assert unbound.kernel is not None
    assert unbound.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.UNKNOWN


def test_propagation_tail_reevaluates_worry_affected_by_health_change(
    tmp_path: Path,
) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def level_healthy(subject):\n"
        "    return subject['level'] >= 10\n\n"
        "def system_healthy(subject):\n"
        "    return subject['level-ok'] == 'true'\n",
        encoding="utf-8",
    )
    registered = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )
    registered = create_worry(
        registered,
        "system-ok",
        (NodeKey.worry("level-ok").encode(),),
    )
    bound, level_binding = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "level_healthy",
    )
    bound, system_binding = bind_worry(
        bound,
        ProjectPythonBindingLoader(),
        tmp_path,
        "system-ok",
        "rules/checks.py",
        "system_healthy",
    )

    updated = set_monitored_attributes(
        WorryMonitoringState(bound),
        "tank",
        {"level": 12},
        {"level-ok": level_binding, "system-ok": system_binding},
    )

    assert updated.kernel is not None
    assert updated.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.TRUE
    assert updated.kernel.truth(NodeKey.worry("system-ok")) is TruthValue.TRUE


def test_iteration_boundary_aborts_entire_attribute_candidate(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def level_healthy(subject):\n"
        "    return subject['level'] >= 10\n\n"
        "def system_healthy(subject):\n"
        "    return subject['level-ok'] == 'true'\n",
        encoding="utf-8",
    )
    registered = create_worry(
        _state("tank"),
        "level-ok",
        (attribute_dependency("tank", "level"),),
    )
    registered = create_worry(
        registered,
        "system-ok",
        (NodeKey.worry("level-ok").encode(),),
    )
    bound, level_binding = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "level-ok",
        "rules/checks.py",
        "level_healthy",
    )
    bound, system_binding = bind_worry(
        bound,
        ProjectPythonBindingLoader(),
        tmp_path,
        "system-ok",
        "rules/checks.py",
        "system_healthy",
    )
    committed = WorryMonitoringState(bound)

    with pytest.raises(WorryConvergenceError, match="exceeded") as failure:
        set_monitored_attributes(
            committed,
            "tank",
            {"level": 12},
            {"level-ok": level_binding, "system-ok": system_binding},
            max_iterations=1,
        )

    assert failure.value.iterations == 1
    assert "pending[Worry:level-ok]" in failure.value.signature
    assert committed.attributes == ()
    assert committed.kernel is not None
    assert committed.kernel.truth(NodeKey.worry("level-ok")) is TruthValue.UNKNOWN
    assert committed.kernel.truth(NodeKey.worry("system-ok")) is TruthValue.UNKNOWN


def test_repeated_state_signature_aborts_oscillating_worry(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "flip = False\n\n"
        "def oscillate(subject):\n"
        "    global flip\n"
        "    flip = not flip\n"
        "    return flip\n",
        encoding="utf-8",
    )
    registered = create_worry(
        _state("tank"),
        "oscillator",
        (
            attribute_dependency("tank", "level"),
            NodeKey.worry("oscillator").encode(),
        ),
    )
    bound, loaded = bind_worry(
        registered,
        ProjectPythonBindingLoader(),
        tmp_path,
        "oscillator",
        "rules/checks.py",
        "oscillate",
    )
    committed = WorryMonitoringState(bound)

    with pytest.raises(WorryConvergenceError, match="repeated a state") as failure:
        set_monitored_attributes(
            committed,
            "tank",
            {"level": 12},
            {"oscillator": loaded},
        )

    assert failure.value.iterations == 3
    assert "Worry:oscillator" in failure.value.signature
    assert committed.attributes == ()
    assert committed.kernel is not None
    assert committed.kernel.truth(NodeKey.worry("oscillator")) is TruthValue.UNKNOWN
