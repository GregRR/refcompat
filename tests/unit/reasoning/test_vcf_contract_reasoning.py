"""Tests for VCF projection into generic contracts and evidence."""

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model.constraints import (
    ConstraintId,
    ConstraintState,
    SatisfactionMode,
)
from refcompat.model.contracts import (
    ReferenceBaseRequirement,
    ResourceContract,
    SequenceIdentityRequirement,
    SequenceLengthRequirement,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.evidence import EvidenceMethod
from refcompat.model.identity import (
    CollectionCompleteness,
    Md5Digest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import ReferenceContext, SequenceBindingId
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.vcf import (
    VcfChromUsage,
    VcfContextSnapshot,
    VcfContigDeclaration,
    VcfHeaderData,
)
from refcompat.model.vcf_ref import (
    VcfRefCheckState,
    VcfRefRecord,
    VcfRefRecordCheck,
    VcfRefSequenceSummary,
    VcfRefValidationResult,
)
from refcompat.model.vcf_ref_pattern import VcfRefConflictPattern
from refcompat.model.verdict import CompatibilityVerdict
from refcompat.reasoning import aggregate_bundle_verdict, reason_bundle
from refcompat.reasoning.reference_context import build_reference_context
from refcompat.reasoning.vcf_binding import derive_vcf_sequence_bindings
from refcompat.reasoning.vcf_contract import project_vcf_contract
from refcompat.reasoning.vcf_ref import evaluate_vcf_ref_records

_VCF = ResourceId("variants")
_FASTA = ResourceId("fasta")


def _context(*names: str) -> ReferenceContext:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, EvaluationScope((_FASTA, _VCF)))
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=tuple(SnapshotSequence(name, 100, index) for index, name in enumerate(names)),
    )
    return build_reference_context(request, snapshot)


def _vcf_snapshot(*usage: tuple[str, int]) -> VcfContextSnapshot:
    return VcfContextSnapshot(
        _VCF,
        VcfHeaderData("VCFv4.5"),
        record_count=sum(count for _, count in usage),
        chrom_usage=tuple(VcfChromUsage(name, count) for name, count in usage),
    )


def _validation(
    *summaries: VcfRefSequenceSummary,
    matches: int,
    mismatches: tuple[VcfRefRecordCheck, ...] = (),
    out_of_bounds: tuple[VcfRefRecordCheck, ...] = (),
    unresolved: tuple[VcfRefRecordCheck, ...] = (),
    fasta_resource_id: ResourceId = _FASTA,
    vcf_resource_id: ResourceId = _VCF,
    binding_ids: tuple[SequenceBindingId, ...] = (),
) -> VcfRefValidationResult:
    problems = (*mismatches, *out_of_bounds, *unresolved)
    return VcfRefValidationResult(
        vcf_resource_id,
        fasta_resource_id,
        record_count=matches + len(problems),
        match_count=matches,
        mismatch_count=len(mismatches),
        out_of_bounds_count=len(out_of_bounds),
        unresolved_sequence_count=len(unresolved),
        sequence_summaries=summaries,
        problem_records=problems,
        sequence_binding_ids=binding_ids,
    )


_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")


def _binding_context() -> ReferenceContext:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, EvaluationScope((_FASTA, _VCF)))
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),),
    )
    return build_reference_context(request, snapshot)


class _Reference:
    resource_id = _FASTA

    def sequence_length(self, sequence_name: str) -> int | None:
        return 4 if sequence_name == "chr1" else None

    def fetch(self, sequence_name: str, start: int, end: int) -> str:
        assert sequence_name == "chr1"
        return "ACGT"[start:end]


def test_projection_creates_used_sequence_presence_and_one_base_requirement() -> None:
    snapshot = _vcf_snapshot(("chr1", 2), ("chr2", 1))
    validation = _validation(
        VcfRefSequenceSummary("chr1", 2, match_count=2),
        VcfRefSequenceSummary("chr2", 1, match_count=1),
        matches=3,
    )
    projection = project_vcf_contract(snapshot, validation, _context("chr1", "chr2"))
    presence = tuple(
        item
        for item in projection.contract.requirements
        if isinstance(item, SequencePresenceRequirement)
    )
    base = tuple(
        item
        for item in projection.contract.requirements
        if isinstance(item, ReferenceBaseRequirement)
    )
    assert tuple(item.sequence_name for item in presence) == ("chr1", "chr2")
    assert len(base) == 1
    assert base[0].anchor_resource_id == _FASTA
    assert base[0].record_count == 3
    direct_support = tuple(
        item
        for item in projection.evidence.supporting_evidence
        if item.method is EvidenceMethod.EXHAUSTIVE_REFERENCE_BASE_VALIDATION
    )
    assert len(direct_support) == 1
    assert direct_support[0].capability_id == projection.reference_base_capability.id
    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )


