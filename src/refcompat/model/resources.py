"""Core resource identity types.

Artifact-byte identity is intentionally separate from biological sequence and
sequence-collection identity. A file checksum can establish that two files are
byte-for-byte identical; it must never be substituted for a refget or SeqCol
identifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NewType

ResourceId = NewType("ResourceId", str)


class ResourceKind(StrEnum):
    """Resource formats planned for the RefCompat v0.1 compatibility surface."""

    FASTA = "fasta"
    FASTA_INDEX = "fasta_index"
    SEQUENCE_DICTIONARY = "sequence_dictionary"
    VCF = "vcf"
    BAM = "bam"
    CRAM = "cram"
    GTF = "gtf"
    GFF3 = "gff3"


class ArtifactDigestAlgorithm(StrEnum):
    """Algorithms permitted for byte-level artifact identity."""

    SHA256 = "sha256"


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """Digest of exact artifact bytes, not of biological sequence content."""

    algorithm: ArtifactDigestAlgorithm
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("artifact digest value must not be empty")


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Local identity of one supplied artifact."""

    path: Path
    byte_size: int | None = None
    digest: ArtifactDigest | None = None

    def __post_init__(self) -> None:
        if self.byte_size is not None and self.byte_size < 0:
            raise ValueError("artifact byte size must not be negative")


@dataclass(frozen=True, slots=True)
class Resource:
    """Thin identity for one supplied genomic resource."""

    id: ResourceId
    kind: ResourceKind
    artifact: ArtifactIdentity
    display_name: str | None = None
