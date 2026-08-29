"""Milestone 5 exit coverage for GTF/GFF3 reference compatibility."""

from __future__ import annotations

from pathlib import Path

from refcompat.inspectors.annotation import inspect_annotation_context, iter_annotation_features
from refcompat.model.annotation import AnnotationContextSnapshot
from refcompat.model.annotation_bounds import AnnotationCoordinateValidationResult
from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.contracts import (
    CapabilityId,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
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
from refcompat.reasoning.annotation_contract import project_annotation_contract
from refcompat.reasoning.reference_context import build_reference_context

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "milestone5"
_FASTA = ResourceId("fasta")
_ANNOTATION = ResourceId("annotation")
_MD5_ACGT = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_TTTT = Md5Digest("2f803268a6367d0943978eb5f84cc62e")


def _annotation(name: str, kind: ResourceKind) -> Resource:
    return Resource(_ANNOTATION, kind, ArtifactIdentity(_FIXTURES / name))


def _context(
    annotation: Resource,
    *sequences: SnapshotSequence,
) -> tuple[EvaluationRequest, SequenceCollectionSnapshot, ReferenceContext]:
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=sequences,
    )
    return request, anchor, build_reference_context(request, anchor)


def _bundle_verdict(
    annotation: Resource,
    *sequences: SnapshotSequence,
    binding_identity_capabilities: tuple[SequenceIdentityCapability, ...] = (),
) -> tuple[
    CompatibilityVerdict,
    AnnotationContextSnapshot,
    AnnotationCoordinateValidationResult,
    BundleReasoningResult,
]:
    request, anchor, context = _context(annotation, *sequences)
    snapshot = inspect_annotation_context(annotation)
    bindings = derive_annotation_sequence_bindings(
        snapshot,
        context,
        binding_identity_capabilities=binding_identity_capabilities,
    )
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
        bindings,
    )
    projection = project_annotation_contract(
        snapshot,
        validation,
        context,
        binding_identity_capabilities=binding_identity_capabilities,
    )
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )
    return aggregate_bundle_verdict(bundle).verdict, snapshot, validation, bundle


def test_gtf_exact_sparse_coordinates_are_compatible() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gtf_exact.gtf", ResourceKind.GTF),
        SnapshotSequence("chr1", 100, 0),
        SnapshotSequence("unused", 50, 1),
    )

    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert validation.coordinate_conflict_count == 0


def test_gtf_verified_content_identity_resolves_cross_name_seqid() -> None:
    annotation = _annotation("gtf_alias.gtf", ResourceKind.GTF)
    identity = SequenceIdentityCapability(
        CapabilityId("milestone5:gtf-alias-content"),
        _ANNOTATION,
        "1",
        _MD5_ACGT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    verdict, _snapshot, validation, bundle = _bundle_verdict(
        annotation,
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        binding_identity_capabilities=(identity,),
    )

    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert validation.representable_count == 1
    assert len(bundle.sequence_bindings) == 1
    assert bundle.sequence_bindings[0].local_sequence_name == "1"
    assert bundle.sequence_bindings[0].anchor_sequence_name == "chr1"


def test_gtf_verified_content_identity_can_prove_required_sequence_absent() -> None:
    identity = SequenceIdentityCapability(
        CapabilityId("milestone5:gtf-absent-content"),
        _ANNOTATION,
        "1",
        _MD5_TTTT,
        SequenceIdentityProvenance.CONTENT_DERIVED,
    )

    verdict, _snapshot, validation, bundle = _bundle_verdict(
        _annotation("gtf_alias.gtf", ResourceKind.GTF),
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        binding_identity_capabilities=(identity,),
    )

    assert verdict is CompatibilityVerdict.INCOMPATIBLE
    assert validation.unresolved_sequence_count == 1
    assert bundle.sequence_bindings == ()
    assert len(bundle.derived_capabilities) == 1
    assert len(bundle.evidence.conclusive_contradictions) == 1


def test_gtf_familiar_cross_name_without_identity_remains_indeterminate() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gtf_alias.gtf", ResourceKind.GTF),
        SnapshotSequence("chr1", 4, 0),
    )

    assert verdict is CompatibilityVerdict.INDETERMINATE
    assert validation.unresolved_sequence_count == 1


def test_gtf_proven_out_of_bounds_coordinate_is_incompatible() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gtf_out_of_bounds.gtf", ResourceKind.GTF),
        SnapshotSequence("chr1", 100, 0),
    )

    assert verdict is CompatibilityVerdict.INCOMPATIBLE
    assert validation.out_of_bounds_count == 1


def test_gff3_sequence_region_conflict_is_incompatible() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gff3_region_conflict.gff3", ResourceKind.GFF3),
        SnapshotSequence("chr1", 100, 0),
    )

    assert verdict is CompatibilityVerdict.INCOMPATIBLE
    assert validation.coordinate_conflict_count == 1


def test_gff3_proven_single_wrap_circular_origin_is_compatible() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gff3_circular.gff3", ResourceKind.GFF3),
        SnapshotSequence("chrM", 100, 0),
    )

    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert validation.circular_representable_count == 1


def test_gff3_embedded_content_can_prove_sequence_identity_conflict() -> None:
    verdict, _snapshot, _validation, bundle = _bundle_verdict(
        _annotation("gff3_embedded_identity_conflict.gff3", ResourceKind.GFF3),
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )

    assert verdict is CompatibilityVerdict.INCOMPATIBLE
    assert len(bundle.evidence.conclusive_contradictions) == 1


def test_gff3_provenance_claim_cannot_override_verified_content_binding() -> None:
    verdict, snapshot, validation, bundle = _bundle_verdict(
        _annotation("gff3_provenance_vs_identity.gff3", ResourceKind.GFF3),
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
    )

    assert snapshot.provenance_claims
    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert validation.representable_count == 1
    assert len(bundle.sequence_bindings) == 1


def test_duplicate_anchor_identity_keeps_cross_name_gff3_indeterminate() -> None:
    verdict, _snapshot, validation, bundle = _bundle_verdict(
        _annotation("gff3_duplicate_identity.gff3", ResourceKind.GFF3),
        SnapshotSequence("chr1", 4, 0, md5=_MD5_ACGT),
        SnapshotSequence("chrDup", 4, 1, md5=_MD5_ACGT),
    )

    assert verdict is CompatibilityVerdict.INDETERMINATE
    assert bundle.sequence_bindings == ()
    assert validation.unresolved_sequence_count == 1


def test_non_model_scaffold_needs_no_registry_when_exact_anchor_facts_suffice() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gtf_non_model.gtf", ResourceKind.GTF),
        SnapshotSequence("scaffold_42", 20, 0),
    )

    assert verdict is CompatibilityVerdict.COMPATIBLE
    assert validation.representable_count == 1


def test_hard_coordinate_conflict_dominates_independent_unresolved_seqid() -> None:
    verdict, _snapshot, validation, _bundle = _bundle_verdict(
        _annotation("gff3_mixed_conflict.gff3", ResourceKind.GFF3),
        SnapshotSequence("chr1", 100, 0),
    )

    assert verdict is CompatibilityVerdict.INCOMPATIBLE
    assert validation.out_of_bounds_count == 1
    assert validation.unresolved_sequence_count == 1
