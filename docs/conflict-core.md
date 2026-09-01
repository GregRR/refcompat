# Milestone 2 conflict-core extraction

**Status:** implemented as the sixth and final Milestone 2 reasoning slice.
Milestone 7 Slice 2 now adds analysis status and the immutable `CompatibilityReport` root above this extraction; stable serialization remains pending.

A conflict core is a compact trace of the mandatory relationship that actually
determined a non-positive categorical verdict. It is intentionally not a dump
of every mismatch in the bundle and does not recompute constraint truth,
evidence strength, or verdict policy.

## Current v0.1 shape

`extract_conflict_cores()` consumes an already-validated `BundleReasoningResult`
and its matching `VerdictAggregation`.

For each verdict-basis finding it emits one `ConflictCore` containing only:

- the decisive mandatory constraint ID(s);
- the corresponding requirement ID(s);
- the decisive finding ID;
- evidence IDs directly attached to those decisive constraints;
- the minimum resource IDs implied by the requirement and cited evidence.

Evidence retains capability, observation, and sequence-binding provenance, so
those transitive objects are not duplicated into the core.

## Verdict behavior

- `INCOMPATIBLE` -> contradiction cores for unsatisfied mandatory constraints;
- unresolved `INDETERMINATE` -> unresolved cores for unresolved mandatory
  constraints;
- `INDETERMINATE` with no applicable mandatory basis -> no evidence core;
- `COMPATIBLE` / `COMPATIBLE_WITH_CONDITIONS` -> no conflict cores.

Hard-conflict precedence is preserved: if a bundle contains both a mandatory
contradiction and a mandatory unresolved relationship, only the contradiction
is decisive for the categorical verdict and therefore only contradiction cores
are emitted.

## "Smallest useful" rather than one arbitrary global minimum

The current interpreter emits one finding per non-satisfied applicable
constraint. Conflict-core extraction therefore keeps one compact core per
decisive finding. Multiple independent contradictions remain separate small
cores rather than being merged into an undifferentiated wall of mismatches or
reduced to one arbitrary chosen failure.

If future interpretation introduces findings spanning multiple constraints,
core projection and verdict-basis selection must be tightened together so only
actually decisive constraints/evidence are retained.

Core IDs are content-stable, but the `ConflictCoreExtraction.cores` tuple
currently follows verdict-basis input order. A later reporting layer that needs
stable presentation or snapshot ordering should sort cores by an explicit
canonical key rather than treating tuple position as part of the reasoning API.

## Deliberately excluded

Conflict-core extraction does not implement:

- numeric scoring, weighting, or voting;
- evidence-count minimization;
- stable `CompatibilityReport` serialization;
- workflow/CLI exit policy over the now-implemented analysis-status axis;
- CLI exit-code policy;
- format-specific VCF/BAM/CRAM/GTF reasoning.
