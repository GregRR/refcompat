"""Tests for exhaustive sequence-content absence reasoning."""

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model import (
    ArtifactIdentity,
    CapabilityId,
    CollectionCompleteness,
    CompatibilityVerdict,
    ConstraintId,
    ConstraintState,
    EvaluationRequest,
    EvaluationScope,
    EvidenceMethod,
    EvidencePolarity,
    EvidenceStrength,
    Md5Digest,
    ObservationId,
    ReferenceContext,
    RefgetSequenceId,
    Requirement,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
    SnapshotSequence,
)
from refcompat.reasoning import (
    aggregate_bundle_verdict,
    build_constraint,
    build_reference_context,
    derive_constraint_evidence,
    derive_sequence_identity_absences,
    evaluate_constraint,
    reason_bundle,
)

_FASTA = ResourceId("fasta")
_CONSUMER = ResourceId("consumer")
_MD5_A = Md5Digest("0" * 32)
_MD5_B = Md5Digest("1" * 32)
_MD5_C = Md5Digest("2" * 32)
_REFGET_A = RefgetSequenceId("SQ." + "A" * 32)


def _request(anchor_names: tuple[str, ...] | None = None) -> EvaluationRequest:
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    consumer = Resource(
        _CONSUMER,
        ResourceKind.SEQUENCE_DICTIONARY,
        ArtifactIdentity(Path("consumer.dict")),
    )
    return EvaluationRequest(
        (fasta, consumer),
        _FASTA,
        EvaluationScope((_FASTA, _CONSUMER), anchor_names),
    )


def _context(
    *sequences: SnapshotSequence,
    anchor_names: tuple[str, ...] | None = None,
) -> tuple[EvaluationRequest, SequenceCollectionSnapshot, ReferenceContext]:
    request = _request(anchor_names)
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )
    return request, snapshot, build_reference_context(request, snapshot)


def _presence_contract(
    sequence_name: str,
    *capabilities: SequenceIdentityCapability,
    identity_requirement: SequenceIdentityRequirement | None = None,
) -> ResourceContract:
    requirements: list[Requirement] = [
        SequencePresenceRequirement(
            RequirementId("presence"),
            _CONSUMER,
            RequirementOrigin.CORE_FORMAT,
            RequirementLevel.MANDATORY,
            sequence_name,
        )
    ]
    if identity_requirement is not None:
        requirements.append(identity_requirement)
    return ResourceContract(
        _CONSUMER,
        requirements=tuple(requirements),
        capabilities=capabilities,
    )


def _identity(
    capability_id: str,
    sequence_name: str,
    identity: Md5Digest | RefgetSequenceId,
    provenance: SequenceIdentityProvenance = SequenceIdentityProvenance.CONTENT_DERIVED,
) -> SequenceIdentityCapability:
    return SequenceIdentityCapability(
        CapabilityId(capability_id),
        _CONSUMER,
        sequence_name,
        identity,
        provenance,
        source_observation_ids=(ObservationId(f"obs:{capability_id}"),),
    )


def test_complete_content_identity_no_match_derives_absence() -> None:
    _request_value, _snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    local = _identity("local", "1", _MD5_B)
    contract = _presence_contract("1", local)

    absences = derive_sequence_identity_absences(
        context,
        (ResourceContract(_FASTA), contract),
    )

    assert len(absences) == 1
    absence = absences[0]
    assert absence.resource_id == _FASTA
    assert absence.subject_resource_id == _CONSUMER
    assert absence.sequence_name == "1"
    assert absence.identity_values == (_MD5_B,)
    assert absence.source_identity_capability_ids == (local.id,)
    assert absence.source_observation_ids == local.source_observation_ids


def test_metadata_identity_cannot_prove_absence_with_complete_anchor_coverage() -> None:
    _request_value, _snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    metadata = _identity(
        "metadata",
        "1",
        _MD5_B,
        SequenceIdentityProvenance.DECLARED_METADATA,
    )
    contract = _presence_contract("1", metadata)

    assert (
        derive_sequence_identity_absences(
            context,
            (ResourceContract(_FASTA), contract),
        )
        == ()
    )


def test_incomplete_identity_coverage_cannot_prove_absence() -> None:
    _request_value, _snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
        SnapshotSequence("chr2", 10, 1),
    )
    content = _identity("content", "1", _MD5_B)
    contract = _presence_contract("1", content)

    assert (
        derive_sequence_identity_absences(
            context,
            (ResourceContract(_FASTA), contract),
        )
        == ()
    )


