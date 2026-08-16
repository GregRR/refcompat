"""Evaluation request and explicit-scope vocabulary.

Milestone 2 compatibility conclusions are contextual. These immutable values
identify the supplied resources, the explicit FASTA anchor used by the v0.1
reasoner, and any resource/sequence scope chosen by the caller without
embedding compatibility conclusions in the request itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType

from refcompat.model.resources import Resource, ResourceId, ResourceKind

ProfileId = NewType("ProfileId", str)
EvaluationPolicyId = NewType("EvaluationPolicyId", str)


@dataclass(frozen=True, slots=True)
class EvaluationScope:
    """Explicit resource and optional sequence-name scope for one evaluation.

    ``anchor_sequence_names=None`` means that the request has not narrowed the
    sequence namespace below the selected resources. A non-empty tuple denotes
    an explicit subset in the selected FASTA anchor's local namespace. Other
    resources require evidence-backed bindings into that namespace; the scope
    must not imply a global string namespace or silently infer exclusions from
    familiar sequence classes.
    """

    resource_ids: tuple[ResourceId, ...]
    anchor_sequence_names: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if not self.resource_ids:
            raise ValueError("evaluation scope must contain at least one resource")
        if any(not resource_id for resource_id in self.resource_ids):
            raise ValueError("evaluation scope resource IDs must not be empty")
        if len(set(self.resource_ids)) != len(self.resource_ids):
            raise ValueError("evaluation scope resource IDs must be unique")

        if self.anchor_sequence_names is None:
            return
        if not self.anchor_sequence_names:
            raise ValueError("explicit sequence scope must contain at least one sequence name")
        if any(not name for name in self.anchor_sequence_names):
            raise ValueError("evaluation scope sequence names must not be empty")
        if len(set(self.anchor_sequence_names)) != len(self.anchor_sequence_names):
            raise ValueError("evaluation scope sequence names must be unique")


@dataclass(frozen=True, slots=True)
class EvaluationRequest:
    """Immutable v0.1 anchor-driven compatibility evaluation request.

    The explicitly selected anchor must be a supplied FASTA and must be in the
    evaluation scope. Profile and policy identifiers are opaque selectors at
    this layer; their requirements are introduced by later contract builders,
    not interpreted by this request object.
    """

    resources: tuple[Resource, ...]
    anchor_resource_id: ResourceId
    scope: EvaluationScope
    active_profiles: tuple[ProfileId, ...] = ()
    policy_id: EvaluationPolicyId | None = None

    def __post_init__(self) -> None:
        if not self.resources:
            raise ValueError("evaluation request must contain at least one resource")

        resource_ids = tuple(resource.id for resource in self.resources)
        if any(not resource_id for resource_id in resource_ids):
            raise ValueError("evaluation request resource IDs must not be empty")
        if len(set(resource_ids)) != len(resource_ids):
            raise ValueError("evaluation request resource IDs must be unique")
        if not self.anchor_resource_id:
            raise ValueError("evaluation anchor resource ID must not be empty")

        resources_by_id = {resource.id: resource for resource in self.resources}
        anchor = resources_by_id.get(self.anchor_resource_id)
        if anchor is None:
            raise ValueError("evaluation anchor must identify a supplied resource")
        if anchor.kind is not ResourceKind.FASTA:
            raise ValueError("v0.1 evaluation anchor must be a FASTA resource")

        supplied_ids = set(resource_ids)
        if not set(self.scope.resource_ids).issubset(supplied_ids):
            raise ValueError("evaluation scope may reference only supplied resources")
        if self.anchor_resource_id not in self.scope.resource_ids:
            raise ValueError("evaluation scope must include the FASTA anchor")

        if any(not profile_id for profile_id in self.active_profiles):
            raise ValueError("evaluation profile IDs must not be empty")
        if len(set(self.active_profiles)) != len(self.active_profiles):
            raise ValueError("evaluation profile IDs must be unique")
        if self.policy_id is not None and not self.policy_id:
            raise ValueError("evaluation policy ID must not be empty")
