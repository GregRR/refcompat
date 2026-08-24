from pathlib import Path
from typing import cast

import pytest

from refcompat.model import (
    ArtifactIdentity,
    CapabilityId,
    CollectionCompleteness,
    ConditionKind,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
    FindingKind,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    RefgetSequenceId,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SatisfactionMode,
    SequenceCollectionSnapshot,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderRequirement,
    SequencePresenceRequirement,
    SnapshotSequence,
)
from refcompat.reasoning import reason_bundle

_REFERENCE = ResourceId("reference")
_CONSUMER = ResourceId("consumer")
_PEER = ResourceId("peer")
_A = RefgetSequenceId("SQ." + "A" * 32)
_B = RefgetSequenceId("SQ." + "B" * 32)
_ORIGIN = RequirementOrigin.CORE_FORMAT
_LEVEL = RequirementLevel.MANDATORY


def _resource(resource_id: ResourceId, kind: ResourceKind) -> Resource:
    return Resource(resource_id, kind, ArtifactIdentity(path=Path(str(resource_id))))


def _request(
    *,
    include_peer: bool = False,
    scope_peer: bool = False,
    names: tuple[str, ...] | None = None,
) -> EvaluationRequest:
    resources = [
        _resource(_REFERENCE, ResourceKind.FASTA),
        _resource(_CONSUMER, ResourceKind.SEQUENCE_DICTIONARY),
    ]
    scope = [_REFERENCE, _CONSUMER]
    if include_peer:
        resources.append(_resource(_PEER, ResourceKind.SEQUENCE_DICTIONARY))
        if scope_peer:
            scope.append(_PEER)
    return EvaluationRequest(tuple(resources), _REFERENCE, EvaluationScope(tuple(scope), names))


def _snapshot(
    sequences: tuple[SnapshotSequence, ...] | None = None,
) -> SequenceCollectionSnapshot:
    return SequenceCollectionSnapshot(
        _REFERENCE,
        CollectionCompleteness.COMPLETE,
        sequences=sequences
        or (
            SnapshotSequence("chr1", 10, 0, _A),
            SnapshotSequence("chr2", 20, 1, _B),
        ),
    )


def test_bundle_evaluates_all_requirements_against_anchor_without_verdict() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId("presence"), _CONSUMER, _ORIGIN, _LEVEL, "chr1"
            ),
            SequenceLengthRequirement(
                RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "chr2", 20
            ),
        ),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert [e.state for e in result.evaluations] == [
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    ]
    assert result.interpretation.findings == ()
    assert not hasattr(result, "verdict")


def test_cross_name_binding_satisfies_typed_requirements() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequencePresenceRequirement(RequirementId("presence"), _CONSUMER, _ORIGIN, _LEVEL, "1"),
            SequenceLengthRequirement(RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "1", 10),
            SequenceIdentityRequirement(
                RequirementId("identity"), _CONSUMER, _ORIGIN, _LEVEL, "1", _A
            ),
        ),
        capabilities=(SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "1", _A),),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert len(result.sequence_bindings) == 1
    assert [e.satisfaction_mode for e in result.evaluations] == [
        SatisfactionMode.VERIFIED_ALIAS,
        SatisfactionMode.VERIFIED_ALIAS,
        SatisfactionMode.VERIFIED_SEQUENCE_IDENTITY,
    ]
    assert all(
        item.method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING for item in result.evidence.evidence
    )
    assert all(e.sequence_binding_ids for e in result.evidence.evidence)


def test_cross_name_without_binding_stays_unresolved() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "1", 10),
        ),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_peer_resource_cannot_vote_in_place_of_anchor() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(
                RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "missing", 10
            ),
        ),
    )
    peer = ResourceContract(
        _PEER,
        capabilities=(SequenceLengthCapability(CapabilityId("peer"), _PEER, "missing", 10),),
    )
    result = reason_bundle(
        _request(include_peer=True, scope_peer=True),
        _snapshot(),
        (peer, consumer, ResourceContract(_REFERENCE)),
    )
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert all(
        capability.resource_id == _REFERENCE
        for constraint in result.constraints
        for capability in constraint.candidate_capabilities
    )


