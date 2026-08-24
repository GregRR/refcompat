"""Evidence-backed compatibility reasoning."""

from refcompat.reasoning.bundle import reason_bundle
from refcompat.reasoning.conflict_core import extract_conflict_cores
from refcompat.reasoning.constraints import build_constraint, evaluate_constraint
from refcompat.reasoning.evidence import aggregate_constraint_evidence, derive_constraint_evidence
from refcompat.reasoning.fasta_index import evaluate_fasta_index_integrity
from refcompat.reasoning.interpretation import interpret_constraint_results
from refcompat.reasoning.reference_context import build_reference_context, derive_sequence_bindings
from refcompat.reasoning.sequence_dictionary import evaluate_sequence_dictionary_integrity
from refcompat.reasoning.vcf_contract import project_vcf_contract
from refcompat.reasoning.vcf_ref import VcfRefEvaluationError, evaluate_vcf_ref_records
from refcompat.reasoning.vcf_ref_pattern import classify_vcf_ref_conflicts
from refcompat.reasoning.verdict import aggregate_bundle_verdict

__all__ = [
    "VcfRefEvaluationError",
    "aggregate_bundle_verdict",
    "aggregate_constraint_evidence",
    "build_constraint",
    "build_reference_context",
    "classify_vcf_ref_conflicts",
    "derive_constraint_evidence",
    "derive_sequence_bindings",
    "evaluate_constraint",
    "evaluate_fasta_index_integrity",
    "evaluate_sequence_dictionary_integrity",
    "evaluate_vcf_ref_records",
    "extract_conflict_cores",
    "interpret_constraint_results",
    "project_vcf_contract",
    "reason_bundle",
]
