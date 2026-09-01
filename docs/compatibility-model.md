
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
Verdict aggregation
    └── VerdictAggregation / CompatibilityVerdict
    |
    v
CompatibilityReport
    └── AnalysisStatus
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

## `VcfRefValidationResult`

Milestone 3 adds a separate direct-check result for exhaustive VCF REF-to-FASTA comparison. It is not
a `ResourceObservation` because `MATCH`/`MISMATCH` require comparison with the explicit FASTA anchor,
and it is not a bundle verdict because it describes only RCHECK-050B record evidence.

The result stores aggregate and per-VCF-sequence counts for `MATCH`, `MISMATCH`, `OUT_OF_BOUNDS`,
and `UNRESOLVED_SEQUENCE`. Matching records are counted rather than retained individually; every
non-match retains its source VCF resource ID, file ordinal, CHROM, native one-based POS, REF, and
the directly relevant anchor trace. A mismatch also retains the fetched FASTA bases. This keeps fully matching VCFs
memory-efficient without sacrificing traceability of conflicts or unresolved records.

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

For v0.1 the explicitly selected FASTA anchor defines the reference context from a complete `SequenceCollectionSnapshot`. Explicit anchor-sequence scope filters that context while preserving FASTA order. The reasoner derives anchor presence, length, identity, and order capabilities from the selected sequences. Other resources are evaluated against those anchor capabilities; resources do not vote on reference identity.

A future context-status layer may still distinguish states such as `VERIFIED`, `PARTIALLY_VERIFIED`, `OBSERVED`, and `UNRESOLVED`. Those status ideas are retained for later policy/reporting work rather than being embedded prematurely in the current `ReferenceContext` object.

## `SequenceBinding`

Connects a resource-local sequence label to a sequence identity or other evidence-backed coordinate entity.

For example:

```text
FASTA local name chr1 -> SQ.ABC...
GTF local name 1     -> SQ.ABC...
```

A verified alias relationship may then be derived from common identity. The first implementation requires the comparable identity scheme to be available for every sequence in the complete FASTA anchor and to resolve one local name to exactly one selected anchor sequence. Any other local identity that has a known full-anchor match must agree on that same target even if its own scheme is incomplete. Duplicate anchor sequences with the same content identity, or anchor sequences whose identity is unobserved in the scheme establishing uniqueness, remain ambiguous rather than being broken by string resemblance. Conflicting local identity facts likewise remain unbound. The architecture prefers the question “what sequence does this name denote?” over a global string-replacement table.

For VCF resources, a syntactically valid `##contig` MD5 declaration may be retained as a `DECLARED_METADATA` identity capability only for binding evidence after it uniquely identifies a sequence in the complete FASTA anchor and passes the VCF binding checks. FASTA anchor identities are `CONTENT_DERIVED`; only those derived capabilities may satisfy identity requirements or act as candidate reference authority. The declared identity can establish which anchor sequence a VCF label denotes, but it is not direct REF-compatibility proof; exhaustive REF comparison remains authoritative for base agreement.

For an actually used VCF contig, a declared `##contig` length is also a mandatory
structural requirement. An exact-name or verified-bound FASTA sequence with a
different length is contradictory structural evidence even if every observed REF
record lies inside the shared coordinate range and matches. Without a verified
name resolution, a cross-name length declaration remains unresolved; length
equality alone never establishes an alias.

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

Requirements record origin (`CORE_FORMAT`, `PROFILE`, `USER_POLICY`) and level (`MANDATORY`, `ADVISORY`). The typed implementation covers sequence presence, exact length, content identity (refget or M5/MD5 without cross-algorithm comparison), explicit evidence-backed local-to-anchor binding, exact local sequence order, scalable exhaustive coordinate-bounds validation, and scalable exhaustive reference-base consistency. A missing capability is not proof of absence. Absence requires an explicit negative fact, including the reasoner-owned `SequenceIdentityAbsenceCapability` when at least one independently established content-identity scheme has complete anchor coverage and no local content-derived identity positively matches anywhere in the full anchor.

## Typed requirements and capabilities

Avoid generic string dictionaries. Prefer typed variants such as:

```text
SequencePresenceRequirement
SequenceLengthRequirement
SequenceIdentityRequirement
SequenceBindingRequirement
CoordinateBoundsRequirement
ReferenceBaseRequirement
DerivedFromRequirement
SequenceOrderRequirement
```

and corresponding capability types.

Typed variants prevent comparisons between unrelated scientific constraints and make type checking useful.

Milestone 6 adds `SequenceBindingRequirement` for profile or policy contexts in
which exact-name availability is insufficient and the local-to-anchor
relationship itself must be authenticated. It is evaluated only against an
anchor-owned pair-derived `SequenceBindingValidationCapability`; unresolved
relationships are represented by absence of that capability rather than a
negative assertion. A `BOUND` validation requires an explicit `SequenceBinding`,
while `PROVEN_ABSENT` is reserved for a producer that has exhaustive content
evidence for the required external target. The generic model contains no UCSC
identifiers or alias-table rules.