def test_verified_binding_overrides_misleading_same_string_name() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(
                RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "chr1", 20
            ),
        ),
        capabilities=(SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "chr1", _B),),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert result.sequence_bindings[0].anchor_sequence_name == "chr2"
    assert result.evaluations[0].state is ConstraintState.SATISFIED
    assert result.evaluations[0].satisfaction_mode is SatisfactionMode.VERIFIED_ALIAS
    assert result.evidence.evidence[0].method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING
    assert result.evidence.evidence[0].sequence_binding_ids == (result.sequence_bindings[0].id,)


def test_bindings_project_sequence_order() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceOrderRequirement(
                RequirementId("order"), _CONSUMER, _ORIGIN, _LEVEL, ("1", "2")
            ),
        ),
        capabilities=(
            SequenceIdentityCapability(CapabilityId("one"), _CONSUMER, "1", _A),
            SequenceIdentityCapability(CapabilityId("two"), _CONSUMER, "2", _B),
        ),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert result.evaluations[0].satisfaction_mode is SatisfactionMode.VERIFIED_ALIAS
    assert len(result.evidence.evidence[0].sequence_binding_ids) == 2


def test_duplicate_anchor_content_leaves_cross_name_requirement_unresolved() -> None:
    snapshot = _snapshot(
        (
            SnapshotSequence("chr1", 10, 0, _A),
            SnapshotSequence("chrDup", 10, 1, _A),
        )
    )
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "1", 10),
        ),
        capabilities=(SequenceIdentityCapability(CapabilityId("local"), _CONSUMER, "1", _A),),
    )
    result = reason_bundle(_request(), snapshot, (ResourceContract(_REFERENCE), consumer))
    assert result.sequence_bindings == ()
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED


def test_contract_input_order_does_not_change_bundle_result() -> None:
    request = _request(include_peer=True, scope_peer=True)
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(
                RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "chr1", 10
            ),
        ),
    )
    anchor = ResourceContract(_REFERENCE)
    peer = ResourceContract(_PEER)
    assert reason_bundle(request, _snapshot(), (anchor, consumer, peer)) == reason_bundle(
        request, _snapshot(), (peer, consumer, anchor)
    )


def test_bundle_preserves_explicit_scope_conditions() -> None:
    result = reason_bundle(
        _request(include_peer=True, names=("chr1",)),
        _snapshot(),
        (ResourceContract(_REFERENCE), ResourceContract(_CONSUMER)),
    )
    assert [condition.kind for condition in result.interpretation.conditions] == [
        ConditionKind.EXPLICIT_RESOURCE_SCOPE,
        ConditionKind.EXPLICIT_ANCHOR_SEQUENCE_SCOPE,
    ]


def test_bundle_requires_contract_for_every_scoped_resource() -> None:
    with pytest.raises(ValueError, match="exactly one contract per scoped resource"):
        reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE),))


def test_bundle_rejects_duplicate_resource_contracts() -> None:
    consumer = ResourceContract(_CONSUMER)
    with pytest.raises(ValueError, match="contracts must have unique resource IDs"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), consumer, consumer),
        )


def test_explicit_anchor_sequence_scope_hides_out_of_scope_presence() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequencePresenceRequirement(
                RequirementId("presence"), _CONSUMER, _ORIGIN, _LEVEL, "chr2"
            ),
        ),
    )
    result = reason_bundle(
        _request(names=("chr1",)),
        _snapshot(),
        (ResourceContract(_REFERENCE), consumer),
    )
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_explicit_anchor_sequence_scope_hides_out_of_scope_anchor_facts() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(
                RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "chr2", 20
            ),
        ),
    )
    result = reason_bundle(
        _request(names=("chr1",)),
        _snapshot(),
        (ResourceContract(_REFERENCE), consumer),
    )
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_missing_raw_name_does_not_synthesize_negative_presence() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequencePresenceRequirement(RequirementId("presence"), _CONSUMER, _ORIGIN, _LEVEL, "1"),
        ),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_constraint_carries_only_bindings_relevant_to_its_requirement() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "1", 10),
        ),
        capabilities=(
            SequenceIdentityCapability(CapabilityId("one"), _CONSUMER, "1", _A),
            SequenceIdentityCapability(CapabilityId("two"), _CONSUMER, "2", _B),
        ),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert len(result.sequence_bindings) == 2
    assert len(result.constraints[0].sequence_bindings) == 1
    assert result.constraints[0].sequence_bindings[0].local_sequence_name == "1"