def test_anchor_match_ambiguity_or_scope_exclusion_cannot_prove_absence() -> None:
    local = _identity("local", "1", _MD5_A)
    contract = _presence_contract("1", local)

    _request_value, _snapshot, duplicate_context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
        SnapshotSequence("chrDup", 10, 1, md5=_MD5_A),
    )
    assert (
        derive_sequence_identity_absences(
            duplicate_context,
            (ResourceContract(_FASTA), contract),
        )
        == ()
    )

    _request_value, _snapshot, scoped_context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_B),
        SnapshotSequence("chr2", 10, 1, md5=_MD5_A),
        anchor_names=("chr1",),
    )
    assert (
        derive_sequence_identity_absences(
            scoped_context,
            (ResourceContract(_FASTA), contract),
        )
        == ()
    )


def test_conflicting_local_identity_or_any_anchor_match_blocks_absence() -> None:
    _request_value, _snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, _REFGET_A, _MD5_A),
    )
    conflicting = _presence_contract(
        "1",
        _identity("md5-b", "1", _MD5_B),
        _identity("md5-c", "1", _MD5_C),
    )
    assert (
        derive_sequence_identity_absences(
            context,
            (ResourceContract(_FASTA), conflicting),
        )
        == ()
    )

    mixed = _presence_contract(
        "1",
        _identity("refget-match", "1", _REFGET_A),
        _identity("md5-absent", "1", _MD5_B),
    )
    assert (
        derive_sequence_identity_absences(
            context,
            (ResourceContract(_FASTA), mixed),
        )
        == ()
    )


def test_incomplete_scheme_positive_match_blocks_complete_scheme_absence() -> None:
    _request_value, _snapshot, context = _context(
        SnapshotSequence(
            "chr1",
            10,
            0,
            refget_id=_REFGET_A,
            md5=_MD5_A,
        ),
        SnapshotSequence("chr2", 10, 1, md5=_MD5_C),
    )
    mixed = _presence_contract(
        "1",
        _identity("md5-absent", "1", _MD5_B),
        _identity("refget-match", "1", _REFGET_A),
    )

    assert (
        derive_sequence_identity_absences(
            context,
            (ResourceContract(_FASTA), mixed),
        )
        == ()
    )


def test_mandatory_exact_identity_conflict_suppresses_redundant_absence() -> None:
    _request_value, _snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    local = _identity("local", "chr1", _MD5_B)
    identity_requirement = SequenceIdentityRequirement(
        RequirementId("identity"),
        _CONSUMER,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        "chr1",
        _MD5_B,
    )
    contract = _presence_contract(
        "chr1",
        local,
        identity_requirement=identity_requirement,
    )

    assert (
        derive_sequence_identity_absences(
            context,
            (ResourceContract(_FASTA), contract),
        )
        == ()
    )


def test_scoped_same_name_identity_does_not_false_reject_absence() -> None:
    request, snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
        SnapshotSequence("chr2", 10, 1, md5=_MD5_C),
        anchor_names=("chr2",),
    )
    local = _identity("local", "chr1", _MD5_B)
    identity_requirement = SequenceIdentityRequirement(
        RequirementId("identity"),
        _CONSUMER,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        "chr1",
        _MD5_B,
    )
    contract = _presence_contract(
        "chr1",
        local,
        identity_requirement=identity_requirement,
    )

    absences = derive_sequence_identity_absences(
        context,
        (ResourceContract(_FASTA), contract),
    )
    assert len(absences) == 1

    bundle = reason_bundle(
        request,
        snapshot,
        (ResourceContract(_FASTA), contract),
    )

    assert bundle.derived_capabilities == absences
    assert tuple(evaluation.state for evaluation in bundle.evaluations) == (
        ConstraintState.UNSATISFIED,
        ConstraintState.UNRESOLVED,
    )
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_exhaustive_identity_absence_overrides_same_name_presence_as_tier_a() -> None:
    requirement = SequencePresenceRequirement(
        RequirementId("presence"),
        _CONSUMER,
        RequirementOrigin.CORE_FORMAT,
        RequirementLevel.MANDATORY,
        "chr1",
    )
    present = SequencePresenceCapability(
        CapabilityId("present"),
        _FASTA,
        "chr1",
        True,
    )
    absence = SequenceIdentityAbsenceCapability(
        CapabilityId("absence"),
        _FASTA,
        _CONSUMER,
        "chr1",
        (_MD5_B,),
        (CapabilityId("source"),),
        (ObservationId("obs:source"),),
    )
    constraint = build_constraint(
        ConstraintId("presence"),
        requirement,
        (present, absence),
    )

    evaluation = evaluate_constraint(constraint)
    evidence = derive_constraint_evidence(constraint, evaluation)

    assert evaluation.state is ConstraintState.UNSATISFIED
    assert evaluation.relevant_capability_ids == (absence.id,)
    assert len(evidence) == 1
    assert evidence[0].method is EvidenceMethod.EXHAUSTIVE_SEQUENCE_IDENTITY_ABSENCE
    assert evidence[0].strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT
    assert evidence[0].polarity is EvidencePolarity.CONTRADICTS


