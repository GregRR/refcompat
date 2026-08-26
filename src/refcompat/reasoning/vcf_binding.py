"""Derive conservative VCF sequence-name bindings from declared content identity.

VCF ``##contig`` MD5 values are metadata claims about the referenced sequence.
They are never treated as REF compatibility proof. A claim may establish a
cross-name ``SequenceBinding`` only when it is a syntactically valid MD5,
resolves uniquely against the complete FASTA anchor snapshot, is inside the
selected anchor scope, and does not contradict a declared contig length.
"""

from __future__ import annotations

import hashlib
import json

from refcompat.model.contracts import (
    CapabilityId,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
)
from refcompat.model.identity import Md5Digest, SnapshotSequence
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.model.vcf import VcfContextSnapshot
from refcompat.reasoning.reference_context import derive_sequence_bindings


def vcf_binding_identity_capabilities(
    snapshot: VcfContextSnapshot,
    context: ReferenceContext,
) -> tuple[SequenceIdentityCapability, ...]:
    """Return only VCF MD5 claims safe to use for cross-name binding.

    The complete anchor snapshot establishes uniqueness before explicit anchor
    sequence scope is applied. Exact same-name declarations do not need a
    binding and are intentionally omitted. Declared MD5 metadata remains
    binding evidence only; exhaustive REF comparison still decides reference
    compatibility.
    """

    _validate_vcf_binding_inputs(snapshot, context)

    if any(sequence.md5 is None for sequence in context.anchor_snapshot.sequences):
        return ()

    anchor_by_md5: dict[Md5Digest, list[SnapshotSequence]] = {}
    for sequence in context.anchor_snapshot.sequences:
        if sequence.md5 is not None:
            anchor_by_md5.setdefault(sequence.md5, []).append(sequence)

    scoped_names = {sequence.local_name for sequence in context.sequences}
    used_names = set(snapshot.used_sequence_names)
    capabilities: list[SequenceIdentityCapability] = []

    for contig in snapshot.header.contigs:
        if contig.name not in used_names or contig.md5 is None:
            continue
        try:
            digest = Md5Digest(contig.md5)
        except ValueError:
            continue

        targets = anchor_by_md5.get(digest, [])
        if len(targets) != 1:
            continue
        target = targets[0]
        if target.local_name not in scoped_names:
            continue
        if target.local_name == contig.name:
            continue
        if contig.length is not None and target.length != contig.length:
            continue

        capabilities.append(
            SequenceIdentityCapability(
                id=_binding_capability_id(snapshot, contig.name, digest),
                resource_id=snapshot.resource_id,
                sequence_name=contig.name,
                identity=digest,
                provenance=SequenceIdentityProvenance.DECLARED_METADATA,
            )
        )

    return tuple(capabilities)


def derive_vcf_sequence_bindings(
    snapshot: VcfContextSnapshot,
    context: ReferenceContext,
) -> tuple[SequenceBinding, ...]:
    """Derive verified cross-name VCF bindings from usable ``##contig`` MD5 claims."""

    capabilities = vcf_binding_identity_capabilities(snapshot, context)
    vcf_contract = ResourceContract(snapshot.resource_id, capabilities=capabilities)
    contracts = tuple(
        vcf_contract if resource_id == snapshot.resource_id else ResourceContract(resource_id)
        for resource_id in context.scope.resource_ids
    )
    bindings = derive_sequence_bindings(context, contracts)
    return tuple(binding for binding in bindings if binding.resource_id == snapshot.resource_id)


def _validate_vcf_binding_inputs(
    snapshot: VcfContextSnapshot,
    context: ReferenceContext,
) -> None:
    if snapshot.resource_id == context.anchor_resource_id:
        raise ValueError("VCF binding resource cannot be the FASTA anchor")
    if snapshot.resource_id not in context.scope.resource_ids:
        raise ValueError("VCF binding resource must be inside the reference-context scope")


def _binding_capability_id(
    snapshot: VcfContextSnapshot,
    sequence_name: str,
    digest: Md5Digest,
) -> CapabilityId:
    payload = json.dumps(
        [str(snapshot.resource_id), sequence_name, digest.value],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CapabilityId(f"vcf-binding-identity:{hashlib.sha256(payload).hexdigest()}")
