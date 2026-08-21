"""RefCompat-owned biological sequence and collection identity values.

GA4GH refget and SeqCol define the identity semantics. These immutable values
copy standards-backed results across RefCompat's adapter boundary so external
``refget``/``gtars`` objects never become part of the reasoning model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from refcompat._compat import StrEnum
from refcompat.model.resources import ResourceId

_SHA512T24U_RE = re.compile(r"^[A-Za-z0-9_-]{32}$")
_MD5_RE = re.compile(r"^[0-9a-fA-F]{32}$")


@dataclass(frozen=True, slots=True)
class RefgetSequenceId:
    """GA4GH refget sequence identifier in canonical ``SQ.<digest>`` form."""

    value: str

    def __post_init__(self) -> None:
        prefix = "SQ."
        if not self.value.startswith(prefix) or not _SHA512T24U_RE.fullmatch(
            self.value[len(prefix) :]
        ):
            raise ValueError("refget sequence ID must be SQ. followed by a 32-character digest")


@dataclass(frozen=True, slots=True)
class SeqColDigest:
    """Top-level GA4GH SeqCol collection digest."""

    value: str

    def __post_init__(self) -> None:
        if not _SHA512T24U_RE.fullmatch(self.value):
            raise ValueError("SeqCol digest must be a 32-character SHA512t24u value")


@dataclass(frozen=True, slots=True)
class SeqColAttributeDigest:
    """Digest of one SeqCol collection attribute array."""

    value: str

    def __post_init__(self) -> None:
        if not _SHA512T24U_RE.fullmatch(self.value):
            raise ValueError("SeqCol attribute digest must be a 32-character SHA512t24u value")


@dataclass(frozen=True, slots=True)
class Md5Digest:
    """Legacy sequence-content MD5 used by formats such as SAM ``M5``."""

    value: str

    def __post_init__(self) -> None:
        if not _MD5_RE.fullmatch(self.value):
            raise ValueError("MD5 digest must be a 32-character hexadecimal value")
        object.__setattr__(self, "value", self.value.lower())


class CollectionCompleteness(StrEnum):
    """How completely a resource describes its underlying sequence collection."""

    COMPLETE = "complete"
    DECLARED_COMPLETE = "declared_complete"
    PARTIAL = "partial"
    USED_SUBSET = "used_subset"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class IdentityProviderInfo:
    """Implementation provenance for a standards-backed identity computation."""

    name: str
    version: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("identity provider name must not be empty")
        if not self.version:
            raise ValueError("identity provider version must not be empty")


@dataclass(frozen=True, slots=True)
class SnapshotSequence:
    """Sequence identity exposed by one resource-local sequence record."""

    local_name: str
    length: int | None = None
    ordinal: int | None = None
    refget_id: RefgetSequenceId | None = None
    md5: Md5Digest | None = None

    def __post_init__(self) -> None:
        if not self.local_name:
            raise ValueError("sequence local name must not be empty")
        if self.length is not None and self.length < 0:
            raise ValueError("sequence length must not be negative")
        if self.ordinal is not None and self.ordinal < 0:
            raise ValueError("sequence ordinal must not be negative")


@dataclass(frozen=True, slots=True)
class SequenceCollectionSnapshot:
    """Standards-backed sequence-collection facts exposed by one resource.

    FASTA inspection yields a complete snapshot. Sparse formats such as GTF or
    VCF must use weaker completeness states when they are implemented; merely
    observing a subset of sequence names must never be promoted to a complete
    reference collection.
    """

    resource_id: ResourceId
    completeness: CollectionCompleteness
    collection_digest: SeqColDigest | None = None
    names_digest: SeqColAttributeDigest | None = None
    lengths_digest: SeqColAttributeDigest | None = None
    sequences_digest: SeqColAttributeDigest | None = None
    sequences: tuple[SnapshotSequence, ...] = ()
    provider: IdentityProviderInfo | None = None

    def __post_init__(self) -> None:
        collection_digests = (
            self.collection_digest,
            self.names_digest,
            self.lengths_digest,
            self.sequences_digest,
        )
        if any(digest is not None for digest in collection_digests) and self.completeness not in {
            CollectionCompleteness.COMPLETE,
            CollectionCompleteness.DECLARED_COMPLETE,
        }:
            raise ValueError(
                "collection-level SeqCol digests require a complete or declared-complete snapshot"
            )

        ordinals = tuple(sequence.ordinal for sequence in self.sequences)
        known_ordinals = tuple(ordinal for ordinal in ordinals if ordinal is not None)
        if known_ordinals and len(known_ordinals) != len(ordinals):
            raise ValueError("snapshot sequence ordinals must be either all known or all unknown")
        if known_ordinals and known_ordinals != tuple(range(len(self.sequences))):
            raise ValueError("snapshot sequence ordinals must be contiguous and zero-based")
