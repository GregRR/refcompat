"""Explicit deterministic draft JSON projection for compatibility reports.

Milestone 7 serializes report-owned concepts deliberately rather than dumping
Python dataclasses recursively.  The wire shape in this module is still a
*draft*: Slice 4 will review it before the first stable JSON Schema/version is
frozen.
"""

from __future__ import annotations

import json

from refcompat._compat import assert_never
from refcompat.model.bundle import BundleReasoningResult
from refcompat.model.constraints import CompatibilityConstraint, ConstraintEvaluation
from refcompat.model.contracts import (
    Capability,
    CapabilityId,
    CoordinateBoundsRequirement,
    CoordinateBoundsValidationCapability,
    ReferenceBaseRequirement,
    ReferenceBaseValidationCapability,
    Requirement,
    SequenceBindingRequirement,
    SequenceBindingValidationCapability,
    SequenceIdentityAbsenceCapability,
    SequenceIdentityCapability,
    SequenceIdentityRequirement,
    SequenceIdentityValue,
    SequenceLengthCapability,
    SequenceLengthRequirement,
    SequenceOrderCapability,
    SequenceOrderRequirement,
    SequencePresenceCapability,
    SequencePresenceRequirement,
)
from refcompat.model.evaluation import EvaluationRequest, EvaluationScope
from refcompat.model.evidence import Evidence
from refcompat.model.identity import Md5Digest, RefgetSequenceId
from refcompat.model.reference_context import SequenceBinding
from refcompat.model.report import AnalysisIssue, CompatibilityReport
from refcompat.model.resources import ArtifactIdentity, Resource

DRAFT_REPORT_FORMAT = "refcompat.compatibility_report"
DRAFT_REPORT_REVISION = 2


def compatibility_report_draft_payload(report: CompatibilityReport) -> dict[str, object]:
    """Project one validated report root into the provisional M7 JSON shape."""

    scientific_result: dict[str, object] | None = None
    if report.bundle is not None:
        assert report.verdict is not None
        assert report.conflict_cores is not None
        scientific_result = _scientific_result_payload(report.bundle, report)

    return {
        "report_format": {
            "name": DRAFT_REPORT_FORMAT,
            "stability": "draft",
            "revision": DRAFT_REPORT_REVISION,
        },
        "tool_version": report.tool_version,
        "analysis": {
            "status": report.analysis_status.value,
            "issues": [
                _analysis_issue_payload(issue)
                for issue in sorted(report.analysis_issues, key=lambda item: str(item.id))
            ],
        },
        "request": _request_payload(report.request),
        "scientific_result": scientific_result,
    }


def render_compatibility_report_draft_json(report: CompatibilityReport) -> bytes:
    """Render deterministic UTF-8 draft JSON with a trailing newline."""

    payload = compatibility_report_draft_payload(report)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    return (text + "\n").encode("utf-8")


def _analysis_issue_payload(issue: AnalysisIssue) -> dict[str, object]:
    return {
        "id": str(issue.id),
        "kind": issue.kind.value,
        "detail": issue.detail,
        "resource_ids": sorted(str(resource_id) for resource_id in issue.resource_ids),
    }


def _request_payload(request: EvaluationRequest) -> dict[str, object]:
    return {
        "resources": [_resource_payload(resource) for resource in request.resources],
        "anchor_resource_id": str(request.anchor_resource_id),
        "scope": _scope_payload(request.scope),
        "active_profiles": [str(profile_id) for profile_id in request.active_profiles],
        "policy_id": str(request.policy_id) if request.policy_id is not None else None,
    }


def _resource_payload(resource: Resource) -> dict[str, object]:
    return {
        "id": str(resource.id),
        "kind": resource.kind.value,
        "display_name": resource.display_name,
        "artifact": _artifact_payload(resource.artifact),
    }


def _artifact_payload(artifact: ArtifactIdentity) -> dict[str, object]:
    digest: dict[str, object] | None = None
    if artifact.digest is not None:
        digest = {
            "algorithm": artifact.digest.algorithm.value,
            "value": artifact.digest.value,
        }
    return {
        "byte_size": artifact.byte_size,
        "digest": digest,
    }


def _scope_payload(scope: EvaluationScope) -> dict[str, object]:
    return {
        "resource_ids": [str(resource_id) for resource_id in scope.resource_ids],
        "anchor_sequence_names": (
            list(scope.anchor_sequence_names) if scope.anchor_sequence_names is not None else None
        ),
    }


