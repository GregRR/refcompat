"""Anchor-driven reference context and evidence-backed sequence bindings.

A ``ReferenceContext`` is produced by the reasoner from the explicitly selected
FASTA anchor and evaluation scope. ``SequenceBinding`` connects a resource-local
sequence label to one anchor-local sequence only when comparable content
identity evidence establishes the relationship.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat._compat import StrEnum
from refcompat.model.contracts import Capability, CapabilityId, SequenceIdentityValue
from refcompat.model.evaluation import EvaluationScope
from refcompat.model.identity import (
    CollectionCompleteness,
    SequenceCollectionSnapshot,
    SnapshotSequence,
)
from refcompat.model.resources import ResourceId

SequenceBindingId = NewType("SequenceBindingId", str)


class SequenceBindingMethod(StrEnum):
    """Evidence-backed mechanism establishing a local-to-anchor sequence mapping."""

    VERIFIED_SEQUENCE_IDENTITY = "verified_sequence_identity"


@dataclass(frozen=True, slots=True)
class ReferenceContext:
    """Explicit FASTA-anchored sequence context for one evaluation scope.

    ``sequences`` is the anchor snapshot projected into the caller-selected
    anchor sequence scope while preserving FASTA order. ``anchor_capabilities``
    are reasoner-produced capabilities derived only from those selected anchor
    sequences; they are not capabilities contributed by peer resources.
    """

    anchor_resource_id: ResourceId
    scope: EvaluationScope
    anchor_snapshot: SequenceCollectionSnapshot
    sequences: tuple[SnapshotSequence, ...]
    anchor_capabilities: tuple[Capability, ...]

    def __post_init__(self) -> None:
        if not self.anchor_resource_id:
            raise ValueError("reference-context anchor resource ID must not be empty")
        if self.anchor_resource_id not in self.scope.resource_ids:
            raise ValueError("reference-context anchor must be inside evaluation scope")
        if self.anchor_snapshot.resource_id != self.anchor_resource_id:
            raise ValueError("reference-context snapshot must belong to the FASTA anchor")
        if self.anchor_snapshot.completeness is not CollectionCompleteness.COMPLETE:
            raise ValueError("v0.1 FASTA reference context requires a complete anchor snapshot")
        if not self.sequences:
            raise ValueError("reference context must contain at least one anchor sequence")

        names = tuple(sequence.local_name for sequence in self.sequences)
        if len(set(names)) != len(names):
            raise ValueError("reference-context anchor sequence names must be unique")
        if any(sequence.length is None for sequence in self.sequences):
            raise ValueError("reference-context FASTA sequences must have known lengths")

        snapshot_names = tuple(sequence.local_name for sequence in self.anchor_snapshot.sequences)
        if len(set(snapshot_names)) != len(snapshot_names):
            raise ValueError("FASTA anchor snapshot sequence names must be unique")
        snapshot_by_name = {
            sequence.local_name: sequence for sequence in self.anchor_snapshot.sequences
        }
        if any(
            snapshot_by_name.get(sequence.local_name) != sequence for sequence in self.sequences
        ):
            raise ValueError("reference-context sequences must come from the anchor snapshot")

        selected_names = self.scope.anchor_sequence_names
        if selected_names is None:
            if names != snapshot_names:
                raise ValueError(
                    "unbounded reference context must retain the full anchor sequence set"
                )
        elif set(names) != set(selected_names):
            raise ValueError("reference-context sequences must exactly match explicit anchor scope")

        capability_ids = tuple(capability.id for capability in self.anchor_capabilities)
        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError("reference-context anchor capability IDs must be unique")
        if any(
            capability.resource_id != self.anchor_resource_id
            for capability in self.anchor_capabilities
        ):
            raise ValueError("reference-context capabilities must belong to the FASTA anchor")


@dataclass(frozen=True, slots=True)
class SequenceBinding:
    """Verified mapping from one resource-local label to one anchor-local sequence.

    Bindings are established only from comparable content identities. The
    capability IDs retain the concrete identity facts used to establish the
    relationship. String resemblance alone must never construct this object.
    """

    id: SequenceBindingId
    resource_id: ResourceId
    local_sequence_name: str
    anchor_resource_id: ResourceId
    anchor_sequence_name: str
    method: SequenceBindingMethod
    identity_values: tuple[SequenceIdentityValue, ...]
    capability_ids: tuple[CapabilityId, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("sequence-binding ID must not be empty")
        if not self.resource_id:
            raise ValueError("sequence-binding resource ID must not be empty")
        if not self.local_sequence_name:
            raise ValueError("sequence-binding local sequence name must not be empty")
        if not self.anchor_resource_id:
            raise ValueError("sequence-binding anchor resource ID must not be empty")
        if not self.anchor_sequence_name:
            raise ValueError("sequence-binding anchor sequence name must not be empty")
        if not self.identity_values:
            raise ValueError("sequence binding requires at least one content identity")
        if len(set(self.identity_values)) != len(self.identity_values):
            raise ValueError("sequence-binding identity values must be unique")
        if not self.capability_ids:
            raise ValueError("sequence binding requires source capability IDs")
        if any(not capability_id for capability_id in self.capability_ids):
            raise ValueError("sequence-binding capability IDs must not be empty")
        if len(set(self.capability_ids)) != len(self.capability_ids):
            raise ValueError("sequence-binding capability IDs must be unique")
