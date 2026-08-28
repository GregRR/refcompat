"""Stream narrow GTF/GFF3 reference-coordinate observations.

The inspector intentionally extracts only facts needed by RCHECK-060. It does
not build gene-model hierarchy, infer aliases, validate biological annotation,
or decide compatibility. GFF3 seqids are percent-decoded for logical namespace
comparison while raw values are retained for traceability.

References:
- Sequence Ontology GFF3 specification:
  https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
- Ensembl GFF/GTF format documentation:
  https://www.ensembl.org/info/website/upload/gff.html
- NCBI GFF3 format notes:
  https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/file-formats/annotation-files/about-ncbi-gff3/
"""

from __future__ import annotations

import gzip
import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationFeatureRecord,
    AnnotationProvenanceClaim,
    AnnotationSequenceUsage,
    Gff3EmbeddedFastaSequence,
    Gff3FastaBoundary,
    Gff3SequenceRegion,
)
from refcompat.model.identity import Md5Digest
from refcompat.model.resources import Resource, ResourceKind

_POSITIVE_INTEGER_RE = re.compile(r"^[0-9]+$")
_GFF3_RAW_SEQID_RE = re.compile(r"^(?:[A-Za-z0-9.:^*$@!+_?\-|]|%[0-9A-Fa-f]{2})+$")
_GFF3_UNESCAPED_SEQID_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.:^*$@!+_?-|"
)
_NCBI_PROVENANCE_KEYS = {
    "genome-build",
    "genome-build-accession",
    "annotation-date",
    "annotation-source",
}
_GTF_HEADER_KEYS = {"description", "provider", "date"}


class AnnotationInspectionError(Exception):
    """Base class for normalized GTF/GFF3 inspection failures."""


class UnsupportedAnnotationResourceError(AnnotationInspectionError):
    """The requested operation does not apply to the supplied resource kind."""


class AnnotationUnreadableError(AnnotationInspectionError):
    """The supplied annotation cannot be read locally."""


class AnnotationParseError(AnnotationInspectionError):
    """The supplied annotation cannot be parsed by the narrow RCHECK-060 parser."""


class _Md5Hash(Protocol):
    def update(self, data: bytes) -> None: ...

    def hexdigest(self) -> str: ...


@dataclass(frozen=True, slots=True)
class _GffVersionEvent:
    value: str
    line_number: int


@dataclass(frozen=True, slots=True)
class _SequenceRegionEvent:
    value: Gff3SequenceRegion


@dataclass(frozen=True, slots=True)
class _ProvenanceEvent:
    value: AnnotationProvenanceClaim


@dataclass(frozen=True, slots=True)
class _FastaBoundaryEvent:
    value: Gff3FastaBoundary


_AnnotationEvent: TypeAlias = (
    AnnotationFeatureRecord
    | _GffVersionEvent
    | _SequenceRegionEvent
    | _ProvenanceEvent
    | _FastaBoundaryEvent
)


@dataclass(slots=True)
class _UsageAccumulator:
    first_raw_sequence_name: str
    has_multiple_raw_sequence_names: bool
    feature_count: int
    minimum_start: int
    maximum_end: int
    first_feature_line: int
    circular_feature_count: int
    first_circular_feature_line: int | None
    circular_landmark_candidate_count: int
    first_circular_landmark_start: int | None
    first_circular_landmark_end: int | None
    first_circular_landmark_line: int | None