def _scientific_result_payload(
    bundle: BundleReasoningResult,
    report: CompatibilityReport,
) -> dict[str, object]:
    assert report.verdict is not None
    assert report.conflict_cores is not None

    requirements = sorted(
        (constraint.requirement for constraint in bundle.constraints),
        key=lambda item: str(item.id),
    )
    capability_index = _capability_index(bundle)
    included_capability_ids = _trace_capability_ids(bundle)
    capabilities = [
        _capability_payload(capability_index[capability_id])
        for capability_id in sorted(included_capability_ids, key=str)
    ]

    return {
        "verdict": {
            "value": report.verdict.verdict.value,
            "mandatory_constraint_ids": [
                str(value) for value in sorted(report.verdict.mandatory_constraint_ids, key=str)
            ],
            "constraint_states": {
                "satisfied": [
                    str(value)
                    for value in sorted(report.verdict.satisfied_mandatory_constraint_ids, key=str)
                ],
                "unsatisfied": [
                    str(value)
                    for value in sorted(
                        report.verdict.unsatisfied_mandatory_constraint_ids, key=str
                    )
                ],
                "unresolved": [
                    str(value)
                    for value in sorted(report.verdict.unresolved_mandatory_constraint_ids, key=str)
                ],
                "not_applicable": [
                    str(value)
                    for value in sorted(
                        report.verdict.not_applicable_mandatory_constraint_ids, key=str
                    )
                ],
            },
            "condition_ids": sorted(str(value) for value in report.verdict.condition_ids),
            "basis_finding_ids": sorted(str(value) for value in report.verdict.basis_finding_ids),
        },
        "requirements": [_requirement_payload(item) for item in requirements],
        "capabilities": capabilities,
        "sequence_bindings": [
            _sequence_binding_payload(binding)
            for binding in sorted(bundle.sequence_bindings, key=lambda item: str(item.id))
        ],
        "constraints": [
            _constraint_payload(constraint)
            for constraint in sorted(bundle.constraints, key=lambda item: str(item.id))
        ],
        "evaluations": [
            _evaluation_payload(evaluation)
            for evaluation in sorted(bundle.evaluations, key=lambda item: str(item.constraint_id))
        ],
        "evidence": {
            "items": [
                _evidence_payload(item)
                for item in sorted(bundle.evidence.evidence, key=lambda item: str(item.id))
            ],
            "unresolved_constraint_ids": sorted(
                str(value) for value in bundle.evidence.unresolved_constraint_ids
            ),
            "not_applicable_constraint_ids": sorted(
                str(value) for value in bundle.evidence.not_applicable_constraint_ids
            ),
        },
        "findings": [
            {
                "id": str(item.id),
                "kind": item.kind.value,
                "constraint_ids": sorted(str(value) for value in item.constraint_ids),
                "requirement_ids": sorted(str(value) for value in item.requirement_ids),
                "evidence_ids": sorted(str(value) for value in item.evidence_ids),
                "resource_ids": sorted(str(value) for value in item.resource_ids),
            }
            for item in sorted(bundle.interpretation.findings, key=lambda item: str(item.id))
        ],
        "conditions": [
            {
                "id": str(item.id),
                "kind": item.kind.value,
                "scope": _scope_payload(item.scope),
                "anchor_resource_id": str(item.anchor_resource_id),
                "constraint_ids": sorted(str(value) for value in item.constraint_ids),
                "excluded_resource_ids": sorted(str(value) for value in item.excluded_resource_ids),
            }
            for item in sorted(bundle.interpretation.conditions, key=lambda item: str(item.id))
        ],
        "conflict_cores": [
            {
                "id": str(core.id),
                "kind": core.kind.value,
                "constraint_ids": sorted(str(value) for value in core.constraint_ids),
                "requirement_ids": sorted(str(value) for value in core.requirement_ids),
                "finding_ids": sorted(str(value) for value in core.finding_ids),
                "evidence_ids": sorted(str(value) for value in core.evidence_ids),
                "resource_ids": sorted(str(value) for value in core.resource_ids),
            }
            for core in sorted(report.conflict_cores.cores, key=lambda item: str(item.id))
        ],
    }


