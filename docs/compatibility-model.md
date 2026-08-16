
# RefCompat compatibility model

This document expands the formal object model summarized in `DESIGN.md`.

## Layering

```text
EvaluationRequest
    |
    v
Resources
    |
    v
Inspection
    ├── ResourceObservation
    ├── ProvenanceClaim
    ├── ResourceRelationClaim
    ├── SequenceCollectionSnapshot
    └── CoordinateContext
    |
    v
Contract construction
    ├── Capability
    ├── Requirement
    └── ResourceContract
    |
    v
Reasoning
    ├── ReferenceContext
    ├── Evidence
    ├── CompatibilityConstraint
    ├── ConstraintEvaluation
    └── ClaimAssessment
    |
    v
Interpretation
    ├── CompatibilityFinding
    └── CompatibilityCondition
    |
    v
CompatibilityReport
    ├── AnalysisStatus
    └── CompatibilityVerdict
```

Information becomes more interpreted as it moves downward. Lower layers may refer back to evidence from earlier layers; earlier layers must not smuggle later conclusions into observations.

## `Resource`

Represents one supplied artifact or logical input. It should remain thin.

Typical fields:

- stable RefCompat resource ID;
- resource kind;
- artifact location;
- optional byte size;
- optional artifact-level content digest;
- optional display name.

### Invariant: artifact identity is not genomic identity

The cryptographic checksum of the exact bytes of `genome.fa`, a refget sequence identifier, a SeqCol collection digest, and a SAM `M5` value are distinct concepts and must have distinct types/fields.

## `ResourceObservation`

A directly extracted immutable fact.

Examples:

- BAM `@SQ SN=chr1`;
- BAM `@SQ LN=248956422`;
- VCF record `CHROM=1, POS=100, REF=A`;
- GTF maximum end coordinate on seqid `1`;
- FASTA local sequence name and length.

Observations should retain source location where practical: header field, record index, line/feature identifier, or other traceable origin.

Milestone 1 implements a format-neutral `ResourceObservation` with caller-supplied `ObservationId`, typed `ObservationKind`, resource ID, primitive fact value, and optional `SourceLocation` components (`line_number`, `record_index`, `field`, `locator`). Milestone 2 capabilities can now carry source observation IDs forward into generalized evidence; observation-ID generation itself remains producer-specific until concrete inspectors are wired into contract construction.

### Invariant

An observation never says `MATCH`, `WRONG_BUILD`, `COMPATIBLE`, `ALIAS`, or similar interpreted conclusions.

## `ProvenanceClaim`

A statement about identity/origin whose truth is not assumed merely because it is present.

Examples:

- `assembly = GRCh38` from metadata;
- annotation provider/release;
- `##reference` URI;
- collaborator note saying “hg38”.

Claims remain immutable historical statements.

## `ClaimAssessment`

A later evaluation of a claim against evidence.

Candidate states:

- `SUPPORTED`
- `VERIFIED`
- `CONTRADICTED`
- `UNRESOLVED`

`SUPPORTED` is intentionally weaker than `VERIFIED`: matching names/lengths or consistent metadata can support a claim without proving exact sequence identity.

## `ResourceRelationClaim`

Represents claimed relationships among artifacts or references, such as:

- `.dict DERIVED_FROM genome.fa`;
- `sample.bam ALIGNED_TO reference-X`;
- `variants.vcf CALLED_AGAINST reference-X`;
- `genes.gtf ANNOTATES assembly-X`;
- resource `BELONGS_TO_BUNDLE bundle-Y`.

This is important for detecting stale derived artifacts and incoherent bundles.

## `SequenceCollectionSnapshot`

A per-resource description of what sequence-collection information that resource actually exposes.

Typical contents:

- local sequence names;
- lengths;
- order where meaningful;
- refget sequence identities where established;
- legacy content checksums where present;
- SeqCol identity/component digests when a complete collection can be established;
- completeness semantics;
- evidence IDs.

### `CollectionCompleteness`

At minimum the model must distinguish:

- `COMPLETE`
- `DECLARED_COMPLETE`
- `PARTIAL`
- `USED_SUBSET`
- `UNKNOWN`

Absence from a sparse VCF or GTF must never be interpreted as absence from the underlying biological reference unless the format/context supports that conclusion.

## `ReferenceContext`

A reasoner-produced candidate or established reference context for the evaluation. It is not the same as a per-resource snapshot.

For v0.1 the explicitly selected FASTA anchor defines the candidate reference context. Other resources are evaluated against it; resources do not vote on the reference identity.

Candidate status values may include:

- `VERIFIED`
- `PARTIALLY_VERIFIED`
- `OBSERVED`
- `UNRESOLVED`

## `SequenceBinding`

Connects a resource-local sequence label to a sequence identity or other evidence-backed coordinate entity.

For example:

```text
FASTA local name chr1 -> SQ.ABC...
GTF local name 1     -> SQ.ABC...
```

A verified alias relationship may then be derived from common identity. The architecture should prefer the question “what sequence does this name denote?” over a global string-replacement table.

## `CoordinateContext`

Describes coordinate encoding, not biological identity.

Examples include:

- one-based closed GTF/GFF intervals;
- zero-based half-open BED intervals in a later release;
- the local sequence namespace used by a resource.

The format may determine coordinate convention. The reference relationship is established separately through requirements/evidence.

## `EvaluationRequest` and `EvaluationScope`

Compatibility sufficiency is contextual. A request identifies:

