"""End-to-end public relation-command surface tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "--root", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_now_is_public_and_returns_persisted_relation_identity(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def moves(subject, destination, speed=1):\n"
        "    return subject == 'robot' and speed > 0\n",
        encoding="utf-8",
    )
    assert _run(tmp_path, "create", "robot").returncode == 0
    assert _run(tmp_path, "create", "moves", "--category", "abstract").returncode == 0
    assert (
        _run(
            tmp_path,
            "bind",
            "moves",
            "moves",
            "-f",
            "rules/checks.py",
            "--verb",
        ).returncode
        == 0
    )

    completed = _run(tmp_path, "now", "robot", "moves", "dock", "speed=2")

    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result["status"] == "success"
    assert result["data"]["subject"] == "robot"
    assert result["data"]["verb"] == "moves"
    assert result["data"]["node_key"].startswith("SVK:robot:moves:")


def test_svo_command_is_removed_and_has_no_compatibility_alias() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "svo", "robot", "moves", "dock"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr
