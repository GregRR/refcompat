
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
