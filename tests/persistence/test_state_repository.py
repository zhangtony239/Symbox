"""Project scope, state loading, and credential exclusion tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbox.persistence.state_format import StateDocument, StateFormatError
from symbox.persistence.state_repository import (
    ProjectScope,
    ProjectScopeError,
    StateRepository,
    discover_project_scope,
)


def test_scope_discovery_walks_to_nearest_project_marker(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "package"
    nested.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    scope = discover_project_scope(nested)

    assert scope.root == project.resolve()
    assert scope.state_path == project.resolve() / ".sbox" / "state.json"


def test_nested_project_does_not_read_parent_state(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    (parent / "pyproject.toml").write_text("[project]\nname='parent'\n", encoding="utf-8")
    (child / "pyproject.toml").write_text("[project]\nname='child'\n", encoding="utf-8")
    parent_state = ProjectScope(parent).state_path
    parent_state.parent.mkdir()
    parent_state.write_bytes(StateDocument(revision=9).to_bytes())

    repository = StateRepository(discover_project_scope(child))

    assert repository.scope.root == child.resolve()
    assert repository.load() == StateDocument()


def test_missing_state_loads_as_empty_and_valid_state_round_trips(tmp_path: Path) -> None:
    scope = ProjectScope(tmp_path)
    repository = StateRepository(scope)
    assert repository.load() == StateDocument()

    scope.state_dir.mkdir()
    expected = StateDocument(revision=3, objects=({"name": "robot"},))
    scope.state_path.write_bytes(expected.to_bytes())

    assert repository.load() == expected


@pytest.mark.parametrize(
    "content",
    [
        b"broken",
        StateDocument().to_bytes().replace(b'"schema_version":1', b'"schema_version":99'),
    ],
)
def test_repository_rejects_corrupt_or_unknown_state(tmp_path: Path, content: bytes) -> None:
    scope = ProjectScope(tmp_path)
    scope.state_dir.mkdir()
    scope.state_path.write_bytes(content)

    with pytest.raises(StateFormatError):
        StateRepository(scope).load()


def test_environment_credentials_are_not_serialized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-never-persist-this"
    monkeypatch.setenv("SBOX_EMBEDDING_API_KEY", secret)

    content = StateRepository(ProjectScope(tmp_path)).load().to_bytes()

    assert secret.encode() not in content
    assert b"API_KEY" not in content


def test_invalid_scope_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(ProjectScopeError):
        ProjectScope(missing)
