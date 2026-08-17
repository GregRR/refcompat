from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    CapabilityId,
    CollectionCompleteness,
    EvaluationRequest,
    EvaluationScope,
    ReferenceContext,
    RefgetSequenceId,
    Resource,
    ResourceId,
    ResourceKind,
    SequenceBinding,
    SequenceBindingId,
    SequenceBindingMethod,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_IDENTITY = RefgetSequenceId("SQ." + "A" * 32)


def _request() -> EvaluationRequest:
    resources = (
        Resource(
            _REFERENCE,
            ResourceKind.FASTA,
            ArtifactIdentity(path=Path("reference.fa")),
        ),
        Resource(
            _CONSUMER,
            ResourceKind.SEQUENCE_DICTIONARY,
            ArtifactIdentity(path=Path("consumer.dict")),
        ),
    )
    return EvaluationRequest(
        resources,
        _REFERENCE,
        EvaluationScope((_REFERENCE, _CONSUMER)),
    )


def _snapshot(completeness: CollectionCompleteness) -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        completeness,
        sequences=(SnapshotSequence("chr1", 10, 0, _IDENTITY),),
    )


def test_reference_context_requires_complete_fasta_snapshot() -> None:
    request = _request()
    with pytest.raises(ValueError, match="complete anchor snapshot"):
        ReferenceContext(
            _REFERENCE,
            request.scope,
            _snapshot(CollectionCompleteness.PARTIAL),
            (SnapshotSequence("chr1", 10, 0, _IDENTITY),),
            (),
        )


def test_sequence_binding_requires_identity_trace() -> None:
    with pytest.raises(ValueError, match="at least one content identity"):
        SequenceBinding(
            SequenceBindingId("binding"),
            _CONSUMER,
            "1",
            _REFERENCE,
            "chr1",
            SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
            (),
            (CapabilityId("capability"),),
        )


def test_sequence_binding_requires_capability_trace() -> None:
    with pytest.raises(ValueError, match="source capability IDs"):
        SequenceBinding(
            SequenceBindingId("binding"),
            _CONSUMER,
            "1",
            _REFERENCE,
            "chr1",
            SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
            (_IDENTITY,),
            (),
        )


def test_sequence_binding_rejects_duplicate_trace_values() -> None:
    with pytest.raises(ValueError, match="identity values must be unique"):
        SequenceBinding(
            SequenceBindingId("binding"),
            _CONSUMER,
            "1",
            _REFERENCE,
            "chr1",
            SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY,
            (_IDENTITY, _IDENTITY),
            (CapabilityId("local"), CapabilityId("anchor")),
        )
