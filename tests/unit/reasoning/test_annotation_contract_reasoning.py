"""Tests for annotation projection into generic contracts and bundle reasoning."""

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model.annotation import (
    AnnotationContextSnapshot,
    AnnotationFeatureRecord,
    AnnotationProvenanceClaim,
    AnnotationSequenceUsage,
    Gff3EmbeddedFastaSequence,
    Gff3FastaBoundary,
    Gff3SequenceRegion,
)
from refcompat.model.annotation_contract import AnnotationContractProjection
from refcompat.model.constraints import ConstraintState
from refcompat.model.contracts import (
    CapabilityId,
    CoordinateBoundsRequirement,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
    SequenceIdentityRequirement,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.evidence import EvidenceMethod, EvidenceStrength
from refcompat.model.identity import (
    CollectionCompleteness,
    Md5Digest,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.verdict import CompatibilityVerdict
from refcompat.reasoning import aggregate_bundle_verdict, reason_bundle
from refcompat.reasoning.annotation_binding import derive_annotation_sequence_bindings
from refcompat.reasoning.annotation_bounds import evaluate_annotation_coordinates
from refcompat.reasoning.annotation_contract import (
    build_annotation_contract,
    project_annotation_contract,
)
from refcompat.reasoning.reference_context import build_reference_context

_ANNOTATION = ResourceId("annotation")
_FASTA = ResourceId("fasta")


def _request(
    *sequences: tuple[str, int],
) -> tuple[EvaluationRequest, SequenceCollectionSnapshot, ReferenceContext]:
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa"))),
        Resource(_ANNOTATION, ResourceKind.GTF, ArtifactIdentity(Path("genes.gtf"))),
    )
    request = EvaluationRequest(resources, _FASTA, EvaluationScope((_FASTA, _ANNOTATION)))
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=tuple(
            SnapshotSequence(name, length, ordinal)
            for ordinal, (name, length) in enumerate(sequences)
        ),
    )
    return request, anchor, build_reference_context(request, anchor)


def _feature(ordinal: int, name: str, start: int, end: int) -> AnnotationFeatureRecord:
    return AnnotationFeatureRecord(
        _ANNOTATION,
        ordinal,
        ordinal + 1,
        name,
        name,
        "gene",
        start,
        end,
    )


def _snapshot(
    *usage: tuple[str, int, int, int],
    kind: ResourceKind = ResourceKind.GTF,
    regions: tuple[Gff3SequenceRegion, ...] = (),
    provenance: tuple[AnnotationProvenanceClaim, ...] = (),
) -> AnnotationContextSnapshot:
    return AnnotationContextSnapshot(
        _ANNOTATION,
        kind,
        feature_count=sum(item[1] for item in usage),
        sequence_usage=tuple(
            AnnotationSequenceUsage(
                sequence_name=name,
                first_raw_sequence_name=name,
                feature_count=count,
                minimum_start=minimum_start,
                maximum_end=maximum_end,
                first_feature_line=index + 1,
            )
            for index, (name, count, minimum_start, maximum_end) in enumerate(usage)
        ),
        sequence_regions=regions,
        provenance_claims=provenance,
    )


def _project(
    snapshot: AnnotationContextSnapshot,
    features: tuple[AnnotationFeatureRecord, ...],
    *anchor_sequences: tuple[str, int],
) -> AnnotationContractProjection:
    _request_value, _anchor, context = _request(*anchor_sequences)
    validation = evaluate_annotation_coordinates(snapshot, features, context)
    return project_annotation_contract(snapshot, validation, context)


def test_contract_projects_used_seqids_and_one_coordinate_requirement() -> None:
    _request_value, _anchor, context = _request(("chr1", 100), ("chr2", 100))
    contract = build_annotation_contract(
        _snapshot(("chr1", 2, 1, 20), ("chr2", 1, 5, 5)),
        context,
    )

    presence = tuple(
        item for item in contract.requirements if isinstance(item, SequencePresenceRequirement)
    )
    bounds = tuple(
        item for item in contract.requirements if isinstance(item, CoordinateBoundsRequirement)
    )
    assert tuple(item.sequence_name for item in presence) == ("chr1", "chr2")
    assert len(bounds) == 1
    assert bounds[0].anchor_resource_id == _FASTA
    assert bounds[0].coordinate_count == 3