`ReferenceBaseRequirement` is resource-level, names the selected anchor resource explicitly, and carries the exhaustive checked-record count rather than expanding into one object per locus. `ReferenceBaseValidationCapability` is owned by that anchor, names the subject resource, and partitions the exhaustive check into match, mismatch, and unresolved counts. Generic comparability requires the capability owner to equal the requirement's named anchor, so pair-derived evidence from another FASTA cannot satisfy the requirement. Generic evaluation gives mismatch Tier-A precedence, leaves unresolved-only checks unresolved without fabricated evidence, and treats an empty record set as not applicable. Format-specific local mismatch/bounds/name details remain in the producing validation model. VCF additionally exposes `VcfRefConflictPatternSummary` as descriptive format-specific interpretation; it is not a generic requirement, capability, finding, or verdict state.

Milestone 5 implements the same scalable pair-derived pattern for coordinate statements. `CoordinateBoundsRequirement` is resource-level rather than one requirement per feature, names the selected anchor, and carries the exhaustive in-scope coordinate count. Its anchor-owned `CoordinateBoundsValidationCapability` partitions those statements into representable, conflicting, and unresolved counts for the same subject resource. Generic evaluation gives proven conflicts precedence, leaves unresolved-only checks unresolved without fabricated evidence, treats an empty coordinate set as not applicable, and emits Tier-B structural evidence for resolved support/contradiction. Format-specific interpretation happens before projection: unresolved sequence names and ambiguous circular-landmark cases remain unresolved, while a proven GFF3 single-wrap feature is counted as representable. The annotation-specific result retains ordinary/circular feature outcomes plus GFF3 sequence-region checks so the generic model stays compact. Coordinate agreement never becomes sequence-content identity evidence. Separately, relevant GFF3 embedded FASTA bases can produce annotation-owned `CONTENT_DERIVED` MD5 capabilities and mandatory identity requirements; these reuse the existing full-anchor `SequenceBinding` machinery and may yield Tier-A sequence-identity evidence without changing the coordinate evidence tier or anchor authority. Independently supplied annotation-owned `CONTENT_DERIVED` identity may also establish a binding or, when at least one local identity scheme covers every sequence in the complete anchor and no local content-derived identity matches anywhere in that full anchor, a reasoner-owned Tier-A sequence-identity absence fact.

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
- `VERIFIED_SEQUENCE_BINDING`
- `VERIFIED_SUBSET`

Do not encode mechanisms as proliferating states such as `SATISFIED_BY_ALIAS`.

The evaluator supports exact typed comparisons plus projection through explicit verified `SequenceBinding` objects. It returns `UNRESOLVED` when comparable evidence is absent or internally conflicting and never infers a cross-name relationship from familiar names alone. Bound cross-name presence/length/order may use `VERIFIED_ALIAS`; identity remains `VERIFIED_SEQUENCE_IDENTITY`. An explicit `SequenceBindingRequirement` uses `VERIFIED_SEQUENCE_BINDING` only when its pair validation and binding agree on one anchor target. Evidence records `VERIFIED_SEQUENCE_BINDING` and the binding IDs when a verified mapping is required. A reasoner-derived `SequenceIdentityAbsenceCapability` is a separate Tier-A contradiction to presence; a pair-derived binding validation may likewise carry Tier-A exhaustive target absence for a profile requirement. Both are usable only after their producing layer has the required exhaustive content evidence.

## `Evidence` and `EvidenceAggregate`

Generalized evidence relates one typed requirement to one evaluator-relevant capability. It records qualitative kind, method, strength, and support/contradiction polarity plus constraint/requirement/capability IDs and available source-observation traceability.

The aggregate retains evidence items and unresolved/not-applicable constraint IDs. It exposes Tier-A contradictions explicitly but does not weight, average, score, or assign a bundle verdict. A constraint may remain unresolved while carrying both supporting and contradicting evidence when its candidate capabilities conflict.

## `CompatibilityFinding`

A meaningful interpretation that may summarize one or more low-level evaluations. The first implementation emits deterministic issue/unresolved findings for individual typed constraints while leaving satisfied constraints represented by their evaluations/evidence.

Examples:

- `VERIFIED_NAMING_ONLY_DIFFERENCE`
- `STALE_SEQUENCE_DICTIONARY`
- `REFERENCE_DISTRIBUTION_SUPERSET`
- `MISSING_REQUIRED_SEQUENCE`
- `REFERENCE_BASE_CONFLICT`
- `DECLARED_REFERENCE_CONTRADICTED`
- `ANNOTATION_COORDINATE_OUT_OF_BOUNDS`
- `NO_REFERENCE_INCOMPATIBILITY_DEMONSTRATED`

## `CompatibilityCondition`

