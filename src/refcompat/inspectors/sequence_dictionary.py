"""Parse SAM/Picard ``.dict`` files and derive expected records from FASTA identity.

This module extracts dictionary observations. It does not decide top-level
compatibility or convert declared aliases/provenance metadata into verified
relationships. Exact comparison lives in
:mod:`refcompat.reasoning.sequence_dictionary`.

The parser is intentionally narrow: a ``.dict`` may contain an optional ``@HD``
line followed by ``@SQ`` records, with no alignment records or unrelated SAM
header record types. Unknown tags on ``@SQ`` records are accepted and ignored;
standard tags relevant to RefCompat are preserved.

References:
- SAM v1 specification: https://samtools.github.io/hts-specs/SAMv1.pdf
- Picard CreateSequenceDictionary
- samtools dict: https://www.htslib.org/doc/samtools-dict.html
"""

from __future__ import annotations

import re
from pathlib import Path

from refcompat.model.identity import CollectionCompleteness, Md5Digest, SequenceCollectionSnapshot
from refcompat.model.resources import Resource, ResourceKind
from refcompat.model.sequence_dictionary import (
    ExpectedSequenceDictionary,
    MoleculeTopology,
    SequenceDictionaryData,
    SequenceDictionaryRecord,
    SequenceDictionarySnapshot,
)

_HEADER_TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]$")
_SAM_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+$")


class SequenceDictionaryError(Exception):
    """Base class for normalized sequence-dictionary inspection failures."""


class UnsupportedSequenceDictionaryResourceError(SequenceDictionaryError):
    """The requested operation does not apply to the supplied resource kind."""


class SequenceDictionaryUnreadableError(SequenceDictionaryError):
    """A supplied sequence dictionary cannot be read."""


class SequenceDictionaryParseError(SequenceDictionaryError):
    """A supplied ``.dict`` is not a valid narrow SAM sequence dictionary."""


class SequenceDictionaryComputationError(SequenceDictionaryError):
    """Expected dictionary records cannot be formed from the FASTA snapshot."""


def read_sequence_dictionary(resource: Resource) -> SequenceDictionarySnapshot:
    """Parse one supplied SAM/Picard-style ``.dict`` resource."""

    if resource.kind is not ResourceKind.SEQUENCE_DICTIONARY:
        raise UnsupportedSequenceDictionaryResourceError(
            "sequence-dictionary parsing requires a sequence-dictionary resource"
        )

    path = resource.artifact.path
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SequenceDictionaryParseError(
            f"sequence dictionary is not valid UTF-8: {path}"
        ) from exc
    except OSError as exc:
        raise SequenceDictionaryUnreadableError(f"cannot read sequence dictionary: {path}") from exc

    records: list[SequenceDictionaryRecord] = []
    sam_version: str | None = None
    saw_hd = False

    lines = text.splitlines()
    if not lines:
        raise SequenceDictionaryParseError(f"sequence dictionary is empty: {path}")

    for line_number, line in enumerate(lines, start=1):
        if not line:
            raise SequenceDictionaryParseError(
                f"blank sequence-dictionary line at line {line_number}: {path}"
            )
        if not line.startswith("@"):
            raise SequenceDictionaryParseError(
                f"sequence dictionary contains a non-header record at line {line_number}: {path}"
            )

        record_type = line.split("\t", maxsplit=1)[0]
        if record_type == "@HD":
            if saw_hd or line_number != 1:
                raise SequenceDictionaryParseError(
                    f"@HD must appear at most once and as the first line: {path}"
                )
            fields = _parse_header_fields(line, line_number=line_number, path=path)
            version = fields.get("VN")
            if version is None or _SAM_VERSION_RE.fullmatch(version) is None:
                raise SequenceDictionaryParseError(
                    f"@HD requires a valid VN tag at line {line_number}: {path}"
                )
            sam_version = version
            saw_hd = True
            continue

        if record_type != "@SQ":
            raise SequenceDictionaryParseError(
                f"unexpected SAM header record {record_type!r} at line {line_number}: {path}"
            )

        fields = _parse_header_fields(line, line_number=line_number, path=path)
        records.append(_record_from_fields(fields, line_number=line_number, path=path))

    try:
        data = SequenceDictionaryData(records=tuple(records), sam_version=sam_version)
    except ValueError as exc:
        raise SequenceDictionaryParseError(f"invalid sequence dictionary: {path}") from exc

    return SequenceDictionarySnapshot(resource_id=resource.id, data=data)


