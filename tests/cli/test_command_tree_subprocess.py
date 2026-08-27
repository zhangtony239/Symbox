"""End-to-end subprocess coverage for the full public v0.6 command tree."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def test_no_arguments_is_equivalent_to_help() -> None:
    bare = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main"],
        check=False,
        capture_output=True,
        text=True,
    )
    explicit_help = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert bare.returncode == explicit_help.returncode == 0
    assert bare.stdout == explicit_help.stdout
    assert bare.stderr == explicit_help.stderr == ""
    assert bare.stdout.startswith("usage: sbox")


def _run(root: Path, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "--root", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, json.loads(completed.stdout)


def _success(root: Path, *arguments: str) -> Any:
    completed, result = _run(root, *arguments)
    assert completed.returncode == 0, completed.stderr or result
    assert result["status"] == "success"
    return result["data"]


def test_full_write_query_and_backup_command_tree(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "checks.py").write_text(
        "def moves(subject, destination, speed=1):\n"
        "    return subject == 'robot' and bool(destination) and speed > 0\n",
        encoding="utf-8",
    )

    _success(tmp_path, "create", "robot")
    _success(tmp_path, "create", "moves", "--category", "abstract")
    _success(
        tmp_path,
        "bind",
        "moves",
        "-f",
        "rules/checks.py",
        "--verb",
    )
    _success(tmp_path, "set", "robot", "level=12", 'mode="ready"')
    relation = _success(tmp_path, "now", "robot", "moves", "dock", "speed=2")
    assert relation["node_key"].startswith("SVK:robot:moves:")

    objects = _success(tmp_path, "list", "objects")
    assert [item["name"] for item in objects] == ["moves", "robot"]
    verbs = _success(tmp_path, "list", "verbs")
    assert [item["object_name"] for item in verbs] == ["moves"]
    detail = _success(tmp_path, "list", "robot")
    assert {item["key"] for item in detail["attributes"]} == {"level", "mode"}

    backup = _success(tmp_path, "backup", "create", "before mutation")
    commit_id = backup["commit_id"]
    _success(tmp_path, "set", "robot", "level=3")
    listed = _success(tmp_path, "backup", "list")
    assert [item["commit_id"] for item in listed] == [commit_id]

    restored = _success(tmp_path, "backup", "rollback", commit_id)
    assert restored["commit_id"] == commit_id
    restored_detail = _success(tmp_path, "list", "robot")
    values = {item["key"]: item["value"] for item in restored_detail["attributes"]}
    assert values == {"level": 12, "mode": "ready"}

    _success(tmp_path, "unset", "robot", "mode")
    _success(tmp_path, "unbind", "moves")
    _success(tmp_path, "delete", "moves")
    _success(tmp_path, "backup", "delete", commit_id)
    assert _success(tmp_path, "backup", "list") == []


def test_backup_log_command_is_removed_and_replaced_by_backup_list(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "--root", str(tmp_path), "backup", "log"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr
