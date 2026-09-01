"""Tests for descriptive BAM/CRAM header-dictionary relationship reasoning."""

from dataclasses import replace
from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentContentRelationship,
    AlignmentHeaderData,
    AlignmentHeaderSnapshot,
    AlignmentMembershipRelationship,
    AlignmentNameResolutionMethod,
    AlignmentNamingRelationship,
    AlignmentOrderRelationship,
    ArtifactIdentity,
    CollectionCompleteness,
    EvaluationRequest,
    EvaluationScope,
    Md5Digest,
    ReferenceContext,
    Resource,
    ResourceContract,
    ResourceId,
    ResourceKind,
    SequenceCollectionSnapshot,
    SequenceDictionaryRecord,
    SnapshotSequence,
)
from refcompat.reasoning import (
    build_alignment_contract,
    build_reference_context,
    classify_alignment_dictionary_relationship,
    reason_bundle,
)

_FASTA = ResourceId("fasta")
_ALIGNMENT = ResourceId("reads")
_MD5_A = Md5Digest("f1f8f4bf413b16ad135722aa4591043e")
_MD5_B = Md5Digest("2f803268a6367d0943978eb5f84cc62e")
_MD5_C = Md5Digest("b41c1949bef0cb7c83998d0a5d83bcc2")


def _context(
    *,
    scope_names: tuple[str, ...] | None = None,
    kind: ResourceKind = ResourceKind.BAM,
    sequences: tuple[SnapshotSequence, ...] | None = None,
) -> ReferenceContext:
    anchor_sequences = (
        sequences
        if sequences is not None
        else (
            SnapshotSequence("chr1", 4, 0, md5=_MD5_A),
            SnapshotSequence("chr2", 4, 1, md5=_MD5_B),
        )
    )
    resources = (
        Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa"))),
        Resource(_ALIGNMENT, kind, ArtifactIdentity(Path("reads.bam"))),
    )
    request = EvaluationRequest(
        resources,
        _FASTA,
        EvaluationScope((_FASTA, _ALIGNMENT), scope_names),
    )
    snapshot = SequenceCollectionSnapshot(
        _FASTA,
        CollectionCompleteness.COMPLETE,
        sequences=anchor_sequences,
    )
    return build_reference_context(request, snapshot)


def _alignment(
    *records: SequenceDictionaryRecord,
    kind: ResourceKind = ResourceKind.BAM,
) -> AlignmentHeaderSnapshot:
    return AlignmentHeaderSnapshot(
        _ALIGNMENT,
        kind,
        AlignmentHeaderData(sequences=records),
    )


@pytest.mark.parametrize("kind", [ResourceKind.BAM, ResourceKind.CRAM])
def test_exact_identity_requires_complete_matching_m5(kind: ResourceKind) -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
            kind=kind,
        ),
        _context(kind=kind),
    )

    assert summary.exact_identity
    assert not summary.verified_naming_only_difference
    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.naming is AlignmentNamingRelationship.EXACT
    assert summary.order is AlignmentOrderRelationship.CONSISTENT
    assert summary.content is AlignmentContentRelationship.M5_VERIFIED


def test_verified_cross_name_bindings_can_be_naming_only_difference() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("2", 4, md5=_MD5_B),
        ),
        _context(),
    )

    assert not summary.exact_identity
    assert summary.verified_naming_only_difference
    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.naming is AlignmentNamingRelationship.VERIFIED_DIFFERENCE
    assert summary.order is AlignmentOrderRelationship.CONSISTENT
    assert summary.content is AlignmentContentRelationship.M5_VERIFIED
    assert tuple(item.method for item in summary.resolutions) == (
        AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
        AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
    )
    assert all(item.sequence_binding_id is not None for item in summary.resolutions)


def test_reordered_full_dictionary_is_distinguished_from_naming_only() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.order is AlignmentOrderRelationship.DIFFERENT
    assert summary.content is AlignmentContentRelationship.M5_VERIFIED
    assert not summary.exact_identity
    assert not summary.verified_naming_only_difference


def test_empty_sq_dictionary_is_vacuous_subset_with_unresolved_details() -> None:
    summary = classify_alignment_dictionary_relationship(_alignment(), _context())

    assert summary.membership is AlignmentMembershipRelationship.ALIGNMENT_SUBSET
    assert summary.naming is AlignmentNamingRelationship.UNRESOLVED
    assert summary.order is AlignmentOrderRelationship.UNRESOLVED
    assert summary.content is AlignmentContentRelationship.UNRESOLVED
    assert summary.resolutions == ()
    assert not summary.exact_identity


def test_verified_subset_preserves_relative_order() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(SequenceDictionaryRecord("chr1", 4, md5=_MD5_A)),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.ALIGNMENT_SUBSET
    assert summary.order is AlignmentOrderRelationship.CONSISTENT
    assert summary.content is AlignmentContentRelationship.M5_VERIFIED


def test_verified_superset_requires_extra_content_absent_from_complete_anchor() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
            SequenceDictionaryRecord("decoy", 4, md5=_MD5_C),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.ALIGNMENT_SUPERSET
    assert summary.m5_distinct_extra_sequence_names == ("decoy",)
    assert summary.unresolved_sequence_names == ()
    assert summary.order is AlignmentOrderRelationship.CONSISTENT


def test_unfamiliar_name_without_m5_does_not_become_superset() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
            SequenceDictionaryRecord("decoy", 4),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert summary.unresolved_sequence_names == ("decoy",)
    assert summary.m5_distinct_extra_sequence_names == ()


