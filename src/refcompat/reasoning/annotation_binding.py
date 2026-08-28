"""Derive conservative GFF3 embedded-FASTA sequence bindings.

Only sequence content bundled after the GFF3 FASTA boundary can contribute
annotation-local content identity. FASTA identifiers are used only to associate
that content with an exact logical annotation seqid; they are not treated as
aliases to the external FASTA anchor. Cross-name binding is delegated to the
existing complete-anchor identity reasoner so explicit scope cannot manufacture
uniqueness.
"""

from __future__ import annotations

import hashlib
import json

from refcompat.model.annotation import AnnotationContextSnapshot
from refcompat.model.contracts import (
    CapabilityId,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
)
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.model.resources import ResourceKind
from refcompat.reasoning.reference_context import derive_sequence_bindings


def annotation_embedded_identity_capabilities(
    snapshot: AnnotationContextSnapshot,
) -> tuple[SequenceIdentityCapability, ...]:
    """Return content-derived identities for embedded sequences relevant to RCHECK-060."""

    if snapshot.resource_kind is not ResourceKind.GFF3:
        return ()

    relevant_names = set(snapshot.used_sequence_names) | {
        region.sequence_name for region in snapshot.sequence_regions
    }
    return tuple(
        SequenceIdentityCapability(
            id=_capability_id(snapshot, sequence.sequence_name, sequence.md5.value),
            resource_id=snapshot.resource_id,
            sequence_name=sequence.sequence_name,
            identity=sequence.md5,
            provenance=SequenceIdentityProvenance.CONTENT_DERIVED,
        )
        for sequence in snapshot.embedded_fasta_sequences
        if sequence.sequence_name in relevant_names
    )


def derive_annotation_sequence_bindings(
    snapshot: AnnotationContextSnapshot,
    context: ReferenceContext,
) -> tuple[SequenceBinding, ...]:
    """Derive verified cross-name bindings from relevant embedded FASTA content."""

    if snapshot.resource_id == context.anchor_resource_id:
        raise ValueError("annotation binding resource cannot be the FASTA anchor")
    if snapshot.resource_id not in context.scope.resource_ids:
        raise ValueError("annotation binding resource must be inside reference-context scope")

    capabilities = annotation_embedded_identity_capabilities(snapshot)
    local_contract = ResourceContract(snapshot.resource_id, capabilities=capabilities)
    contracts = tuple(
        local_contract if resource_id == snapshot.resource_id else ResourceContract(resource_id)
        for resource_id in context.scope.resource_ids
    )
    return tuple(
        binding
        for binding in derive_sequence_bindings(context, contracts)
        if binding.resource_id == snapshot.resource_id
        and binding.local_sequence_name != binding.anchor_sequence_name
    )


def _capability_id(
    snapshot: AnnotationContextSnapshot,
    sequence_name: str,
    digest: str,
) -> CapabilityId:
    payload = json.dumps(
        [str(snapshot.resource_id), sequence_name, digest],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CapabilityId(f"annotation-embedded-identity:{hashlib.sha256(payload).hexdigest()}")