def test_projection_keeps_one_local_mismatch_as_hard_generic_contradiction() -> None:
    mismatch = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 9, "chr1", 10, "T"),
        VcfRefCheckState.MISMATCH,
        anchor_sequence_name="chr1",
        fasta_bases="A",
    )
    snapshot = _vcf_snapshot(("chr1", 10))
    validation = _validation(
        VcfRefSequenceSummary("chr1", 10, match_count=9, mismatch_count=1),
        matches=9,
        mismatches=(mismatch,),
    )
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    assert projection.evaluations[-1].state is ConstraintState.UNSATISFIED
    assert projection.reference_base_capability.mismatch_count == 1
    assert len(projection.evidence.conclusive_contradictions) == 1
    assert projection.conflict_pattern.pattern is VcfRefConflictPattern.ISOLATED


def test_projection_preserves_unresolved_sequence_without_guessing_alias() -> None:
    unresolved = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 0, "1", 1, "A"),
        VcfRefCheckState.UNRESOLVED_SEQUENCE,
    )
    snapshot = _vcf_snapshot(("1", 1))
    validation = _validation(
        VcfRefSequenceSummary("1", 1, unresolved_sequence_count=1),
        matches=0,
        unresolved=(unresolved,),
    )
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
    assert projection.evidence.evidence == ()


def test_projection_hard_mismatch_precedes_other_unresolved_records() -> None:
    mismatch = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 0, "chr1", 1, "T"),
        VcfRefCheckState.MISMATCH,
        anchor_sequence_name="chr1",
        fasta_bases="A",
    )
    unresolved = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 1, "missing", 1, "A"),
        VcfRefCheckState.UNRESOLVED_SEQUENCE,
    )
    snapshot = _vcf_snapshot(("chr1", 1), ("missing", 1))
    validation = _validation(
        VcfRefSequenceSummary("chr1", 1, mismatch_count=1),
        VcfRefSequenceSummary("missing", 1, unresolved_sequence_count=1),
        matches=0,
        mismatches=(mismatch,),
        unresolved=(unresolved,),
    )
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    assert projection.evaluations[-1].state is ConstraintState.UNSATISFIED
    assert projection.evidence.has_conclusive_contradiction
    assert projection.conflict_pattern.pattern is VcfRefConflictPattern.UNCLASSIFIED


def test_projection_empty_vcf_has_not_applicable_base_requirement() -> None:
    snapshot = _vcf_snapshot()
    validation = _validation(matches=0)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    assert len(projection.contract.requirements) == 1
    assert projection.evaluations[0].state is ConstraintState.NOT_APPLICABLE


def test_projection_rejects_crosswired_resources_and_sequence_coverage() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    good_summary = VcfRefSequenceSummary("chr1", 1, match_count=1)
    with pytest.raises(ValueError, match="same VCF resource"):
        project_vcf_contract(
            snapshot,
            _validation(good_summary, matches=1, vcf_resource_id=ResourceId("other")),
            _context("chr1"),
        )
    with pytest.raises(ValueError, match="FASTA anchor"):
        project_vcf_contract(
            snapshot,
            _validation(good_summary, matches=1, fasta_resource_id=ResourceId("other")),
            _context("chr1"),
        )
    with pytest.raises(ValueError, match="CHROM usage"):
        project_vcf_contract(
            snapshot,
            _validation(VcfRefSequenceSummary("chr2", 1, match_count=1), matches=1),
            _context("chr1", "chr2"),
        )


def test_projection_ids_are_deterministic() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    context = _context("chr1")
    first = project_vcf_contract(snapshot, validation, context)
    second = project_vcf_contract(snapshot, validation, context)
    assert first.contract == second.contract
    assert first.reference_base_capability.id == second.reference_base_capability.id
    assert tuple(item.id for item in first.constraints) == tuple(
        item.id for item in second.constraints
    )


def test_projection_out_of_bounds_only_keeps_base_requirement_unresolved() -> None:
    bounds = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 0, "chr1", 101, "A"),
        VcfRefCheckState.OUT_OF_BOUNDS,
        anchor_sequence_name="chr1",
    )
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(
        VcfRefSequenceSummary("chr1", 1, out_of_bounds_count=1),
        matches=0,
        out_of_bounds=(bounds,),
    )
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    assert projection.evaluations[0].state is ConstraintState.SATISFIED
    assert projection.evaluations[-1].state is ConstraintState.UNRESOLVED
    assert all(item.kind.value != "reference_bases" for item in projection.evidence.evidence)