def inspect_annotation_context(resource: Resource) -> AnnotationContextSnapshot:
    """Stream one GTF/GFF3 and summarize reference-relevant observations."""

    _require_annotation_kind(resource)

    feature_count = 0
    usage: dict[str, _UsageAccumulator] = {}
    sequence_regions: list[Gff3SequenceRegion] = []
    sequence_region_names: set[str] = set()
    provenance_claims: list[AnnotationProvenanceClaim] = []
    gff_version: str | None = None
    fasta_boundary: Gff3FastaBoundary | None = None

    for event in _iter_annotation_events(resource):
        if isinstance(event, AnnotationFeatureRecord):
            feature_count += 1
            accumulator = usage.get(event.sequence_name)
            if accumulator is None:
                usage[event.sequence_name] = _UsageAccumulator(
                    first_raw_sequence_name=event.raw_sequence_name,
                    has_multiple_raw_sequence_names=False,
                    feature_count=1,
                    minimum_start=event.start,
                    maximum_end=event.end,
                    first_feature_line=event.line_number,
                    circular_feature_count=1 if event.is_circular else 0,
                    first_circular_feature_line=event.line_number if event.is_circular else None,
                    circular_landmark_candidate_count=(
                        1 if _is_circular_landmark_candidate(event) else 0
                    ),
                    first_circular_landmark_start=(
                        event.start if _is_circular_landmark_candidate(event) else None
                    ),
                    first_circular_landmark_end=(
                        event.end if _is_circular_landmark_candidate(event) else None
                    ),
                    first_circular_landmark_line=(
                        event.line_number if _is_circular_landmark_candidate(event) else None
                    ),
                )
            else:
                accumulator.feature_count += 1
                accumulator.minimum_start = min(accumulator.minimum_start, event.start)
                accumulator.maximum_end = max(accumulator.maximum_end, event.end)
                if event.raw_sequence_name != accumulator.first_raw_sequence_name:
                    accumulator.has_multiple_raw_sequence_names = True
                if event.is_circular:
                    accumulator.circular_feature_count += 1
                    if accumulator.first_circular_feature_line is None:
                        accumulator.first_circular_feature_line = event.line_number
                if _is_circular_landmark_candidate(event):
                    accumulator.circular_landmark_candidate_count += 1
                    if accumulator.first_circular_landmark_line is None:
                        accumulator.first_circular_landmark_start = event.start
                        accumulator.first_circular_landmark_end = event.end
                        accumulator.first_circular_landmark_line = event.line_number
            continue

        if isinstance(event, _GffVersionEvent):
            if gff_version is None:
                gff_version = event.value
        elif isinstance(event, _SequenceRegionEvent):
            if event.value.sequence_name in sequence_region_names:
                raise AnnotationParseError(
                    "duplicate GFF3 sequence-region seqid "
                    f"{event.value.sequence_name!r} at line {event.value.line_number}: "
                    f"{resource.artifact.path}"
                )
            sequence_region_names.add(event.value.sequence_name)
            sequence_regions.append(event.value)
        elif isinstance(event, _ProvenanceEvent):
            provenance_claims.append(event.value)
        else:
            fasta_boundary = event.value

    sequence_usage = tuple(
        AnnotationSequenceUsage(
            sequence_name=sequence_name,
            first_raw_sequence_name=accumulator.first_raw_sequence_name,
            feature_count=accumulator.feature_count,
            minimum_start=accumulator.minimum_start,
            maximum_end=accumulator.maximum_end,
            first_feature_line=accumulator.first_feature_line,
            has_multiple_raw_sequence_names=accumulator.has_multiple_raw_sequence_names,
            circular_feature_count=accumulator.circular_feature_count,
            first_circular_feature_line=accumulator.first_circular_feature_line,
            circular_landmark_candidate_count=accumulator.circular_landmark_candidate_count,
            first_circular_landmark_start=accumulator.first_circular_landmark_start,
            first_circular_landmark_end=accumulator.first_circular_landmark_end,
            first_circular_landmark_line=accumulator.first_circular_landmark_line,
        )
        for sequence_name, accumulator in usage.items()
    )
    return AnnotationContextSnapshot(
        resource_id=resource.id,
        resource_kind=resource.kind,
        feature_count=feature_count,
        sequence_usage=sequence_usage,
        gff_version=gff_version,
        sequence_regions=tuple(sequence_regions),
        provenance_claims=tuple(provenance_claims),
        fasta_boundary=fasta_boundary,
        embedded_fasta_sequences=(
            _inspect_embedded_fasta(resource, fasta_boundary) if fasta_boundary is not None else ()
        ),
    )