def _trace_capability_ids(bundle: BundleReasoningResult) -> set[CapabilityId]:
    required: set[CapabilityId] = set()
    for constraint in bundle.constraints:
        required.update(capability.id for capability in constraint.candidate_capabilities)
    for evaluation in bundle.evaluations:
        required.update(evaluation.relevant_capability_ids)
    for evidence in bundle.evidence.evidence:
        required.add(evidence.capability_id)
    for binding in bundle.sequence_bindings:
        required.update(binding.capability_ids)

    index = _capability_index(bundle)
    pending = list(required)
    while pending:
        capability_id = pending.pop()
        capability = index.get(capability_id)
        if capability is None:
            raise ValueError(f"report trace references unknown capability ID: {capability_id}")
        if isinstance(capability, SequenceIdentityAbsenceCapability):
            for source_id in capability.source_identity_capability_ids:
                if source_id not in required:
                    required.add(source_id)
                    pending.append(source_id)
    return required


def _capability_index(bundle: BundleReasoningResult) -> dict[CapabilityId, Capability]:
    capabilities: list[Capability] = []
    for contract in bundle.contracts:
        capabilities.extend(contract.capabilities)
    capabilities.extend(bundle.reference_context.anchor_capabilities)
    capabilities.extend(bundle.derived_capabilities)
    capabilities.extend(bundle.supplemental_capabilities)

    by_id: dict[CapabilityId, Capability] = {}
    for capability in capabilities:
        existing = by_id.get(capability.id)
        if existing is not None and existing != capability:
            raise ValueError(f"report capability ID is cross-wired: {capability.id}")
        by_id[capability.id] = capability
    return by_id


def _requirement_payload(requirement: Requirement) -> dict[str, object]:
    base: dict[str, object] = {
        "id": str(requirement.id),
        "resource_id": str(requirement.resource_id),
        "origin": requirement.origin.value,
        "level": requirement.level.value,
    }
    if isinstance(requirement, SequencePresenceRequirement):
        return {**base, "type": "sequence_presence", "sequence_name": requirement.sequence_name}
    if isinstance(requirement, SequenceLengthRequirement):
        return {
            **base,
            "type": "sequence_length",
            "sequence_name": requirement.sequence_name,
            "length": requirement.length,
        }
    if isinstance(requirement, SequenceIdentityRequirement):
        return {
            **base,
            "type": "sequence_identity",
            "sequence_name": requirement.sequence_name,
            "identity": _identity_payload(requirement.identity),
        }
    if isinstance(requirement, SequenceBindingRequirement):
        return {
            **base,
            "type": "sequence_binding",
            "anchor_resource_id": str(requirement.anchor_resource_id),
            "sequence_name": requirement.sequence_name,
        }
    if isinstance(requirement, SequenceOrderRequirement):
        return {
            **base,
            "type": "sequence_order",
            "sequence_names": list(requirement.sequence_names),
        }
    if isinstance(requirement, CoordinateBoundsRequirement):
        return {
            **base,
            "type": "coordinate_bounds",
            "anchor_resource_id": str(requirement.anchor_resource_id),
            "coordinate_count": requirement.coordinate_count,
        }
    if isinstance(requirement, ReferenceBaseRequirement):
        return {
            **base,
            "type": "reference_bases",
            "anchor_resource_id": str(requirement.anchor_resource_id),
            "record_count": requirement.record_count,
        }
    assert_never(requirement)


