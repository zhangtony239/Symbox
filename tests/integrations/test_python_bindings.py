"""Project-local callable loading and signature validation tests."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from symbox.domain.models import DomainInvariantError
from symbox.integrations.python_bindings import BindingLoadError, load_binding


def _write_binding(project: Path, content: str) -> Path:
    rules = project / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    source = rules / "checks.py"
    source.write_text(content, encoding="utf-8")
    return source


def test_loads_qualified_callable_and_records_source_digest(tmp_path: Path) -> None:
    source = _write_binding(
        tmp_path,
        "class Checks:\n"
        "    @staticmethod\n"
        "    def is_safe(subject, threshold=10):\n"
        "        return subject['value'] >= threshold\n",
    )

    loaded = load_binding(tmp_path, "rules/checks.py", "Checks.is_safe", is_verb=True)

    assert loaded.callable({"value": 12}, threshold=10) is True
    assert loaded.reference.source_path == "rules/checks.py"
    assert loaded.reference.source_digest == sha256(source.read_bytes()).hexdigest()
    assert loaded.reference.is_verb
    assert tuple(loaded.signature.parameters) == ("subject", "threshold")


@pytest.mark.parametrize(
    ("source_path", "qualified_name", "content", "message"),
    [
        ("missing.py", "check", None, "regular non-symlink"),
        ("rules/checks.py", "missing", "def check(subject): return True\n", "not found"),
        ("rules/checks.py", "value", "value = 1\n", "not callable"),
        ("rules/checks.py", "check", "def check(): return True\n", "explicit first"),
        (
            "rules/checks.py",
            "check",
            "def check(*, subject): return True\n",
            "positionally",
        ),
        ("rules/checks.py", "check", "raise RuntimeError('boom')\n", "execution failed"),
    ],
)
def test_rejects_invalid_source_name_target_or_signature(
    tmp_path: Path,
    source_path: str,
    qualified_name: str,
    content: str | None,
    message: str,
) -> None:
    if content is not None:
        _write_binding(tmp_path, content)

    with pytest.raises(BindingLoadError, match=message):
        load_binding(tmp_path, source_path, qualified_name)


def test_rejects_parent_traversal_before_loading(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"
    outside.write_text("def check(subject): return True\n", encoding="utf-8")

    with pytest.raises(DomainInvariantError, match="project-relative"):
        load_binding(tmp_path, "../outside.py", "check")


def test_rejects_symlink_source_when_platform_supports_it(tmp_path: Path) -> None:
    source = _write_binding(tmp_path, "def check(subject): return True\n")
    link = tmp_path / "linked.py"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(BindingLoadError, match="non-symlink"):
        load_binding(tmp_path, "linked.py", "check")