def test_whole_bundle_proven_absence_is_incompatible() -> None:
    request, snapshot, context = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    local = _identity("local", "1", _MD5_B)
    contract = _presence_contract("1", local)

    bundle = reason_bundle(
        request,
        snapshot,
        (ResourceContract(_FASTA), contract),
    )

    assert len(bundle.derived_capabilities) == 1
    assert bundle.reference_context == context
    assert bundle.evaluations[0].state is ConstraintState.UNSATISFIED
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_whole_bundle_content_absence_overrides_same_name_label() -> None:
    request, snapshot, _context_value = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    local = _identity("local", "chr1", _MD5_B)
    contract = _presence_contract("chr1", local)

    bundle = reason_bundle(
        request,
        snapshot,
        (ResourceContract(_FASTA), contract),
    )

    assert len(bundle.derived_capabilities) == 1
    assert bundle.evaluations[0].state is ConstraintState.UNSATISFIED
    assert (
        bundle.evidence.conclusive_contradictions[0].method
        is EvidenceMethod.EXHAUSTIVE_SEQUENCE_IDENTITY_ABSENCE
    )
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_bundle_rejects_absence_when_other_local_scheme_matches_anchor() -> None:
    request, snapshot, _context_value = _context(
        SnapshotSequence(
            "chr1",
            10,
            0,
            refget_id=_REFGET_A,
            md5=_MD5_A,
        ),
        SnapshotSequence("chr2", 10, 1, md5=_MD5_C),
    )
    md5_absent = _identity("md5-absent", "1", _MD5_B)
    contract = _presence_contract("1", md5_absent)
    bundle = reason_bundle(
        request,
        snapshot,
        (ResourceContract(_FASTA), contract),
    )
    assert len(bundle.derived_capabilities) == 1

    refget_match = _identity("refget-match", "1", _REFGET_A)
    contradictory_contract = _presence_contract(
        "1",
        md5_absent,
        refget_match,
    )
    with pytest.raises(ValueError, match="absent from the complete anchor"):
        replace(
            bundle,
            contracts=(ResourceContract(_FASTA), contradictory_contract),
        )


def test_bundle_rejects_crosswired_derived_absence_trace() -> None:
    request, snapshot, _context_value = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    local = _identity("local", "1", _MD5_B)
    contract = _presence_contract("1", local)
    bundle = reason_bundle(
        request,
        snapshot,
        (ResourceContract(_FASTA), contract),
    )
    derived = bundle.derived_capabilities[0]

    with pytest.raises(ValueError, match="subject contract"):
        replace(
            bundle,
            derived_capabilities=(
                replace(
                    derived,
                    source_identity_capability_ids=(CapabilityId("wrong-source"),),
                ),
            ),
        )

    with pytest.raises(ValueError, match="observations must match"):
        replace(
            bundle,
            derived_capabilities=(
                replace(
                    derived,
                    source_observation_ids=(ObservationId("obs:forged"),),
                ),
            ),
        )


def test_bundle_rejects_semantically_forged_identity_absence() -> None:
    request, snapshot, _context_value = _context(
        SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
    )
    local = _identity("local", "1", _MD5_B)
    contract = _presence_contract("1", local)
    bundle = reason_bundle(
        request,
        snapshot,
        (ResourceContract(_FASTA), contract),
    )
    derived = bundle.derived_capabilities[0]

    forged_local = replace(local, identity=_MD5_A)
    forged_contract = _presence_contract("1", forged_local)
    forged_derived = replace(derived, identity_values=(_MD5_A,))
    with pytest.raises(ValueError, match="absent from the complete anchor"):
        replace(
            bundle,
            contracts=(ResourceContract(_FASTA), forged_contract),
            derived_capabilities=(forged_derived,),
        )

    incomplete_snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence("chr1", 10, 0, md5=_MD5_A),
            SnapshotSequence("chr2", 10, 1),
        ),
    )
    incomplete_context = build_reference_context(request, incomplete_snapshot)
    with pytest.raises(ValueError, match="complete anchor identity coverage"):
        replace(bundle, reference_context=incomplete_context)
