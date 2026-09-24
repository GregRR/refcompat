"""Stream strict standard BED observations in native coordinates.

The caller supplies an explicit standard layout because BED does not identify
standard-versus-custom columns in-band. The inspector validates local BEDv1
structure and emits RefCompat-owned observations only; it does not infer an
assembly, resolve aliases, inspect a FASTA, or decide compatibility.

Specification:
- GA4GH BED v1: https://samtools.github.io/hts-specs/BEDv1.pdf
"""

from __future__ import annotations

import gzip
import re
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from refcompat.model.bed import (
    BedContextSnapshot,
    BedFeatureRecord,
    BedLayout,
    BedSequenceUsage,
)
from refcompat.model.resources import Resource, ResourceKind

_CHROM_RE = re.compile(r"^[A-Za-z0-9_]{1,255}$")
_UNSIGNED_INTEGER_RE = re.compile(r"^[0-9]+$")
_ITEM_RGB_RE = re.compile(r"^[0-9]+,[0-9]+,[0-9]+$")
_INTEGER_LIST_RE = re.compile(r"^[0-9]+(?:,[0-9]+)*,?$")
_TRACK_LINE_RE = re.compile(r"^(?:track|browser)(?:[ \t]|$)")
_U64_MAX = (1 << 64) - 1


class BedInspectionError(Exception):
    """Base class for normalized BED inspection failures."""


class UnsupportedBedResourceError(BedInspectionError):
    """The requested operation does not apply to the supplied resource kind."""


class UnsupportedBedLayoutError(BedInspectionError):
    """The supplied layout is not an explicit supported standard BED layout."""


class BedUnreadableError(BedInspectionError):
    """The supplied BED resource cannot be read locally."""


class BedParseError(BedInspectionError):
    """The supplied resource is not valid for its declared standard BED layout."""


@dataclass(slots=True)
class _UsageAccumulator:
    feature_count: int
    minimum_start: int
    maximum_end: int
    first_feature_line: int
    zero_length_feature_count: int


def inspect_bed_context(resource: Resource, layout: BedLayout) -> BedContextSnapshot:
    """Stream one BED resource and summarize native coordinate observations."""

    _require_bed_resource(resource)
    _require_bed_layout(layout)

    feature_count = 0
    usage: dict[str, _UsageAccumulator] = {}
    for feature in iter_bed_features(resource, layout):
        feature_count += 1
        accumulator = usage.get(feature.chrom)
        if accumulator is None:
            usage[feature.chrom] = _UsageAccumulator(
                feature_count=1,
                minimum_start=feature.chrom_start,
                maximum_end=feature.chrom_end,
                first_feature_line=feature.line_number,
                zero_length_feature_count=1 if feature.is_zero_length else 0,
            )
        else:
            accumulator.feature_count += 1
            accumulator.minimum_start = min(accumulator.minimum_start, feature.chrom_start)
            accumulator.maximum_end = max(accumulator.maximum_end, feature.chrom_end)
            if feature.is_zero_length:
                accumulator.zero_length_feature_count += 1

    sequence_usage = tuple(
        BedSequenceUsage(
            chrom=chrom,
            feature_count=accumulator.feature_count,
            minimum_start=accumulator.minimum_start,
            maximum_end=accumulator.maximum_end,
            first_feature_line=accumulator.first_feature_line,
            zero_length_feature_count=accumulator.zero_length_feature_count,
        )
        for chrom, accumulator in usage.items()
    )
    return BedContextSnapshot(
        resource_id=resource.id,
        resource_kind=resource.kind,
        layout=layout,
        feature_count=feature_count,
        sequence_usage=sequence_usage,
    )


def iter_bed_features(resource: Resource, layout: BedLayout) -> Iterator[BedFeatureRecord]:
    """Yield strictly parsed BED features in source order."""

    _require_bed_resource(resource)
    _require_bed_layout(layout)

    ordinal = 0
    for line_number, line in _iter_source_lines(resource.artifact.path):
        _validate_line_characters(line, line_number=line_number, path=resource.artifact.path)
        if not line.strip(" \t") or line.startswith("#"):
            continue
        if _TRACK_LINE_RE.match(line) is not None:
            raise BedParseError(
                f"BED track/browser line is not valid BED input at line {line_number}: "
                f"{resource.artifact.path}"
            )
        yield _parse_feature_line(
            line,
            resource=resource,
            layout=layout,
            ordinal=ordinal,
            line_number=line_number,
        )
        ordinal += 1


