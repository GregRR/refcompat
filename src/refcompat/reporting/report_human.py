"""Deterministic human-readable rendering for ``CompatibilityReport``.

Human output is deliberately a presentation layer over the immutable report.
It summarizes existing report facts and trace identifiers without computing a
new verdict, evidence relationship, or scientific recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timezone

from refcompat.model.alignment_relationship import AlignmentDictionaryRelationshipSummary
from refcompat.model.conflict_core import ConflictCore
from refcompat.model.interpretation import CompatibilityCondition, CompatibilityFinding
from refcompat.model.observations import ResourceObservation, SourceLocation
from refcompat.model.reference_context import SequenceBinding
from refcompat.model.report import AnalysisIssue, CompatibilityReport
from refcompat.model.report_context import ProfileProvenanceContext, ProfileSequenceTrace


def render_compatibility_report_human(report: CompatibilityReport) -> str:
    """Render one compatibility report as deterministic plain text."""

    lines: list[str] = ["RefCompat compatibility report", ""]
    _render_resources(lines, report)
    _render_reference_context(lines, report)
    _render_analysis(lines, report)

    if report.bundle is not None:
        _render_decisive_findings(lines, report)
        _render_conflict_cores(lines, report)
        _render_alignment_relationships(lines, report.alignment_relationships)
        _render_observations(lines, report.observations)
        _render_profile_contexts(lines, report.profile_contexts)
        _render_conditions(lines, report)

    return "\n".join(lines).rstrip() + "\n"


def _render_resources(lines: list[str], report: CompatibilityReport) -> None:
    lines.append("Resources")
    for resource in report.request.resources:
        details = [resource.kind.value]
        if resource.id == report.request.anchor_resource_id:
            details.append("anchor")
        if resource.id not in report.request.scope.resource_ids:
            details.append("outside scope")
        label = resource.display_name if resource.display_name is not None else str(resource.id)
        lines.append(f"- {resource.id}: {label} ({', '.join(details)})")
    lines.append("")


def _render_reference_context(lines: list[str], report: CompatibilityReport) -> None:
    lines.extend(
        [
            "Reference context",
            f"- selected FASTA anchor: {report.request.anchor_resource_id}",
            f"- scoped resources: {_join(report.request.scope.resource_ids)}",
        ]
    )
    if report.request.scope.anchor_sequence_names is None:
        lines.append("- anchor sequence scope: all anchor sequences")
    else:
        lines.append(
            f"- anchor sequence scope: {_join(report.request.scope.anchor_sequence_names)}"
        )
    active_profiles = (
        _join(report.request.active_profiles) if report.request.active_profiles else "none"
    )
    lines.append(f"- active profiles: {active_profiles}")
    lines.append(
        f"- policy: {report.request.policy_id if report.request.policy_id is not None else 'none'}"
    )

    if report.bundle is None:
        lines.append("- verified sequence bindings: unavailable")
    elif not report.bundle.sequence_bindings:
        lines.append("- verified sequence bindings: none")
    else:
        lines.append("- verified sequence bindings:")
        for binding in sorted(report.bundle.sequence_bindings, key=lambda item: str(item.id)):
            lines.append(_binding_line(binding))
    lines.append("")


def _render_analysis(lines: list[str], report: CompatibilityReport) -> None:
    lines.extend(
        [
            "Analysis",
            f"- tool version: {report.tool_version}",
            f"- status: {report.analysis_status.value}",
        ]
    )
    if report.verdict is None:
        lines.append("- compatibility verdict: unavailable")
    else:
        verdict = report.verdict
        lines.extend(
            [
                f"- compatibility verdict: {verdict.verdict.value}",
                "- mandatory constraints: "
                f"satisfied={len(verdict.satisfied_mandatory_constraint_ids)}, "
                f"unsatisfied={len(verdict.unsatisfied_mandatory_constraint_ids)}, "
                f"unresolved={len(verdict.unresolved_mandatory_constraint_ids)}, "
                f"not_applicable={len(verdict.not_applicable_mandatory_constraint_ids)}",
            ]
        )
    if not report.analysis_issues:
        lines.append("- analysis issues: none")
    else:
        lines.append("- analysis issues:")
        for issue in sorted(report.analysis_issues, key=lambda item: str(item.id)):
            lines.append(_analysis_issue_line(issue))
    lines.append("")


def _render_decisive_findings(lines: list[str], report: CompatibilityReport) -> None:
    assert report.bundle is not None
    assert report.verdict is not None
    findings_by_id = {finding.id: finding for finding in report.bundle.interpretation.findings}
    lines.append("Decisive findings")
    if not report.verdict.basis_finding_ids:
        lines.append("- none")
    else:
        for finding_id in sorted(report.verdict.basis_finding_ids, key=str):
            _append_finding(lines, findings_by_id[finding_id])
    lines.append("")


def _render_conflict_cores(lines: list[str], report: CompatibilityReport) -> None:
    assert report.conflict_cores is not None
    lines.append("Decisive conflict cores")
    if not report.conflict_cores.cores:
        lines.append("- none")
    else:
        for core in sorted(report.conflict_cores.cores, key=lambda item: str(item.id)):
            _append_conflict_core(lines, core)
    lines.append("")


def _render_alignment_relationships(
    lines: list[str],
    relationships: tuple[AlignmentDictionaryRelationshipSummary, ...],
) -> None:
    lines.append("Alignment dictionary relationships")
    if not relationships:
        lines.append("- none")
        lines.append("")
        return

    for relationship in relationships:
        lines.append(
            f"- {relationship.alignment_resource_id} -> {relationship.fasta_resource_id}: "
            f"membership={relationship.membership.value}; naming={relationship.naming.value}; "
            f"order={relationship.order.value}; content={relationship.content.value}"
        )
        for resolution in relationship.resolutions:
            binding = (
                f"; binding={resolution.sequence_binding_id}"
                if resolution.sequence_binding_id is not None
                else ""
            )
            lines.append(
                f"  - {resolution.local_sequence_name} -> {resolution.anchor_sequence_name}: "
                f"{resolution.method.value}{binding}"
            )
        _append_named_values(
            lines,
            "  - unresolved sequence names",
            relationship.unresolved_sequence_names,
        )
        _append_named_values(
            lines,
            "  - M5-distinct extra sequence names",
            relationship.m5_distinct_extra_sequence_names,
        )
        _append_named_values(
            lines,
            "  - duplicate anchor target names",
            relationship.duplicate_anchor_target_names,
        )
        _append_named_values(
            lines,
            "  - length-conflict sequence names",
            relationship.length_conflict_sequence_names,
        )
        _append_named_values(
            lines,
            "  - identity-conflict sequence names",
            relationship.identity_conflict_sequence_names,
        )
    lines.append("")


def _render_conditions(lines: list[str], report: CompatibilityReport) -> None:
    assert report.bundle is not None
    lines.append("Conditions")
    if not report.bundle.interpretation.conditions:
        lines.append("- none")
    else:
        for condition in sorted(
            report.bundle.interpretation.conditions,
            key=lambda item: str(item.id),
        ):
            lines.append(_condition_line(condition))
    lines.append("")


def _render_observations(
    lines: list[str],
    observations: tuple[ResourceObservation, ...],
) -> None:
    lines.append("Report observations")
    if not observations:
        lines.append("- none")
    else:
        for observation in sorted(observations, key=lambda item: str(item.id)):
            lines.append(_observation_line(observation))
    lines.append("")


def _render_profile_contexts(
    lines: list[str],
    contexts: tuple[ProfileProvenanceContext, ...],
) -> None:
    lines.append("Profile/provider provenance")
    if not contexts:
        lines.append("- none")
        lines.append("")
        return

    for context in sorted(contexts, key=lambda item: str(item.profile_id)):
        provider_context = (
            str(context.provider_context_id)
            if context.provider_context_id is not None
            else "unavailable"
        )
        lines.append(
            f"- {context.profile_id}: kind={context.kind.value}; provider={context.provider}; "
            f"target={context.target}; context={provider_context}"
        )
        if context.completeness:
            lines.append(
                "  - completeness: "
                + ", ".join(
                    f"{item.dimension.value}={item.state.value}"
                    for item in sorted(context.completeness, key=lambda item: item.dimension.value)
                )
            )
        else:
            lines.append("  - completeness: unavailable")
        if context.sources:
            lines.append("  - provider sources:")
            for source in sorted(context.sources, key=lambda item: str(item.id)):
                lines.append(
                    f"    - {source.id}: {source.locator}; "
                    f"acquired={source.acquired_at.astimezone(timezone.utc).isoformat()}; "
                    f"dimensions={_join(sorted(item.value for item in source.dimensions))}"
                )
        else:
            lines.append("  - provider sources: none")
        if context.sequence_traces:
            lines.append("  - sequence traces:")
            for trace in sorted(context.sequence_traces, key=lambda item: str(item.requirement_id)):
                _append_profile_trace(lines, trace)
        else:
            lines.append("  - sequence traces: none")
    lines.append("")


def _binding_line(binding: SequenceBinding) -> str:
    return (
        f"  - {binding.id}: {binding.resource_id}:{binding.local_sequence_name} -> "
        f"{binding.anchor_resource_id}:{binding.anchor_sequence_name}; "
        f"method={binding.method.value}"
    )


def _analysis_issue_line(issue: AnalysisIssue) -> str:
    resources = _join(issue.resource_ids) if issue.resource_ids else "none"
    return f"  - {issue.id}: {issue.kind.value}; resources={resources}; {issue.detail}"


def _append_finding(lines: list[str], finding: CompatibilityFinding) -> None:
    evidence = _join(finding.evidence_ids) if finding.evidence_ids else "none"
    lines.extend(
        [
            f"- {finding.id}: {finding.kind.value}",
            f"  resources: {_join(finding.resource_ids)}",
            f"  constraints: {_join(finding.constraint_ids)}",
            f"  requirements: {_join(finding.requirement_ids)}",
            f"  evidence: {evidence}",
        ]
    )


def _append_conflict_core(lines: list[str], core: ConflictCore) -> None:
    evidence = _join(core.evidence_ids) if core.evidence_ids else "none"
    lines.extend(
        [
            f"- {core.id}: {core.kind.value}",
            f"  resources: {_join(core.resource_ids)}",
            f"  constraints: {_join(core.constraint_ids)}",
            f"  requirements: {_join(core.requirement_ids)}",
            f"  findings: {_join(core.finding_ids)}",
            f"  evidence: {evidence}",
        ]
    )


def _condition_line(condition: CompatibilityCondition) -> str:
    details = [
        f"kind={condition.kind.value}",
        f"anchor={condition.anchor_resource_id}",
        f"scope_resources={_join(condition.scope.resource_ids)}",
    ]
    if condition.scope.anchor_sequence_names is not None:
        details.append(f"anchor_sequences={_join(condition.scope.anchor_sequence_names)}")
    if condition.excluded_resource_ids:
        details.append(f"excluded_resources={_join(condition.excluded_resource_ids)}")
    return f"- {condition.id}: {'; '.join(details)}"


def _observation_line(observation: ResourceObservation) -> str:
    location = _source_location(observation.source_location)
    suffix = f"; source={location}" if location is not None else ""
    return (
        f"- {observation.id}: resource={observation.resource_id}; kind={observation.kind}; "
        f"value={observation.value!r}{suffix}"
    )


def _source_location(location: SourceLocation | None) -> str | None:
    if location is None:
        return None
    parts: list[str] = []
    if location.line_number is not None:
        parts.append(f"line={location.line_number}")
    if location.record_index is not None:
        parts.append(f"record={location.record_index}")
    if location.field is not None:
        parts.append(f"field={location.field}")
    if location.locator is not None:
        parts.append(f"locator={location.locator}")
    return ", ".join(parts)


def _append_profile_trace(lines: list[str], trace: ProfileSequenceTrace) -> None:
    lines.extend(
        [
            f"    - requirement: {trace.requirement_id}",
            f"      resource/local sequence: {trace.resource_id}:{trace.local_sequence_name}",
            "      name resolution: "
            f"{trace.name_resolution_state.value}/{trace.name_resolution_reason.value}",
        ]
    )
    if trace.name_resolution_method is not None:
        lines.append(f"      name method: {trace.name_resolution_method.value}")
    if trace.provider_target_name is not None:
        lines.append(f"      provider target: {trace.provider_target_name}")
    if trace.target_resolution_state is not None:
        assert trace.target_resolution_reason is not None
        lines.append(
            "      target resolution: "
            f"{trace.target_resolution_state.value}/{trace.target_resolution_reason.value}"
        )
    if trace.target_anchor_sequence_name is not None:
        lines.append(f"      anchor sequence: {trace.target_anchor_sequence_name}")
    if trace.sequence_binding_id is not None:
        lines.append(f"      sequence binding: {trace.sequence_binding_id}")
    if trace.validation_capability_id is not None:
        lines.append(f"      validation capability: {trace.validation_capability_id}")


def _append_named_values(
    lines: list[str],
    label: str,
    values: tuple[str, ...],
) -> None:
    if values:
        lines.append(f"{label}: {_join(values)}")


def _join(values: Iterable[object]) -> str:
    return ", ".join(str(value) for value in values)
