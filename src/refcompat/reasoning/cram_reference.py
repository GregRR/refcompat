"""Conservative offline reference planning for CRAM record decoding.

Header-only CRAM analysis stays reference-independent. If a later operation
would need reference content, RefCompat may use only an explicitly selected,
locally readable FASTA anchor whose header relationship is strong enough for
provider-level exact-name lookup. Otherwise the operation must remain deferred;
this layer never delegates to ambient ``REF_PATH``/``REF_CACHE`` or header
``UR`` lookup.
"""

from __future__ import annotations

from pathlib import Path

from refcompat.model.alignment import AlignmentHeaderSnapshot
from refcompat.model.alignment_relationship import (
    AlignmentContentRelationship,
    AlignmentDictionaryRelationshipSummary,
    AlignmentMembershipRelationship,
    AlignmentNamingRelationship,
)
from refcompat.model.cram_reference import CramOfflineReferenceAction, CramOfflineReferencePlan
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ResourceKind
from refcompat.reasoning.alignment_relationship import classify_alignment_dictionary_relationship


def plan_cram_offline_reference(
    snapshot: AlignmentHeaderSnapshot,
    context: ReferenceContext,
    request: EvaluationRequest,
) -> CramOfflineReferencePlan:
    """Plan offline-safe handling if a future CRAM operation needs reference bases.

    The function does not inspect CRAM compression headers, slices, or records,
    so it deliberately does not decide whether an external reference is
    required. It decides only whether the selected FASTA anchor is safe to pass
    explicitly as ``reference_filename`` if reference-dependent decoding is
    later requested.
    """

    if snapshot.resource_kind is not ResourceKind.CRAM:
        raise ValueError("offline CRAM reference planning requires a CRAM snapshot")
    if request.anchor_resource_id != context.anchor_resource_id:
        raise ValueError("CRAM reference planning request/context anchor mismatch")
    if request.scope != context.scope:
        raise ValueError("CRAM reference planning request/context scope mismatch")
    if snapshot.resource_id not in request.scope.resource_ids:
        raise ValueError("CRAM reference planning requires the CRAM resource in evaluation scope")

    resources_by_id = {resource.id: resource for resource in request.resources}
    cram_resource = resources_by_id.get(snapshot.resource_id)
    if cram_resource is None or cram_resource.kind is not ResourceKind.CRAM:
        raise ValueError("CRAM reference planning requires a supplied CRAM resource")
    anchor_resource = resources_by_id.get(context.anchor_resource_id)
    if anchor_resource is None or anchor_resource.kind is not ResourceKind.FASTA:
        raise ValueError("CRAM reference planning requires the selected FASTA anchor resource")

    relationship = classify_alignment_dictionary_relationship(snapshot, context)
    anchor_path = anchor_resource.artifact.path
    anchor_path_readable = _is_readable_file(anchor_path)
    can_use_anchor = anchor_path_readable and _relationship_supports_explicit_local_anchor(
        relationship
    )

    if can_use_anchor:
        return CramOfflineReferencePlan(
            cram_resource_id=snapshot.resource_id,
            anchor_resource_id=context.anchor_resource_id,
            action=CramOfflineReferenceAction.USE_EXPLICIT_LOCAL_ANCHOR,
            anchor_path=anchor_path,
            anchor_path_readable=True,
            relationship=relationship,
            reference_path=anchor_path,
        )

    return CramOfflineReferencePlan(
        cram_resource_id=snapshot.resource_id,
        anchor_resource_id=context.anchor_resource_id,
        action=CramOfflineReferenceAction.DEFER_REFERENCE_DEPENDENT_DECODING,
        anchor_path=anchor_path,
        anchor_path_readable=anchor_path_readable,
        relationship=relationship,
    )


def _relationship_supports_explicit_local_anchor(
    relationship: AlignmentDictionaryRelationshipSummary,
) -> bool:
    return (
        relationship.membership
        in {
            AlignmentMembershipRelationship.EXACT,
            AlignmentMembershipRelationship.ALIGNMENT_SUBSET,
        }
        and relationship.naming is AlignmentNamingRelationship.EXACT
        and relationship.content is AlignmentContentRelationship.M5_VERIFIED
        and not relationship.length_conflict_sequence_names
    )


def _is_readable_file(path: Path) -> bool:
    try:
        with path.open("rb"):
            return True
    except OSError:
        return False
