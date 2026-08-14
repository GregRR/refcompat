"""RefCompat-owned immutable domain model.

External library types must not leak into this layer.
"""

from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
from refcompat.model.fasta_index import (
    ComputedFastaIndex,
    FastaIndexData,
    FastaIndexDifference,
    FastaIndexDifferenceKind,
    FastaIndexIntegrityResult,
    FastaIndexRecord,
    FastaIndexSnapshot,
)
from refcompat.model.identity import (
    CollectionCompleteness,
    IdentityProviderInfo,
    Md5Digest,
    RefgetSequenceId,
    SeqColAttributeDigest,
    SeqColDigest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.resources import (
    ArtifactDigest,
    ArtifactDigestAlgorithm,
    ArtifactIdentity,
    Resource,
    ResourceId,
    ResourceKind,
)

__all__ = [
    "ArtifactDigest",
    "ArtifactDigestAlgorithm",
    "ArtifactIdentity",
    "CollectionCompleteness",
    "ComputedFastaIndex",
    "EvidencePolarity",
    "EvidenceStrength",
    "FastaIndexData",
    "FastaIndexDifference",
    "FastaIndexDifferenceKind",
    "FastaIndexIntegrityResult",
    "FastaIndexRecord",
    "FastaIndexSnapshot",
    "IdentityProviderInfo",
    "Md5Digest",
    "RefgetSequenceId",
    "Resource",
    "ResourceId",
    "ResourceKind",
    "SeqColAttributeDigest",
    "SeqColDigest",
    "SequenceCollectionSnapshot",
    "SnapshotSequence",
]
