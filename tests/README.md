
# RefCompat test strategy

Executable test/tooling configuration is defined in `pyproject.toml` and GitHub Actions. This document records the test structure the implementation should grow into.

## Test layers

### Unit tests

Small deterministic tests for domain invariants, parser behavior, identity adapters, requirement/capability construction, and reasoning rules.

### Integration tests

Cross-format checks that exercise a realistic small bundle through inspection, evidence, reasoning, and reporting.

### Known-answer standards tests

Pin representative GA4GH refget/SeqCol identity/comparison outcomes to published compliance/specification fixtures where redistribution permits.

The FASTA/`.fai` integration fixture also pins the canonical HTSlib `faidx(5)` example geometry and independently checks that `refget.compute_fai` produces the same five-column values. The FASTA/`.dict` integration fixture reuses the independently pinned GA4GH/refget per-sequence M5 values to verify exact SAM dictionary content evidence without recomputing the expected checksums inside the dictionary evaluator. Milestone 1 CLI integration tests then exercise those same known-answer resources through human and JSON diagnostic output without introducing a top-level compatibility verdict.

### Corpus-derived fixtures

Use small synthetic or clearly redistributable fixtures derived from the failure *patterns* in the 200-case corpus. Do not copy arbitrary users' genomic datasets into the repository.

`fixtures/milestone1/` closes the first milestone with deterministic controls for same-name/different-sequence identity, alias-only dictionaries, order differences, and `.fai`/`.dict` artifacts that are stale by construction. Tests distinguish that construction history from the narrower structural/content evidence the checkers are justified in reporting.

Milestone 2 unit tests exercise request/scope invariants, typed requirement/capability contracts, constraint/evaluation separation, exact and verified-binding sequence presence/length/identity/order rules, explicit negative presence, conservative `UNRESOLVED` behavior, source-observation and sequence-binding traceability, deterministic qualitative evidence IDs, aggregation that preserves Tier-A contradictions without numeric voting, structured conflict/unresolved findings, explicit scope conditions, FASTA reference-context construction, ambiguous-binding rejection, anchor-driven whole-bundle orchestration that prevents peer resources from voting on reference identity, and categorical mandatory-constraint verdict aggregation with advisory isolation and explicit-condition handling., plus compact conflict-core extraction that excludes satisfied/advisory material, preserves separate independent failures, and represents evidence-free unresolved mandatory relationships without fabricating evidence.

Later regression hardening: add an explicit out-of-scope `SequenceIdentityRequirement` test parallel to the existing presence, length, and order scope tests so identity scope behavior remains pinned to `UNRESOLVED`.

### Negative controls

Include cases where reference compatibility passes but the motivating workflow symptom has another cause. RefCompat must not invent a reference diagnosis merely because a workflow failed.

## Required early fixture families

See [`../docs/check-specifications.md`](../docs/check-specifications.md) for the current 30-case minimum fixture matrix.

## Safety properties worth testing directly

- hard content conflicts never become `COMPATIBLE` through weak evidence aggregation;
- metadata never becomes `VERIFIED` without appropriate evidence;
- unresolved aliases remain unresolved;
- conditions require explicit scope;
- derived artifacts require exact source correspondence rather than biological alias equivalence;
- local identity inspection performs no network access;
- non-human/custom references do not depend on a human assembly registry;
- negative controls do not produce speculative reference findings.

- Milestone 3 VCF/VCF.gz observation tests cover header claims, contig metadata, CHROM usage, bgzip input, sparse declarations, provider-boundary failures, and explicit BCF deferral.
- Milestone 3 REF-validation tests cover source-resource cross-wiring guards, exhaustive record order, one-based POS conversion, multi-base REF spans, hard local mismatches beside many matches, unresolved exact-name cases, bounds/telomere outcomes, VCF IUPAC reduction, per-sequence aggregation, BGZF streaming without a variant index, and FASTA random access through a temporary recomputed FAI rather than an adjacent user index.
- Milestone 3 VCF contract-projection tests cover actual-CHROM presence requirements, scalable aggregate reference-base requirements, explicit FASTA-anchor scoping for pair-derived capabilities, Tier-A mismatch precedence without averaging, unresolved/bounds-only behavior, empty VCFs, order-independent sequence-coverage cross-checks, input cross-wiring, and deterministic IDs.
- Milestone 3 supplemental bundle-orchestration tests cover anchor ownership, scoped subjects, unused/duplicate/competing capability rejection, unchanged categorical verdict behavior, and decisive conflict-core traceability.
- Milestone 3 VCF REF pattern tests cover threshold-free isolated/localized/distributed/systematic classification, incomplete-pattern conservatism, deterministic affected-sequence summaries, and projection-level traceability without changing generic verdict semantics.
