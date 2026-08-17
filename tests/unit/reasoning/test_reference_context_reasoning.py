from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    CapabilityId,
    CollectionCompleteness,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    RefgetSequenceId,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceIdentityCapability,
    SnapshotSequence,
)
from refcompat.reasoning import build_reference_context, derive_sequence_bindings

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_REFGET_A = RefgetSequenceId("SQ." + "A" * 32)
_REFGET_B = RefgetSequenceId("SQ." + "B" * 32)


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request(names: tuple[str, ...] | None = None) -> EvaluationRequest:
    resources = (
        _resource(_REFERENCE, ResourceKind.FASTA),
        _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
    )
    return EvaluationRequest(
        resources,
        _REFERENCE,
        EvaluationScope((_REFERENCE, _CONSUMER), names),
    )


def _snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chr2", 20, 1, _REFGET_B),
        ),
    )


def test_reference_context_projects_anchor_and_subset_in_fasta_order() -> None:
    context = build_reference_context(_request(("chr2", "chr1")), _snapshot())
    assert tuple(sequence.local_name for sequence in context.sequences) == ("chr1", "chr2")
    assert {cap.resource_id for cap in context.anchor_capabilities} == {_REFERENCE}


def test_reference_context_rejects_unknown_scoped_name() -> None:
    with pytest.raises(ValueError, match="names absent from FASTA"):
        build_reference_context(_request(("chr3",)), _snapshot())


def test_reference_context_rejects_wrong_snapshot_resource() -> None:
    snapshot = SequenceCollectionSnapshot(
        ResourceId("other"),
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 10, 0),),
    )
    with pytest.raises(ValueError, match="evaluation FASTA anchor"):
        build_reference_context(_request(), snapshot)


def test_cross_name_content_identity_derives_binding() -> None:
    context = build_reference_context(_request(), _snapshot())
    local = SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "1", _REFGET_A)
    bindings = derive_sequence_bindings(
        context,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, capabilities=(local,)),
        ),
    )
    assert len(bindings) == 1
    assert bindings[0].local_sequence_name == "1"
    assert bindings[0].anchor_sequence_name == "chr1"


def test_duplicate_anchor_content_does_not_guess_binding() -> None:
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chrDup", 10, 1, _REFGET_A),
        ),
    )
    context = build_reference_context(_request(), snapshot)
    local = SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "1", _REFGET_A)
    assert (
        derive_sequence_bindings(
            context,
            (
                ResourceContract(_REFERENCE),
                ResourceContract(_CONSUMER, capabilities=(local,)),
            ),
        )
        == ()
    )


def test_sequence_scope_does_not_turn_duplicate_content_into_verified_binding() -> None:
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, _REFGET_A),
            SnapshotSequence("chrDup", 10, 1, _REFGET_A),
        ),
    )
    context = build_reference_context(_request(("chr1",)), snapshot)
    local = SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "1", _REFGET_A)

    assert (
        derive_sequence_bindings(
            context,
            (
                ResourceContract(_REFERENCE),
                ResourceContract(_CONSUMER, capabilities=(local,)),
            ),
        )
        == ()
    )


def test_unique_binding_target_outside_scope_remains_unbound() -> None:
    context = build_reference_context(_request(("chr1",)), _snapshot())
    local = SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "2", _REFGET_B)

    assert (
        derive_sequence_bindings(
            context,
            (
                ResourceContract(_REFERENCE),
                ResourceContract(_CONSUMER, capabilities=(local,)),
            ),
        )
        == ()
    )


def test_conflicting_local_identity_does_not_create_binding() -> None:
    context = build_reference_context(_request(), _snapshot())
    caps = (
        SequenceIdentityCapability(CapabilityId("a"), _CONSUMER, "1", Md5Digest("0" * 32)),
        SequenceIdentityCapability(CapabilityId("b"), _CONSUMER, "1", Md5Digest("1" * 32)),
    )
    assert (
        derive_sequence_bindings(
            context,
            (
                ResourceContract(_REFERENCE),
                ResourceContract(_CONSUMER, capabilities=caps),
            ),
        )
        == ()
    )


def test_binding_requires_contract_for_each_scoped_resource() -> None:
    context = build_reference_context(_request(), _snapshot())
    with pytest.raises(ValueError, match="exactly one contract per scoped resource"):
        derive_sequence_bindings(context, (ResourceContract(_REFERENCE),))


def test_binding_rejects_duplicate_resource_contracts() -> None:
    context = build_reference_context(_request(), _snapshot())
    consumer = ResourceContract(_CONSUMER)
    with pytest.raises(ValueError, match="contracts must have unique resource IDs"):
        derive_sequence_bindings(
            context,
            (ResourceContract(_REFERENCE), consumer, consumer),
        )


def test_identity_schemes_do_not_cross_bind() -> None:
    context = build_reference_context(_request(), _snapshot())
    local = SequenceIdentityCapability(
        CapabilityId("local-md5"), _CONSUMER, "1", Md5Digest("0" * 32)
    )
    assert (
        derive_sequence_bindings(
            context,
            (
                ResourceContract(_REFERENCE),
                ResourceContract(_CONSUMER, capabilities=(local,)),
            ),
        )
        == ()
    )


def test_binding_is_deterministic_across_capability_input_order() -> None:
    refget_capability = SequenceIdentityCapability(
        CapabilityId("refget"), _CONSUMER, "1", _REFGET_A
    )
    md5 = Md5Digest("0" * 32)
    snapshot = SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 10, 0, _REFGET_A, md5),),
    )
    context = build_reference_context(_request(), snapshot)
    md5_capability = SequenceIdentityCapability(CapabilityId("md5"), _CONSUMER, "1", md5)

    first = derive_sequence_bindings(
        context,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, capabilities=(refget_capability, md5_capability)),
        ),
    )
    second = derive_sequence_bindings(
        context,
        (
            ResourceContract(_REFERENCE),
            ResourceContract(_CONSUMER, capabilities=(md5_capability, refget_capability)),
        ),
    )
    assert first == second
