"""Derive conservative annotation sequence bindings from content identity.

GFF3 sequence content bundled after the FASTA boundary can contribute intrinsic
annotation-local identity. Callers may also supply independently established
annotation-owned content identities for reference-relevant seqids, which is the
only path for GTF to participate in content-verified cross-name binding or
exhaustive content-absence reasoning. Neither FASTA identifiers nor familiar
strings are treated as aliases to the external FASTA anchor. Cross-name binding
is delegated to the existing complete-anchor identity reasoner so explicit scope
cannot manufacture uniqueness.
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


def annotation_binding_identity_capabilities(
    snapshot: AnnotationContextSnapshot,
    additional_capabilities: tuple[SequenceIdentityCapability, ...] = (),
) -> tuple[SequenceIdentityCapability, ...]:
    """Return content identities allowed in annotation reference reasoning.

    GFF3 embedded FASTA contributes intrinsic annotation-owned sequence content.
    Callers may also supply independently established content-derived identities
    for reference-relevant annotation seqids. These capabilities can support
    conservative binding or exhaustive absence reasoning without treating a
    familiar string pattern or declared metadata as alias authority.
    """

    embedded = annotation_embedded_identity_capabilities(snapshot)
    relevant_names = set(snapshot.used_sequence_names) | {
        region.sequence_name for region in snapshot.sequence_regions
    }
    embedded_ids = {capability.id for capability in embedded}
    additional_ids: set[CapabilityId] = set()
    for capability in additional_capabilities:
        if capability.id in embedded_ids or capability.id in additional_ids:
            raise ValueError("annotation binding identity capability IDs must be unique")
        additional_ids.add(capability.id)
        if capability.resource_id != snapshot.resource_id:
            raise ValueError("annotation binding identity capability must belong to the annotation")
        if capability.provenance is not SequenceIdentityProvenance.CONTENT_DERIVED:
            raise ValueError("annotation binding identity capability must be content-derived")
        if capability.sequence_name not in relevant_names:
            raise ValueError(
                "annotation binding identity capability sequence name must be reference-relevant"
            )
    return (*embedded, *additional_capabilities)


def derive_annotation_sequence_bindings(
    snapshot: AnnotationContextSnapshot,
    context: ReferenceContext,
    *,
    binding_identity_capabilities: tuple[SequenceIdentityCapability, ...] = (),
) -> tuple[SequenceBinding, ...]:
    """Derive verified cross-name bindings from annotation-owned content identity."""

    if snapshot.resource_id == context.anchor_resource_id:
        raise ValueError("annotation binding resource cannot be the FASTA anchor")
    if snapshot.resource_id not in context.scope.resource_ids:
        raise ValueError("annotation binding resource must be inside reference-context scope")

    capabilities = annotation_binding_identity_capabilities(
        snapshot,
        binding_identity_capabilities,
    )
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
