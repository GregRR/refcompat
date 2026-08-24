# Milestone 2 typed reasoning foundation

**Status:** implemented as the first Milestone 2 reasoning slice. The later evidence, findings/conditions, FASTA-anchored bundle, categorical verdict, and conflict-core slices are also implemented.

This slice introduces the typed question/evaluation boundary used by later
bundle reasoning. It deliberately does not emit a whole-bundle compatibility
verdict.

## Evaluation request and scope

`EvaluationRequest` records the supplied resources, the explicitly selected
FASTA anchor used by the v0.1 reasoner, an `EvaluationScope`, and optional
profile/policy identifiers.

`EvaluationScope` always names the resources in scope and may optionally narrow
the evaluation to an explicit tuple of FASTA-anchor local sequence names. `None` means the
caller has not narrowed sequence scope. RefCompat does not infer exclusions for
ALT, decoy, patch, mitochondrial, unplaced, or other sequence classes merely
because their names are familiar.

The v0.1 request model requires the anchor to be a supplied FASTA and to remain
inside the selected resource scope. Reference-free inspection remains a later
mode and is not represented by weakening the anchor-driven request invariant.

## Typed requirements and capabilities

The current `ResourceContract` vocabulary supports five sequence/reference-oriented
scientific dimensions:

- sequence presence;
- exact sequence length;
- content identity (`RefgetSequenceId` or SAM-style `Md5Digest`);
- exact local sequence order;
- exhaustive resource-level reference-base consistency (`ReferenceBaseRequirement` /
  `ReferenceBaseValidationCapability`, added by Milestone 3).

Requirements additionally record:

- `RequirementOrigin`: `CORE_FORMAT`, `PROFILE`, or `USER_POLICY`;
- `RequirementLevel`: `MANDATORY` or `ADVISORY`.

Those fields do not decide a verdict in this slice. They are retained so the
later aggregator can distinguish a contradicted mandatory requirement from an
advisory one without changing the underlying constraint evaluation.

Capabilities remain typed as well. RefCompat never compares a length
requirement to a presence capability just because both happen to contain
primitive values.

Requirements and capabilities intentionally need not belong to the same
resource. A requirement's `resource_id` identifies the resource whose needs
are being evaluated, while a capability's `resource_id` identifies the
resource that exposed the candidate fact. A common constraint therefore asks
whether a requirement from a consumer resource can be satisfied by a
capability from the selected reference anchor. `ResourceContract` remains
strictly per-resource; later binding/orchestration code may select requirements
from one contract and candidate capabilities from another without treating
resource-ID equality as a comparability rule.

### Explicit negative presence

A missing capability is an evidence gap, not proof of absence.

`SequencePresenceCapability(present=False)` is therefore an explicit negative
fact that may be produced only when the evaluation context can actually prove
absence—for example, from a complete authoritative FASTA snapshot. If no
presence capability exists for the required name, the first evaluator returns
`UNRESOLVED`, not `UNSATISFIED`.

This preserves the project-wide rule that absence of evidence is not
incompatibility and gives later sparse VCF/GTF/BAM contracts a conservative
representation.

## Constraints and evaluations

`CompatibilityConstraint` is the immutable question. `ConstraintEvaluation`
is the separate answer.

Initial states are:

- `SATISFIED`;
- `UNSATISFIED`;
- `UNRESOLVED`;
- `NOT_APPLICABLE`.

A satisfied result records a separate `SatisfactionMode`; the state itself does
not proliferate into values such as `SATISFIED_BY_ALIAS`.

The original evaluator supports exact typed sequence comparisons for:

- exact named presence;
- exact length for the same local name;
- exact identity value for the same local name and identity scheme;
- exact sequence order.

Milestone 3 extends the same typed evaluator with exhaustive resource-level
`ReferenceBaseRequirement` evaluation. The requirement names its expected anchor resource, and only a direct validation capability owned by that anchor is comparable. A direct validation capability with any
proven mismatch is `UNSATISFIED`; otherwise unresolved direct comparisons are
`UNRESOLVED`, a non-empty all-match validation is `SATISFIED` with
`EXHAUSTIVE_DIRECT`, and an empty record set is `NOT_APPLICABLE`. This extension
still performs no scoring, voting, or format-specific mismatch-pattern policy.

MD5 and refget identifiers are not cross-compared. A matching MD5 capability
does not satisfy a refget requirement, or vice versa, merely because both are
content identities.

Cross-name identity/verified alias reasoning is implemented only through the later `SequenceBinding` layer documented in `reference-context-bundle.md`. The base evaluator still manufactures no alias from string similarity; a same-content capability under another local name is usable only when an explicit verified binding is attached to the constraint.

If comparable candidate capabilities conflict with each other, the evaluator
returns `UNRESOLVED` rather than choosing one or averaging them.

## Deliberately not implemented yet

This typed-constraint slice itself does **not** introduce findings or bundle
interpretation. The following generalized evidence layer is documented in
`evidence-aggregation.md` and provides evidence items/IDs plus qualitative
aggregation. The next interpretation slice, documented in
`findings-conditions.md`, provides structured conflict/unresolved findings and
explicit-scope conditions. This exact evaluator still does not own:

- provenance claim assessment;
- top-level bundle verdict aggregation;
- conflict-core reporting;
- stable `CompatibilityReport` serialization.

The verdict and conflict-core layers are now implemented in later Milestone 2 slices; provenance claim assessment and stable report serialization remain later boundaries. None of them is hidden inside this exact evaluator.
