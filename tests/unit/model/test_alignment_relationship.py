"""Invariant tests for alignment dictionary relationship summaries."""

import pytest

from refcompat.model import (
    AlignmentContentRelationship,
    AlignmentDictionaryRelationshipSummary,
    AlignmentMembershipRelationship,
    AlignmentNameResolutionMethod,
    AlignmentNamingRelationship,
    AlignmentOrderRelationship,
    AlignmentSequenceResolution,
    ResourceId,
    SequenceBindingId,
)

_ALIGNMENT = ResourceId("reads")
_FASTA = ResourceId("fasta")


def _summary(
    *,
    membership: AlignmentMembershipRelationship = AlignmentMembershipRelationship.EXACT,
    naming: AlignmentNamingRelationship = AlignmentNamingRelationship.EXACT,
    order: AlignmentOrderRelationship = AlignmentOrderRelationship.CONSISTENT,
    content: AlignmentContentRelationship = AlignmentContentRelationship.M5_VERIFIED,
    resolutions: tuple[AlignmentSequenceResolution, ...] | None = None,
    duplicate_anchor_target_names: tuple[str, ...] = (),
    length_conflict_sequence_names: tuple[str, ...] = (),
) -> AlignmentDictionaryRelationshipSummary:
    if resolutions is None:
        resolutions = (
            AlignmentSequenceResolution(
                "chr1",
                "chr1",
                AlignmentNameResolutionMethod.EXACT_NAME,
            ),
        )
    return AlignmentDictionaryRelationshipSummary(
        alignment_resource_id=_ALIGNMENT,
        fasta_resource_id=_FASTA,
        membership=membership,
        naming=naming,
        order=order,
        content=content,
        resolutions=resolutions,
        duplicate_anchor_target_names=duplicate_anchor_target_names,
        length_conflict_sequence_names=length_conflict_sequence_names,
    )


def test_exact_name_resolution_requires_identical_names() -> None:
    with pytest.raises(ValueError, match="requires identical names"):
        AlignmentSequenceResolution(
            "1",
            "chr1",
            AlignmentNameResolutionMethod.EXACT_NAME,
        )


def test_verified_binding_resolution_requires_different_names() -> None:
    with pytest.raises(ValueError, match="requires a cross-name mapping"):
        AlignmentSequenceResolution(
            "chr1",
            "chr1",
            AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
            SequenceBindingId("binding:1"),
        )


def test_exact_name_resolution_cannot_cite_binding_id() -> None:
    with pytest.raises(ValueError, match="cannot cite a sequence binding"):
        AlignmentSequenceResolution(
            "chr1",
            "chr1",
            AlignmentNameResolutionMethod.EXACT_NAME,
            SequenceBindingId("binding:1"),
        )


def test_verified_binding_resolution_requires_binding_id() -> None:
    with pytest.raises(ValueError, match="requires a sequence-binding ID"):
        AlignmentSequenceResolution(
            "1",
            "chr1",
            AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
        )


def test_content_conflict_requires_named_identity_conflict() -> None:
    with pytest.raises(ValueError, match="requires an identity conflict"):
        _summary(content=AlignmentContentRelationship.M5_CONFLICT)


def test_duplicate_anchor_target_requires_unresolved_membership() -> None:
    with pytest.raises(ValueError, match="require unresolved membership"):
        _summary(
            naming=AlignmentNamingRelationship.VERIFIED_DIFFERENCE,
            resolutions=(
                AlignmentSequenceResolution(
                    "1",
                    "chr1",
                    AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
                    SequenceBindingId("binding:1"),
                ),
                AlignmentSequenceResolution(
                    "chrOne",
                    "chr1",
                    AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
                    SequenceBindingId("binding:2"),
                ),
            ),
            duplicate_anchor_target_names=("chr1",),
        )


def test_naming_only_property_requires_no_other_dictionary_difference() -> None:
    summary = _summary(
        naming=AlignmentNamingRelationship.VERIFIED_DIFFERENCE,
        resolutions=(
            AlignmentSequenceResolution(
                "1",
                "chr1",
                AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
                SequenceBindingId("binding:1"),
            ),
        ),
    )
    reordered = _summary(
        naming=AlignmentNamingRelationship.VERIFIED_DIFFERENCE,
        order=AlignmentOrderRelationship.DIFFERENT,
        resolutions=summary.resolutions,
    )

    assert summary.verified_naming_only_difference
    assert not reordered.verified_naming_only_difference