def test_projection_uses_actual_chrom_usage_not_declared_unused_contigs() -> None:
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(
                VcfContigDeclaration("chr1", length=100),
                VcfContigDeclaration("chr2", length=200),
            ),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("chr1", 1),),
    )
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1", "chr2"))
    presence_names = tuple(
        item.sequence_name
        for item in projection.contract.requirements
        if isinstance(item, SequencePresenceRequirement)
    )
    assert presence_names == ("chr1",)
    length_names = tuple(
        item.sequence_name
        for item in projection.contract.requirements
        if isinstance(item, SequenceLengthRequirement)
    )
    assert length_names == ("chr1",)


def test_projection_model_rejects_capability_counts_crosswired_from_validation() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    crosswired = replace(
        projection.reference_base_capability,
        match_count=0,
        mismatch_count=1,
    )

    with pytest.raises(ValueError, match="match count must match validation"):
        replace(projection, reference_base_capability=crosswired)


def test_projection_model_rejects_duplicate_evaluation_constraint_ids() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))

    with pytest.raises(ValueError, match="evaluation constraint IDs must be unique"):
        replace(projection, evaluations=(projection.evaluations[0], projection.evaluations[0]))


def test_projection_model_requires_constraints_for_exact_contract_requirements() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    incomplete_contract = replace(
        projection.contract,
        requirements=projection.contract.requirements[1:],
    )

    with pytest.raises(ValueError, match="cover exactly the contract requirements"):
        replace(projection, contract=incomplete_contract)


def test_projection_model_rejects_unknown_aggregate_constraint_ids() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    crosswired_evidence = replace(
        projection.evidence,
        unresolved_constraint_ids=(ConstraintId("unknown"),),
    )

    with pytest.raises(ValueError, match="evidence references an unknown constraint"):
        replace(projection, evidence=crosswired_evidence)


def test_projection_sequence_coverage_check_ignores_summary_order() -> None:
    snapshot = _vcf_snapshot(("chr1", 1), ("chr2", 1))
    validation = _validation(
        VcfRefSequenceSummary("chr2", 1, match_count=1),
        VcfRefSequenceSummary("chr1", 1, match_count=1),
        matches=2,
    )

    projection = project_vcf_contract(snapshot, validation, _context("chr1", "chr2"))

    presence_names = tuple(
        item.sequence_name
        for item in projection.contract.requirements
        if isinstance(item, SequencePresenceRequirement)
    )
    assert presence_names == ("chr1", "chr2")
    assert projection.evaluations[-1].state is ConstraintState.SATISFIED
    assert projection.conflict_pattern.pattern is VcfRefConflictPattern.NONE


def test_projection_rejects_vcf_outside_reference_context_scope() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    context = _context("chr1")
    out_of_scope_context = replace(
        context,
        scope=EvaluationScope((_FASTA,)),
    )

    with pytest.raises(ValueError, match="inside the reference-context scope"):
        project_vcf_contract(snapshot, validation, out_of_scope_context)


def test_projection_model_rejects_crosswired_conflict_pattern() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    crosswired = replace(
        projection.conflict_pattern,
        vcf_resource_id=ResourceId("other"),
    )

    with pytest.raises(ValueError, match="conflict pattern must belong to the VCF"):
        replace(projection, conflict_pattern=crosswired)


def test_projection_model_rejects_crosswired_conflict_pattern_sequence_trace() -> None:
    snapshot = _vcf_snapshot(("chr1", 1))
    validation = _validation(VcfRefSequenceSummary("chr1", 1, match_count=1), matches=1)
    projection = project_vcf_contract(snapshot, validation, _context("chr1"))
    crosswired = replace(
        projection.conflict_pattern,
        compared_sequence_names=("chr2",),
    )

    with pytest.raises(ValueError, match="compared sequences must match validation"):
        replace(projection, conflict_pattern=crosswired)


def test_projection_pair_capability_can_feed_whole_bundle_reasoning() -> None:
    context = _context("chr1")
    snapshot = _vcf_snapshot(("chr1", 2))
    validation = _validation(
        VcfRefSequenceSummary("chr1", 2, match_count=2),
        matches=2,
    )
    projection = project_vcf_contract(snapshot, validation, context)
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, context.scope)

    bundle = reason_bundle(
        request,
        context.anchor_snapshot,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.reference_base_capability,),
    )

    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )
    assert bundle.supplemental_capabilities == (projection.reference_base_capability,)
    assert any(
        item.method is EvidenceMethod.EXHAUSTIVE_REFERENCE_BASE_VALIDATION
        for item in bundle.evidence.supporting_evidence
    )


