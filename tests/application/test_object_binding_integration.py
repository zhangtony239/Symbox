"""Lifecycle, binding, Verb marker, and category-isolation integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbox.application.bindings import BindingState, bind_object, unbind_object
from symbox.application.objects import (
    ObjectAlreadyExistsError,
    ObjectState,
    create_object,
)
from symbox.application.relation_guards import NotAVerbError, validate_relation_objects
from symbox.domain.models import CategoryConstraintError, ObjectCategory
from symbox.integrations.python_bindings import BindingLoadError, ProjectPythonBindingLoader
from symbox.kernel.fake import InMemoryTruthKernel

LOADER = ProjectPythonBindingLoader()


def _project_state() -> BindingState:
    objects = ObjectState((), InMemoryTruthKernel())
    objects = create_object(objects, "robot", ObjectCategory.PHYSICAL)
    objects = create_object(objects, "moves", ObjectCategory.ABSTRACT)
    objects = create_object(objects, "worry", ObjectCategory.META)
    return BindingState(objects)


def _write_check(project: Path, signature: str = "subject") -> None:
    (project / "checks.py").write_text(
        f"def check({signature}):\n    return True\n",
        encoding="utf-8",
    )


def test_duplicate_object_and_invalid_binding_leave_state_unchanged(tmp_path: Path) -> None:
    state = _project_state()

    with pytest.raises(ObjectAlreadyExistsError):
        create_object(state.objects, "robot", ObjectCategory.ABSTRACT)
    with pytest.raises(BindingLoadError):
        bind_object(state, LOADER, tmp_path, "moves", "missing.py", "check", is_verb=True)

    assert state.binding_for("moves") is None
    assert len(state.objects.objects) == 3


def test_non_verb_position_is_rejected_and_unbind_removes_marker(tmp_path: Path) -> None:
    _write_check(tmp_path)
    state = _project_state()

    with pytest.raises(NotAVerbError, match="not marked"):
        validate_relation_objects(state, "robot", "moves")

    bound, _ = bind_object(
        state,
        LOADER,
        tmp_path,
        "moves",
        "checks.py",
        "check",
        is_verb=True,
    )
    validate_relation_objects(bound, "robot", "moves")

    unbound = unbind_object(bound, "moves")
    with pytest.raises(NotAVerbError, match="not marked"):
        validate_relation_objects(unbound, "robot", "moves")


def test_ordinary_verb_rejects_meta_subject_before_callable_runs(tmp_path: Path) -> None:
    _write_check(tmp_path)
    bound, loaded = bind_object(
        _project_state(),
        LOADER,
        tmp_path,
        "moves",
        "checks.py",
        "check",
        is_verb=True,
    )
    calls = 0

    def invoke() -> None:
        nonlocal calls
        validate_relation_objects(bound, "worry", "moves")
        calls += 1
        loaded.callable("worry")

    with pytest.raises(CategoryConstraintError, match="subject requires"):
        invoke()

    assert calls == 0