def _inspect_embedded_fasta(
    resource: Resource,
    boundary: Gff3FastaBoundary,
) -> tuple[Gff3EmbeddedFastaSequence, ...]:
    """Summarize embedded GFF3 FASTA sequence content without materializing bases."""

    if resource.kind is not ResourceKind.GFF3:
        raise AnnotationParseError("embedded FASTA is only valid for GFF3")

    sequences: list[Gff3EmbeddedFastaSequence] = []
    seen_names: set[str] = set()
    current_name: str | None = None
    current_header_line: int | None = None
    current_length = 0
    current_md5: _Md5Hash | None = None
    in_fasta = False

    def finish_current() -> None:
        nonlocal current_name, current_header_line, current_length, current_md5
        if current_name is None:
            return
        assert current_header_line is not None
        assert current_md5 is not None
        if current_length == 0:
            raise AnnotationParseError(
                f"embedded GFF3 FASTA sequence {current_name!r} has no sequence content "
                f"after header line {current_header_line}: {resource.artifact.path}"
            )
        digest = current_md5.hexdigest()
        sequences.append(
            Gff3EmbeddedFastaSequence(
                sequence_name=current_name,
                length=current_length,
                md5=Md5Digest(digest),
                header_line=current_header_line,
            )
        )
        current_name = None
        current_header_line = None
        current_length = 0
        current_md5 = None

    for line_number, line in _iter_source_lines(resource.artifact.path):
        if line_number < boundary.line_number:
            continue
        if line_number == boundary.line_number and boundary.explicit_directive:
            in_fasta = True
            continue
        if not in_fasta:
            in_fasta = True

        if not line:
            continue
        if line.startswith("#"):
            raise AnnotationParseError(
                f"GFF3 content after FASTA boundary is not FASTA at line {line_number}: "
                f"{resource.artifact.path}"
            )
        if line.startswith(";"):
            raise AnnotationParseError(
                f"GFF3 embedded FASTA uses unsupported semicolon-comment syntax "
                f"at line {line_number}: {resource.artifact.path}"
            )
        if line.startswith(">"):
            finish_current()
            body = line[1:].strip()
            if not body:
                raise AnnotationParseError(
                    f"embedded GFF3 FASTA header has no identifier at line {line_number}: "
                    f"{resource.artifact.path}"
                )
            sequence_name = body.split(maxsplit=1)[0]
            if sequence_name in seen_names:
                raise AnnotationParseError(
                    f"embedded GFF3 FASTA has duplicate sequence identifier {sequence_name!r} "
                    f"at line {line_number}: {resource.artifact.path}"
                )
            seen_names.add(sequence_name)
            current_name = sequence_name
            current_header_line = line_number
            current_length = 0
            current_md5 = hashlib.md5(usedforsecurity=False)
            continue
        if current_name is None:
            raise AnnotationParseError(
                f"embedded GFF3 FASTA sequence data precedes a header at line {line_number}: "
                f"{resource.artifact.path}"
            )
        try:
            raw = line.encode("ascii")
        except UnicodeEncodeError as exc:
            raise AnnotationParseError(
                f"embedded GFF3 FASTA sequence is not ASCII at line {line_number}: "
                f"{resource.artifact.path}"
            ) from exc
        canonical = bytes(
            byte - 32 if 97 <= byte <= 122 else byte
            for byte in raw
            if 65 <= byte <= 90 or 97 <= byte <= 122
        )
        assert current_md5 is not None
        current_md5.update(canonical)
        current_length += len(canonical)

    finish_current()
    if not sequences:
        raise AnnotationParseError(
            f"GFF3 FASTA boundary is not followed by a sequence record: {resource.artifact.path}"
        )
    return tuple(sequences)


