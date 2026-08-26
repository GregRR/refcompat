"""Extract BAM/CRAM header reference metadata with pysam.

The adapter copies primitive values out of ``pysam`` objects immediately so
HTSlib-backed provider types do not enter the RefCompat domain model. This slice
is header-only: it does not iterate alignment records and does not require
reference sequence content merely to observe a CRAM header.

References:
- SAM v1 specification: https://samtools.github.io/hts-specs/SAMv1.pdf
- CRAM v3 specification: https://samtools.github.io/hts-specs/CRAMv3.pdf
- pysam AlignmentFile API: https://pysam.readthedocs.io/en/latest/api.html
"""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from refcompat.model.alignment import (
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    AlignmentProgramRecord,
)
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import Resource, ResourceKind
from refcompat.model.sequence_dictionary import MoleculeTopology, SequenceDictionaryRecord

_HEADER_TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]$")


class AlignmentInspectionError(Exception):
    """Base class for normalized BAM/CRAM header-inspection failures."""


class UnsupportedAlignmentResourceError(AlignmentInspectionError):
    """The requested operation does not apply to the supplied resource kind."""


class AlignmentUnreadableError(AlignmentInspectionError):
    """The supplied BAM/CRAM cannot be read locally."""


class AlignmentParseError(AlignmentInspectionError):
    """The supplied artifact cannot be parsed as the declared alignment format."""


class AlignmentProviderIncompatibleError(AlignmentInspectionError):
    """The installed pysam provider exposes an unsupported API/result shape."""


class _AlignmentFile(Protocol):
    text: object
    references: object
    lengths: object
    is_bam: object
    is_cram: object

    def close(self) -> object: ...


class _PysamModule(Protocol):
    __version__: object

    def AlignmentFile(
        self,
        filename: str,
        mode: str,
        *,
        check_sq: bool,
    ) -> _AlignmentFile: ...


def _load_pysam() -> _PysamModule:
    try:
        module = import_module("pysam")
    except ImportError as exc:  # pragma: no cover - required dependency in normal installs
        raise AlignmentProviderIncompatibleError("pysam is not importable") from exc
    return cast(_PysamModule, module)


def inspect_alignment_header(resource: Resource) -> AlignmentHeaderSnapshot:
    """Inspect one BAM/CRAM SAM header without scanning alignment records."""

    if resource.kind not in {ResourceKind.BAM, ResourceKind.CRAM}:
        raise UnsupportedAlignmentResourceError(
            "alignment header inspection requires a BAM or CRAM resource"
        )

    path = resource.artifact.path
    _require_readable(path)
    pysam_module = _load_pysam()
    mode = "rb" if resource.kind is ResourceKind.BAM else "rc"

    try:
        alignment_file = pysam_module.AlignmentFile(str(path), mode, check_sq=False)
    except OSError as exc:
        try:
            _require_readable(path)
        except AlignmentUnreadableError as unreadable:
            raise unreadable from exc
        raise AlignmentParseError(f"cannot parse {resource.kind.value.upper()}: {path}") from exc
    except (AssertionError, NotImplementedError, TypeError, ValueError) as exc:
        raise AlignmentParseError(f"cannot parse {resource.kind.value.upper()}: {path}") from exc

    try:
        _validate_provider_format(alignment_file, resource_kind=resource.kind, path=path)
        header = _header_data(alignment_file, path=path)
    except AlignmentInspectionError:
        raise
    except (AssertionError, NotImplementedError, OSError, TypeError, ValueError) as exc:
        raise AlignmentParseError(f"cannot parse alignment header: {path}") from exc
    finally:
        alignment_file.close()

    return AlignmentHeaderSnapshot(
        resource_id=resource.id,
        resource_kind=resource.kind,
        header=header,
    )


def _require_readable(path: Path) -> None:
    try:
        with path.open("rb"):
            pass
    except OSError as exc:
        raise AlignmentUnreadableError(f"cannot read alignment resource: {path}") from exc


def _validate_provider_format(
    alignment_file: _AlignmentFile,
    *,
    resource_kind: ResourceKind,
    path: Path,
) -> None:
    if not isinstance(alignment_file.is_bam, bool) or not isinstance(alignment_file.is_cram, bool):
        raise AlignmentProviderIncompatibleError(
            f"pysam returned invalid alignment format metadata: {path}"
        )
    if alignment_file.is_bam == alignment_file.is_cram:
        raise AlignmentProviderIncompatibleError(
            f"pysam returned ambiguous alignment format metadata: {path}"
        )

    provider_kind = ResourceKind.BAM if alignment_file.is_bam else ResourceKind.CRAM
    if provider_kind is not resource_kind:
        raise AlignmentParseError(
            f"resource declared as {resource_kind.value.upper()} but provider identified "
            f"{provider_kind.value.upper()}: {path}"
        )


