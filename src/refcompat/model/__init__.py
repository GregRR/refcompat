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
from refcompat.model.observations import (
    ObservationId,
    ObservationKind,
    ResourceObservation,
    SourceLocation,
)
from refcompat.model.resources import (
    ArtifactDigest,
    ArtifactDigestAlgorithm,
    ArtifactIdentity,
    Resource,
    ResourceId,
    ResourceKind,
)
from refcompat.model.sequence_dictionary import (
    ExpectedSequenceDictionary,
    MoleculeTopology,
    SequenceDictionaryContentIdentityMatch,
    SequenceDictionaryCrossNameM5LengthInconsistency,
    SequenceDictionaryData,
    SequenceDictionaryDifference,
    SequenceDictionaryDifferenceKind,
    SequenceDictionaryIntegrityResult,
    SequenceDictionaryRecord,
    SequenceDictionarySnapshot,
)

__all__ = [
    "ArtifactDigest",
    "ArtifactDigestAlgorithm",
    "ArtifactIdentity",
    "CollectionCompleteness",
    "ComputedFastaIndex",
    "EvidencePolarity",
    "EvidenceStrength",
    "ExpectedSequenceDictionary",
    "FastaIndexData",
    "FastaIndexDifference",
    "FastaIndexDifferenceKind",
    "FastaIndexIntegrityResult",
    "FastaIndexRecord",
    "FastaIndexSnapshot",
    "IdentityProviderInfo",
    "Md5Digest",
    "MoleculeTopology",
    "ObservationId",
    "ObservationKind",
    "RefgetSequenceId",
    "Resource",
    "ResourceId",
    "ResourceKind",
    "ResourceObservation",
    "SeqColAttributeDigest",
    "SeqColDigest",
    "SequenceCollectionSnapshot",
    "SequenceDictionaryContentIdentityMatch",
    "SequenceDictionaryCrossNameM5LengthInconsistency",
    "SequenceDictionaryData",
    "SequenceDictionaryDifference",
    "SequenceDictionaryDifferenceKind",
    "SequenceDictionaryIntegrityResult",
    "SequenceDictionaryRecord",
    "SequenceDictionarySnapshot",
    "SnapshotSequence",
    "SourceLocation",
]