def expected_sequence_dictionary_from_snapshot(
    snapshot: SequenceCollectionSnapshot,
) -> ExpectedSequenceDictionary:
    """Build expected ``SN``/``LN``/``M5`` records from a complete FASTA snapshot."""

    if snapshot.completeness is not CollectionCompleteness.COMPLETE:
        raise SequenceDictionaryComputationError(
            "expected FASTA dictionary requires a complete sequence-collection snapshot"
        )
    if not snapshot.sequences:
        raise SequenceDictionaryComputationError(
            "expected FASTA dictionary requires at least one sequence"
        )

    records: list[SequenceDictionaryRecord] = []
    for sequence in snapshot.sequences:
        if sequence.length is None:
            raise SequenceDictionaryComputationError(
                f"FASTA sequence length is unavailable for dictionary record: {sequence.local_name}"
            )
        if sequence.length == 0:
            raise SequenceDictionaryComputationError(
                f"SAM sequence dictionaries cannot represent zero-length FASTA sequence: "
                f"{sequence.local_name}"
            )
        if sequence.md5 is None:
            raise SequenceDictionaryComputationError(
                f"FASTA sequence M5 identity is unavailable for dictionary record: "
                f"{sequence.local_name}"
            )

        try:
            records.append(
                SequenceDictionaryRecord(
                    name=sequence.local_name,
                    length=sequence.length,
                    md5=sequence.md5,
                )
            )
        except ValueError as exc:
            raise SequenceDictionaryComputationError(
                f"FASTA sequence cannot be represented as a SAM dictionary record: "
                f"{sequence.local_name}"
            ) from exc

    try:
        data = SequenceDictionaryData(records=tuple(records))
    except ValueError as exc:
        raise SequenceDictionaryComputationError(
            "FASTA snapshot cannot form an unambiguous SAM sequence dictionary"
        ) from exc

    return ExpectedSequenceDictionary(fasta_resource_id=snapshot.resource_id, data=data)


def _parse_header_fields(line: str, *, line_number: int, path: Path) -> dict[str, str]:
    parts = line.split("\t")
    if len(parts) < 2:
        raise SequenceDictionaryParseError(
            f"SAM header line has no tagged fields at line {line_number}: {path}"
        )

    fields: dict[str, str] = {}
    for raw_field in parts[1:]:
        if len(raw_field) < 4 or raw_field[2] != ":":
            raise SequenceDictionaryParseError(
                f"invalid SAM header field at line {line_number}: {path}"
            )
        tag = raw_field[:2]
        value = raw_field[3:]
        if _HEADER_TAG_RE.fullmatch(tag) is None or not value:
            raise SequenceDictionaryParseError(
                f"invalid SAM header field at line {line_number}: {path}"
            )
        if tag in fields:
            raise SequenceDictionaryParseError(
                f"duplicate SAM header tag {tag} at line {line_number}: {path}"
            )
        fields[tag] = value
    return fields


def _record_from_fields(
    fields: dict[str, str], *, line_number: int, path: Path
) -> SequenceDictionaryRecord:
    name = fields.get("SN")
    raw_length = fields.get("LN")
    if name is None or raw_length is None:
        raise SequenceDictionaryParseError(f"@SQ requires SN and LN at line {line_number}: {path}")

    try:
        length = int(raw_length, 10)
    except ValueError as exc:
        raise SequenceDictionaryParseError(f"invalid @SQ LN at line {line_number}: {path}") from exc

    try:
        md5 = Md5Digest(fields["M5"]) if "M5" in fields else None
        alternate_names = tuple(fields["AN"].split(",")) if "AN" in fields else ()
        topology = MoleculeTopology(fields["TP"]) if "TP" in fields else None
        return SequenceDictionaryRecord(
            name=name,
            length=length,
            md5=md5,
            alternate_names=alternate_names,
            assembly=fields.get("AS"),
            species=fields.get("SP"),
            uri=fields.get("UR"),
            topology=topology,
            alternate_locus=fields.get("AH"),
        )
    except ValueError as exc:
        raise SequenceDictionaryParseError(
            f"invalid @SQ record at line {line_number}: {path}"
        ) from exc
