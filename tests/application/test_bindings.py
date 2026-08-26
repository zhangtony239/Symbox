"""Generic bind/unbind and load-time revalidation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbox.application.bindings import (
    BindingNotFoundError,
    BindingSourceChangedError,
    BindingState,
    bind_object,
    revalidate_bindings,
    unbind_object,
)
from symbox.application.objects import ObjectNotFoundError, ObjectState, create_object
from symbox.integrations.python_bindings import BindingLoadError, ProjectPythonBindingLoader
from symbox.kernel.fake import InMemoryTruthKernel


def _state(*names: str) -> BindingState:
    objects = ObjectState((), InMemoryTruthKernel())
    for name in names:
        objects = create_object(objects, name)
    return BindingState(objects)


LOADER = ProjectPythonBindingLoader()


def _write_check(project: Path, body: str = "return True") -> None:
    rules = project / "rules"
    rules.mkdir(exist_ok=True)
    (rules / "checks.py").write_text(
        f"def check(subject):\n    {body}\n",
        encoding="utf-8",
    )


def test_bind_records_reference_and_explicit_verb_marker(tmp_path: Path) -> None:
    _write_check(tmp_path)

    bound, loaded = bind_object(
        _state("moves"),
        LOADER,
        tmp_path,
        "moves",
        "rules/checks.py",
        "check",
        is_verb=True,
    )

    assert bound.is_verb("moves")
    assert bound.binding_for("moves") is not None
    assert bound.binding_for("moves").reference == loaded.reference  # type: ignore[union-attr]
    assert loaded.callable({}) is True


def test_plain_binding_does_not_mark_object_as_verb(tmp_path: Path) -> None:
    _write_check(tmp_path)

    bound, _ = bind_object(
        _state("checker"),
        LOADER,
        tmp_path,
        "checker",
        "rules/checks.py",
        "check",
    )

    assert not bound.is_verb("checker")


def test_failed_rebind_preserves_existing_reference(tmp_path: Path) -> None:
    _write_check(tmp_path)
    original, _ = bind_object(
        _state("checker"),
        LOADER,
        tmp_path,
        "checker",
        "rules/checks.py",
        "check",
    )

    with pytest.raises(BindingLoadError):
        bind_object(
            original,
            LOADER,
            tmp_path,
            "checker",
            "missing.py",
            "check",
            is_verb=True,
        )

    assert original.binding_for("checker") is not None
    assert not original.is_verb("checker")


def test_unbind_removes_reference_and_verb_marker(tmp_path: Path) -> None:
    _write_check(tmp_path)
    bound, _ = bind_object(
        _state("moves"),
        LOADER,
        tmp_path,
        "moves",
        "rules/checks.py",
        "check",
        is_verb=True,
    )

    unbound = unbind_object(bound, "moves")

    assert unbound.binding_for("moves") is None
    assert not unbound.is_verb("moves")
    with pytest.raises(BindingNotFoundError):
        unbind_object(unbound, "moves")


def test_bind_rejects_unknown_object_before_loading(tmp_path: Path) -> None:
    _write_check(tmp_path)

    with pytest.raises(ObjectNotFoundError, match="unknown object"):
        bind_object(_state(), LOADER, tmp_path, "missing", "rules/checks.py", "check")


def test_load_time_revalidation_accepts_unchanged_source(tmp_path: Path) -> None:
    _write_check(tmp_path)
    bound, _ = bind_object(
        _state("checker"),
        LOADER,
        tmp_path,
        "checker",
        "rules/checks.py",
        "check",
    )

    loaded = revalidate_bindings(bound, LOADER, tmp_path)

    assert len(loaded) == 1
    assert loaded[0].callable({}) is True


def test_load_time_revalidation_rejects_source_digest_drift(tmp_path: Path) -> None:
    _write_check(tmp_path)
    bound, _ = bind_object(
        _state("checker"),
        LOADER,
        tmp_path,
        "checker",
        "rules/checks.py",
        "check",
    )
    _write_check(tmp_path, "return False")

    with pytest.raises(BindingSourceChangedError, match="source changed"):
        revalidate_bindings(bound, LOADER, tmp_path)
