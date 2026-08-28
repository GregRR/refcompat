"""Invariant tests for conservative offline CRAM reference plans."""

from pathlib import Path

import pytest

from refcompat.model import (
    AlignmentContentRelationship,
    AlignmentDictionaryRelationshipSummary,
    AlignmentMembershipRelationship,
    AlignmentNameResolutionMethod,
    AlignmentNamingRelationship,
    AlignmentOrderRelationship,
    AlignmentSequenceResolution,
    CramOfflineReferenceAction,
    CramOfflineReferencePlan,
    ResourceId,
)

_CRAM = ResourceId("reads")
_FASTA = ResourceId("fasta")


def _relationship(
    *,
    alignment_resource_id: ResourceId = _CRAM,
    fasta_resource_id: ResourceId = _FASTA,
    membership: AlignmentMembershipRelationship = AlignmentMembershipRelationship.EXACT,
    naming: AlignmentNamingRelationship = AlignmentNamingRelationship.EXACT,
    content: AlignmentContentRelationship = AlignmentContentRelationship.M5_VERIFIED,
    length_conflict_sequence_names: tuple[str, ...] = (),
) -> AlignmentDictionaryRelationshipSummary:
    return AlignmentDictionaryRelationshipSummary(
        alignment_resource_id=alignment_resource_id,
        fasta_resource_id=fasta_resource_id,
        membership=membership,
        naming=naming,
        order=AlignmentOrderRelationship.CONSISTENT,
        content=content,
        resolutions=(
            AlignmentSequenceResolution(
                "chr1",
                "chr1",
                AlignmentNameResolutionMethod.EXACT_NAME,
            ),
        ),
        length_conflict_sequence_names=length_conflict_sequence_names,
    )


def test_explicit_local_anchor_requires_readable_path() -> None:
    path = Path("anchor.fa")

    with pytest.raises(ValueError, match="requires a readable FASTA anchor"):
        CramOfflineReferencePlan(
            cram_resource_id=_CRAM,
            anchor_resource_id=_FASTA,
            action=CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR,
            anchor_path=path,
            anchor_path_readable=False,
            relationship=_relationship(),
            reference_path=path,
        )


def test_explicit_reference_must_be_selected_anchor_path() -> None:
    with pytest.raises(ValueError, match="must use the selected FASTA anchor path"):
        CramOfflineReferencePlan(
            cram_resource_id=_CRAM,
            anchor_resource_id=_FASTA,
            action=CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR,
            anchor_path=Path("anchor.fa"),
            anchor_path_readable=True,
            relationship=_relationship(),
            reference_path=Path("other.fa"),
        )


def test_deferred_decoding_cannot_carry_reference_path() -> None:
    with pytest.raises(ValueError, match="cannot carry a reference path"):
        CramOfflineReferencePlan(
            cram_resource_id=_CRAM,
            anchor_resource_id=_FASTA,
            action=CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING,
            anchor_path=Path("anchor.fa"),
            anchor_path_readable=True,
            relationship=_relationship(),
            reference_path=Path("anchor.fa"),
        )


def test_relationship_resource_ids_are_cross_checked() -> None:
    with pytest.raises(ValueError, match="must belong to the CRAM resource"):
        CramOfflineReferencePlan(
            cram_resource_id=_CRAM,
            anchor_resource_id=_FASTA,
            action=CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING,
            anchor_path=Path("anchor.fa"),
            anchor_path_readable=False,
            relationship=_relationship(alignment_resource_id=ResourceId("other")),
        )


def test_explicit_reference_requires_safe_header_relationship() -> None:
    path = Path("anchor.fa")

    with pytest.raises(ValueError, match="requires complete M5 verification"):
        CramOfflineReferencePlan(
            cram_resource_id=_CRAM,
            anchor_resource_id=_FASTA,
            action=CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR,
            anchor_path=path,
            anchor_path_readable=True,
            relationship=_relationship(content=AlignmentContentRelationship.UNRESOLVED),
            reference_path=path,
        )


def test_explicit_reference_forbids_length_conflict() -> None:
    path = Path("anchor.fa")

    with pytest.raises(ValueError, match="forbids declared length conflicts"):
        CramOfflineReferencePlan(
            cram_resource_id=_CRAM,
            anchor_resource_id=_FASTA,
            action=CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR,
            anchor_path=path,
            anchor_path_readable=True,
            relationship=_relationship(length_conflict_sequence_names=("chr1",)),
            reference_path=path,
        )
