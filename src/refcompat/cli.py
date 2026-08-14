"""Command-line entry point for RefCompat."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from refcompat import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level command-line parser."""
    parser = argparse.ArgumentParser(
        prog="refcompat",
        description=(
            "Check whether genomic resources can share a coherent reference-coordinate context."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the RefCompat command-line interface."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
