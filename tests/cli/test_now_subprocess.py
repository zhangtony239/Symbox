"""End-to-end public relation-command surface tests."""

from __future__ import annotations

import json
import subprocess
import sys


def test_now_is_public_and_returns_machine_readable_parse() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "now", "robot", "moves", "dock", "speed=2"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result["status"] == "success"
    assert result["data"]["command"] == "now"
    assert result["data"]["parsed"] == {
        "subject": "robot",
        "verb": "moves",
        "args": ["dock"],
        "kwargs": [["speed", 2]],
    }


def test_svo_is_not_a_public_compatibility_command() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "symbox.cli.main", "svo", "robot", "moves", "dock"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "invalid choice" in completed.stderr
