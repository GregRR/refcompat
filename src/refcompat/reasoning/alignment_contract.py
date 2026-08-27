"""Project BAM/CRAM header declarations into generic compatibility requirements.

This bridge remains header-only. It treats ``@SQ`` names, lengths, and M5
values as declarations made by the alignment resource. M5 becomes a mandatory
identity requirement when present, but this slice does not yet emit peer
identity capabilities or derive cross-name bindings from alignment metadata.
"""

from __future__ import annotations

import hashlib
import json

from refcompat.model.alignment import AlignmentHeaderSnapshot
from refcompat.model.contracts import (
    Requirement,
    RequirementId,
    RequirementLevel,
    RequirementOrigin,
    ResourceContract,
    SequenceIdentityRequirement,
    SequenceLengthRequirement,
    SequencePresenceRequirement,
)
from refcompat.model.reference_context import ReferenceContext
from refcompat.model.resources import ResourceId


def build_alignment_contract(
    snapshot: AlignmentHeaderSnapshot,
    reference_context: ReferenceContext,
) -> ResourceContract:
    """Build the core-format contract declared by one BAM/CRAM SAM header.

    Every declared ``@SQ`` record contributes mandatory sequence-presence and
    sequence-length requirements. A declared ``M5`` additionally contributes a
    mandatory sequence-identity requirement. Header order, aliases, assembly,
    URI, species, topology, alternate-locus metadata, and ``@PG`` provenance
    remain observations in this slice and do not create requirements.

    The contract intentionally emits no peer identity capabilities yet, so
    cross-name M5 binding remains a later Milestone 4 boundary. Exact-name M5
    declarations can nevertheless be assessed against content-derived FASTA
    identity through the generic constraint machinery.
    """

    if snapshot.resource_id not in reference_context.scope.resource_ids:
        raise ValueError("alignment resource must be inside the reference-context scope")

    presence_requirements = tuple(
        SequencePresenceRequirement(
            id=_requirement_id("presence", snapshot.resource_id, record.name),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=record.name,
        )
        for record in snapshot.header.sequences
    )
    length_requirements = tuple(
        SequenceLengthRequirement(
            id=_requirement_id(
                "length",
                snapshot.resource_id,
                f"{record.name}:{record.length}",
            ),
            resource_id=snapshot.resource_id,
            origin=RequirementOrigin.CORE_FORMAT,
            level=RequirementLevel.MANDATORY,
            sequence_name=record.name,
            length=record.length,
        )
        for record in snapshot.header.sequences
    )
    identity_requirements: list[SequenceIdentityRequirement] = []
    for record in snapshot.header.sequences:
        digest = record.md5
        if digest is None:
            continue
        identity_requirements.append(
            SequenceIdentityRequirement(
                id=_requirement_id(
                    "identity",
                    snapshot.resource_id,
                    f"{record.name}:{digest.value}",
                ),
                resource_id=snapshot.resource_id,
                origin=RequirementOrigin.CORE_FORMAT,
                level=RequirementLevel.MANDATORY,
                sequence_name=record.name,
                identity=digest,
            )
        )

    requirements: tuple[Requirement, ...] = (
        *presence_requirements,
        *length_requirements,
        *identity_requirements,
    )
    return ResourceContract(
        resource_id=snapshot.resource_id,
        requirements=requirements,
    )


def _requirement_id(kind: str, resource_id: ResourceId, value: str) -> RequirementId:
    payload = json.dumps(
        [kind, str(resource_id), value],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return RequirementId(f"alignment-requirement:{hashlib.sha256(payload).hexdigest()}")
