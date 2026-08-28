"""End-to-end Milestone 5 ordinary annotation-coordinate integration tests."""

from pathlib import Path

import pytest

from refcompat.inspectors.annotation import inspect_annotation_context, iter_annotation_features
from refcompat.model.contracts import ResourceContract
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
from refcompat.reasoning.annotation_bounds import (
    AnnotationCoordinateEvaluationError,
    evaluate_annotation_coordinates,
)
from refcompat.reasoning.annotation_contract import project_annotation_contract
from refcompat.reasoning.reference_context import build_reference_context

_FASTA = ResourceId("fasta")
_ANNOTATION = ResourceId("annotation")


def _context(
    annotation: Resource,
    *sequences: tuple[str, int],
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
        sequences=tuple(
            SnapshotSequence(name, length, ordinal)
            for ordinal, (name, length) in enumerate(sequences)
        ),
    )
    return request, anchor, build_reference_context(request, anchor)


@pytest.mark.parametrize(
    ("kind", "filename", "content"),
    [
        (
            ResourceKind.GTF,
            "genes.gtf",
            'chr1\tsrc\tgene\t1\t20\t.\t+\t.\tgene_id "g1";\n',
        ),
        (
            ResourceKind.GFF3,
            "genes.gff3",
            "##gff-version 3\nchr1\tsrc\tgene\t1\t20\t.\t+\t.\tID=g1\n",
        ),
    ],
)
def test_streamed_annotation_reaches_compatible_bundle_against_fasta_superset(
    tmp_path: Path,
    kind: ResourceKind,
    filename: str,
    content: str,
) -> None:
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    annotation = Resource(_ANNOTATION, kind, ArtifactIdentity(path))
    request, anchor, context = _context(annotation, ("chr1", 100), ("unused", 50))

    snapshot = inspect_annotation_context(annotation)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE
    assert validation.representable_count == 1