def test_resolved_and_unresolved_local_name_cannot_overlap() -> None:
    with pytest.raises(ValueError, match="both resolved and unresolved"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.UNRESOLVED,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            order=AlignmentOrderRelationship.UNRESOLVED,
            content=AlignmentContentRelationship.UNRESOLVED,
            resolutions=(
                AlignmentSequenceResolution(
                    "chr1",
                    "chr1",
                    AlignmentNameResolutionMethod.EXACT_NAME,
                ),
            ),
            unresolved_sequence_names=("chr1",),
        )


def test_conflicts_must_name_resolved_local_sequence() -> None:
    with pytest.raises(ValueError, match="must name resolved local sequences"):
        _summary(length_conflict_sequence_names=("missing",))


def test_duplicate_anchor_target_list_must_match_resolutions() -> None:
    with pytest.raises(ValueError, match="exactly match the resolutions"):
        _summary(
            membership=AlignmentMembershipRelationship.UNRESOLVED,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            resolutions=(
                AlignmentSequenceResolution(
                    "1",
                    "chr1",
                    AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
                    SequenceBindingId("binding:1"),
                ),
                AlignmentSequenceResolution(
                    "chrOne",
                    "chr1",
                    AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
                    SequenceBindingId("binding:2"),
                ),
            ),
        )


def test_naming_relationship_must_match_resolution_methods() -> None:
    with pytest.raises(ValueError, match="must match the resolution methods"):
        _summary(
            naming=AlignmentNamingRelationship.EXACT,
            resolutions=(
                AlignmentSequenceResolution(
                    "1",
                    "chr1",
                    AlignmentNameResolutionMethod.VERIFIED_M5_BINDING,
                    SequenceBindingId("binding:1"),
                ),
            ),
        )


def test_exact_membership_cannot_include_m5_distinct_extra() -> None:
    with pytest.raises(ValueError, match="cannot include M5-distinct extras"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.EXACT,
            naming=AlignmentNamingRelationship.EXACT,
            order=AlignmentOrderRelationship.CONSISTENT,
            content=AlignmentContentRelationship.M5_VERIFIED,
            resolutions=(
                AlignmentSequenceResolution(
                    "chr1",
                    "chr1",
                    AlignmentNameResolutionMethod.EXACT_NAME,
                ),
            ),
            m5_distinct_extra_sequence_names=("decoy",),
        )


def test_absent_resolutions_require_unresolved_order_and_content() -> None:
    with pytest.raises(ValueError, match="require unresolved order"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.ALIGNMENT_SUBSET,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            order=AlignmentOrderRelationship.CONSISTENT,
            content=AlignmentContentRelationship.UNRESOLVED,
        )

    with pytest.raises(ValueError, match="require unresolved M5 content"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.ALIGNMENT_SUBSET,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            order=AlignmentOrderRelationship.UNRESOLVED,
            content=AlignmentContentRelationship.M5_VERIFIED,
        )


def test_unresolved_sequence_cannot_claim_resolved_order_or_verified_content() -> None:
    resolution = AlignmentSequenceResolution(
        "chr1",
        "chr1",
        AlignmentNameResolutionMethod.EXACT_NAME,
    )
    with pytest.raises(ValueError, match="require unresolved order"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.UNRESOLVED,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            order=AlignmentOrderRelationship.CONSISTENT,
            content=AlignmentContentRelationship.UNRESOLVED,
            resolutions=(resolution,),
            unresolved_sequence_names=("missing",),
        )

    with pytest.raises(ValueError, match="cannot claim fully verified M5 content"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.UNRESOLVED,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            order=AlignmentOrderRelationship.UNRESOLVED,
            content=AlignmentContentRelationship.M5_VERIFIED,
            resolutions=(resolution,),
            unresolved_sequence_names=("missing",),
        )


def test_fully_resolved_mapping_cannot_claim_unresolved_order() -> None:
    with pytest.raises(ValueError, match="require a resolved order relationship"):
        _summary(order=AlignmentOrderRelationship.UNRESOLVED)


def test_exact_membership_requires_at_least_one_resolution() -> None:
    with pytest.raises(ValueError, match="requires resolved sequences"):
        AlignmentDictionaryRelationshipSummary(
            alignment_resource_id=_ALIGNMENT,
            fasta_resource_id=_FASTA,
            membership=AlignmentMembershipRelationship.EXACT,
            naming=AlignmentNamingRelationship.UNRESOLVED,
            order=AlignmentOrderRelationship.UNRESOLVED,
            content=AlignmentContentRelationship.UNRESOLVED,
        )