def test_exact_in_bounds_projection_is_structurally_satisfied() -> None:
    projection = _project(
        _snapshot(("chr1", 2, 1, 100)),
        (_feature(0, "chr1", 1, 20), _feature(1, "chr1", 100, 100)),
        ("chr1", 100),
    )

    assert tuple(item.state for item in projection.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )
    evidence = projection.evidence.evidence[-1]
    assert evidence.method is EvidenceMethod.EXHAUSTIVE_COORDINATE_BOUNDS_VALIDATION
    assert evidence.strength is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL


def test_sparse_annotation_accepts_fasta_superset() -> None:
    request, anchor, context = _request(("chr1", 100), ("chr2", 100), ("decoy", 50))
    snapshot = _snapshot(("chr1", 1, 1, 10))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "chr1", 1, 10),), context)
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.COMPATIBLE
    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.SATISFIED,
        ConstraintState.SATISFIED,
    )


def test_gtf_content_identity_can_supply_verified_alias_without_identity_requirement() -> None:
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    annotation = Resource(_ANNOTATION, ResourceKind.GTF, ArtifactIdentity(Path("genes.gtf")))
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    digest = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, md5=digest),),
    )
    context = build_reference_context(request, anchor)
    snapshot = _snapshot(("1", 1, 1, 4))
    feature = _feature(0, "1", 1, 4)
    capability = SequenceIdentityCapability(
        CapabilityId("external-content:1"),
        _ANNOTATION,
        "1",
        digest,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    bindings = derive_annotation_sequence_bindings(
        snapshot,
        context,
        binding_identity_capabilities=(capability,),
    )
    validation = evaluate_annotation_coordinates(snapshot, (feature,), context, bindings)
    projection = project_annotation_contract(
        snapshot,
        validation,
        context,
        binding_identity_capabilities=(capability,),
    )

    identity_requirements = tuple(
        requirement
        for requirement in projection.contract.requirements
        if isinstance(requirement, SequenceIdentityRequirement)
    )
    assert identity_requirements == ()
    assert projection.contract.capabilities == (capability,)
    assert len(projection.sequence_bindings) == 1

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_gtf_external_identity_rejects_stale_unbound_validation() -> None:
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    annotation = Resource(_ANNOTATION, ResourceKind.GTF, ArtifactIdentity(Path("genes.gtf")))
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    digest = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, md5=digest),),
    )
    context = build_reference_context(request, anchor)
    snapshot = _snapshot(("1", 1, 1, 4))
    feature = _feature(0, "1", 1, 4)
    capability = SequenceIdentityCapability(
        CapabilityId("external-content:stale"),
        _ANNOTATION,
        "1",
        digest,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )
    stale_validation = evaluate_annotation_coordinates(snapshot, (feature,), context)

    with pytest.raises(ValueError, match="exactly the verified sequence bindings"):
        project_annotation_contract(
            snapshot,
            stale_validation,
            context,
            binding_identity_capabilities=(capability,),
        )


def test_unfamiliar_seqid_remains_indeterminate_not_proven_absent() -> None:
    request, anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(("1", 1, 1, 10))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "1", 1, 10),), context)
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.INDETERMINATE
    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
    assert bundle.evidence.evidence == ()


def test_one_ordinary_out_of_bounds_feature_makes_bundle_incompatible() -> None:
    request, anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(("chr1", 2, 1, 101))
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 100), _feature(1, "chr1", 101, 101)),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    verdict = aggregate_bundle_verdict(bundle)

    assert verdict.verdict is CompatibilityVerdict.INCOMPATIBLE
    assert bundle.evaluations[-1].state is ConstraintState.UNSATISFIED
    assert bundle.evidence.conclusive_contradictions == ()
    assert (
        bundle.evidence.contradicting_evidence[0].strength
        is EvidenceStrength.TIER_B_DIRECT_STRUCTURAL
    )


def test_empty_annotation_has_only_not_applicable_coordinate_requirement() -> None:
    projection = _project(_snapshot(), (), ("chr1", 100))

    assert len(projection.contract.requirements) == 1
    assert isinstance(projection.contract.requirements[0], CoordinateBoundsRequirement)
    assert projection.evaluations[0].state is ConstraintState.NOT_APPLICABLE