def test_projection_rejects_stale_exact_name_validation_when_verified_alias_exists() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    unresolved = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 0, "1", 1, "A"),
        VcfRefCheckState.UNRESOLVED_SEQUENCE,
    )
    stale = _validation(
        VcfRefSequenceSummary("1", 1, unresolved_sequence_count=1),
        matches=0,
        unresolved=(unresolved,),
    )

    with pytest.raises(ValueError, match="must use exactly the verified sequence bindings"):
        project_vcf_contract(snapshot, stale, context)


def test_verified_alias_revalidation_projects_presence_and_direct_bases() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    bindings = derive_vcf_sequence_bindings(snapshot, context)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 1, "A"),),
        reference=_Reference(),
        sequence_bindings=bindings,
    )

    projection = project_vcf_contract(snapshot, validation, context)

    assert projection.sequence_bindings == bindings
    assert len(projection.contract.capabilities) == 1
    assert projection.evaluations[0].state is ConstraintState.SATISFIED
    assert projection.evaluations[0].satisfaction_mode is SatisfactionMode.VERIFIED_ALIAS
    assert projection.evaluations[-1].state is ConstraintState.SATISFIED
    assert any(
        item.method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING
        for item in projection.evidence.supporting_evidence
    )


def test_verified_alias_projection_feeds_whole_bundle_without_peer_voting() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    bindings = derive_vcf_sequence_bindings(snapshot, context)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 1, "A"),),
        reference=_Reference(),
        sequence_bindings=bindings,
    )
    projection = project_vcf_contract(snapshot, validation, context)
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, context.scope)

    bundle = reason_bundle(
        request,
        context.anchor_snapshot,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.reference_base_capability,),
    )

    assert bundle.sequence_bindings == projection.sequence_bindings
    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )
    assert bundle.evaluations[0].satisfaction_mode is SatisfactionMode.VERIFIED_ALIAS
    assert bundle.evaluations[1].satisfaction_mode is SatisfactionMode.VERIFIED_SEQUENCE_IDENTITY
    assert bundle.evaluations[2].satisfaction_mode is SatisfactionMode.VERIFIED_ALIAS


def test_used_valid_md5_creates_mandatory_identity_requirement() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("chr1", length=4, md5=_MD5_ACGT.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("chr1", 1),),
    )
    validation = _validation(
        VcfRefSequenceSummary("chr1", 1, match_count=1),
        matches=1,
    )

    projection = project_vcf_contract(snapshot, validation, context)

    identity_requirements = tuple(
        requirement
        for requirement in projection.contract.requirements
        if isinstance(requirement, SequenceIdentityRequirement)
    )
    assert len(identity_requirements) == 1
    assert identity_requirements[0].sequence_name == "chr1"
    assert identity_requirements[0].identity == _MD5_ACGT
    assert projection.sequence_bindings == ()
    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )


def test_used_declared_length_creates_mandatory_length_requirement() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("chr1", length=4),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("chr1", 1),),
    )
    validation = _validation(
        VcfRefSequenceSummary("chr1", 1, match_count=1),
        matches=1,
    )

    projection = project_vcf_contract(snapshot, validation, context)

    length_requirements = tuple(
        requirement
        for requirement in projection.contract.requirements
        if isinstance(requirement, SequenceLengthRequirement)
    )
    assert len(length_requirements) == 1
    assert length_requirements[0].sequence_name == "chr1"
    assert length_requirements[0].length == 4
    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )


def test_unmatched_cross_name_md5_requirement_stays_unresolved() -> None:
    context = _binding_context()
    unmatched_md5 = Md5Digest("0" * 32)
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("1", length=4, md5=unmatched_md5.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    unresolved = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 0, "1", 1, "A"),
        VcfRefCheckState.UNRESOLVED_SEQUENCE,
    )
    validation = _validation(
        VcfRefSequenceSummary("1", 1, unresolved_sequence_count=1),
        matches=0,
        unresolved=(unresolved,),
    )

    projection = project_vcf_contract(snapshot, validation, context)

    assert projection.sequence_bindings == ()
    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
    assert projection.evidence.evidence == ()


