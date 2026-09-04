"""Stable CI/workflow exit policy for whole-bundle compatibility reports.

The policy is intentionally separate from the provisional Milestone 1 CLI
commands. It maps one already-validated ``CompatibilityReport`` to a stable
process-status category without changing or reinterpreting the scientific
verdict.
"""

from __future__ import annotations

from enum import IntEnum

from refcompat._compat import assert_never
from refcompat.model.report import AnalysisStatus, CompatibilityReport
from refcompat.model.verdict import CompatibilityVerdict


class WorkflowExitCode(IntEnum):
    """Stable process exit codes for whole-bundle RefCompat workflows.

    ``SUCCESS`` groups ``COMPATIBLE`` and ``COMPATIBLE_WITH_CONDITIONS`` only
    for process status. Callers that require unconditional compatibility must
    still inspect the report verdict and conditions.

    ``OPERATIONAL_FAILURE`` is reserved for a command/adapter/runtime failure
    that prevents construction of a ``CompatibilityReport`` at all, so no
    report instance maps to that value.
    """

    SUCCESS = 0
    INCOMPATIBLE = 1
    INVALID_INPUT = 2
    INDETERMINATE = 3
    PARTIAL = 4
    OPERATIONAL_FAILURE = 5


def workflow_exit_code(report: CompatibilityReport) -> WorkflowExitCode:
    """Return the stable workflow exit code for one validated report."""

    status = report.analysis_status
    if status is AnalysisStatus.INVALID_INPUT:
        return WorkflowExitCode.INVALID_INPUT
    if status is AnalysisStatus.PARTIAL:
        return WorkflowExitCode.PARTIAL
    if status is AnalysisStatus.COMPLETE:
        assert report.verdict is not None
        verdict = report.verdict.verdict
        if verdict in (
            CompatibilityVerdict.COMPATIBLE,
            CompatibilityVerdict.COMPATIBLE_WITH_CONDITIONS,
        ):
            return WorkflowExitCode.SUCCESS
        if verdict is CompatibilityVerdict.INCOMPATIBLE:
            return WorkflowExitCode.INCOMPATIBLE
        if verdict is CompatibilityVerdict.INDETERMINATE:
            return WorkflowExitCode.INDETERMINATE
        assert_never(verdict)
    assert_never(status)
