# Milestone 2 qualitative evidence aggregation

**Status:** implemented as the second Milestone 2 reasoning slice. The following findings/conditions, FASTA-anchored bundle, categorical verdict, and conflict-core slices are also implemented.

This layer turns already-evaluated typed compatibility questions into explicit,
traceable evidence relationships. It does **not** compute a numeric compatibility
score and does **not** decide a whole-bundle verdict.

## Evidence items

`Evidence` is one immutable relationship between a typed requirement and one
capability the constraint evaluator considered relevant.

Each evidence item records:

- an opaque deterministic `EvidenceId`;
- an `EvidenceKind` identifying the scientific dimension;
- an `EvidenceMethod` identifying how the relationship was derived;
- qualitative `EvidenceStrength`;
- `EvidencePolarity` (`SUPPORTS` or `CONTRADICTS`);
- the constraint, requirement, and capability IDs involved;
- source `ObservationId` values already attached to the capability.

The current evidence kinds mirror the typed sequence questions implemented in
the first Milestone 2 slice:

- sequence presence;
- sequence length;
- sequence identity;
- sequence order;
- exhaustive reference-base consistency.

The baseline derivation method is `EXACT_TYPED_CONSTRAINT`. The later
reference-context/bundle slice also uses `VERIFIED_SEQUENCE_BINDING` when an
explicit content-verified binding is required to project a resource-local name
into the FASTA-anchor namespace. Milestone 3 additionally uses
`EXHAUSTIVE_REFERENCE_BASE_VALIDATION` for an anchor-backed complete REF comparison. None of
these methods is a generic rules language.

## Source traceability

Capabilities now carry an optional tuple of `source_observation_ids`.
Contract-producing code should populate those IDs when a capability is derived
from concrete `ResourceObservation` values. Evidence copies that trace forward.

An empty observation tuple is allowed during this transitional layer because the
existing Milestone 1 inspectors have not yet been rewired into generalized
contract producers. Empty does **not** mean that no source observation exists;
it means this capability has not yet been given generalized observation links.

This preserves the intended direction of the later trace:

```text
finding / condition
    -> constraint evaluation
        -> evidence
            -> capability
                -> source observation(s)
                    -> resource + source location
```

Claims and claim assessments are still deferred, so this slice does not pretend
to provide their future provenance branch yet.

## Evidence IDs

Generalized evidence IDs are deterministic and opaque. For evidence derived by
this exact typed evaluator, RefCompat hashes the constraint ID, requirement ID,
capability ID, evidence kind, method, strength, and polarity into a namespaced
identifier.

The hash is an identity mechanism for the derived evidence relationship, not a
scientific score. Consumers must treat the identifier as opaque and must not
parse policy or biological meaning from it.

## Strength and polarity

The current exact sequence evaluator maps evidence conservatively:

- exact same-scheme sequence identity (refget or M5/MD5) -> Tier A;
- sequence presence -> Tier B;
- exact sequence length -> Tier B;
- exact sequence order -> Tier B;
- exhaustive reference-base agreement/contradiction -> Tier A.

A matching candidate supports its requirement. A directly comparable but
nonmatching candidate contradicts it.

Algorithm-incomparable identity capabilities are filtered before they become
evidence. Different local sequence names remain unresolved unless the later
reference-context layer attaches an explicit content-verified `SequenceBinding`;
string resemblance alone never manufactures a comparison or contradiction.

## Aggregation without voting

`EvidenceAggregate` retains the individual evidence items plus the IDs of
constraints that remain `UNRESOLVED` or `NOT_APPLICABLE`.

It exposes useful qualitative projections such as:

- supporting evidence;
- contradicting evidence;
- Tier-A conclusive contradictions.

It intentionally does not:

- add evidence-strength numbers;
- compute a weighted score;
- let counts of Tier-B/C/D support cancel Tier-A contradiction;
- change an unresolved constraint merely because some candidate facts exist;
- assign `COMPATIBLE`, `INCOMPATIBLE`, or any other bundle verdict.

A constraint may remain `UNRESOLVED` while carrying both supporting and
contradicting evidence when its candidate capabilities conflict with one
another. The aggregate preserves that disagreement rather than choosing a
winner.

## Constraint-evaluation traceability

A decisive `SATISFIED` or `UNSATISFIED` evaluation must cite at least one
relevant capability. An unresolved evaluation may cite none, and may cite
multiple candidates when those candidates conflict. A `NOT_APPLICABLE`
evaluation cannot cite candidate capabilities because those capabilities did
not determine an applicable truth value.

The evidence aggregate validates that every supplied constraint has exactly one
matching evaluation and that decisive evaluation states agree with the polarity
of the evidence derived from their cited capabilities.

## Deliberately not implemented yet

This slice does not implement:

- provenance claims or claim assessments;
- mandatory/advisory aggregation policy;
- whole-bundle verdicts;
- conflict-core extraction;
- stable `CompatibilityReport` serialization.

The following reference-context/bundle slice now attaches verified
sequence-binding IDs to evidence when cross-name projection is required.
The later verdict and conflict-core layers now consume this evidence
rather than being smuggled into aggregation itself.
