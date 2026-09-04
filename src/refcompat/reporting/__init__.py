"""Human and machine-readable reporting surfaces for RefCompat checks."""

from refcompat.reporting.diagnostics import (
    fasta_index_integrity_payload,
    render_fasta_index_integrity,
    render_json,
    render_sequence_collection_snapshot,
    render_sequence_dictionary_integrity,
    sequence_collection_snapshot_payload,
    sequence_dictionary_integrity_payload,
)
from refcompat.reporting.report_context import project_ucsc_preflight_report_context
from refcompat.reporting.report_json import (
    DRAFT_REPORT_FORMAT,
    DRAFT_REPORT_REVISION,
    REPORT_FORMAT,
    REPORT_SCHEMA_VERSION,
    compatibility_report_draft_payload,
    compatibility_report_payload,
    render_compatibility_report_draft_json,
    render_compatibility_report_json,
)

__all__ = [
    "DRAFT_REPORT_FORMAT",
    "DRAFT_REPORT_REVISION",
    "REPORT_FORMAT",
    "REPORT_SCHEMA_VERSION",
    "compatibility_report_draft_payload",
    "compatibility_report_payload",
    "fasta_index_integrity_payload",
    "project_ucsc_preflight_report_context",
    "render_compatibility_report_draft_json",
    "render_compatibility_report_json",
    "render_fasta_index_integrity",
    "render_json",
    "render_sequence_collection_snapshot",
    "render_sequence_dictionary_integrity",
    "sequence_collection_snapshot_payload",
    "sequence_dictionary_integrity_payload",
]