def test_streamed_gff3_landmark_allows_valid_circular_origin_wrap(tmp_path: Path) -> None:
    path = tmp_path / "circular.gff3"
    path.write_text(
        "##gff-version 3\n"
        "chrM\tsrc\tregion\t1\t100\t.\t+\t.\tID=chrM;Is_circular=true\n"
        "chrM\tsrc\tgene\t90\t120\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    request, anchor, context = _context(annotation, ("chrM", 100))

    snapshot = inspect_annotation_context(annotation)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert validation.out_of_bounds_count == 0
    assert validation.circular_representable_count == 1
    assert validation.circular_bounds_unresolved_count == 0
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_streamed_gff3_decoded_seqid_uses_column9_landmark_id_rules(
    tmp_path: Path,
) -> None:
    path = tmp_path / "encoded-circular.gff3"
    path.write_text(
        "##gff-version 3\n"
        "chr%2F1\tsrc\tregion\t1\t100\t.\t+\t.\tID=chr/1;Is_circular=true\n"
        "chr%2F1\tsrc\tgene\t90\t120\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    request, anchor, context = _context(annotation, ("chr/1", 100))

    snapshot = inspect_annotation_context(annotation)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert snapshot.sequence_usage[0].sequence_name == "chr/1"
    assert snapshot.sequence_usage[0].circular_landmark_candidate_count == 1
    assert validation.circular_representable_count == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_streamed_gff3_circular_child_does_not_create_landmark_exception(
    tmp_path: Path,
) -> None:
    path = tmp_path / "not-landmark.gff3"
    path.write_text(
        "##gff-version 3\n"
        "chrM\tsrc\tgene\t1\t100\t.\t+\t.\tID=g0;Is_circular=true\n"
        "chrM\tsrc\tgene\t90\t120\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    request, anchor, context = _context(annotation, ("chrM", 100))

    snapshot = inspect_annotation_context(annotation)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert validation.circular_representable_count == 0
    assert validation.out_of_bounds_count == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_streamed_gff3_sequence_region_participates_in_anchor_validation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "region.gff3"
    path.write_text(
        "##gff-version 3\n"
        "##sequence-region chr1 1 101\n"
        "##genome-build NCBI GRCh38\n"
        "chr1\tsrc\tgene\t1\t20\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    request, anchor, context = _context(annotation, ("chr1", 100))

    snapshot = inspect_annotation_context(annotation)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
        context,
    )
    projection = project_annotation_contract(snapshot, validation, context)
    bundle = reason_bundle(
        request,
        anchor,
        (ResourceContract(_FASTA), projection.contract),
        supplemental_capabilities=(projection.coordinate_bounds_capability,),
    )

    assert validation.feature_count == 1
    assert validation.coordinate_count == 2
    assert validation.coordinate_conflict_count == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INCOMPATIBLE


def test_streamed_gff3_feature_outside_declared_region_is_invalid_input_boundary(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid-region.gff3"
    path.write_text(
        "##gff-version 3\n##sequence-region chr1 1 80\nchr1\tsrc\tgene\t70\t90\t.\t+\t.\tID=g1\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    _request_value, _anchor, context = _context(annotation, ("chr1", 100))
    snapshot = inspect_annotation_context(annotation)

    with pytest.raises(
        AnnotationCoordinateEvaluationError,
        match="outside its declared sequence-region",
    ):
        evaluate_annotation_coordinates(
            snapshot,
            iter_annotation_features(annotation),
            context,
        )


def test_streamed_gff3_embedded_fasta_supports_verified_cross_name_binding(
    tmp_path: Path,
) -> None:
    path = tmp_path / "embedded-binding.gff3"
    path.write_text(
        "##gff-version 3\nchr%2F1\tsrc\tgene\t1\t4\t.\t+\t.\tID=g1\n##FASTA\n>chr/1\nacgt\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    md5 = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 4, 0, md5=md5),),
    )
    context = build_reference_context(request, anchor)

    snapshot = inspect_annotation_context(annotation)
    bindings = derive_annotation_sequence_bindings(snapshot, context)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
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
    assert snapshot.used_sequence_names == ("chr/1",)
    assert snapshot.embedded_fasta_sequences[0].sequence_name == "chr/1"
    assert bindings[0].local_sequence_name == "chr/1"
    assert bindings[0].anchor_sequence_name == "chr1"
    assert validation.representable_count == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.COMPATIBLE


def test_streamed_gff3_embedded_fasta_content_conflict_is_incompatible(
    tmp_path: Path,
) -> None:
    path = tmp_path / "embedded-conflict.gff3"
    path.write_text(
        "##gff-version 3\nchr1\tsrc\tgene\t1\t4\t.\t+\t.\tID=g1\n##FASTA\n>chr1\nTTTT\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(
            SnapshotSequence(
                "chr1",
                4,
                0,
                md5=Md5Digest("f1f8f4bf413b16ad135722aa4591043e"),
            ),
        ),
    )
    context = build_reference_context(request, anchor)

    snapshot = inspect_annotation_context(annotation)
    validation = evaluate_annotation_coordinates(
        snapshot,
        iter_annotation_features(annotation),
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


def test_streamed_gff3_rejects_feature_beyond_matching_embedded_fasta(
    tmp_path: Path,
) -> None:
    path = tmp_path / "embedded-short.gff3"
    path.write_text(
        "##gff-version 3\nchr1\tsrc\tgene\t1\t5\t.\t+\t.\tID=g1\n##FASTA\n>chr1\nACGT\n",
        encoding="utf-8",
    )
    annotation = Resource(_ANNOTATION, ResourceKind.GFF3, ArtifactIdentity(path))
    fasta = Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa")))
    request = EvaluationRequest(
        (fasta, annotation),
        _FASTA,
        EvaluationScope((_FASTA, _ANNOTATION)),
    )
    anchor = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=(SnapshotSequence("chr1", 10, 0),),
    )
    context = build_reference_context(request, anchor)
    snapshot = inspect_annotation_context(annotation)

    with pytest.raises(AnnotationCoordinateEvaluationError, match="matching embedded FASTA"):
        evaluate_annotation_coordinates(
            snapshot,
            iter_annotation_features(annotation),
            context,
        )