def test_order_requirement_crossing_explicit_sequence_scope_stays_unresolved() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceOrderRequirement(
                RequirementId("order"), _CONSUMER, _ORIGIN, _LEVEL, ("chr1", "chr2")
            ),
        ),
    )
    result = reason_bundle(
        _request(names=("chr1",)),
        _snapshot(),
        (ResourceContract(_REFERENCE), consumer),
    )
    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_same_name_identity_binding_is_not_attached_when_projection_is_exact() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            SequenceLengthRequirement(
                RequirementId("length"), _CONSUMER, _ORIGIN, _LEVEL, "chr1", 10
            ),
        ),
        capabilities=(SequenceIdentityCapability(CapabilityId("identity"), _CONSUMER, "chr1", _A),),
    )
    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
    assert len(result.sequence_bindings) == 1
    assert result.constraints[0].sequence_bindings == ()
    assert result.evaluations[0].satisfaction_mode is SatisfactionMode.EXACT
    assert result.evidence.evidence[0].method is EvidenceMethod.EXACT_TYPED_CONSTRAINT


def test_bundle_leaves_pair_derived_reference_base_requirement_unresolved() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            ReferenceBaseRequirement(
                RequirementId("reference-bases"),
                _CONSUMER,
                _REFERENCE,
                _ORIGIN,
                _LEVEL,
                10,
            ),
        ),
    )

    result = reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))

    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.constraints[0].candidate_capabilities == ()
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def _reference_base_contract(*, count: int = 10) -> ResourceContract:
    return ResourceContract(
        _CONSUMER,
        requirements=(
            ReferenceBaseRequirement(
                RequirementId("reference-bases"),
                _CONSUMER,
                _REFERENCE,
                _ORIGIN,
                _LEVEL,
                count,
            ),
        ),
    )


def _reference_base_capability(
    *,
    capability_id: str = "direct-ref",
    resource_id: ResourceId = _REFERENCE,
    subject_resource_id: ResourceId = _CONSUMER,
    checked_count: int = 10,
    match_count: int = 10,
    mismatch_count: int = 0,
    unresolved_count: int = 0,
) -> ReferenceBaseValidationCapability:
    return ReferenceBaseValidationCapability(
        CapabilityId(capability_id),
        resource_id,
        subject_resource_id,
        checked_count,
        match_count,
        mismatch_count,
        unresolved_count,
    )


def test_bundle_ingests_anchor_owned_reference_base_capability() -> None:
    capability = _reference_base_capability()
    result = reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), _reference_base_contract()),
        supplemental_capabilities=(capability,),
    )

    assert result.supplemental_capabilities == (capability,)
    assert result.constraints[0].candidate_capabilities == (capability,)
    assert result.evaluations[0].state is ConstraintState.SATISFIED
    assert result.evaluations[0].satisfaction_mode is SatisfactionMode.EXHAUSTIVE_DIRECT
    assert len(result.evidence.supporting_evidence) == 1
    assert (
        result.evidence.supporting_evidence[0].method
        is EvidenceMethod.EXHAUSTIVE_REFERENCE_BASE_VALIDATION
    )
    assert (
        result.evidence.supporting_evidence[0].strength
        is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    )
    assert result.evidence.supporting_evidence[0].polarity is EvidencePolarity.SUPPORTS


