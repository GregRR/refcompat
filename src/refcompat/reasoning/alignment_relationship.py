"""Conservative BAM/CRAM header-dictionary relationship classification."""

from __future__ import annotations

from collections import Counter

from refcompat._compat import assert_never
from refcompat.model.alignment import AlignmentHeaderSnapshot
from refcompat.model.alignment_relationship import (
    AlignmentContentRelationship,
    AlignmentDictionaryRelationshipSummary,
    AlignmentMembershipRelationship,
    AlignmentNameResolutionMethod,
    AlignmentNamingRelationship,
    AlignmentOrderRelationship,
    AlignmentSequenceResolution,
)
from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.identity import Md5Digest
from refcompat.model.reference_context import (
    ReferenceContext,
    SequenceBinding,
    SequenceBindingMethod,
)
from refcompat.model.sequence_dictionary import SequenceDictionaryRecord
from refcompat.reasoning.alignment_binding import derive_alignment_sequence_bindings


def classify_alignment_dictionary_relationship(
    snapshot: AlignmentHeaderSnapshot,
    context: ReferenceContext,
    *,
    bundle_result: BundleReasoningResult | None = None,
) -> AlignmentDictionaryRelationshipSummary:
    """Describe the alignment header dictionary relative to the FASTA anchor.

    Exact names are structurally resolvable in the selected anchor scope.
    Cross-name resolution may use an M5-backed binding derived from the header,
    or an already-validated authoritative-name binding carried by a completed
    ``BundleReasoningResult``. An unfamiliar local name becomes M5-distinct only
    when its declared M5 is absent from a complete-MD5 FASTA anchor and the name does
    not identify any FASTA sequence outside the selected scope.

    This function is descriptive. It does not scan reads, change generic
    compatibility constraints, or aggregate a second alignment-specific verdict.
    """

    if snapshot.resource_id == context.anchor_resource_id:
        raise ValueError("alignment relationship resource cannot be the FASTA anchor")
    if snapshot.resource_id not in context.scope.resource_ids:
        raise ValueError(
            "alignment relationship resource must be inside the reference-context scope"
        )

    bindings = {
        binding.local_sequence_name: binding
        for binding in _alignment_sequence_bindings(snapshot, context, bundle_result)
    }
    scoped_anchor = {sequence.local_name: sequence for sequence in context.sequences}
    full_anchor_names = {sequence.local_name for sequence in context.anchor_snapshot.sequences}
    full_anchor_md5_complete = all(
        sequence.md5 is not None for sequence in context.anchor_snapshot.sequences
    )
    full_anchor_md5s = {
        sequence.md5 for sequence in context.anchor_snapshot.sequences if sequence.md5 is not None
    }

    resolutions: list[AlignmentSequenceResolution] = []
    unresolved_names: list[str] = []
    m5_distinct_extra_names: list[str] = []
    length_conflicts: list[str] = []
    identity_conflicts: list[str] = []
    content_unresolved = False

    for record in snapshot.header.sequences:
        binding = bindings.get(record.name)
        if binding is not None:
            target_name = binding.anchor_sequence_name
            if target_name == record.name:
                method = AlignmentNameResolutionMethod.EXACT_NAME
                sequence_binding_id = None
            elif binding.method is SequenceBindingMethod.VERIFIED_SEQUENCE_IDENTITY:
                if record.md5 is None or record.md5 not in binding.identity_values:
                    raise ValueError("alignment identity binding must be backed by the record M5")
                method = AlignmentNameResolutionMethod.VERIFIED_M5_BINDING
                sequence_binding_id = binding.id
            elif binding.method is SequenceBindingMethod.AUTHORITATIVE_NAME:
                method = AlignmentNameResolutionMethod.AUTHORITATIVE_NAME_BINDING
                sequence_binding_id = binding.id
            else:
                assert_never(binding.method)
        elif record.name in scoped_anchor:
            target_name = record.name
            method = AlignmentNameResolutionMethod.EXACT_NAME
            sequence_binding_id = None
        else:
            if _is_m5_distinct_extra(
                record,
                full_anchor_names=full_anchor_names,
                full_anchor_md5_complete=full_anchor_md5_complete,
                full_anchor_md5s=full_anchor_md5s,
            ):
                m5_distinct_extra_names.append(record.name)
            else:
                unresolved_names.append(record.name)
            continue

        target = scoped_anchor[target_name]
        resolutions.append(
            AlignmentSequenceResolution(
                local_sequence_name=record.name,
                anchor_sequence_name=target_name,
                method=method,
                sequence_binding_id=sequence_binding_id,
            )
        )

        if record.length != target.length:
            length_conflicts.append(record.name)

        if record.md5 is None or target.md5 is None:
            content_unresolved = True
        elif record.md5 != target.md5:
            identity_conflicts.append(record.name)

    duplicate_targets = tuple(
        name
        for name, count in Counter(
            resolution.anchor_sequence_name for resolution in resolutions
        ).items()
        if count > 1
    )
    membership = _membership_relationship(
        context,
        resolutions=tuple(resolutions),
        unresolved_names=tuple(unresolved_names),
        m5_distinct_extra_names=tuple(m5_distinct_extra_names),
        duplicate_targets=duplicate_targets,
    )
    naming = _naming_relationship(
        resolutions=tuple(resolutions),
        unresolved_names=tuple(unresolved_names),
        duplicate_targets=duplicate_targets,
    )
    order = _order_relationship(
        context,
        resolutions=tuple(resolutions),
        unresolved_names=tuple(unresolved_names),
        duplicate_targets=duplicate_targets,
    )
    content = _content_relationship(
        resolutions=tuple(resolutions),
        unresolved_names=tuple(unresolved_names),
        identity_conflicts=tuple(identity_conflicts),
        content_unresolved=content_unresolved,
    )

    return AlignmentDictionaryRelationshipSummary(
        alignment_resource_id=snapshot.resource_id,
        fasta_resource_id=context.anchor_resource_id,
        membership=membership,
        naming=naming,
        order=order,
        content=content,
        resolutions=tuple(resolutions),
        unresolved_sequence_names=tuple(unresolved_names),
        m5_distinct_extra_sequence_names=tuple(m5_distinct_extra_names),
        duplicate_anchor_target_names=duplicate_targets,
        length_conflict_sequence_names=tuple(length_conflicts),
        identity_conflict_sequence_names=tuple(identity_conflicts),
    )


