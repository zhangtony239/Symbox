"""Package and command-entry smoke tests."""

import json

import pytest

from symbox import __version__
from symbox.cli.main import main


def test_package_version_matches_v06() -> None:
    assert __version__ == "0.6.0"


def test_command_entry_accepts_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "success"
    assert result["data"] == {"version": "0.6.0"}
