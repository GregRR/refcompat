"""VCF header/reference-context observations.

This model preserves metadata and record-usage facts extracted from a supplied
VCF without treating header declarations as proof of reference compatibility.
Direct REF-to-FASTA validation belongs to the later authoritative VCF reasoning
slice.
"""

from __future__ import annotations

from dataclasses import dataclass

from refcompat.model.resources import ResourceId


@dataclass(frozen=True, slots=True)
class VcfContigDeclaration:
    """One normalized ``##contig`` declaration exposed by the VCF parser."""

    name: str
    length: int | None = None
    md5: str | None = None
    assembly: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("VCF contig name must not be empty")
        if self.length is not None and self.length < 0:
            raise ValueError("VCF contig length must not be negative")
        for field_name, value in (
            ("md5", self.md5),
            ("assembly", self.assembly),
            ("URL", self.url),
        ):
            if value is not None and not value:
                raise ValueError(f"VCF contig {field_name} value must not be empty")


@dataclass(frozen=True, slots=True)
class VcfHeaderData:
    """Reference-relevant metadata from the parser-visible normalized VCF header."""

    file_format: str
    reference_claims: tuple[str, ...] = ()
    contigs: tuple[VcfContigDeclaration, ...] = ()

    def __post_init__(self) -> None:
        if not self.file_format:
            raise ValueError("VCF file format must not be empty")
        if any(not claim for claim in self.reference_claims):
            raise ValueError("VCF reference claims must not be empty")
        contig_names = tuple(contig.name for contig in self.contigs)
        if len(set(contig_names)) != len(contig_names):
            raise ValueError("VCF contig declarations must have unique names")


@dataclass(frozen=True, slots=True)
class VcfChromUsage:
    """Observed record usage for one VCF CHROM value."""

    sequence_name: str
    record_count: int

    def __post_init__(self) -> None:
        if not self.sequence_name:
            raise ValueError("VCF CHROM usage name must not be empty")
        if self.record_count < 1:
            raise ValueError("VCF CHROM usage count must be positive")


@dataclass(frozen=True, slots=True)
class VcfContextSnapshot:
    """Reference-context observations from one supplied VCF resource.

    ``chrom_usage`` summarizes the entire record stream. It is observational:
    a CHROM value absent from a sparse VCF does not prove that the underlying
    reference lacks that sequence.
    """

    resource_id: ResourceId
    header: VcfHeaderData
    record_count: int
    chrom_usage: tuple[VcfChromUsage, ...] = ()

    def __post_init__(self) -> None:
        if not self.resource_id:
            raise ValueError("VCF snapshot resource ID must not be empty")
        if self.record_count < 0:
            raise ValueError("VCF record count must not be negative")
        usage_names = tuple(usage.sequence_name for usage in self.chrom_usage)
        if len(set(usage_names)) != len(usage_names):
            raise ValueError("VCF CHROM usage names must be unique")
        if sum(usage.record_count for usage in self.chrom_usage) != self.record_count:
            raise ValueError("VCF CHROM usage counts must sum to the record count")
        if self.record_count == 0 and self.chrom_usage:
            raise ValueError("empty VCF record stream cannot have CHROM usage")

    @property
    def declared_sequence_names(self) -> tuple[str, ...]:
        """Ordered sequence names declared by ``##contig`` header lines."""

        return tuple(contig.name for contig in self.header.contigs)

    @property
    def used_sequence_names(self) -> tuple[str, ...]:
        """CHROM values in first-observed record order."""

        return tuple(usage.sequence_name for usage in self.chrom_usage)

    @property
    def undeclared_used_sequence_names(self) -> tuple[str, ...]:
        """Used CHROM values lacking a ``##contig`` declaration."""

        declared = set(self.declared_sequence_names)
        return tuple(name for name in self.used_sequence_names if name not in declared)

    @property
    def declared_unused_sequence_names(self) -> tuple[str, ...]:
        """Declared contigs not observed in any record.

        This is a usage observation only and must not be interpreted as evidence
        that the VCF's underlying reference excludes those sequences.
        """

        used = set(self.used_sequence_names)
        return tuple(name for name in self.declared_sequence_names if name not in used)
