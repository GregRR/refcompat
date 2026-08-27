"""Tests for BAM/CRAM header projection into generic contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    ArtifactIdentity,
    CollectionCompleteness,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ReferenceContext,
    RefgetSequenceId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SatisfactionMode,
    SequenceCollectionSnapshot,
    SequenceDictionaryRecord,
    SequenceIdentityRequirement,
    SequenceLengthRequirement,
    SequencePresenceRequirement,
    SnapshotSequence,
)
from refcompat.reasoning import (
    build_alignment_contract,
    build_reference_context,
    reason_bundle,
)

_REFERENCE = ResourceId("reference")
_ALIGNMENT = ResourceId("reads")
_OTHER = ResourceId("other")
_MD5_A = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_B = Md5Digest("31fc6ca291a32fb9df82b85e5f077e31")
_REFGET_A = RefgetSequenceId("SQ." + "A" * 32)
_REFGET_B = RefgetSequenceId("SQ." + "B" * 32)


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(Path(str(resource_id))))


def _request(*, include_alignment: bool = True) -> EvaluationRequest:
    resources = [_resource(_REFERENCE, ResourceKind.FASTA)]
    scope = [_REFERENCE]
    if include_alignment:
        resources.append(_resource(_ALIGNMENT, ResourceKind.BAM))
        scope.append(_ALIGNMENT)
    else:
        resources.append(_resource(_OTHER, ResourceKind.BAM))
        scope.append(_OTHER)
    return EvaluationRequest(
        resources=tuple(resources),
        anchor_resource_id=_REFERENCE,
        scope=EvaluationScope(tuple(scope)),
    )


def _anchor_snapshot() -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        resource_id=_REFERENCE,
        completeness=CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 4, 0, _REFGET_A, _MD5_A),
            SnapshotSequence("chr2", 8, 1, _REFGET_B, _MD5_B),
        ),
    )


def _alignment_snapshot(
    sequences: tuple[SequenceDictionaryRecord, ...],
) -> AlignmentHeaderSnapshot:
    return AlignmentHeaderSnapshot(
        resource_id=_ALIGNMENT,
        resource_kind=ResourceKind.BAM,
        header=AlignmentHeaderData(sequences=sequences),
    )


def _context(*, include_alignment: bool = True) -> ReferenceContext:
    return build_reference_context(
        _request(include_alignment=include_alignment),
        _anchor_snapshot(),
    )


def test_alignment_contract_projects_presence_length_and_declared_m5() -> None:
    snapshot = _alignment_snapshot(
        (
            SequenceDictionaryRecord(
                name="chr1",
                length=4,
                md5=_MD5_A,
                alternate_names=("1",),
                assembly="synthetic",
                species="synthetic species",
                uri="file:///refs/reference.fa",
            ),
            SequenceDictionaryRecord(name="chr2", length=8),
        )
    )

    contract = build_alignment_contract(snapshot, _context())

    assert contract.resource_id == _ALIGNMENT
    assert contract.capabilities == ()
    assert len(contract.requirements) == 5
    assert [type(item) for item in contract.requirements] == [
        SequencePresenceRequirement,
        SequencePresenceRequirement,
        SequenceLengthRequirement,
        SequenceLengthRequirement,
        SequenceIdentityRequirement,
    ]
    assert all(item.origin is RequirementOrigin.CORE_FORMAT for item in contract.requirements)
    assert all(item.level is RequirementLevel.MANDATORY for item in contract.requirements)
    assert [
        item.sequence_name
        for item in contract.requirements
        if isinstance(item, SequencePresenceRequirement)
    ] == ["chr1", "chr2"]
    assert [
        (item.sequence_name, item.length)
        for item in contract.requirements
        if isinstance(item, SequenceLengthRequirement)
    ] == [("chr1", 4), ("chr2", 8)]
    identity = next(
        item for item in contract.requirements if isinstance(item, SequenceIdentityRequirement)
    )
    assert identity.sequence_name == "chr1"
    assert identity.identity == _MD5_A


def test_alignment_contract_empty_sq_produces_no_requirements() -> None:
    contract = build_alignment_contract(_alignment_snapshot(()), _context())

    assert contract.requirements == ()
    assert contract.capabilities == ()


def test_alignment_contract_requires_scoped_resource() -> None:
    with pytest.raises(ValueError, match="inside the reference-context scope"):
        build_alignment_contract(
            _alignment_snapshot((SequenceDictionaryRecord(name="chr1", length=4),)),
            _context(include_alignment=False),
        )


def test_alignment_contract_ids_are_deterministic() -> None:
    snapshot = _alignment_snapshot((SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A),))
    context = _context()

    first = build_alignment_contract(snapshot, context)
    second = build_alignment_contract(snapshot, context)

    assert tuple(item.id for item in first.requirements) == tuple(
        item.id for item in second.requirements
    )
    assert len({item.id for item in first.requirements}) == len(first.requirements)


def test_exact_name_alignment_requirements_use_anchor_content() -> None:
    snapshot = _alignment_snapshot((SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_A),))
    contract = build_alignment_contract(snapshot, _context())

    result = reason_bundle(
        _request(),
        _anchor_snapshot(),
        (ResourceContract(_REFERENCE), contract),
    )

    assert [item.state for item in result.evaluations] == [
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    ]
    assert [item.satisfaction_mode for item in result.evaluations] == [
        SatisfactionMode.EXACT,
        SatisfactionMode.EXACT,
        SatisfactionMode.VERIFIED_SEQUENCE_IDENTITY,
    ]
    assert result.sequence_bindings == ()


def test_same_name_length_conflict_is_unsatisfied() -> None:
    snapshot = _alignment_snapshot((SequenceDictionaryRecord(name="chr1", length=5, md5=_MD5_A),))
    contract = build_alignment_contract(snapshot, _context())

    result = reason_bundle(
        _request(),
        _anchor_snapshot(),
        (ResourceContract(_REFERENCE), contract),
    )

    assert [item.state for item in result.evaluations] == [
        ConstraintState.SATISFIED,
        ConstraintState.UNSATISFIED,
        ConstraintState.SATISFIED,
    ]


def test_same_name_m5_conflict_is_unsatisfied() -> None:
    snapshot = _alignment_snapshot((SequenceDictionaryRecord(name="chr1", length=4, md5=_MD5_B),))
    contract = build_alignment_contract(snapshot, _context())

    result = reason_bundle(
        _request(),
        _anchor_snapshot(),
        (ResourceContract(_REFERENCE), contract),
    )

    assert [item.state for item in result.evaluations] == [
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.UNSATISFIED,
    ]


def test_cross_name_m5_and_an_do_not_create_binding_in_contract_slice() -> None:
    snapshot = _alignment_snapshot(
        (
            SequenceDictionaryRecord(
                name="1",
                length=4,
                md5=_MD5_A,
                alternate_names=("chr1",),
            ),
        )
    )
    contract = build_alignment_contract(snapshot, _context())

    result = reason_bundle(
        _request(),
        _anchor_snapshot(),
        (ResourceContract(_REFERENCE), contract),
    )

    assert contract.capabilities == ()
    assert result.sequence_bindings == ()
    assert all(item.state is ConstraintState.UNRESOLVED for item in result.evaluations)