def test_conflicting_same_name_md5_blocks_false_compatible_bundle() -> None:
    context = _binding_context()
    conflicting_md5 = Md5Digest("0" * 32)
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("chr1", length=4, md5=conflicting_md5.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("chr1", 1),),
    )
    validation = _validation(
        VcfRefSequenceSummary("chr1", 1, match_count=1),
        matches=1,
    )

    projection = project_vcf_contract(snapshot, validation, context)

    assert projection.sequence_bindings == ()
    identity_evaluations = tuple(
        evaluation
        for constraint, evaluation in zip(
            projection.constraints,
            projection.evaluations,
            strict=True,
        )
        if isinstance(constraint.requirement, SequenceIdentityRequirement)
    )
    assert len(identity_evaluations) == 1
    assert identity_evaluations[0].state is ConstraintState.UNSATISFIED
    assert projection.evidence.has_conclusive_contradiction

    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, context.scope)
    bundle = reason_bundle(
        request,
        context.anchor_snapshot,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.reference_base_capability,),
    )

    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.UNSATISFIED,
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_conflicting_same_name_length_blocks_false_compatible_bundle() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("chr1", length=5),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("chr1", 1),),
    )
    validation = _validation(
        VcfRefSequenceSummary("chr1", 1, match_count=1),
        matches=1,
    )

    projection = project_vcf_contract(snapshot, validation, context)

    length_evaluations = tuple(
        evaluation
        for constraint, evaluation in zip(
            projection.constraints,
            projection.evaluations,
            strict=True,
        )
        if isinstance(constraint.requirement, SequenceLengthRequirement)
    )
    assert len(length_evaluations) == 1
    assert length_evaluations[0].state is ConstraintState.UNSATISFIED

    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, context.scope)
    bundle = reason_bundle(
        request,
        context.anchor_snapshot,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.reference_base_capability,),
    )

    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.UNSATISFIED,
        ConstraintState.SATISFIED,
    )
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_verified_alias_revalidation_keeps_bound_ref_mismatch_hard() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    bindings = derive_vcf_sequence_bindings(snapshot, context)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 2, "T"),),
        reference=_Reference(),
        sequence_bindings=bindings,
    )

    projection = project_vcf_contract(snapshot, validation, context)

    assert projection.evaluations[0].state is ConstraintState.SATISFIED
    assert projection.evaluations[-1].state is ConstraintState.UNSATISFIED
    assert projection.evidence.has_conclusive_contradiction
    assert projection.validation.problem_records[0].anchor_sequence_name == "chr1"


def test_projection_model_rejects_binding_citing_wrong_local_identity_capability() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData(
            "VCFv4.5",
            contigs=(VcfContigDeclaration("1", length=4, md5=_MD5_ACGT.value),),
        ),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    bindings = derive_vcf_sequence_bindings(snapshot, context)
    validation = evaluate_vcf_ref_records(
        vcf_resource_id=_VCF,
        fasta_resource_id=_FASTA,
        records=(VcfRefRecord(_VCF, 0, "1", 1, "A"),),
        reference=_Reference(),
        sequence_bindings=bindings,
    )
    projection = project_vcf_contract(snapshot, validation, context)
    crosswired = replace(
        projection.sequence_bindings[0],
        local_sequence_name="other",
    )

    with pytest.raises(ValueError, match="local VCF identity capability"):
        replace(projection, sequence_bindings=(crosswired,))


def test_unverified_cross_name_case_stays_unresolved_through_bundle() -> None:
    context = _binding_context()
    snapshot = VcfContextSnapshot(
        _VCF,
        VcfHeaderData("VCFv4.5", contigs=(VcfContigDeclaration("1", length=4),)),
        record_count=1,
        chrom_usage=(VcfChromUsage("1", 1),),
    )
    unresolved = VcfRefRecordCheck(
        VcfRefRecord(_VCF, 0, "1", 1, "A"),
        VcfRefCheckState.UNRESOLVED_SEQUENCE,
    )
    validation = _validation(
        VcfRefSequenceSummary("1", 1, unresolved_sequence_count=1),
        matches=0,
        unresolved=(unresolved,),
    )
    projection = project_vcf_contract(snapshot, validation, context)
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(path=Path("anchor.fa"))),
        Resource(_VCF, ResourceKind.VCF, ArtifactIdentity(path=Path("variants.vcf"))),
    )
    request = EvaluationRequest(resources, _FASTA, context.scope)

    bundle = reason_bundle(
        request,
        context.anchor_snapshot,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.reference_base_capability,),
    )

    assert projection.sequence_bindings == ()
    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
    assert bundle.sequence_bindings == ()
    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