def test_projection_rejects_crosswired_validation_and_coverage() -> None:
    snapshot = _snapshot(("chr1", 1, 1, 10))
    _request_value, _anchor, context = _request(("chr1", 100), ("chr2", 100))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "chr1", 1, 10),), context)

    with pytest.raises(ValueError, match="same resource"):
        project_annotation_contract(
            snapshot,
            replace(validation, annotation_resource_id=ResourceId("other")),
            context,
        )
    with pytest.raises(ValueError, match="FASTA anchor"):
        project_annotation_contract(
            snapshot,
            replace(validation, fasta_resource_id=ResourceId("other")),
            context,
        )

    bad_summary = replace(validation.sequence_summaries[0], sequence_name="chr2")
    with pytest.raises(ValueError, match="seqid usage"):
        project_annotation_contract(
            snapshot,
            replace(validation, sequence_summaries=(bad_summary,)),
            context,
        )


def test_projection_ids_are_deterministic() -> None:
    snapshot = _snapshot(("chr1", 1, 1, 10))
    _request_value, _anchor, context = _request(("chr1", 100))
    validation = evaluate_annotation_coordinates(snapshot, (_feature(0, "chr1", 1, 10),), context)

    first = project_annotation_contract(snapshot, validation, context)
    second = project_annotation_contract(snapshot, validation, context)

    assert tuple(item.id for item in first.contract.requirements) == tuple(
        item.id for item in second.contract.requirements
    )
    assert first.coordinate_bounds_capability.id == second.coordinate_bounds_capability.id
    assert tuple(item.id for item in first.constraints) == tuple(
        item.id for item in second.constraints
    )


def test_sequence_region_adds_presence_and_coordinate_statement() -> None:
    _request_value, _anchor, context = _request(("chr1", 100), ("chr2", 100))
    snapshot = _snapshot(
        ("chr1", 1, 1, 10),
        kind=ResourceKind.GFF3,
        regions=(Gff3SequenceRegion("chr2", "chr2", 1, 50, 1),),
    )

    contract = build_annotation_contract(snapshot, context)

    presence = tuple(
        item for item in contract.requirements if isinstance(item, SequencePresenceRequirement)
    )
    bounds = tuple(
        item for item in contract.requirements if isinstance(item, CoordinateBoundsRequirement)
    )
    assert tuple(item.sequence_name for item in presence) == ("chr1", "chr2")
    assert bounds[0].coordinate_count == 2


def test_sequence_region_outside_anchor_makes_bundle_incompatible() -> None:
    request, anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(
        ("chr1", 1, 1, 10),
        kind=ResourceKind.GFF3,
        regions=(Gff3SequenceRegion("chr1", "chr1", 1, 101, 1),),
    )
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 10),),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert projection.coordinate_bounds_capability.checked_count == 2
    assert projection.coordinate_bounds_capability.conflict_count == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_sequence_region_only_unfamiliar_seqid_keeps_bundle_indeterminate() -> None:
    request, anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(
        kind=ResourceKind.GFF3,
        regions=(Gff3SequenceRegion("1", "1", 1, 100, 1),),
    )
    validation = evaluate_annotation_coordinates(snapshot, (), context)
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert tuple(item.state for item in bundle.evaluations) == (
        ConstraintState.UNRESOLVED,
        ConstraintState.UNRESOLVED,
    )
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INDETERMINATE


def test_provenance_claims_do_not_change_annotation_contract() -> None:
    _request_value, _anchor, context = _request(("chr1", 100))
    plain = _snapshot(("chr1", 1, 1, 10), kind=ResourceKind.GFF3)
    claimed = _snapshot(
        ("chr1", 1, 1, 10),
        kind=ResourceKind.GFF3,
        provenance=(
            AnnotationProvenanceClaim("##genome-build", "NCBI GRCh38", 1),
            AnnotationProvenanceClaim("#!genome-build-accession", "GCF_000001405.40", 2),
        ),
    )

    assert build_annotation_contract(plain, context) == build_annotation_contract(claimed, context)


