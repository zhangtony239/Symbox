"""The ``sbox`` command entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from symbox import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command parser."""
    parser = argparse.ArgumentParser(prog="sbox", description="Symbox v0.6 CLI")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line adapter."""
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
