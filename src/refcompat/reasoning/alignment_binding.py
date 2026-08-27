"""Derive conservative BAM/CRAM sequence-name bindings from declared M5 identity.

SAM ``@SQ M5`` values are metadata claims about reference sequence content. A
claim may establish a cross-name ``SequenceBinding`` only when it resolves
uniquely against the complete FASTA anchor snapshot, is inside the selected
anchor scope, and does not contradict the same ``@SQ`` record's declared
length. ``AN`` values and familiar naming conventions are not binding evidence.
"""

from __future__ import annotations

import hashlib
import json

from refcompat.model.alignment import AlignmentHeaderSnapshot
from refcompat.model.contracts import (
    CapabilityId,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityProvenance,
)
from refcompat.model.identity import Md5Digest, SnapshotSequence
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.reasoning.reference_context import derive_sequence_bindings


def alignment_binding_identity_capabilities(
    snapshot: AlignmentHeaderSnapshot,
    context: ReferenceContext,
) -> tuple[SequenceIdentityCapability, ...]:
    """Return alignment M5 claims safe to use for cross-name binding.

    Uniqueness is established against the complete FASTA anchor snapshot before
    explicit anchor-sequence scope is applied. Exact same-name declarations do
    not need a binding and are intentionally omitted. The emitted capabilities
    remain declared metadata and are suitable only as binding evidence.
    """

    _validate_alignment_binding_inputs(snapshot, context)

    if any(sequence.md5 is None for sequence in context.anchor_snapshot.sequences):
        return ()

    anchor_by_md5: dict[Md5Digest, list[SnapshotSequence]] = {}
    for sequence in context.anchor_snapshot.sequences:
        if sequence.md5 is not None:
            anchor_by_md5.setdefault(sequence.md5, []).append(sequence)

    scoped_names = {sequence.local_name for sequence in context.sequences}
    capabilities: list[SequenceIdentityCapability] = []

    for record in snapshot.header.sequences:
        digest = record.md5
        if digest is None:
            continue

        targets = anchor_by_md5.get(digest, [])
        if len(targets) != 1:
            continue
        target = targets[0]
        if target.local_name not in scoped_names:
            continue
        if target.local_name == record.name:
            continue
        if target.length != record.length:
            continue

        capabilities.append(
            SequenceIdentityCapability(
                id=_binding_capability_id(snapshot, record.name, digest),
                resource_id=snapshot.resource_id,
                sequence_name=record.name,
                identity=digest,
                provenance=SequenceIdentityProvenance.DECLARED_METADATA,
            )
        )

    return tuple(capabilities)


def derive_alignment_sequence_bindings(
    snapshot: AlignmentHeaderSnapshot,
    context: ReferenceContext,
) -> tuple[SequenceBinding, ...]:
    """Derive verified cross-name BAM/CRAM bindings from usable ``@SQ M5`` claims."""

    capabilities = alignment_binding_identity_capabilities(snapshot, context)
    alignment_contract = ResourceContract(snapshot.resource_id, capabilities=capabilities)
    contracts = tuple(
        alignment_contract if resource_id == snapshot.resource_id else ResourceContract(resource_id)
        for resource_id in context.scope.resource_ids
    )
    bindings = derive_sequence_bindings(context, contracts)
    return tuple(binding for binding in bindings if binding.resource_id == snapshot.resource_id)


def _validate_alignment_binding_inputs(
    snapshot: AlignmentHeaderSnapshot,
    context: ReferenceContext,
) -> None:
    if snapshot.resource_id == context.anchor_resource_id:
        raise ValueError("alignment binding resource cannot be the FASTA anchor")
    if snapshot.resource_id not in context.scope.resource_ids:
        raise ValueError("alignment binding resource must be inside the reference-context scope")


def _binding_capability_id(
    snapshot: AlignmentHeaderSnapshot,
    sequence_name: str,
    digest: Md5Digest,
) -> CapabilityId:
    payload = json.dumps(
        [str(snapshot.resource_id), sequence_name, digest.value],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CapabilityId(f"alignment-binding-identity:{hashlib.sha256(payload).hexdigest()}")
