"""Evidence-backed compatibility reasoning."""

from refcompat.reasoning.alignment_binding import (
    alignment_binding_identity_capabilities,
    derive_alignment_sequence_bindings,
)
from refcompat.reasoning.alignment_contract import build_alignment_contract
from refcompat.reasoning.bundle import reason_bundle
from refcompat.reasoning.conflict_core import extract_conflict_cores
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence, derive_constraint_evidence
from refcompat.reasoning.fasta_index import evaluate_fasta_index_integrity
from refcompat.reasoning.interpretation import interpret_constraint_results
from refcompat.reasoning.reference_context import build_reference_context, derive_sequence_bindings
from refcompat.reasoning.sequence_dictionary import evaluate_sequence_dictionary_integrity
from refcompat.reasoning.vcf_binding import (
    derive_vcf_sequence_bindings,
    vcf_binding_identity_capabilities,
)
from refcompat.reasoning.vcf_contract import build_vcf_contract, project_vcf_contract
from refcompat.reasoning.vcf_ref import VcfRefEvaluationError, evaluate_vcf_ref_records
from refcompat.reasoning.vcf_ref_pattern import classify_vcf_ref_conflicts
from refcompat.reasoning.verdict import aggregate_bundle_verdict

__all__ = [
    "VcfRefEvaluationError",
    "aggregate_bundle_verdict",
    "aggregate_constraint_evidence",
    "alignment_binding_identity_capabilities",
    "build_alignment_contract",
    "build_constraint",
    "build_reference_context",
    "build_vcf_contract",
    "classify_vcf_ref_conflicts",
    "derive_alignment_sequence_bindings",
    "derive_constraint_evidence",
    "derive_sequence_bindings",
    "derive_vcf_sequence_bindings",
    "evaluate_constraint",
    "evaluate_fasta_index_integrity",
    "evaluate_sequence_dictionary_integrity",
    "evaluate_vcf_ref_records",
    "extract_conflict_cores",
    "interpret_constraint_results",
    "project_vcf_contract",
    "reason_bundle",
    "vcf_binding_identity_capabilities",
]
