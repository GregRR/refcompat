"""Anchor-driven orchestration across all scoped resource contracts."""

from __future__ import annotations

import hashlib
import json

from refcompat._compat import assert_never
from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.constraints import ConstraintId, capability_is_comparable
from refcompat.model.contracts import (
    Capability,
    ReferenceBaseRequirement,
    Requirement,
    ResourceContract,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest
from refcompat.model.identity import SequenceCollectionSnapshot
from refcompat.model.reference_context import ReferenceContext, SequenceBinding
from refcompat.model.resources import ResourceId
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence
from refcompat.reasoning.interpretation import interpret_constraint_results
from refcompat.reasoning.reference_context import build_reference_context, derive_sequence_bindings


def reason_bundle(
    request: EvaluationRequest,
    anchor_snapshot: SequenceCollectionSnapshot,
    contracts: tuple[ResourceContract, ...],
) -> BundleReasoningResult:
    """Evaluate every scoped typed requirement against the explicit FASTA anchor.

    Peer-resource capabilities participate only in evidence-backed sequence
    binding construction. They never become competing reference candidates and
    therefore cannot outvote or replace the selected anchor.
    """

    ordered_contracts = _ordered_contracts(request, contracts)
    context = build_reference_context(request, anchor_snapshot)
    bindings = derive_sequence_bindings(context, ordered_contracts)

    constraints = []
    for contract in ordered_contracts:
        for requirement in contract.requirements:
            relevant_bindings = _bindings_for_requirement(requirement, bindings)
            candidates = _anchor_candidates(context, requirement, relevant_bindings)
            constraints.append(
                build_constraint(
                    _make_constraint_id(
                        request.anchor_resource_id,
                        requirement,
                        candidates,
                        relevant_bindings,
                    ),
                    requirement,
                    candidates,
                    relevant_bindings,
                )
            )

    constraint_tuple = tuple(constraints)
    evaluations = tuple(evaluate_constraint(constraint) for constraint in constraint_tuple)
    evidence = aggregate_constraint_evidence(constraint_tuple, evaluations)
    interpretation = interpret_constraint_results(
        request,
        constraint_tuple,
        evaluations,
        evidence,
    )
    return BundleReasoningResult(
        request=request,
        contracts=ordered_contracts,
        reference_context=context,
        sequence_bindings=bindings,
        constraints=constraint_tuple,
        evaluations=evaluations,
        evidence=evidence,
        interpretation=interpretation,
    )


def _bindings_for_requirement(
    requirement: Requirement,
    bindings: tuple[SequenceBinding, ...],
) -> tuple[SequenceBinding, ...]:
    resource_bindings = tuple(
        binding
        for binding in bindings
        if binding.resource_id == requirement.resource_id
        and binding.anchor_sequence_name != binding.local_sequence_name
    )
    if isinstance(
        requirement,
        (
            SequencePresenceRequirement,
            SequenceLengthRequirement,
            SequenceIdentityRequirement,
        ),
    ):
        return tuple(
            binding
            for binding in resource_bindings
            if binding.local_sequence_name == requirement.sequence_name
        )
    if isinstance(requirement, SequenceOrderRequirement):
        names = set(requirement.sequence_names)
        return tuple(
            binding for binding in resource_bindings if binding.local_sequence_name in names
        )
    if isinstance(requirement, ReferenceBaseRequirement):
        return ()
    assert_never(requirement)


def _ordered_contracts(
    request: EvaluationRequest,
    contracts: tuple[ResourceContract, ...],
) -> tuple[ResourceContract, ...]:
    resource_ids = tuple(contract.resource_id for contract in contracts)
    if len(set(resource_ids)) != len(resource_ids):
        raise ValueError("bundle contracts must have unique resource IDs")
    if set(resource_ids) != set(request.scope.resource_ids):
        raise ValueError("bundle reasoning requires exactly one contract per scoped resource")

    by_id = {contract.resource_id: contract for contract in contracts}
    return tuple(by_id[resource_id] for resource_id in request.scope.resource_ids)


def _anchor_candidates(
    context: ReferenceContext,
    requirement: Requirement,
    bindings: tuple[SequenceBinding, ...],
) -> tuple[Capability, ...]:
    target_name = _target_anchor_name(requirement, bindings)
    candidates: list[Capability] = []
    for capability in context.anchor_capabilities:
        if not capability_is_comparable(requirement, capability):
            continue
        if isinstance(requirement, SequencePresenceRequirement):
            if not isinstance(capability, SequencePresenceCapability):
                continue
            if capability.sequence_name != target_name:
                continue
        elif isinstance(requirement, SequenceLengthRequirement):
            if not isinstance(capability, SequenceLengthCapability):
                continue
            if capability.sequence_name != target_name:
                continue
        elif isinstance(requirement, SequenceIdentityRequirement):
            if not isinstance(capability, SequenceIdentityCapability):
                continue
            if capability.sequence_name != target_name:
                continue
        elif isinstance(requirement, SequenceOrderRequirement):
            projected_names = _target_anchor_order(requirement, bindings)
            scoped_names = {sequence.local_name for sequence in context.sequences}
            if any(name not in scoped_names for name in projected_names):
                continue
        elif isinstance(requirement, ReferenceBaseRequirement):
            continue
        else:
            assert_never(requirement)
        candidates.append(capability)
    return tuple(candidates)


def _target_anchor_order(
    requirement: SequenceOrderRequirement,
    bindings: tuple[SequenceBinding, ...],
) -> tuple[str, ...]:
    by_local_name = {binding.local_sequence_name: binding for binding in bindings}
    return tuple(
        by_local_name[name].anchor_sequence_name if name in by_local_name else name
        for name in requirement.sequence_names
    )


def _target_anchor_name(
    requirement: Requirement,
    bindings: tuple[SequenceBinding, ...],
) -> str | None:
    if isinstance(requirement, (SequenceOrderRequirement, ReferenceBaseRequirement)):
        return None
    if isinstance(
        requirement,
        (
            SequencePresenceRequirement,
            SequenceLengthRequirement,
            SequenceIdentityRequirement,
        ),
    ):
        local_name = requirement.sequence_name
    else:
        assert_never(requirement)

    binding = next(
        (item for item in bindings if item.local_sequence_name == local_name),
        None,
    )
    return binding.anchor_sequence_name if binding is not None else local_name


def _make_constraint_id(
    anchor_resource_id: ResourceId,
    requirement: Requirement,
    candidates: tuple[Capability, ...],
    bindings: tuple[SequenceBinding, ...],
) -> ConstraintId:
    payload = json.dumps(
        [
            str(anchor_resource_id),
            str(requirement.id),
            [str(capability.id) for capability in candidates],
            [str(binding.id) for binding in bindings],
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ConstraintId(f"constraint:{hashlib.sha256(payload).hexdigest()}")
