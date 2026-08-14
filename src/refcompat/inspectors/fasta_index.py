"""Read supplied FASTA indexes and compute expected FAI geometry.

Parsing a supplied ``.fai`` and computing the geometry implied by the FASTA are
inspection/extraction operations. They do not decide compatibility. Exact
comparison is performed by :mod:`refcompat.reasoning.fasta_index`.

The observed parser follows HTSlib's five-column FASTA FAI format. Expected
geometry is delegated to the public ``refget.compute_fai`` API (backed by
``gtars`` in refget 0.12.x) and copied immediately into RefCompat-owned values.

References:
- HTSlib faidx(5): https://www.htslib.org/doc/faidx.html
- gtars/refget compute_fai API: https://docs.bedbase.org/gtars/python/refget-api/
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from os import PathLike
from pathlib import Path
from typing import Protocol, cast

from refcompat.model.fasta_index import (
    ComputedFastaIndex,
    FastaIndexData,
    FastaIndexRecord,
    FastaIndexSnapshot,
)
from refcompat.model.resources import Resource, ResourceKind


class FastaIndexError(Exception):
    """Base class for normalized FASTA-index inspection failures."""


class UnsupportedFastaIndexResourceError(FastaIndexError):
    """The requested FAI operation does not apply to the supplied resource kind."""


class UnsupportedFastaIndexRepresentationError(FastaIndexError):
    """The FASTA representation cannot yet be verified by the local FAI calculator."""


class FastaIndexUnreadableError(FastaIndexError):
    """A required FASTA or FAI artifact cannot be read."""


class FastaIndexParseError(FastaIndexError):
    """A supplied ``.fai`` is not a valid five-column FASTA index."""


class FastaIndexComputationError(FastaIndexError):
    """Expected FAI geometry could not be computed from the supplied FASTA."""


class FastaIndexProviderIncompatibleError(FastaIndexError):
    """The installed refget provider returned an unsupported FAI result shape."""


class _ExternalFaiMetadata(Protocol):
    offset: object
    line_bases: object
    line_bytes: object


class _ExternalFaiRecord(Protocol):
    name: object
    length: object
    fai: _ExternalFaiMetadata | None


class _RefgetFaiModule(Protocol):
    def compute_fai(self, fasta: str | PathLike[str]) -> object: ...


@dataclass(frozen=True, slots=True)
class _FaiValues:
    name: str
    length: int
    offset: int
    line_bases: int
    line_bytes: int


def _load_refget_fai() -> _RefgetFaiModule:
    try:
        module = import_module("refget")
    except ImportError as exc:  # pragma: no cover - required dependency in normal installs
        raise FastaIndexProviderIncompatibleError("refget is not importable") from exc
    return cast(_RefgetFaiModule, module)


def read_fasta_index(resource: Resource) -> FastaIndexSnapshot:
    """Parse a supplied five-column FASTA ``.fai`` without interpreting compatibility."""

    if resource.kind is not ResourceKind.FASTA_INDEX:
        raise UnsupportedFastaIndexResourceError(
            f"FAI inspection requires a FASTA_INDEX resource, got {resource.kind.value}"
        )

    path = resource.artifact.path
    records: list[FastaIndexRecord] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                records.append(_parse_fai_line(raw_line, line_number=line_number, path=path))
    except OSError as exc:
        raise FastaIndexUnreadableError(f"cannot read FASTA index: {path}") from exc
    except UnicodeError as exc:
        raise FastaIndexParseError(f"FASTA index is not valid UTF-8 text: {path}") from exc

    if not records:
        raise FastaIndexParseError(f"FASTA index contains no records: {path}")

    try:
        return FastaIndexSnapshot(
            resource_id=resource.id,
            data=FastaIndexData(tuple(records)),
        )
    except ValueError as exc:
        raise FastaIndexParseError(f"invalid FASTA index structure: {path}") from exc


def compute_expected_fasta_index(resource: Resource) -> ComputedFastaIndex:
    """Compute exact FAI geometry for an uncompressed FASTA using refget 0.12.x."""

    if resource.kind is not ResourceKind.FASTA:
        raise UnsupportedFastaIndexResourceError(
            f"FAI computation requires a FASTA resource, got {resource.kind.value}"
        )

    path = resource.artifact.path
    if _preflight_is_gzip_stream(path):
        # HTSlib can index BGZF FASTA with an accompanying .gzi, but refget
        # 0.12's compute_fai API explicitly supports uncompressed FASTA only.
        # Do not pretend that an ordinary gzip/BGZF layout has been verified.
        raise UnsupportedFastaIndexRepresentationError(
            f"FAI geometry computation currently requires uncompressed FASTA: {path}"
        )

    refget = _load_refget_fai()

    try:
        external = cast(Sequence[_ExternalFaiRecord], refget.compute_fai(path))
    except OSError as exc:
        if not _is_readable_file(path):
            raise FastaIndexUnreadableError(f"cannot read FASTA: {path}") from exc
        raise FastaIndexComputationError(f"cannot compute FASTA index geometry: {path}") from exc
    except (AttributeError, TypeError) as exc:
        raise FastaIndexProviderIncompatibleError(
            "installed refget does not expose a compatible compute_fai API"
        ) from exc

    values = _extract_external_values(external)
    _validate_computed_values(values, path)
    try:
        return ComputedFastaIndex(
            fasta_resource_id=resource.id,
            data=FastaIndexData(tuple(_record_from_values(value) for value in values)),
        )
    except ValueError as exc:
        # The provider shape/types were already validated. A structurally invalid
        # geometry now means the supplied FASTA cannot form the exact FAI model
        # RefCompat is evaluating, not that biological compatibility was tested.
        raise FastaIndexComputationError(
            f"computed FAI geometry is invalid for FASTA: {path}"
        ) from exc


def _parse_fai_line(raw_line: str, *, line_number: int, path: Path) -> FastaIndexRecord:
    line = raw_line.rstrip("\r\n")
    if not line:
        raise FastaIndexParseError(f"blank FAI record at line {line_number}: {path}")
    fields = line.split("\t")
    if len(fields) != 5:
        raise FastaIndexParseError(
            f"FAI line {line_number} must contain exactly five TAB-delimited fields: {path}"
        )

    try:
        length, offset, line_bases, line_bytes = (int(value, 10) for value in fields[1:])
        return FastaIndexRecord(
            name=fields[0],
            length=length,
            offset=offset,
            line_bases=line_bases,
            line_bytes=line_bytes,
        )
    except ValueError as exc:
        raise FastaIndexParseError(f"invalid FAI record at line {line_number}: {path}") from exc


def _extract_external_values(
    external: Sequence[_ExternalFaiRecord],
) -> tuple[_FaiValues, ...]:
    values: list[_FaiValues] = []
    for record in external:
        try:
            name = record.name
            length = record.length
            metadata = record.fai
        except (AttributeError, TypeError) as exc:
            raise FastaIndexProviderIncompatibleError(
                "refget returned an unsupported FAI result shape"
            ) from exc

        if not isinstance(name, str):
            raise FastaIndexProviderIncompatibleError("refget returned a non-string FAI name")
        if not isinstance(length, int) or isinstance(length, bool):
            raise FastaIndexProviderIncompatibleError("refget returned a non-integer FAI length")
        if length < 0:
            raise FastaIndexProviderIncompatibleError("refget returned a negative FAI length")

        if metadata is None:
            if length == 0:
                # gtars/refget 0.12 legitimately returns ``fai=None`` for a
                # named zero-length FASTA record because no sequence line
                # exists from which byte geometry can be derived. This is a
                # limitation of the current geometry calculator, not evidence
                # that the provider API is incompatible.
                raise FastaIndexComputationError(
                    f"cannot compute FAI geometry for zero-length FASTA sequence: {name}"
                )
            raise FastaIndexProviderIncompatibleError(
                "refget returned FAI metadata as unavailable for a non-empty sequence"
            )

        try:
            offset = metadata.offset
            line_bases = metadata.line_bases
            line_bytes = metadata.line_bytes
        except (AttributeError, TypeError) as exc:
            raise FastaIndexProviderIncompatibleError(
                "refget returned an unsupported FAI metadata shape"
            ) from exc

        geometry = (offset, line_bases, line_bytes)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in geometry):
            raise FastaIndexProviderIncompatibleError("refget returned non-integer FAI geometry")

        values.append(
            _FaiValues(
                name=name,
                length=length,
                offset=cast(int, offset),
                line_bases=cast(int, line_bases),
                line_bytes=cast(int, line_bytes),
            )
        )
    return tuple(values)


def _validate_computed_values(values: tuple[_FaiValues, ...], path: Path) -> None:
    # Keep these anchor-name checks aligned with identity/refget.py. They are
    # repeated here intentionally because digest_fasta() and compute_fai() are
    # independent upstream entry points that may evolve independently.
    if not values:
        raise FastaIndexComputationError(f"FASTA produced no indexable sequence records: {path}")

    names = tuple(value.name for value in values)
    if any(not name for name in names):
        raise FastaIndexComputationError(
            f"FASTA contains a sequence without an indexable local name: {path}"
        )
    if len(set(names)) != len(names):
        raise FastaIndexComputationError(f"FASTA contains duplicate sequence names: {path}")


def _record_from_values(values: _FaiValues) -> FastaIndexRecord:
    return FastaIndexRecord(
        name=values.name,
        length=values.length,
        offset=values.offset,
        line_bases=values.line_bases,
        line_bytes=values.line_bytes,
    )


def _preflight_is_gzip_stream(path: Path) -> bool:
    """Confirm readability and return whether the FASTA starts with gzip/BGZF magic."""

    try:
        with path.open("rb") as handle:
            # Opening can succeed for non-regular filesystem objects such as
            # FIFOs or character devices. FAI byte geometry is defined for a
            # stable file representation, so exclude those explicitly.
            if not path.is_file():
                raise OSError("path is not a regular file")
            return handle.read(2) == b"\x1f\x8b"
    except OSError as exc:
        raise FastaIndexUnreadableError(f"cannot read FASTA: {path}") from exc


def _is_readable_file(path: Path) -> bool:
    try:
        with path.open("rb"):
            return path.is_file()
    except OSError:
        return False
