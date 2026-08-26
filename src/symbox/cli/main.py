"""The ``sbox`` command entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict

from symbox import __version__
from symbox.cli.now_parser import parse_now_tokens
from symbox.cli.results import ResultEnvelope, ResultStatus


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(prog="sbox", description="Symbox v0.6 CLI")
    parser.add_argument("--version", action="store_true", help="return version information")
    commands = parser.add_subparsers(dest="command")
    now = commands.add_parser("now", help="assert a variable-arity SVK relation")
    now.add_argument("subject")
    now.add_argument("verb")
    now.add_argument("arguments", nargs="*")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line adapter."""
    arguments = build_parser().parse_args(argv)
    data: dict[str, object]
    if arguments.version:
        data = {"version": __version__}
    elif arguments.command == "now":
        parsed = parse_now_tokens(
            (arguments.subject, arguments.verb, *arguments.arguments)
        )
        data = {"command": "now", "parsed": asdict(parsed)}
    else:
        data = {"command": "sbox"}
    result = ResultEnvelope(status=ResultStatus.SUCCESS, data=data)
    print(result.to_json())
    return int(result.exit_code)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