def _iter_source_lines(path: Path) -> Iterator[tuple[int, str]]:
    try:
        with path.open("rb") as stream:
            magic = stream.read(2)
    except OSError as exc:
        raise BedUnreadableError(f"cannot read BED resource: {path}") from exc

    try:
        if magic == b"\x1f\x8b":
            with gzip.open(path, mode="rt", encoding="ascii", newline=None) as text_stream:
                for line_number, raw_line in enumerate(text_stream, start=1):
                    yield line_number, raw_line.rstrip("\r\n")
        else:
            with path.open(mode="rt", encoding="ascii", newline=None) as text_stream:
                for line_number, raw_line in enumerate(text_stream, start=1):
                    yield line_number, raw_line.rstrip("\r\n")
    except UnicodeDecodeError as exc:
        raise BedParseError(f"BED resource is not 7-bit ASCII: {path}") from exc
    except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
        raise BedParseError(f"BED gzip stream is invalid: {path}") from exc
    except OSError as exc:
        raise BedUnreadableError(f"cannot read BED resource: {path}") from exc


def _parse_feature_line(
    line: str,
    *,
    resource: Resource,
    layout: BedLayout,
    ordinal: int,
    line_number: int,
) -> BedFeatureRecord:
    path = resource.artifact.path
    fields = _split_fields(line, layout=layout, line_number=line_number, path=path)

    chrom = fields[0]
    if _CHROM_RE.fullmatch(chrom) is None:
        raise BedParseError(
            f"BED chrom must contain 1-255 ASCII letters, digits, or underscores "
            f"at line {line_number}: {path}"
        )
    chrom_start = _parse_u64(fields[1], field="chromStart", line_number=line_number, path=path)
    chrom_end = _parse_u64(fields[2], field="chromEnd", line_number=line_number, path=path)
    if chrom_start > chrom_end:
        raise BedParseError(f"BED chromStart exceeds chromEnd at line {line_number}: {path}")

    if layout.field_count >= 4:
        name = fields[3]
        if not 1 <= len(name) <= 255:
            raise BedParseError(
                f"BED name must contain 1-255 characters at line {line_number}: {path}"
            )
    if layout.field_count >= 5:
        score = _parse_u64(fields[4], field="score", line_number=line_number, path=path)
        if score > 1000:
            raise BedParseError(f"BED score exceeds 1000 at line {line_number}: {path}")
    if layout.field_count >= 6 and fields[5] not in {"+", "-", "."}:
        raise BedParseError(f"BED strand must be '+', '-', or '.' at line {line_number}: {path}")

    thick_start: int | None = None
    thick_end: int | None = None
    if layout.field_count >= 7:
        thick_start = _parse_u64(fields[6], field="thickStart", line_number=line_number, path=path)
        if not chrom_start <= thick_start <= chrom_end:
            raise BedParseError(
                f"BED thickStart lies outside the feature at line {line_number}: {path}"
            )
    if layout.field_count >= 8:
        assert thick_start is not None
        thick_end = _parse_u64(fields[7], field="thickEnd", line_number=line_number, path=path)
        if not thick_start <= thick_end <= chrom_end:
            raise BedParseError(
                f"BED thickEnd lies before thickStart or outside the feature "
                f"at line {line_number}: {path}"
            )
    if layout.field_count >= 9:
        _validate_item_rgb(fields[8], line_number=line_number, path=path)

    block_sizes: tuple[int, ...] = ()
    block_starts: tuple[int, ...] = ()
    if layout is BedLayout.BED12:
        block_count = _parse_u64(fields[9], field="blockCount", line_number=line_number, path=path)
        if block_count == 0:
            raise BedParseError(f"BED blockCount must be positive at line {line_number}: {path}")
        span = chrom_end - chrom_start
        if block_count > span:
            raise BedParseError(
                f"BED blockCount exceeds feature length at line {line_number}: {path}"
            )
        block_sizes = _parse_integer_list(
            fields[10], field="blockSizes", line_number=line_number, path=path
        )
        block_starts = _parse_integer_list(
            fields[11], field="blockStarts", line_number=line_number, path=path
        )
        if len(block_sizes) != block_count or len(block_starts) != block_count:
            raise BedParseError(
                f"BED block list lengths do not match blockCount at line {line_number}: {path}"
            )
        _validate_blocks(
            block_sizes,
            block_starts,
            span=span,
            line_number=line_number,
            path=path,
        )

    return BedFeatureRecord(
        resource_id=resource.id,
        ordinal=ordinal,
        line_number=line_number,
        chrom=chrom,
        chrom_start=chrom_start,
        chrom_end=chrom_end,
        thick_start=thick_start,
        thick_end=thick_end,
        block_sizes=block_sizes,
        block_starts=block_starts,
    )