- supplied resources;
- explicit anchor where required;
- evaluation scope;
- active profiles;
- evaluation policy.

### Invariant

Resource relationships are factual; whether those relationships are sufficient is scoped.

RefCompat must not change a SeqCol or sequence relationship to obtain a convenient verdict.

The first Milestone 2 implementation requires a supplied FASTA anchor, validates that it remains in explicit resource scope, and permits an optional explicit FASTA-anchor sequence-name subset. Profile/policy identifiers are selectors only at this layer; they do not mutate facts or create requirements until contract construction.

## `ResourceContract`

A resource contract is produced for a resource **in an evaluation context**. It is not a permanent intrinsic property of the file.

A contract contains typed capabilities and requirements.

Examples of capabilities:

- sequence presence;
- sequence length;
- sequence identity;
- verified sequence-name binding;
- coordinate bounds;
- base lookup;
- sequence order;
- provenance evidence.

Examples of requirements:

- sequence X must exist;
- length must equal L;
- content identity must equal D;
- local seqid must resolve;
- coordinates must be in bounds;
- VCF REF bases must equal reference content;
- derived artifact must correspond to exact source representation;
- order must match when explicitly required.

Requirements record origin (`CORE_FORMAT`, `PROFILE`, `USER_POLICY`) and level (`MANDATORY`, `ADVISORY`). The initial typed implementation covers sequence presence, exact length, content identity (refget or M5/MD5 without cross-algorithm comparison), and exact local sequence order. A missing capability is not proof of absence; an explicit negative sequence-presence capability is required to establish absence.

## Typed requirements and capabilities

Avoid generic string dictionaries. Prefer typed variants such as:

```text
SequencePresenceRequirement
SequenceLengthRequirement
SequenceIdentityRequirement
SequenceNameResolutionRequirement
CoordinateBoundsRequirement
ReferenceBaseRequirement
DerivedFromRequirement
SequenceOrderRequirement
```

and corresponding capability types.

Typed variants prevent comparisons between unrelated scientific constraints and make type checking useful.

## `CompatibilityConstraint` and `ConstraintEvaluation`

A constraint is the immutable question connecting a requirement to candidate capabilities and a rule. Its evaluation is a separate result.

Constraint states:

- `SATISFIED`
- `UNSATISFIED`
- `UNRESOLVED`
- `NOT_APPLICABLE`

Mechanism belongs in a separate `SatisfactionMode`, for example:

- `EXACT`
- `VERIFIED_ALIAS`
- `VERIFIED_SEQUENCE_IDENTITY`
- `VERIFIED_SUBSET`

Do not encode mechanisms as proliferating states such as `SATISFIED_BY_ALIAS`.

The first evaluator implements exact typed comparisons only. It returns `UNRESOLVED` when comparable evidence is absent or internally conflicting, and it does not infer a cross-name alias/binding merely from familiar names. The second Milestone 2 slice derives deterministic qualitative evidence items from evaluator-relevant capabilities and aggregates them without numeric scoring or bundle interpretation.

## `Evidence` and `EvidenceAggregate`

Generalized evidence relates one typed requirement to one evaluator-relevant capability. It records qualitative kind, method, strength, and support/contradiction polarity plus constraint/requirement/capability IDs and available source-observation traceability.

The aggregate retains evidence items and unresolved/not-applicable constraint IDs. It exposes Tier-A contradictions explicitly but does not weight, average, score, or assign a bundle verdict. A constraint may remain unresolved while carrying both supporting and contradicting evidence when its candidate capabilities conflict.

## `CompatibilityFinding`

A meaningful interpretation that may summarize many low-level evaluations.

Examples:

- `VERIFIED_NAMING_ONLY_DIFFERENCE`
- `STALE_SEQUENCE_DICTIONARY`
- `REFERENCE_DISTRIBUTION_SUPERSET`
- `MISSING_REQUIRED_SEQUENCE`
- `SYSTEMATIC_VCF_REF_CONFLICT`
- `DECLARED_REFERENCE_CONTRADICTED`
- `ANNOTATION_COORDINATE_OUT_OF_BOUNDS`
- `NO_REFERENCE_INCOMPATIBILITY_DEMONSTRATED`

## `CompatibilityCondition`

Conditions are structured report objects, not merely prose.

A condition identifies:

- the bounded scope in which compatibility was established;
- affected resources/sequences;
- relevant constraint evaluations;
- what remains outside the claim.

### Invariant: conditions require explicit scope

RefCompat must not decide on its own that ALT, decoy, patch, mitochondrial, unplaced, or other sequences are irrelevant. Conditional compatibility follows an explicit evaluation scope or profile rule.

## `CompatibilityReport`

The report is the immutable root result of an evaluation and should carry enough information for every conclusion to be traced to source evidence.

It contains resources, observations, claims, claim assessments, snapshots/reference contexts, contracts, evidence, constraints/evaluations, findings, conditions, analysis status, and compatibility verdict.

## Foundational invariants

1. **Inspection produces facts, never compatibility conclusions.**
2. **Compatibility requirements belong to an evaluation context, not intrinsically to a file.**
3. **Every interpreted conclusion traces backward through evaluations/evidence to immutable observations or claims.**
4. **Strong evidence cannot be outweighed by larger quantities of weak evidence.**
5. **Conditions come from explicit scope, not inferred user intent.**
6. **Derived-artifact correctness is stricter than biological alias equivalence.**
7. **The v0.1 FASTA anchor defines the candidate reference context; resources do not vote.**
