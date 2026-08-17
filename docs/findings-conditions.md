# Milestone 2 structured findings and conditions

**Status:** implemented as the third Milestone 2 reasoning slice. The following anchor-driven `ReferenceContext`/`SequenceBinding` and whole-bundle orchestration slice is also implemented; top-level verdict aggregation, conflict-core reporting, and stable `CompatibilityReport` serialization remain later work.

This layer interprets already-evaluated constraints and qualitative evidence as
structured findings, and records explicit request scope as structured
conditions. It does **not** assign a bundle compatibility verdict.

## Findings

`CompatibilityFinding` is an immutable interpreted issue or unresolved question
that traces back to constraint, requirement, evidence, and resource IDs.

The current interpreter emits findings only for non-satisfied applicable
constraints:

- explicit negative sequence presence -> `MISSING_REQUIRED_SEQUENCE`;
- exact length contradiction -> `SEQUENCE_LENGTH_CONFLICT`;
- same-scheme content-identity contradiction -> `SEQUENCE_IDENTITY_CONFLICT`;
- exact sequence-order contradiction -> `SEQUENCE_ORDER_CONFLICT`;
- missing or internally conflicting evidence -> `UNRESOLVED_REQUIREMENT`.

Satisfied constraints remain represented by their `ConstraintEvaluation` and
supporting evidence. This slice deliberately does not manufacture a generic
"success finding" for every satisfied question, and it does not yet emit
higher-order findings such as `VERIFIED_NAMING_ONLY_DIFFERENCE`,
`REFERENCE_DISTRIBUTION_SUPERSET`, or
`NO_REFERENCE_INCOMPATIBILITY_DEMONSTRATED`.

An advisory requirement may still produce a finding. Requirement level is
preserved on the underlying requirement and is interpreted only by the later
bundle-verdict policy; the finding layer does not silently discard advisory
conflicts.

## Finding traceability

Current findings carry:

- opaque deterministic `FindingId`;
- structured `FindingKind`;
- source constraint IDs;
- source requirement IDs;
- evidence IDs;
- involved resource IDs.

Conflict findings require at least one evidence item. An unresolved finding may
have no evidence at all when the unresolved state comes from an evidence gap,
or may carry multiple supporting/contradicting evidence IDs when candidate
facts conflict.

For cross-resource constraints, the requirement's resource is listed first,
followed by evaluator-relevant capability resources in stable candidate order.
The list is traceability, not a claim that the resources are equivalent.

## Conditions

`CompatibilityCondition` currently records only **explicit scope boundaries**
from `EvaluationRequest`. Each condition carries the selected FASTA anchor ID so
its anchor-sequence namespace remains unambiguous outside the request object:

- `EXPLICIT_RESOURCE_SCOPE` when the caller supplied resources but intentionally
  evaluated only a proper subset;
- `EXPLICIT_ANCHOR_SEQUENCE_SCOPE` when the caller explicitly selected a subset
  of names in the FASTA anchor namespace.

A condition does **not** say compatibility has already been established inside
that scope. It says that any later positive compatibility claim must remain
bounded by the scope the caller explicitly chose.

The interpreter never guesses that ALT, decoy, patch, mitochondrial, unplaced, or any other sequence class is irrelevant. Sequence-name projection is performed only by the later evidence-backed `SequenceBinding` layer; the interpretation layer itself does not infer aliases or compare unrelated local namespaces.

Constraints and capability resources accepted by this interpretation layer must
belong to the explicit request resource scope. This prevents a scoped result
from quietly consuming evidence from an excluded resource.

## Determinism and IDs

Finding and condition IDs are deterministic opaque SHA-256-based identifiers
derived from the structured references that define the interpretation. They are
identity aids, not scientific scores. Consumers must not parse policy or
biological meaning from their string representation.

The interpreter preserves constraint order for findings and emits scope
conditions in deterministic order: resource-scope condition first, then
anchor-sequence-scope condition.

## Deliberately not implemented yet

This slice does not implement:

- provenance claims or claim assessments;
- higher-order multi-constraint scientific findings;
- mandatory/advisory verdict aggregation;
- `COMPATIBLE`, `COMPATIBLE_WITH_CONDITIONS`, `INCOMPATIBLE`, or
  `INDETERMINATE`;
- conflict-core extraction;
- stable `CompatibilityReport` serialization.

Those later layers consume these findings/conditions rather than being hidden
inside this interpretation step.