def _split_fields(line: str, *, layout: BedLayout, line_number: int, path: Path) -> list[str]:
    if line.startswith((" ", "\t")) or line.endswith((" ", "\t")):
        raise BedParseError(
            f"BED data line has leading or trailing horizontal whitespace "
            f"at line {line_number}: {path}"
        )

    if line.count("\t") == layout.field_count - 1:
        fields = line.split("\t")
    else:
        fields = re.split(r"[ \t]+", line)
    if len(fields) != layout.field_count or any(field == "" for field in fields):
        raise BedParseError(
            f"BED data line requires exactly {layout.field_count} fields for {layout.value} "
            f"at line {line_number}: {path}"
        )
    return fields


def _validate_line_characters(line: str, *, line_number: int, path: Path) -> None:
    if any(character != "\t" and not 0x20 <= ord(character) <= 0x7E for character in line):
        raise BedParseError(
            f"BED line contains a non-printable character at line {line_number}: {path}"
        )


def _parse_u64(value: str, *, field: str, line_number: int, path: Path) -> int:
    if _UNSIGNED_INTEGER_RE.fullmatch(value) is None:
        raise BedParseError(f"BED {field} is not an unsigned integer at line {line_number}: {path}")
    normalized = value.lstrip("0") or "0"
    if len(normalized) > 20:
        raise BedParseError(
            f"BED {field} exceeds the unsigned 64-bit range at line {line_number}: {path}"
        )
    parsed = int(normalized, 10)
    if parsed > _U64_MAX:
        raise BedParseError(
            f"BED {field} exceeds the unsigned 64-bit range at line {line_number}: {path}"
        )
    return parsed


def _validate_item_rgb(value: str, *, line_number: int, path: Path) -> None:
    if value == "0":
        return
    if _ITEM_RGB_RE.fullmatch(value) is None:
        raise BedParseError(f"BED itemRgb is invalid at line {line_number}: {path}")
    channels = tuple(
        _parse_u64(channel, field="itemRgb channel", line_number=line_number, path=path)
        for channel in value.split(",")
    )
    if any(channel > 255 for channel in channels):
        raise BedParseError(f"BED itemRgb channel exceeds 255 at line {line_number}: {path}")


def _parse_integer_list(value: str, *, field: str, line_number: int, path: Path) -> tuple[int, ...]:
    if _INTEGER_LIST_RE.fullmatch(value) is None:
        raise BedParseError(f"BED {field} is invalid at line {line_number}: {path}")
    return tuple(
        _parse_u64(item, field=field, line_number=line_number, path=path)
        for item in value.removesuffix(",").split(",")
    )


def _validate_blocks(
    block_sizes: tuple[int, ...],
    block_starts: tuple[int, ...],
    *,
    span: int,
    line_number: int,
    path: Path,
) -> None:
    if block_starts[0] != 0:
        raise BedParseError(
            f"first BED block does not start at chromStart at line {line_number}: {path}"
        )

    previous_end = 0
    for start, size in zip(block_starts, block_sizes, strict=True):
        block_end = start + size
        if start > span or block_end > span:
            raise BedParseError(f"BED block lies outside the feature at line {line_number}: {path}")
        if start < previous_end:
            raise BedParseError(
                f"BED blocks are unordered or overlapping at line {line_number}: {path}"
            )
        previous_end = block_end
    if previous_end != span:
        raise BedParseError(
            f"last BED block does not end at chromEnd at line {line_number}: {path}"
        )


def _require_bed_resource(resource: Resource) -> None:
    if resource.kind is not ResourceKind.BED:
        raise UnsupportedBedResourceError("BED inspection requires a BED resource")


def _require_bed_layout(layout: object) -> None:
    if not isinstance(layout, BedLayout):
        raise UnsupportedBedLayoutError(
            "BED inspection requires an explicit supported BedLayout value"
        )
