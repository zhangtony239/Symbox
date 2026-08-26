"""The ``sbox`` command entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from symbox import __version__
from symbox.cli.results import ResultEnvelope, ResultStatus


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(prog="sbox", description="Symbox v0.6 CLI")
    parser.add_argument("--version", action="store_true", help="return version information")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line adapter."""
    arguments = build_parser().parse_args(argv)
    data = {"version": __version__} if arguments.version else {"command": "sbox"}
    result = ResultEnvelope(status=ResultStatus.SUCCESS, data=data)
    print(result.to_json())
    return int(result.exit_code)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