def _header_data(alignment_file: _AlignmentFile, *, path: Path) -> AlignmentHeaderData:
    raw_text = alignment_file.text
    if not isinstance(raw_text, str):
        raise AlignmentProviderIncompatibleError(
            f"pysam returned invalid unparsed alignment header text: {path}"
        )

    hd: dict[str, str] = {}
    sequences: list[SequenceDictionaryRecord] = []
    programs: list[AlignmentProgramRecord] = []
    saw_hd = False

    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        if not line:
            raise AlignmentParseError(f"blank alignment header line at line {line_number}: {path}")
        if not line.startswith("@"):
            raise AlignmentParseError(
                f"alignment header contains non-header text at line {line_number}: {path}"
            )

        record_type = line.split("\t", maxsplit=1)[0]
        if record_type == "@CO":
            continue
        if record_type not in {"@HD", "@SQ", "@RG", "@PG"}:
            raise AlignmentParseError(
                f"unexpected SAM header record {record_type!r} at line {line_number}: {path}"
            )
        if record_type == "@RG":
            continue

        fields = _parse_header_fields(line, line_number=line_number, path=path)
        if record_type == "@HD":
            if saw_hd or line_number != 1:
                raise AlignmentParseError(f"@HD must appear at most once and first: {path}")
            hd = fields
            saw_hd = True
        elif record_type == "@SQ":
            sequences.append(_sequence_record(fields, path=path))
        else:
            programs.append(_program_record(fields, path=path))

    provider_references = _provider_reference_pairs(alignment_file, path=path)
    observed_references = tuple((record.name, record.length) for record in sequences)
    if observed_references:
        if observed_references != provider_references:
            raise AlignmentProviderIncompatibleError(
                f"pysam header text and binary reference dictionary disagree: {path}"
            )
    elif provider_references:
        try:
            sequences.extend(
                SequenceDictionaryRecord(name=name, length=length)
                for name, length in provider_references
            )
        except ValueError as exc:
            raise AlignmentParseError(
                f"invalid binary alignment reference dictionary: {path}"
            ) from exc

    try:
        return AlignmentHeaderData(
            sequences=tuple(sequences),
            sam_version=hd.get("VN"),
            sort_order=hd.get("SO"),
            group_order=hd.get("GO"),
            subsort=hd.get("SS"),
            programs=tuple(programs),
        )
    except ValueError as exc:
        raise AlignmentParseError(f"invalid normalized alignment header: {path}") from exc


def _provider_reference_pairs(
    alignment_file: _AlignmentFile, *, path: Path
) -> tuple[tuple[str, int], ...]:
    references = alignment_file.references
    lengths = alignment_file.lengths
    if not isinstance(references, tuple) or not isinstance(lengths, tuple):
        raise AlignmentProviderIncompatibleError(
            f"pysam returned invalid alignment reference dictionary metadata: {path}"
        )
    if len(references) != len(lengths):
        raise AlignmentProviderIncompatibleError(
            f"pysam returned inconsistent alignment reference dictionary metadata: {path}"
        )

    pairs: list[tuple[str, int]] = []
    for name, length in zip(references, lengths, strict=True):
        if not isinstance(name, str) or not name:
            raise AlignmentProviderIncompatibleError(
                f"pysam returned invalid alignment reference name metadata: {path}"
            )
        if isinstance(length, bool) or not isinstance(length, int):
            raise AlignmentProviderIncompatibleError(
                f"pysam returned invalid alignment reference length metadata: {path}"
            )
        pairs.append((name, length))
    return tuple(pairs)


def _parse_header_fields(line: str, *, line_number: int, path: Path) -> dict[str, str]:
    parts = line.split("\t")
    if len(parts) < 2:
        raise AlignmentParseError(
            f"SAM header line has no tagged fields at line {line_number}: {path}"
        )

    fields: dict[str, str] = {}
    for raw_field in parts[1:]:
        if len(raw_field) < 4 or raw_field[2] != ":":
            raise AlignmentParseError(f"invalid SAM header field at line {line_number}: {path}")
        tag = raw_field[:2]
        value = raw_field[3:]
        if _HEADER_TAG_RE.fullmatch(tag) is None or not value:
            raise AlignmentParseError(f"invalid SAM header field at line {line_number}: {path}")
        if tag in fields:
            raise AlignmentParseError(
                f"duplicate SAM header tag {tag} at line {line_number}: {path}"
            )
        fields[tag] = value
    return fields


def _sequence_record(record: dict[str, str], *, path: Path) -> SequenceDictionaryRecord:
    name = _required_field(record, "SN", record_type="SQ", path=path)
    raw_length = _required_field(record, "LN", record_type="SQ", path=path)
    try:
        length = int(raw_length, 10)
    except ValueError as exc:
        raise AlignmentParseError(f"alignment header declares invalid SQ.LN: {path}") from exc

    md5_value = record.get("M5")
    alternate_names = _alternate_names(record.get("AN"), path=path)
    topology_value = record.get("TP")

    try:
        return SequenceDictionaryRecord(
            name=name,
            length=length,
            md5=Md5Digest(md5_value) if md5_value is not None else None,
            alternate_names=alternate_names,
            assembly=record.get("AS"),
            species=record.get("SP"),
            uri=record.get("UR"),
            topology=MoleculeTopology(topology_value) if topology_value is not None else None,
            alternate_locus=record.get("AH"),
        )
    except ValueError as exc:
        raise AlignmentParseError(f"invalid normalized @SQ record: {path}") from exc


def _program_record(record: dict[str, str], *, path: Path) -> AlignmentProgramRecord:
    try:
        return AlignmentProgramRecord(
            id=_required_field(record, "ID", record_type="PG", path=path),
            name=record.get("PN"),
            command_line=record.get("CL"),
            previous_id=record.get("PP"),
            description=record.get("DS"),
            version=record.get("VN"),
        )
    except ValueError as exc:
        raise AlignmentParseError(f"invalid normalized @PG record: {path}") from exc


def _required_field(record: dict[str, str], tag: str, *, record_type: str, path: Path) -> str:
    value = record.get(tag)
    if value is None:
        raise AlignmentParseError(f"alignment header requires {record_type}.{tag}: {path}")
    return value


def _alternate_names(value: str | None, *, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    names = tuple(value.split(","))
    if any(not name for name in names):
        raise AlignmentParseError(f"alignment header declares invalid SQ.AN: {path}")
    return names
