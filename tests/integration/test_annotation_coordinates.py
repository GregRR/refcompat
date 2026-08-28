"""End-to-end Milestone 5 ordinary annotation-coordinate integration tests."""

from pathlib import Path

import pytest

from refcompat.inspectors.annotation import inspect_annotation_context, iter_annotation_features
from refcompat.model.contracts import ResourceContract
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.identity import (
    CollectionCompleteness,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ArtifactIdentity, Resource, ResourceId, ResourceKind
from refcompat.model.verdict import CompatibilityVerdict
from refcompat.reasoning import aggregate_bundle_verdict, reason_bundle
from refcompat.reasoning.annotation_bounds import evaluate_annotation_coordinates
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


def test_streamed_gff3_possible_circular_bounds_remain_indeterminate(tmp_path: Path) -> None:
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
    assert validation.circular_bounds_unresolved_count == 1
    assert aggregate_bundle_verdict(bundle).verdict is CompatibilityVerdict.INDETERMINATE