def test_bundle_reference_base_mismatch_remains_hard_contradiction() -> None:
    capability = _reference_base_capability(
        match_count=999_999, mismatch_count=1, checked_count=1_000_000
    )
    result = reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), _reference_base_contract(count=1_000_000)),
        supplemental_capabilities=(capability,),
    )

    assert result.evaluations[0].state is ConstraintState.UNSATISFIED
    assert result.interpretation.findings[0].kind is FindingKind.REFERENCE_BASE_CONFLICT
    assert len(result.evidence.conclusive_contradictions) == 1


def test_bundle_reference_base_incomplete_validation_stays_unresolved_without_evidence() -> None:
    capability = _reference_base_capability(match_count=9, unresolved_count=1)
    result = reason_bundle(
        _request(),
        _snapshot(),
        (ResourceContract(_REFERENCE), _reference_base_contract()),
        supplemental_capabilities=(capability,),
    )

    assert result.evaluations[0].state is ConstraintState.UNRESOLVED
    assert result.evidence.evidence == ()
    assert result.interpretation.findings[0].kind is FindingKind.UNRESOLVED_REQUIREMENT


def test_bundle_rejects_wrong_anchor_supplemental_capability() -> None:
    wrong_anchor = _reference_base_capability(resource_id=ResourceId("peer-anchor"))
    with pytest.raises(ValueError, match="selected FASTA anchor"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), _reference_base_contract()),
            supplemental_capabilities=(wrong_anchor,),
        )


def test_bundle_rejects_supplemental_capability_for_unscoped_subject() -> None:
    unscoped = _reference_base_capability(subject_resource_id=ResourceId("outside"))
    with pytest.raises(ValueError, match="only scoped resources"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), _reference_base_contract()),
            supplemental_capabilities=(unscoped,),
        )


def test_bundle_rejects_unused_supplemental_capability() -> None:
    capability = _reference_base_capability()
    with pytest.raises(ValueError, match="must match a scoped requirement"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), ResourceContract(_CONSUMER)),
            supplemental_capabilities=(capability,),
        )


def test_bundle_rejects_supplemental_capability_with_wrong_record_count() -> None:
    capability = _reference_base_capability(checked_count=5, match_count=5)
    with pytest.raises(ValueError, match="must match a scoped requirement"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), _reference_base_contract()),
            supplemental_capabilities=(capability,),
        )


def test_bundle_rejects_non_reference_base_supplemental_capability() -> None:
    wrong_type = cast(
        ReferenceBaseValidationCapability,
        SequenceLengthCapability(CapabilityId("wrong-type"), _REFERENCE, "chr1", 10),
    )
    with pytest.raises(TypeError, match="must be reference-base validations"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), _reference_base_contract()),
            supplemental_capabilities=(wrong_type,),
        )


def test_bundle_rejects_duplicate_supplemental_capability_ids() -> None:
    first = _reference_base_capability()
    second = _reference_base_capability(match_count=9, unresolved_count=1)
    with pytest.raises(ValueError, match="IDs must be unique"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), _reference_base_contract()),
            supplemental_capabilities=(first, second),
        )


def test_bundle_rejects_multiple_exhaustive_capabilities_for_one_requirement() -> None:
    first = _reference_base_capability(capability_id="first")
    second = _reference_base_capability(capability_id="second", match_count=9, unresolved_count=1)
    with pytest.raises(ValueError, match="only one exhaustive supplemental capability"):
        reason_bundle(
            _request(),
            _snapshot(),
            (ResourceContract(_REFERENCE), _reference_base_contract()),
            supplemental_capabilities=(first, second),
        )


def test_bundle_rejects_reference_base_requirement_for_different_anchor() -> None:
    consumer = ResourceContract(
        _CONSUMER,
        requirements=(
            ReferenceBaseRequirement(
                RequirementId("reference-bases"),
                _CONSUMER,
                ResourceId("wrong-anchor"),
                _ORIGIN,
                _LEVEL,
                10,
            ),
        ),
    )
    with pytest.raises(ValueError, match="must name the selected FASTA anchor"):
        reason_bundle(_request(), _snapshot(), (ResourceContract(_REFERENCE), consumer))
