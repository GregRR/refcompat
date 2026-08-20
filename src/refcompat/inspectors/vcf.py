"""Extract VCF header reference metadata and observed CHROM usage with pysam.

The adapter deliberately copies primitive values out of ``pysam`` objects so
external HTSlib-backed types do not leak into the RefCompat domain model.
Header reference/contig metadata remains a claim or observation, not proof of
compatibility. Authoritative REF-to-FASTA comparison is implemented separately.

References:
- VCF v4.5 specification: https://samtools.github.io/hts-specs/VCFv4.5.pdf
- pysam VariantFile API: https://pysam.readthedocs.io/en/latest/api.html
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

from refcompat.model.resources import Resource, ResourceKind
from refcompat.model.vcf import (
    VcfChromUsage,
    VcfContextSnapshot,
    VcfContigDeclaration,
    VcfHeaderData,
)


class VcfInspectionError(Exception):
    """Base class for normalized VCF inspection failures."""


class UnsupportedVcfResourceError(VcfInspectionError):
    """The requested operation does not apply to the supplied resource kind."""


class VcfUnreadableError(VcfInspectionError):
    """The supplied VCF cannot be read locally."""


class VcfParseError(VcfInspectionError):
    """The supplied artifact cannot be parsed as VCF/BCF by the provider."""


class VcfProviderIncompatibleError(VcfInspectionError):
    """The installed pysam provider exposes an unsupported API/result shape."""


class _VariantHeaderRecord(Protocol):
    key: object
    value: object

    def get(self, key: str, default: object | None = None) -> object: ...


class _VariantContig(Protocol):
    name: object
    length: object
    header_record: _VariantHeaderRecord


class _VariantHeaderContigs(Protocol):
    def items(self) -> Iterable[tuple[object, _VariantContig]]: ...


class _VariantHeader(Protocol):
    version: object
    records: Iterable[_VariantHeaderRecord]
    contigs: _VariantHeaderContigs


class _VariantRecord(Protocol):
    contig: object


class _VariantFile(Protocol):
    header: _VariantHeader
    is_bcf: object

    def __iter__(self) -> Iterator[_VariantRecord]: ...

    def close(self) -> object: ...


class _PysamModule(Protocol):
    __version__: object
    VariantFile: Callable[[str], _VariantFile]


def _load_pysam() -> _PysamModule:
    try:
        module = import_module("pysam")
    except ImportError as exc:  # pragma: no cover - required dependency in normal installs
        raise VcfProviderIncompatibleError("pysam is not importable") from exc
    return cast(_PysamModule, module)


def inspect_vcf_context(resource: Resource) -> VcfContextSnapshot:
    """Read reference-relevant header metadata and scan all records for CHROM usage."""

    if resource.kind is not ResourceKind.VCF:
        raise UnsupportedVcfResourceError("VCF inspection requires a VCF resource")

    path = resource.artifact.path
    _require_readable(path)
    pysam_module = _load_pysam()

    try:
        variant_file = pysam_module.VariantFile(str(path))
    except OSError as exc:
        try:
            _require_readable(path)
        except VcfUnreadableError as unreadable:
            raise unreadable from exc
        raise VcfParseError(f"cannot parse VCF: {path}") from exc
    except (NotImplementedError, TypeError, ValueError) as exc:
        raise VcfParseError(f"cannot parse VCF: {path}") from exc

    try:
        if not isinstance(variant_file.is_bcf, bool):
            raise VcfProviderIncompatibleError(
                f"pysam returned invalid variant format metadata: {path}"
            )
        if variant_file.is_bcf:
            raise VcfParseError("BCF input is deferred; Milestone 3 accepts VCF/VCF.gz only")
        header = _header_data(variant_file.header, path=path)
        record_count, chrom_usage = _scan_chrom_usage(variant_file, path=path)
    except (NotImplementedError, OSError, TypeError, ValueError) as exc:
        raise VcfParseError(f"cannot parse VCF records: {path}") from exc
    finally:
        variant_file.close()

    return VcfContextSnapshot(
        resource_id=resource.id,
        header=header,
        record_count=record_count,
        chrom_usage=chrom_usage,
    )


def _require_readable(path: Path) -> None:
    try:
        with path.open("rb"):
            pass
    except OSError as exc:
        raise VcfUnreadableError(f"cannot read VCF: {path}") from exc


def _header_data(header: _VariantHeader, *, path: Path) -> VcfHeaderData:
    """Copy the normalized header view exposed by pysam/HTSlib.

    HTSlib may collapse duplicate ``##contig`` IDs or drop malformed contig
    declarations before they reach this boundary. RefCompat therefore preserves
    the provider-visible declaration set here, not the raw header byte stream.
    """

    version = header.version
    if not isinstance(version, str):
        raise VcfProviderIncompatibleError(
            f"pysam returned invalid VCF fileformat metadata: {path}"
        )
    if not version:
        raise VcfParseError(f"VCF declares an empty fileformat value: {path}")

    reference_claims: list[str] = []
    for record in header.records:
        key = record.key
        if key != "reference":
            continue
        value = record.value
        if not isinstance(value, str):
            raise VcfProviderIncompatibleError(
                f"pysam returned invalid VCF reference metadata: {path}"
            )
        if not value:
            raise VcfParseError(f"VCF declares an empty reference value: {path}")
        reference_claims.append(value)

    contigs: list[VcfContigDeclaration] = []
    for map_name, contig in header.contigs.items():
        name = contig.name
        if not isinstance(map_name, str) or not isinstance(name, str) or map_name != name:
            raise VcfProviderIncompatibleError(
                f"pysam returned inconsistent VCF contig metadata: {path}"
            )
        header_record = contig.header_record
        length = _optional_header_int(header_record.get("length"), field="length", path=path)
        contigs.append(
            VcfContigDeclaration(
                name=name,
                length=length,
                md5=_optional_str(header_record.get("md5"), field="md5", path=path),
                assembly=_optional_str(header_record.get("assembly"), field="assembly", path=path),
                url=_optional_str(header_record.get("URL"), field="URL", path=path),
            )
        )

    try:
        return VcfHeaderData(
            file_format=version,
            reference_claims=tuple(reference_claims),
            contigs=tuple(contigs),
        )
    except ValueError as exc:
        raise VcfParseError(f"invalid VCF reference metadata: {path}") from exc


def _scan_chrom_usage(
    variant_file: _VariantFile, *, path: Path
) -> tuple[int, tuple[VcfChromUsage, ...]]:
    counts: dict[str, int] = {}
    record_count = 0
    for record in variant_file:
        contig = record.contig
        if not isinstance(contig, str) or not contig:
            raise VcfProviderIncompatibleError(f"pysam returned an invalid VCF CHROM value: {path}")
        record_count += 1
        counts[contig] = counts.get(contig, 0) + 1

    usage = tuple(
        VcfChromUsage(sequence_name=sequence_name, record_count=count)
        for sequence_name, count in counts.items()
    )
    return record_count, usage


def _optional_str(value: object, *, field: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise VcfProviderIncompatibleError(
            f"pysam returned invalid VCF contig {field} metadata: {path}"
        )
    if not value:
        raise VcfParseError(f"VCF declares an empty contig {field} value: {path}")
    return value


def _optional_header_int(value: object, *, field: str, path: Path) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise VcfProviderIncompatibleError(
            f"pysam returned invalid VCF contig {field} metadata: {path}"
        )
    if isinstance(value, int):
        if value < 0:
            raise VcfParseError(f"VCF declares a negative contig {field}: {path}")
        return value
    if isinstance(value, str):
        if value and all("0" <= character <= "9" for character in value):
            return int(value)
        raise VcfParseError(f"VCF declares an invalid contig {field}: {path}")
    raise VcfProviderIncompatibleError(
        f"pysam returned invalid VCF contig {field} metadata: {path}"
    )
