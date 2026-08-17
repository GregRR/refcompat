# Milestone 2 categorical verdict aggregation

**Status:** implemented as the fifth Milestone 2 reasoning slice. Conflict-core
reporting, analysis status, and stable `CompatibilityReport` serialization
remain later work.

This layer converts the already-established whole-bundle constraint states into
one categorical compatibility verdict. It consumes `BundleReasoningResult`; it
does not inspect files, rebuild constraints, re-evaluate evidence, or assign a
numeric compatibility score.

## Verdicts

`CompatibilityVerdict` contains exactly four values:

- `COMPATIBLE`
- `COMPATIBLE_WITH_CONDITIONS`
- `INCOMPATIBLE`
- `INDETERMINATE`

The aggregation precedence is:

1. any `UNSATISFIED` mandatory constraint -> `INCOMPATIBLE`;
2. otherwise any `UNRESOLVED` mandatory constraint -> `INDETERMINATE`;
3. otherwise no applicable mandatory constraint -> `INDETERMINATE`;
4. otherwise one or more explicit conditions -> `COMPATIBLE_WITH_CONDITIONS`;
5. otherwise -> `COMPATIBLE`.

A hard mandatory contradiction therefore cannot be averaged away by satisfied
or advisory constraints, and an explicit scope condition cannot upgrade an
unresolved result into a positive verdict.

## Mandatory and advisory requirements

Only `RequirementLevel.MANDATORY` constraints determine the categorical
verdict. Advisory constraints remain fully represented in evaluations,
evidence, and findings, but an advisory conflict or evidence gap does not veto
an otherwise established compatible result.

`NOT_APPLICABLE` mandatory constraints are neutral when at least one other
mandatory relationship is actually satisfied. If there are no applicable
mandatory constraints at all -- including a bundle with no mandatory
requirements or one whose mandatory constraints are all `NOT_APPLICABLE` --
RefCompat returns `INDETERMINATE` rather than claiming vacuous compatibility.

## Conditions

Conditions are consumed only after all applicable mandatory constraints are
satisfied. At that point:

- no conditions -> `COMPATIBLE`;
- one or more explicit conditions -> `COMPATIBLE_WITH_CONDITIONS`.

Conditions remain attached to an `INCOMPATIBLE` or `INDETERMINATE` aggregation
for scope traceability, but they do not change verdict precedence.

## Traceability

`VerdictAggregation` retains the complete mandatory-constraint partition:

- satisfied;
- unsatisfied;
- unresolved;
- not applicable.

For `INCOMPATIBLE` and unresolved `INDETERMINATE` results,
`basis_finding_ids` identifies the structured findings that cover the
mandatory constraints decisive for that verdict. The aggregator rejects a
decisive mandatory conflict or unresolved state that lacks a traceable
finding.

This object is not the final `CompatibilityReport`; it is the categorical
policy result that a later report can serialize together with the underlying
request, contracts, constraints, evaluations, evidence, findings, and
conditions.

## Deliberately deferred

This slice does **not** implement:

- conflict-core extraction;
- analysis status (`COMPLETE`, `PARTIAL`, `INVALID_INPUT`);
- stable `CompatibilityReport` serialization;
- CI exit-code policy;
- numeric scoring, weighting, voting, or majority semantics;
- format-specific VCF/BAM/CRAM/GTF verdict policy.