Conditions are structured report objects, not merely prose. The first implementation records explicit resource and FASTA-anchor sequence scope boundaries without claiming that compatibility has already been established inside those bounds.

A condition identifies:

- the bounded scope in which compatibility was established;
- affected resources/sequences;
- relevant constraint evaluations;
- what remains outside the claim.

### Invariant: conditions require explicit scope

RefCompat must not decide on its own that ALT, decoy, patch, mitochondrial, unplaced, or other sequences are irrelevant. Conditional compatibility follows an explicit evaluation scope or profile rule.

## `VerdictAggregation` and `CompatibilityVerdict`

The fifth Milestone 2 slice aggregates already-evaluated mandatory constraints into one categorical verdict. Hard mandatory contradictions take precedence over unresolved states; unresolved mandatory relationships take precedence over positive outcomes; and explicit conditions qualify only an otherwise-positive result. Advisory constraints remain visible but do not veto. No applicable mandatory relationship yields `INDETERMINATE`, not vacuous compatibility.

`VerdictAggregation` retains the mandatory constraint IDs partitioned by state, explicit condition IDs, and the finding IDs that cover decisive incompatible or unresolved mandatory constraints. It does not perform conflict-core minimization, analysis-status classification, scoring, voting, or stable report serialization.

## `ConflictCore` and `ConflictCoreExtraction`

The sixth Milestone 2 slice projects the already-decided non-positive verdict basis into compact decisive traces. Each `ConflictCore` retains only decisive constraint/requirement/finding/evidence IDs plus the minimum resource IDs implied by the requirement and cited evidence. `INCOMPATIBLE` produces contradiction cores; unresolved `INDETERMINATE` produces unresolved cores; positive verdicts and an indeterminate result with no applicable mandatory basis produce no cores. The layer does not re-evaluate scientific truth, count evidence, or choose one arbitrary global failure when several independent conflicts exist.

## `BundleReasoningResult`

The anchor-driven whole-bundle layer requires exactly one `ResourceContract` for every explicitly scoped resource, builds the FASTA `ReferenceContext`, derives unique content-backed `SequenceBinding` objects plus any exhaustive sequence-identity absence facts, constructs one anchor-driven constraint for every typed requirement, and then runs the existing evaluation, evidence, and interpretation layers.

Peer-resource identity capabilities are consulted only to establish sequence bindings or reasoner-derived exhaustive absence; they never vote on or replace reference authority. Ordinary positive candidate capabilities for compatibility constraints come from the selected FASTA context. Caller-supplied pair-derived exhaustive validations use a separate supplemental channel: Milestone 3 introduced anchor-owned `ReferenceBaseValidationCapability`, and Milestone 5 adds anchor-owned `CoordinateBoundsValidationCapability`. Supplemental values must describe scoped resources, name the selected anchor through their matching requirement, and match an in-scope typed requirement; unrelated pair-derived capability types are not comparable. `BundleReasoningResult` retains reasoner-derived absence capabilities separately from caller-supplied supplemental capabilities and groups the request, contracts, reference context, bindings, constraints/evaluations, evidence, and interpretation without adding a top-level verdict.

## `CompatibilityReport`

Milestone 7 makes the report the immutable public root result of an evaluation. It carries enough information for every reported conclusion to be traced through RefCompat-owned IDs to source evidence/provenance while remaining insulated from internal dataclass layout and provider-library types. The stable external representation is projected explicitly; it is not `dataclasses.asdict()` over the reasoning graph.

The report includes the evaluation request/scope/profile selectors, resources, relevant observations/provenance records, reference/binding context, contracts, evidence, constraints/evaluations, findings, conditions, conflict cores, analysis status, compatibility verdict when scientifically reportable, and typed relationship context needed to explain the generic verdict. BAM/CRAM dictionary relationship context is one required M7 example because non-bijective or naming-only differences must remain visible without becoming a second verdict.

Analysis status and compatibility are orthogonal. `COMPLETE` means the requested implemented analysis finished; it may still produce `INDETERMINATE`. `PARTIAL` means a requested analysis operation could not complete, rather than merely that evidence was insufficient. `INVALID_INPUT` means required input cannot support the requested scientific evaluation. M7 must prevent partial/invalid execution from masquerading as unconditional positive compatibility.

The normative contract and planned implementation slices are in [`compatibility-report-contract.md`](compatibility-report-contract.md).

## Foundational invariants

1. **Inspection produces facts, never compatibility conclusions.**
2. **Compatibility requirements belong to an evaluation context, not intrinsically to a file.**
3. **Every interpreted conclusion traces backward through evaluations/evidence to immutable observations or claims.**
4. **Strong evidence cannot be outweighed by larger quantities of weak evidence.**
5. **Conditions come from explicit scope, not inferred user intent.**
6. **Derived-artifact correctness is stricter than biological alias equivalence.**
7. **The v0.1 FASTA anchor defines the candidate reference context; resources do not vote.**
