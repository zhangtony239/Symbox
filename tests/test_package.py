"""Package and command-entry smoke tests."""

from symbox import __version__
from symbox.cli.main import main


def test_package_version_matches_v06() -> None:
    assert __version__ == "0.6.0"


def test_command_entry_accepts_version(capsys: object) -> None:
    try:
        main(["--version"])
    except SystemExit as error:
        assert error.code == 0

    assert "sbox 0.6.0" in capsys.readouterr().out  # type: ignore[attr-defined]