def iter_annotation_features(resource: Resource) -> Iterator[AnnotationFeatureRecord]:
    """Yield reference-relevant annotation feature fields in file order."""

    _require_annotation_kind(resource)
    for event in _iter_annotation_events(resource):
        if isinstance(event, AnnotationFeatureRecord):
            yield event


def _iter_annotation_events(resource: Resource) -> Iterator[_AnnotationEvent]:
    path = resource.artifact.path
    feature_ordinal = 0

    for line_number, line in _iter_source_lines(path):
        if not line:
            continue

        if resource.kind is ResourceKind.GFF3:
            if line == "##FASTA":
                yield _FastaBoundaryEvent(
                    Gff3FastaBoundary(line_number=line_number, explicit_directive=True)
                )
                return
            if line.startswith(">"):
                yield _FastaBoundaryEvent(
                    Gff3FastaBoundary(line_number=line_number, explicit_directive=False)
                )
                return

        provenance = _parse_provenance_line(line, line_number=line_number, kind=resource.kind)
        if provenance is not None:
            yield _ProvenanceEvent(provenance)
            continue

        if line.startswith("#"):
            event = (
                _parse_gff3_directive(line, line_number=line_number, path=path)
                if resource.kind is ResourceKind.GFF3
                else None
            )
            if event is not None:
                yield event
            continue

        if "\t" not in line and (line.startswith("track ") or line.startswith("browser ")):
            continue

        feature = _parse_feature_line(
            line,
            resource=resource,
            ordinal=feature_ordinal,
            line_number=line_number,
        )
        yield feature
        feature_ordinal += 1


def _iter_source_lines(path: Path) -> Iterator[tuple[int, str]]:
    try:
        with path.open("rb") as stream:
            magic = stream.read(2)
    except OSError as exc:
        raise AnnotationUnreadableError(f"cannot read annotation: {path}") from exc

    try:
        if magic == b"\x1f\x8b":
            with gzip.open(path, mode="rt", encoding="utf-8", newline=None) as text_stream:
                for line_number, raw_line in enumerate(text_stream, start=1):
                    yield line_number, raw_line.rstrip("\r\n")
        else:
            with path.open(mode="rt", encoding="utf-8", newline=None) as text_stream:
                for line_number, raw_line in enumerate(text_stream, start=1):
                    yield line_number, raw_line.rstrip("\r\n")
    except UnicodeDecodeError as exc:
        raise AnnotationParseError(f"annotation is not valid UTF-8: {path}") from exc
    except (gzip.BadGzipFile, EOFError) as exc:
        raise AnnotationParseError(f"annotation gzip stream is invalid: {path}") from exc
    except OSError as exc:
        raise AnnotationUnreadableError(f"cannot read annotation: {path}") from exc


def _parse_feature_line(
    line: str, *, resource: Resource, ordinal: int, line_number: int
) -> AnnotationFeatureRecord:
    fields = line.split("\t")
    if len(fields) != 9:
        raise AnnotationParseError(
            f"annotation feature requires 9 tab-separated fields at line {line_number}: "
            f"{resource.artifact.path}"
        )

    raw_sequence_name = fields[0]
    feature_type = fields[2]
    if not raw_sequence_name:
        raise AnnotationParseError(
            f"annotation feature seqid is empty at line {line_number}: {resource.artifact.path}"
        )
    if not feature_type:
        raise AnnotationParseError(
            f"annotation feature type is empty at line {line_number}: {resource.artifact.path}"
        )

    if resource.kind is ResourceKind.GFF3:
        sequence_name = _decode_gff3_seqid(
            raw_sequence_name, line_number=line_number, path=resource.artifact.path
        )
        is_circular = _has_gff3_is_circular_true(fields[8])
        feature_id = (
            _gff3_feature_id(fields[8], line_number=line_number, path=resource.artifact.path)
            if is_circular
            else None
        )
    else:
        sequence_name = raw_sequence_name
        is_circular = False
        feature_id = None

    start = _parse_positive_integer(
        fields[3], field="start", line_number=line_number, path=resource.artifact.path
    )
    end = _parse_positive_integer(
        fields[4], field="end", line_number=line_number, path=resource.artifact.path
    )
    if start > end:
        raise AnnotationParseError(
            f"annotation feature start exceeds end at line {line_number}: {resource.artifact.path}"
        )

    return AnnotationFeatureRecord(
        resource_id=resource.id,
        ordinal=ordinal,
        line_number=line_number,
        raw_sequence_name=raw_sequence_name,
        sequence_name=sequence_name,
        feature_type=feature_type,
        start=start,
        end=end,
        is_circular=is_circular,
        feature_id=feature_id,
    )


