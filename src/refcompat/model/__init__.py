"""RefCompat-owned immutable domain model.

External library types must not leak into this layer.
"""

from refcompat.model.evidence import EvidencePolarity, EvidenceStrength
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
    "EvidencePolarity",
    "EvidenceStrength",
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
