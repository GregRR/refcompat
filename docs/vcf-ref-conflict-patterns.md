# VCF REF conflict-pattern interpretation

Milestone 3 now adds a VCF-specific descriptive interpretation over the already
exhaustive direct `VcfRefValidationResult`. This layer explains how proven REF
mismatches are distributed without changing the generic hard-conflict rule or
introducing a mismatch-rate threshold.

## Boundary

`classify_vcf_ref_conflicts()` consumes only the RefCompat-owned exhaustive
validation result. It does not read VCF/FASTA files, infer aliases, inspect
metadata, alter generic constraint truth, or assign a new bundle verdict.

The resulting `VcfRefConflictPatternSummary` is attached to
`VcfContractProjection` because it is VCF-specific interpretation. Generic
`BundleReasoningResult` remains format-neutral and continues to consume only
the already-reviewed reference-base constraint/evidence result.

## Threshold-free pattern rules

RefCompat deliberately avoids a percentage threshold such as “more than 5%
mismatches means systematic.” Mismatch rate is useful descriptive context, but
there is no universally correct cutoff and any proven mismatch remains a hard
local contradiction regardless of rate.

For a **complete** direct REF validation:

- `NONE` — no proven REF mismatch;
- `ISOLATED` — exactly one proven REF mismatch;
- `LOCALIZED` — multiple proven mismatches, but they are confined to one
  sequence or to a strict subset of the directly compared sequence scope;
- `DISTRIBUTED` — multiple proven mismatches affect every sequence in a
  directly compared multi-sequence scope, but at least one record still
  matches;
- `SYSTEMATIC` — every directly comparable record mismatches across a
  multi-sequence scope.

`SYSTEMATIC` is deliberately a strong, threshold-free claim of exhaustive
observed disagreement. RefCompat does not choose an arbitrary mismatch-rate
cutoff and does not infer a particular cause such as wrong assembly, strand
handling, normalization, or pipeline corruption. `DISTRIBUTED` preserves the
important distinction between broad cross-sequence conflict and complete
disagreement. The summary retains the total directly compared count, mismatch
count, compared sequence names, and affected sequence names so later reporting
can present the actual scale beside the categorical distribution.

A single-sequence VCF with multiple mismatches is `LOCALIZED`: a
cross-sequence systematic distribution cannot be established from a
single-sequence scope.

## Incomplete direct comparison

If any record is `UNRESOLVED_SEQUENCE` or `OUT_OF_BOUNDS`, the pattern is
`UNCLASSIFIED`. RefCompat does not call the observed mismatch set isolated,
localized, distributed, or systematic when part of the direct-comparison
scope is unknown.

This does **not** weaken proven contradictions. For example, one confirmed REF
mismatch plus one unresolved sequence still leaves the generic reference-base
constraint `UNSATISFIED` and the bundle can remain `INCOMPATIBLE`; only the
VCF-specific distribution label is withheld.

`UNCLASSIFIED` is not the `INDETERMINATE` bundle verdict. It describes only the
completeness of this VCF-specific pattern interpretation.

## Determinism and traceability

Pattern summaries preserve the VCF and FASTA resource IDs and the validation
record/mismatch/unresolved counts. The summary-level `unresolved_count` combines
`OUT_OF_BOUNDS` and `UNRESOLVED_SEQUENCE`; their distinct causes remain in the
original `VcfRefValidationResult`. Compared and affected sequence names are
stored as sorted unique tuples, so classification is independent of incidental
`sequence_summaries` ordering.

`VcfContractProjection` cross-checks the pattern summary against its underlying
`VcfRefValidationResult`, preventing a pattern derived from another VCF/FASTA
pair or different aggregate counts from being silently attached.

## Still deferred

This slice does not yet:

- infer a cause from an isolated/localized/distributed/systematic pattern;
- turn the pattern into a new generic compatibility finding or verdict rule;
- reinterpret VCF telomere-sentinel `OUT_OF_BOUNDS` cases;
- add stable report serialization or CLI presentation; or
- rewrite REF/ALT data.