def _parse_gff3_directive(
    line: str, *, line_number: int, path: Path
) -> _GffVersionEvent | _SequenceRegionEvent | None:
    if line == "##gff-version" or line.startswith("##gff-version "):
        parts = line.split()
        if (
            len(parts) != 2
            or parts[0] != "##gff-version"
            or parts[1].split(".", maxsplit=1)[0] != "3"
        ):
            raise AnnotationParseError(
                f"invalid GFF3 gff-version directive at line {line_number}: {path}"
            )
        return _GffVersionEvent(value=parts[1], line_number=line_number)

    if line == "##sequence-region" or line.startswith("##sequence-region "):
        parts = line.split()
        if len(parts) != 4 or parts[0] != "##sequence-region":
            raise AnnotationParseError(
                f"invalid GFF3 sequence-region directive at line {line_number}: {path}"
            )
        raw_sequence_name = parts[1]
        sequence_name = _decode_gff3_seqid(raw_sequence_name, line_number=line_number, path=path)
        start = _parse_positive_integer(
            parts[2], field="sequence-region start", line_number=line_number, path=path
        )
        end = _parse_positive_integer(
            parts[3], field="sequence-region end", line_number=line_number, path=path
        )
        if start > end:
            raise AnnotationParseError(
                f"GFF3 sequence-region start exceeds end at line {line_number}: {path}"
            )
        return _SequenceRegionEvent(
            Gff3SequenceRegion(
                raw_sequence_name=raw_sequence_name,
                sequence_name=sequence_name,
                start=start,
                end=end,
                line_number=line_number,
            )
        )

    return None


def _parse_provenance_line(
    line: str, *, line_number: int, kind: ResourceKind
) -> AnnotationProvenanceClaim | None:
    if line.startswith("##species ") and kind is ResourceKind.GFF3:
        return _provenance_claim("##species", line[len("##species ") :], line_number)
    if line.startswith("##genome-build ") and kind is ResourceKind.GFF3:
        return _provenance_claim("##genome-build", line[len("##genome-build ") :], line_number)

    if line.startswith("#!"):
        body = line[2:]
        key, separator, value = body.partition(" ")
        if separator and key in _NCBI_PROVENANCE_KEYS:
            return _provenance_claim(f"#!{key}", value, line_number)

    if kind is ResourceKind.GTF and line.startswith("##"):
        body = line[2:]
        key, separator, value = body.partition(":")
        normalized_key = key.strip().lower()
        if separator and normalized_key in _GTF_HEADER_KEYS:
            return _provenance_claim(f"##{normalized_key}", value.strip(), line_number)

    return None


def _provenance_claim(name: str, value: str, line_number: int) -> AnnotationProvenanceClaim | None:
    value = value.strip()
    if not value:
        return None
    return AnnotationProvenanceClaim(name=name, value=value, line_number=line_number)