def test_projection_rejects_stale_sequence_region_validation() -> None:
    _request_value, _anchor, context = _request(("chr1", 100))
    snapshot = _snapshot(
        ("chr1", 1, 1, 10),
        kind=ResourceKind.GFF3,
        regions=(Gff3SequenceRegion("chr1", "chr1", 1, 100, 1),),
    )
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 10),),
        context,
    )
    assert validation.sequence_region_validation is not None
    stale_check = replace(
        validation.sequence_region_validation.checks[0],
        region=Gff3SequenceRegion("chr1", "chr1", 1, 99, 1),
    )
    stale_regions = replace(
        validation.sequence_region_validation,
        checks=(stale_check,),
    )

    with pytest.raises(ValueError, match="match inspected directives"):
        project_annotation_contract(
            snapshot,
            replace(validation, sequence_region_validation=stale_regions),
            context,
        )


_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_TTTT = Md5Digest("2f803268a6367d0943978eb5f84cc62e")


def _gff3_identity_case(
    local_name: str,
    embedded_md5: Md5Digest,
    *anchor_sequences: SnapshotSequence,
) -> tuple[
    EvaluationRequest,
    SequenceCollectionSnapshot,
    ReferenceContext,
    AnnotationContextSnapshot,
]:
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    annotation = Resource(
        _ANNOTATION,
        ResourceKind.GFF3,
        ArtifactIdentity(Path("genes.gff3")),
    )
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=anchor_sequences,
    )
    context = build_reference_context(request, anchor)
    snapshot = AnnotationContextSnapshot(
        _ANNOTATION,
        ResourceKind.GFF3,
        feature_count=1,
        sequence_usage=(AnnotationSequenceUsage(local_name, local_name, 1, 1, 4, 1),),
        fasta_boundary=Gff3FastaBoundary(2, True),
        embedded_fasta_sequences=(Gff3EmbeddedFastaSequence(local_name, 4, embedded_md5, 3),),
    )
    return request, anchor, context, snapshot


def test_embedded_reference_sequence_adds_content_identity_requirement() -> None:
    _request_value, _anchor, context, snapshot = _gff3_identity_case(
        "chr1",
        _MD5_ACGT,
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )

    contract = build_annotation_contract(snapshot, context)

    identity_requirements = tuple(
        item for item in contract.requirements if isinstance(item, SequenceIdentityRequirement)
    )
    assert len(identity_requirements) == 1
    assert identity_requirements[0].sequence_name == "chr1"
    assert identity_requirements[0].identity == _MD5_ACGT
    assert len(contract.capabilities) == 1


def test_embedded_content_binding_makes_cross_name_annotation_compatible() -> None:
    request, anchor, context, snapshot = _gff3_identity_case(
        "1",
        _MD5_ACGT,
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )
    bindings = derive_annotation_sequence_bindings(snapshot, context)
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "1", 1, 4),),
        context,
        bindings,
    )
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert len(bindings) == 1
    assert all(item.state is ConstraintState.SATISFIED for item in projection.evaluations)
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE
    binding_evidence = tuple(item for item in bundle.evidence.evidence if item.sequence_binding_ids)
    assert binding_evidence
    assert all(item.method is EvidenceMethod.VERIFIED_SEQUENCE_BINDING for item in binding_evidence)


def test_same_name_embedded_content_keeps_projection_exact() -> None:
    request, anchor, context, snapshot = _gff3_identity_case(
        "chr1",
        _MD5_ACGT,
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 4),),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert projection.sequence_bindings == ()
    assert all(not constraint.sequence_bindings for constraint in projection.constraints)
    assert len(bundle.sequence_bindings) == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_same_name_embedded_content_conflict_is_tier_a_incompatible() -> None:
    request, anchor, context, snapshot = _gff3_identity_case(
        "chr1",
        _MD5_TTTT,
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "chr1", 1, 4),),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)

    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE
    assert len(bundle.evidence.conclusive_contradictions) == 1
    contradiction = bundle.evidence.conclusive_contradictions[0]
    assert contradiction.strength is EvidenceStrength.TIER_A_CONCLUSIVE_CONTENT


def test_projection_rejects_stale_exact_name_validation_when_binding_exists() -> None:
    _request_value, _anchor, context, snapshot = _gff3_identity_case(
        "1",
        _MD5_ACGT,
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )
    validation = evaluate_annotation_coordinates(
        snapshot,
        (_feature(0, "1", 1, 4),),
        context,
    )

    with pytest.raises(ValueError, match="exactly the verified sequence bindings"):
        project_annotation_contract(snapshot, validation, context)
