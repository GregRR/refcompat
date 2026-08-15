"""Command-line entry point for RefCompat."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from refcompat import __version__
from refcompat.identity import Ga4ghRefgetIdentityProvider, ReferenceIdentityError
from refcompat.inspectors.fasta_index import (
    FastaIndexError,
    compute_expected_fasta_index,
    read_fasta_index,
)
from refcompat.inspectors.sequence_dictionary import (
    SequenceDictionaryError,
    expected_sequence_dictionary_from_snapshot,
    read_sequence_dictionary,
)
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.reasoning.fasta_index import evaluate_fasta_index_integrity
from refcompat.reasoning.sequence_dictionary import evaluate_sequence_dictionary_integrity
from refcompat.reporting import (
    fasta_index_integrity_payload,
    render_fasta_index_integrity,
    render_json,
    render_sequence_collection_snapshot,
    render_sequence_dictionary_integrity,
    sequence_collection_snapshot_payload,
    sequence_dictionary_integrity_payload,
)

_OUTPUT_CHOICES = ("human", "json")


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

    subparsers = parser.add_subparsers(dest="command")

    inspect_fasta = subparsers.add_parser(
        "inspect-fasta",
        help="report standards-backed sequence identity for one FASTA",
    )
    inspect_fasta.add_argument("fasta", type=Path)
    _add_output_format(inspect_fasta)

    check_fai = subparsers.add_parser(
        "check-fai",
        help="compare a FASTA with a supplied .fai companion",
    )
    check_fai.add_argument("fasta", type=Path)
    check_fai.add_argument("fai", type=Path)
    _add_output_format(check_fai)

    check_dict = subparsers.add_parser(
        "check-dict",
        help="compare a FASTA with a supplied SAM/Picard .dict companion",
    )
    check_dict.add_argument("fasta", type=Path)
    check_dict.add_argument("dictionary", type=Path)
    _add_output_format(check_dict)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the RefCompat command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "inspect-fasta":
            return _inspect_fasta(args.fasta, output_format=args.format)
        if args.command == "check-fai":
            return _check_fai(args.fasta, args.fai, output_format=args.format)
        if args.command == "check-dict":
            return _check_dict(args.fasta, args.dictionary, output_format=args.format)
    except (ReferenceIdentityError, FastaIndexError, SequenceDictionaryError) as exc:
        print(f"refcompat: error: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")  # pragma: no cover - argparse constrains this


def _inspect_fasta(path: Path, *, output_format: str) -> int:
    fasta = _resource(path, ResourceKind.FASTA)
    snapshot = Ga4ghRefgetIdentityProvider().inspect_fasta(fasta)
    if output_format == "json":
        print(render_json(sequence_collection_snapshot_payload(snapshot)), end="")
    else:
        print(render_sequence_collection_snapshot(snapshot), end="")
    return 0


def _check_fai(fasta_path: Path, fai_path: Path, *, output_format: str) -> int:
    fasta = _resource(fasta_path, ResourceKind.FASTA)
    index = _resource(fai_path, ResourceKind.FASTA_INDEX)
    expected = compute_expected_fasta_index(fasta)
    observed = read_fasta_index(index)
    result = evaluate_fasta_index_integrity(expected=expected, observed=observed)
    if output_format == "json":
        print(render_json(fasta_index_integrity_payload(result)), end="")
    else:
        print(render_fasta_index_integrity(result), end="")
    return 0


def _check_dict(fasta_path: Path, dictionary_path: Path, *, output_format: str) -> int:
    fasta = _resource(fasta_path, ResourceKind.FASTA)
    dictionary = _resource(dictionary_path, ResourceKind.SEQUENCE_DICTIONARY)
    snapshot = Ga4ghRefgetIdentityProvider().inspect_fasta(fasta)
    expected = expected_sequence_dictionary_from_snapshot(snapshot)
    observed = read_sequence_dictionary(dictionary)
    result = evaluate_sequence_dictionary_integrity(expected=expected, observed=observed)
    if output_format == "json":
        print(render_json(sequence_dictionary_integrity_payload(result)), end="")
    else:
        print(render_sequence_dictionary_integrity(result), end="")
    return 0


def _resource(path: Path, kind: ResourceKind) -> Resource:
    return Resource(
        id=ResourceId(str(path)),
        kind=kind,
        artifact=ArtifactIdentity(path),
        display_name=path.name,
    )


def _add_output_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=_OUTPUT_CHOICES,
        default="human",
        help="diagnostic output format (default: human)",
    )