def _capability_payload(capability: Capability) -> dict[str, object]:
    base: dict[str, object] = {
        "id": str(capability.id),
        "resource_id": str(capability.resource_id),
        "source_observation_ids": sorted(str(value) for value in capability.source_observation_ids),
    }
    if isinstance(capability, SequencePresenceCapability):
        return {
            **base,
            "type": "sequence_presence",
            "sequence_name": capability.sequence_name,
            "present": capability.present,
        }
    if isinstance(capability, SequenceLengthCapability):
        return {
            **base,
            "type": "sequence_length",
            "sequence_name": capability.sequence_name,
            "length": capability.length,
        }
    if isinstance(capability, SequenceIdentityCapability):
        return {
            **base,
            "type": "sequence_identity",
            "sequence_name": capability.sequence_name,
            "identity": _identity_payload(capability.identity),
            "provenance": capability.provenance.value,
        }
    if isinstance(capability, SequenceIdentityAbsenceCapability):
        return {
            **base,
            "type": "sequence_identity_absence",
            "subject_resource_id": str(capability.subject_resource_id),
            "sequence_name": capability.sequence_name,
            "identity_values": [
                _identity_payload(value)
                for value in sorted(capability.identity_values, key=_identity_sort_key)
            ],
            "source_identity_capability_ids": [
                str(value) for value in sorted(capability.source_identity_capability_ids, key=str)
            ],
        }
    if isinstance(capability, SequenceBindingValidationCapability):
        return {
            **base,
            "type": "sequence_binding_validation",
            "subject_resource_id": str(capability.subject_resource_id),
            "sequence_name": capability.sequence_name,
            "state": capability.state.value,
            "anchor_sequence_name": capability.anchor_sequence_name,
        }
    if isinstance(capability, SequenceOrderCapability):
        return {
            **base,
            "type": "sequence_order",
            "sequence_names": list(capability.sequence_names),
        }
    if isinstance(capability, CoordinateBoundsValidationCapability):
        return {
            **base,
            "type": "coordinate_bounds_validation",
            "subject_resource_id": str(capability.subject_resource_id),
            "checked_count": capability.checked_count,
            "representable_count": capability.representable_count,
            "conflict_count": capability.conflict_count,
            "unresolved_count": capability.unresolved_count,
        }
    if isinstance(capability, ReferenceBaseValidationCapability):
        return {
            **base,
            "type": "reference_base_validation",
            "subject_resource_id": str(capability.subject_resource_id),
            "checked_count": capability.checked_count,
            "match_count": capability.match_count,
            "mismatch_count": capability.mismatch_count,
            "unresolved_count": capability.unresolved_count,
        }
    assert_never(capability)


def _identity_payload(identity: SequenceIdentityValue) -> dict[str, object]:
    if isinstance(identity, RefgetSequenceId):
        return {"scheme": "refget", "value": identity.value}
    if isinstance(identity, Md5Digest):
        return {"scheme": "md5", "value": identity.value}
    assert_never(identity)


def _identity_sort_key(identity: SequenceIdentityValue) -> tuple[str, str]:
    payload = _identity_payload(identity)
    return str(payload["scheme"]), str(payload["value"])


def _sequence_binding_payload(binding: SequenceBinding) -> dict[str, object]:
    return {
        "id": str(binding.id),
        "resource_id": str(binding.resource_id),
        "local_sequence_name": binding.local_sequence_name,
        "anchor_resource_id": str(binding.anchor_resource_id),
        "anchor_sequence_name": binding.anchor_sequence_name,
        "method": binding.method.value,
        "identity_values": [
            _identity_payload(value)
            for value in sorted(binding.identity_values, key=_identity_sort_key)
        ],
        "capability_ids": sorted(str(value) for value in binding.capability_ids),
    }


def _constraint_payload(constraint: CompatibilityConstraint) -> dict[str, object]:
    return {
        "id": str(constraint.id),
        "requirement_id": str(constraint.requirement.id),
        "rule": constraint.rule.value,
        "candidate_capability_ids": [
            str(capability.id)
            for capability in sorted(
                constraint.candidate_capabilities, key=lambda item: str(item.id)
            )
        ],
        "sequence_binding_ids": sorted(str(binding.id) for binding in constraint.sequence_bindings),
    }


def _evaluation_payload(evaluation: ConstraintEvaluation) -> dict[str, object]:
    return {
        "constraint_id": str(evaluation.constraint_id),
        "requirement_id": str(evaluation.requirement_id),
        "state": evaluation.state.value,
        "satisfaction_mode": (
            evaluation.satisfaction_mode.value if evaluation.satisfaction_mode is not None else None
        ),
        "relevant_capability_ids": sorted(
            str(value) for value in evaluation.relevant_capability_ids
        ),
    }


def _evidence_payload(item: Evidence) -> dict[str, object]:
    return {
        "id": str(item.id),
        "kind": item.kind.value,
        "method": item.method.value,
        "strength": item.strength.value,
        "polarity": item.polarity.value,
        "constraint_id": str(item.constraint_id),
        "requirement_id": str(item.requirement_id),
        "capability_id": str(item.capability_id),
        "source_observation_ids": sorted(str(value) for value in item.source_observation_ids),
        "sequence_binding_ids": sorted(str(value) for value in item.sequence_binding_ids),
    }