def _decode_gff3_seqid(raw_value: str, *, line_number: int, path: Path) -> str:
    if _GFF3_RAW_SEQID_RE.fullmatch(raw_value) is None:
        raise AnnotationParseError(f"invalid GFF3 seqid escaping at line {line_number}: {path}")

    decoded_bytes = bytearray()
    index = 0
    while index < len(raw_value):
        if raw_value[index] == "%":
            encoded_byte = int(raw_value[index + 1 : index + 3], 16)
            if encoded_byte in _GFF3_UNESCAPED_SEQID_BYTES:
                raise AnnotationParseError(
                    "GFF3 seqid percent-encodes a character that must remain unescaped "
                    f"at line {line_number}: {path}"
                )
            decoded_bytes.append(encoded_byte)
            index += 3
        else:
            decoded_bytes.append(ord(raw_value[index]))
            index += 1

    try:
        value = bytes(decoded_bytes).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AnnotationParseError(
            f"GFF3 seqid percent-encoding is not valid UTF-8 at line {line_number}: {path}"
        ) from exc
    if not value:
        raise AnnotationParseError(f"GFF3 seqid is empty at line {line_number}: {path}")
    return value


def _parse_positive_integer(value: str, *, field: str, line_number: int, path: Path) -> int:
    if _POSITIVE_INTEGER_RE.fullmatch(value) is None:
        raise AnnotationParseError(
            f"annotation {field} is not a positive integer at line {line_number}: {path}"
        )
    parsed = int(value, 10)
    if parsed < 1:
        raise AnnotationParseError(
            f"annotation {field} is not a positive integer at line {line_number}: {path}"
        )
    return parsed


def _has_gff3_is_circular_true(attributes: str) -> bool:
    return "Is_circular=true" in attributes.split(";")


def _gff3_feature_id(attributes: str, *, line_number: int, path: Path) -> str | None:
    raw_id: str | None = None
    for item in attributes.split(";"):
        key, separator, value = item.partition("=")
        if not separator or key != "ID":
            continue
        if raw_id is not None:
            raise AnnotationParseError(f"duplicate GFF3 ID attribute at line {line_number}: {path}")
        raw_id = value
    if raw_id is None:
        return None
    if not raw_id:
        raise AnnotationParseError(f"empty GFF3 ID attribute at line {line_number}: {path}")
    return _decode_gff3_attribute_value(raw_id, line_number=line_number, path=path)


def _decode_gff3_attribute_value(raw_value: str, *, line_number: int, path: Path) -> str:
    decoded_bytes = bytearray()
    index = 0
    while index < len(raw_value):
        character = raw_value[index]
        if character == "%":
            if index + 2 >= len(raw_value) or not all(
                value in "0123456789abcdefABCDEF" for value in raw_value[index + 1 : index + 3]
            ):
                raise AnnotationParseError(
                    f"invalid GFF3 attribute escaping at line {line_number}: {path}"
                )
            encoded_byte = int(raw_value[index + 1 : index + 3], 16)
            if not (
                encoded_byte <= 0x1F
                or encoded_byte == 0x7F
                or encoded_byte in {0x25, 0x26, 0x2C, 0x3B, 0x3D}
            ):
                raise AnnotationParseError(
                    f"unnecessary GFF3 attribute percent-encoding at line {line_number}: {path}"
                )
            decoded_bytes.append(encoded_byte)
            index += 3
            continue
        if character in ",&=":
            raise AnnotationParseError(
                f"unescaped reserved GFF3 attribute character at line {line_number}: {path}"
            )
        decoded_bytes.extend(character.encode("utf-8"))
        index += 1
    try:
        return bytes(decoded_bytes).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AnnotationParseError(
            f"GFF3 attribute percent-encoding is not valid UTF-8 at line {line_number}: {path}"
        ) from exc


def _is_circular_landmark_candidate(feature: AnnotationFeatureRecord) -> bool:
    return feature.is_circular and feature.feature_id == feature.sequence_name


def _require_annotation_kind(resource: Resource) -> None:
    if resource.kind not in (ResourceKind.GTF, ResourceKind.GFF3):
        raise UnsupportedAnnotationResourceError(
            "annotation inspection requires a GTF or GFF3 resource"
        )