def _alignment_sequence_bindings(
    snapshot: AlignmentHeaderSnapshot,
    context: ReferenceContext,
    bundle_result: BundleReasoningResult | None,
) -> tuple[SequenceBinding, ...]:
    if bundle_result is None:
        return derive_alignment_sequence_bindings(snapshot, context)

    if bundle_result.reference_context != context:
        raise ValueError("alignment relationship bundle must use the supplied reference context")
    if snapshot.resource_id not in {contract.resource_id for contract in bundle_result.contracts}:
        raise ValueError("alignment relationship bundle must contain the alignment resource")

    declared_names = set(snapshot.declared_sequence_names)
    bindings = tuple(
        binding
        for binding in bundle_result.sequence_bindings
        if binding.resource_id == snapshot.resource_id
    )
    if any(binding.local_sequence_name not in declared_names for binding in bindings):
        raise ValueError("alignment relationship bundle binding must address a declared @SQ name")

    scoped_anchor_names = {sequence.local_name for sequence in context.sequences}
    if any(binding.anchor_sequence_name not in scoped_anchor_names for binding in bindings):
        raise ValueError(
            "alignment relationship bundle binding must target the selected anchor scope"
        )
    return bindings


def _is_m5_distinct_extra(
    record: SequenceDictionaryRecord,
    *,
    full_anchor_names: set[str],
    full_anchor_md5_complete: bool,
    full_anchor_md5s: set[Md5Digest],
) -> bool:
    if record.name in full_anchor_names:
        return False
    if set(record.alternate_names) & full_anchor_names:
        return False
    if record.md5 is None or not full_anchor_md5_complete:
        return False
    return record.md5 not in full_anchor_md5s


def _membership_relationship(
    context: ReferenceContext,
    *,
    resolutions: tuple[AlignmentSequenceResolution, ...],
    unresolved_names: tuple[str, ...],
    m5_distinct_extra_names: tuple[str, ...],
    duplicate_targets: tuple[str, ...],
) -> AlignmentMembershipRelationship:
    if unresolved_names or duplicate_targets:
        return AlignmentMembershipRelationship.UNRESOLVED

    anchor_names = {sequence.local_name for sequence in context.sequences}
    resolved_names = {resolution.anchor_sequence_name for resolution in resolutions}

    if resolved_names == anchor_names:
        if m5_distinct_extra_names:
            return AlignmentMembershipRelationship.ALIGNMENT_SUPERSET
        return AlignmentMembershipRelationship.EXACT
    if resolved_names < anchor_names:
        if m5_distinct_extra_names:
            if resolved_names:
                return AlignmentMembershipRelationship.OVERLAP
            return AlignmentMembershipRelationship.DISJOINT
        return AlignmentMembershipRelationship.ALIGNMENT_SUBSET
    return AlignmentMembershipRelationship.UNRESOLVED


def _naming_relationship(
    *,
    resolutions: tuple[AlignmentSequenceResolution, ...],
    unresolved_names: tuple[str, ...],
    duplicate_targets: tuple[str, ...],
) -> AlignmentNamingRelationship:
    if unresolved_names or duplicate_targets or not resolutions:
        return AlignmentNamingRelationship.UNRESOLVED
    if all(
        resolution.method is AlignmentNameResolutionMethod.EXACT_NAME for resolution in resolutions
    ):
        return AlignmentNamingRelationship.EXACT
    return AlignmentNamingRelationship.VERIFIED_DIFFERENCE


def _order_relationship(
    context: ReferenceContext,
    *,
    resolutions: tuple[AlignmentSequenceResolution, ...],
    unresolved_names: tuple[str, ...],
    duplicate_targets: tuple[str, ...],
) -> AlignmentOrderRelationship:
    if unresolved_names or duplicate_targets or not resolutions:
        return AlignmentOrderRelationship.UNRESOLVED

    resolved_order = tuple(resolution.anchor_sequence_name for resolution in resolutions)
    resolved_set = set(resolved_order)
    expected_order = tuple(
        sequence.local_name for sequence in context.sequences if sequence.local_name in resolved_set
    )
    if resolved_order == expected_order:
        return AlignmentOrderRelationship.CONSISTENT
    return AlignmentOrderRelationship.DIFFERENT


def _content_relationship(
    *,
    resolutions: tuple[AlignmentSequenceResolution, ...],
    unresolved_names: tuple[str, ...],
    identity_conflicts: tuple[str, ...],
    content_unresolved: bool,
) -> AlignmentContentRelationship:
    if identity_conflicts:
        return AlignmentContentRelationship.M5_CONFLICT
    if unresolved_names or content_unresolved or not resolutions:
        return AlignmentContentRelationship.UNRESOLVED
    return AlignmentContentRelationship.M5_VERIFIED