def test_subset_plus_m5_distinct_extra_is_overlap_not_superset() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("decoy", 4, md5=_MD5_C),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.OVERLAP
    assert summary.m5_distinct_extra_sequence_names == ("decoy",)


def test_an_matching_anchor_blocks_extra_classification_without_binding() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord(
                "decoy",
                4,
                md5=_MD5_C,
                alternate_names=("chr1",),
            )
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert summary.unresolved_sequence_names == ("decoy",)
    assert summary.m5_distinct_extra_sequence_names == ()


def test_m5_distinct_only_dictionary_is_disjoint_not_overlap() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(SequenceDictionaryRecord("decoy", 4, md5=_MD5_C)),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.DISJOINT
    assert summary.m5_distinct_extra_sequence_names == ("decoy",)
    assert summary.resolutions == ()


def test_same_name_m5_mismatch_is_content_conflict() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_C),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.content is AlignmentContentRelationship.M5_CONFLICT
    assert summary.identity_conflict_sequence_names == ("chr1",)
    assert not summary.exact_identity


def test_missing_m5_keeps_content_unresolved_without_erasing_structure() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.naming is AlignmentNamingRelationship.EXACT
    assert summary.order is AlignmentOrderRelationship.CONSISTENT
    assert summary.content is AlignmentContentRelationship.UNRESOLVED
    assert not summary.exact_identity


def test_length_conflict_is_retained_separately_from_content_identity() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 5, md5=_MD5_A),
            SequenceDictionaryRecord("chr2", 4, md5=_MD5_B),
        ),
        _context(),
    )

    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.content is AlignmentContentRelationship.M5_VERIFIED
    assert summary.length_conflict_sequence_names == ("chr1",)
    assert not summary.exact_identity


def test_cross_name_m5_length_contradiction_stays_unresolved() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(SequenceDictionaryRecord("1", 5, md5=_MD5_A)),
        _context(scope_names=("chr1",)),
    )

    assert summary.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert summary.naming is AlignmentNamingRelationship.UNRESOLVED
    assert summary.order is AlignmentOrderRelationship.UNRESOLVED
    assert summary.content is AlignmentContentRelationship.UNRESOLVED
    assert summary.unresolved_sequence_names == ("1",)


def test_duplicate_local_names_resolving_to_one_anchor_do_not_claim_exact_membership() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("chrOne", 4, md5=_MD5_A),
        ),
        _context(scope_names=("chr1",)),
    )

    assert summary.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert summary.content is AlignmentContentRelationship.M5_VERIFIED
    assert summary.duplicate_anchor_target_names == ("chr1",)
    assert not summary.verified_naming_only_difference


def test_membership_is_relative_to_explicit_anchor_scope() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(SequenceDictionaryRecord("chr1", 4, md5=_MD5_A)),
        _context(scope_names=("chr1",)),
    )

    assert summary.membership is AlignmentMembershipRelationship.EXACT
    assert summary.exact_identity


def test_out_of_scope_anchor_sequence_is_not_misclassified_as_extra() -> None:
    summary = classify_alignment_dictionary_relationship(
        _alignment(SequenceDictionaryRecord("chr2", 4, md5=_MD5_B)),
        _context(scope_names=("chr1",)),
    )

    assert summary.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert summary.unresolved_sequence_names == ("chr2",)
    assert summary.m5_distinct_extra_sequence_names == ()


def test_incomplete_anchor_m5_coverage_cannot_prove_superset() -> None:
    context = _context(
        sequences=(
            SnapshotSequence("chr1", 4, 0, md5=_MD5_A),
            SnapshotSequence("chr2", 4, 1),
        )
    )
    summary = classify_alignment_dictionary_relationship(
        _alignment(
            SequenceDictionaryRecord("chr1", 4, md5=_MD5_A),
            SequenceDictionaryRecord("decoy", 4, md5=_MD5_C),
        ),
        context,
    )

    assert summary.membership is AlignmentMembershipRelationship.UNRESOLVED
    assert summary.unresolved_sequence_names == ("decoy",)
    assert summary.m5_distinct_extra_sequence_names == ()


def test_bundle_identity_binding_must_be_backed_by_record_m5() -> None:
    context = _context(scope_names=("chr1",))
    snapshot = _alignment(SequenceDictionaryRecord("1", 4, md5=_MD5_A))
    request = EvaluationRequest(
        resources=(
            Resource(_FASTA, ResourceKind.FASTA, ArtifactIdentity(Path("anchor.fa"))),
            Resource(_ALIGNMENT, ResourceKind.BAM, ArtifactIdentity(Path("reads.bam"))),
        ),
        anchor_resource_id=_FASTA,
        scope=context.scope,
    )
    contract = build_alignment_contract(snapshot, context)
    bundle = reason_bundle(
        request,
        context.anchor_snapshot,
        (ResourceContract(_FASTA), contract),
    )

    assert len(bundle.sequence_bindings) == 1
    binding = bundle.sequence_bindings[0]
    corrupted_binding = replace(binding, identity_values=(_MD5_B,))
    corrupted_bundle = replace(bundle, sequence_bindings=(corrupted_binding,))

    with pytest.raises(
        ValueError,
        match="alignment identity binding must be backed by the record M5",
    ):
        classify_alignment_dictionary_relationship(
            snapshot,
            context,
            bundle_result=corrupted_bundle,
        )
