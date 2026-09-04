
# RefCompat
## Design Specification v0.5 — Evidence-Backed Reference/Resource Compatibility

**Status:** Design baseline for repository and implementation planning
**Date:** 2026-08-13
**Project:** RefCompat
**Working description:** A deterministic, standards-based Python tool that determines whether heterogeneous genomic resources can share a coherent reference-coordinate context for a stated use case, explains the evidence and conditions behind that conclusion, and avoids unsafe automatic repair.

---

## 1. Executive summary

RefCompat exists to answer a recurring practical question in genomics:

> **Do these genomic resources belong to a coherent reference environment, and are their reference-coordinate requirements jointly satisfiable for the operation I intend to perform?**

The project is not a new reference-genome identifier, another GFF validator, another VCF normalizer, another reference asset manager, or a liftover engine. Those layers have substantial prior art.

RefCompat's intended contribution is the reasoning layer above them. It inspects heterogeneous resources, preserves directly observed facts and provenance claims, obtains standards-based sequence/collection identities, represents what resources require and provide for an evaluation context, evaluates those constraints, and returns a scoped verdict with traceable evidence, conditions, conflicts, and unresolved questions.

The design is informed by two independently assembled and reviewed 100-case incident samples (200 cases total) from public genomics support forums and issue trackers. The corpus is purposive, not population-representative. It tests whether the problem is real, identifies recurring failure classes, provides negative controls, and informs feature order.

The main design conclusions are:

1. **GA4GH refget Sequences and Refget Sequence Collections (SeqCol) own sequence and sequence-collection identity.** RefCompat consumes those standardized identities rather than redefining them.
2. **Compatibility is constraint satisfaction, not similarity.** A hard contradiction cannot be averaged away by numerous weaker matches.
3. **Compatibility is directional and contextual.** Equality of resources is not required when one resource's mandatory requirements are satisfied by a compatible superset.
4. **Inspection and reasoning are separate.** Format inspectors emit observations/claims; they do not decide compatibility.
5. **Provenance claims remain distinct from verification.** A filename or assembly label is evidence of a claim, not content identity.
6. **Conditions require explicit scope.** RefCompat does not guess that ALT, decoy, patch, mitochondrial, or other sequence classes are irrelevant.
7. **Derived-artifact correctness is stricter than biological equivalence.** A verified alias may satisfy a biological naming requirement while still failing an exact `.fai`/`.dict` derivation requirement.
8. **The v0.1 bundle model is anchor-driven.** An explicitly selected FASTA establishes the candidate reference context; resources do not vote on what the reference probably is.
9. **Consumer-specific requirements belong in profiles.** Milestone 6 uses UCSC preflight as the first concrete profile after core stabilization.
10. **No silent scientific repair.** RefCompat diagnoses and explains; it does not silently rename, reheader, lift, rewrite, realign, or repair scientific data.

---

## 2. Research basis

### 2.1 Corpus purpose

The design corpus contains 200 reviewed incidents in two independent 100-case batches. Batch 2 excluded Batch 1 source URLs and intentionally used a different source mix to test whether the problem taxonomy or feature priorities changed materially.

The final corpus contains 137 high-confidence and 63 medium-confidence records, with no retained low-confidence records. The row-level incident records are not distributed as part of RefCompat. Validation uses synthetic or otherwise redistributable fixtures derived from the observed failure patterns.

These records are not a prevalence estimate.

### 2.2 Leading normalized problem families

| Problem family | Batch 1 | Batch 2 | Combined |
|---|---:|---:|---:|
| Bundle selection / provenance | 17 | 33 | 50 |
| Negative / not actually compatibility | 8 | 11 | 19 |
| Reference distribution / subset | 9 | 9 | 18 |
| Alias / naming mismatch | 12 | 5 | 17 |
| Consumer / profile requirement | 11 | 5 | 16 |
| Annotation ↔ reference compatibility | 7 | 6 | 13 |
| Assembly / build mismatch | 8 | 4 | 12 |
| Annotation identifier / semantic | 4 | 6 | 10 |
| Liftover / transformation ambiguity | 7 | 2 | 9 |
| Derived artifact stale/corrupt | 2 | 6 | 8 |
| VCF REF mismatch | 4 | 1 | 5 |
| Sequence / distribution conflict | 4 | 1 | 5 |

The important result is not the proportions. Batch 2 materially changed relative weights without introducing a new dominant problem family or displacing the core architecture.

### 2.3 Product correction from the corpus

The earliest concept emphasized pairwise checks. The corpus repeatedly shows a broader preflight question:

> **I have a bundle of FASTA, annotations, known-sites resources, alignments, indexes, dictionaries, caches, and/or collaborator files. What reference environment do they represent, and is the bundle coherent?**

Therefore bundle coherence and provenance are first-class concepts, not merely metadata attached to independent validators.

### 2.4 Negative controls

Many apparent compatibility symptoms eventually trace to strandedness, malformed input, resource limits, parser/consumer requirements, hosting failures, software bugs, or other causes.

RefCompat must be able to conclude:

> **No reference-coordinate incompatibility was demonstrated by the available evidence.**

It must not turn every workflow failure into a speculative reference diagnosis.

---

## 3. Product thesis and scope

### 3.1 Core statement

**RefCompat determines whether the reference-coordinate requirements of heterogeneous genomic resources can be jointly satisfied by a coherent reference context for a stated evaluation scope, and explains the evidence, limitations, conflicts, conditions, and unresolved questions behind that conclusion.**

### 3.2 Meaning of a positive verdict

A positive RefCompat result means only:

> For the evaluated reference-coordinate scope, the mandatory sequence, naming, coordinate, content, derived-artifact, and applicable provenance constraints represented by the supplied resources are satisfied to the stated evidence level, with any conditions explicitly reported.

It does not certify that an experimental or biological analysis is globally safe, optimal, or scientifically preferable.

### 3.3 Questions outside core scope

Examples:

- which annotation provider is biologically preferable;
- which mouse reference is best for a study;
- whether BQSR is scientifically appropriate;
- whether an aligner/caller/model is optimal;
- whether an observed biological result is correct;
- whether a particular transcript model is biologically valid.

### 3.4 Layer in the ecosystem

```text
Individual sequence identity
        |
        | GA4GH refget Sequences
        v
Sequence-collection identity/comparison
        |
        | GA4GH SeqCol
        v
Resource facts, requirements, capabilities, provenance
        |
        | RefCompat inspection + contracts
        v
Cross-resource constraint evaluation
        |
        | RefCompat reasoning
        v
Scoped verdict + evidence + conditions + unresolved questions
        |
        +--> human report
        +--> machine-readable report
        +--> future profiles
```

---

## 4. Standards and prior-art boundary

### 4.1 refget Sequences

RefCompat SHALL NOT define a new biological sequence digest scheme. Individual sequence identity is delegated to GA4GH refget Sequences when applicable.

Legacy checksums such as SAM M5/MD5 may be consumed as evidence where their semantics are valid, but are represented distinctly from refget identifiers.

### 4.2 SeqCol

RefCompat SHALL NOT redefine sequence-collection identity or comparison semantics. SeqCol owns the standardized collection model and relationships among names, lengths, sequence identities, ordering, and collection overlap.

RefCompat preserves relevant SeqCol comparison facets as evidence and asks a different question: whether those relationships satisfy heterogeneous resource requirements.

### 4.3 Refget/SeqCol Python integration

Current integration design is local-first and adapter-based:

```text
RefCompat domain
    ^
ReferenceIdentityProvider
    ^
Ga4ghRefgetIdentityProvider
    ^
external refget / gtars implementation
```

External library types must be translated into RefCompat-owned immutable values before entering the reasoning model.

Remote SeqCol/metadata services are optional enrichment and use a separate boundary. A network outage must not invalidate otherwise sufficient local analysis.

See `docs/refget-seqcol-integration.md` and ADR 0001/0007.

### 4.4 Important existing tools

RefCompat should complement rather than duplicate:

- GA4GH refget/SeqCol for identity/comparison;
- GATK `CheckReferenceCompatibility` for its specific reference-comparison surface;
- bcftools reference checking/normalization functions;
- SAM/Picard validation tooling;
- UCSC alias and hub validation facilities;
- specialized GTF/GFF validators;
- ref-solver for recognizing known human reference distributions;
- reference asset managers such as refgenie/genomepy.

The project should periodically revisit this boundary and remove planned functionality if another maintained tool already solves it adequately.

---

## 5. Formal domain model

Supporting detail lives in `docs/compatibility-model.md`.

### 5.1 `Resource`

A thin identity for one supplied artifact/logical input. Artifact-byte identity remains separate from genomic sequence/collection identity.

### 5.2 `ResourceObservation`

Immutable directly extracted fact with source location where practical. Observations never contain compatibility conclusions.

### 5.3 `ProvenanceClaim`

Immutable statement about origin/identity, retaining the source of the statement.

### 5.4 `ClaimAssessment`

Later evaluation of a claim as `SUPPORTED`, `VERIFIED`, `CONTRADICTED`, or `UNRESOLVED`.

### 5.5 `ResourceRelationClaim`

Claimed relationships such as `DERIVED_FROM`, `ALIGNED_TO`, `CALLED_AGAINST`, `ANNOTATES`, or `BELONGS_TO_BUNDLE`.

### 5.6 `SequenceCollectionSnapshot`

Per-resource description of the sequence collection information the resource actually exposes. It must carry completeness semantics so sparse resources are not mistaken for complete references.

### 5.7 `ReferenceContext`

Reasoner-produced candidate/established shared reference context. In v0.1 the explicitly selected FASTA anchor establishes the context from a complete `SequenceCollectionSnapshot`, projected only into explicit request scope. Peer resources do not vote on reference identity.

### 5.8 `SequenceBinding`

Evidence-backed mapping from a resource-local name to one anchor-local sequence. The first implementation derives a binding only from a comparable identity scheme that is available for every sequence in the complete FASTA anchor snapshot and resolves the local identity uniquely there; any other local identity with a known full-anchor match must agree on that same target even when its own scheme is incomplete. Explicit sequence scope may hide a unique target but must never manufacture uniqueness by hiding duplicate-content or identity-unobserved alternatives. Conflicting local identities remain unbound. Alias relationships are derived from bindings rather than blind string substitution.

Sequence identity capabilities carry required explicit provenance. `CONTENT_DERIVED` identities may satisfy sequence-identity requirements and may appear in the FASTA anchor context; `DECLARED_METADATA` identities are claims that may support conservative binding but cannot become candidate reference authority. `ReferenceContext` independently verifies that its anchor identity capabilities exactly match the selected FASTA snapshot. Whole-bundle reasoning may additionally use peer-owned `CONTENT_DERIVED` identity to derive an anchor-owned exhaustive absence fact when at least one such identity scheme covers every sequence in the complete FASTA and no local content-derived identity matches anywhere in the full anchor; a positive match in another incompletely covered scheme blocks that path, and declared metadata can never establish it. This provenance distinction applies to VCF `##contig md5`, BAM/CRAM `@SQ M5`, and independently established annotation identity evidence.

Milestone 6 adds one second scientifically distinct binding path: an explicit profile may contribute an authoritative sequence-name relationship only when the provider alias resolves uniquely in the complete relevant provider naming context (canonical catalog plus alias evidence) **and** the provider target sequence is independently content-bound to one sequence in the complete FASTA anchor. The shared `AnchorIdentityResolution` helper factors the reviewed full-anchor content-match/exhaustive-absence semantics out of resource binding so UCSC target reasoning can reuse them without making provider facts into peer capabilities or reference authority. Slice 4 now composes the separately resolved provider name and target through a profile-origin `SequenceBindingRequirement`, an anchor-owned pair validation, and `SequenceBindingMethod.AUTHORITATIVE_NAME`; the binding's identity trace authenticates only the provider-target-to-anchor leg and never becomes peer-owned content identity. Generic bundle reasoning revalidates that full-anchor target trace and requires the matching pair validation before the naming relationship can affect core checks. Conflicting, directly mismatching, or differently matching peer identity evidence prevents provider naming from manufacturing a positive binding, while an independently verified peer binding to a different target remains a hard content conflict. Generic code remains provider-independent and never learns UCSC identifiers or infers aliases from strings. The existing content-identity binding path and its invariants remain unchanged.

Later hardening: if repeated binding derivation becomes performance-sensitive, consider caching or reusing full-snapshot anchor identity capabilities. Any such optimization must preserve complete-FASTA uniqueness and ambiguity semantics.

### 5.9 `CoordinateContext`

Describes coordinate encoding/interval semantics and local sequence namespace; it does not itself prove biological reference identity.

### 5.10 `EvaluationRequest` and `EvaluationScope`

Identify resources, anchor, explicit scope, profiles, and policy. Resource relationships are factual; sufficiency is scoped.

### 5.11 `ResourceContract`

Produced for a resource in a specific evaluation context. Contains typed capabilities and requirements.

### 5.12 `CompatibilityConstraint` and `ConstraintEvaluation`

Separate the immutable question from its evidence-backed result.

Constraint states:

- `SATISFIED`
- `UNSATISFIED`
- `UNRESOLVED`
- `NOT_APPLICABLE`

Mechanism is recorded separately in `SatisfactionMode`, such as `EXACT`, `VERIFIED_ALIAS`, `VERIFIED_SEQUENCE_IDENTITY`, or `VERIFIED_SUBSET`.

### 5.13 `Evidence`

Relationship/support/contradiction derived from observations/claims, with explicit strength and traceability.

### 5.14 `CompatibilityFinding`

Meaningful interpreted issue or verified relationship summarizing one or more evaluations. The first implementation emits structured conflict and unresolved findings from typed constraint evaluations; higher-order verified relationships remain later work.

### 5.15 `CompatibilityCondition`

Structured bounded statement for explicit evaluation scope. The first implementation records caller-selected resource and FASTA-anchor sequence boundaries without claiming that compatibility has already been established inside them. Later verdict aggregation may cite those conditions when a positive result is valid only within that explicit scope. Conditions require explicit scope/profile semantics.

### 5.16 `CompatibilityReport`

Immutable root result containing enough structured information for every user-visible conclusion to trace back to observations/claims.

---

## 6. Evidence hierarchy and rules

### 6.1 Tier A — conclusive content evidence

Examples:

- refget sequence identity;
- applicable SeqCol identities/relationships;
- valid comparable M5 content checksums;
- direct reference-base comparison;
- exhaustive VCF REF mismatch.

### 6.2 Tier B — direct structural/content consistency

Examples:

- names+lengths where digest unavailable;
- `.fai`/`.dict` structural correspondence;
- GTF/GFF seqids resolved and coordinates in bounds.

### 6.3 Tier C — provenance/metadata

Examples:

- VCF `##reference`;
- assembly/provider/release metadata;
- BAM assembly/URI/program metadata;
- source URLs/pipeline configuration.

### 6.4 Tier D — heuristic context

Examples:

- filename contains `hg38`;
- familiar chromosome names;
- coordinate values resemble a known build transition.

### 6.5 Rules

- Hard content contradiction vetoes weaker supporting evidence for the affected scope.
- Absence of evidence is not incompatibility.
- Local conflicts remain localized unless scope makes them global blockers.
- Sampling weakens claims.
- Metadata conflicts remain visible even when content identity governs reasoning.
- No global numeric compatibility score.

See `docs/evidence-model.md`.

---

## 7. Compatibility verdicts and analysis status

### 7.1 `COMPATIBLE`

All mandatory in-scope constraints are satisfied with adequate evidence and no unresolved mandatory issue could change the conclusion.

### 7.2 `COMPATIBLE_WITH_CONDITIONS`

Compatibility is established only within an explicit bounded scope/profile condition. The condition is structured and states what is and is not covered.

### 7.3 `INCOMPATIBLE`

At least one in-scope mandatory constraint is contradicted by sufficient evidence.

### 7.4 `INDETERMINATE`

No hard contradiction is established, but available evidence cannot establish at least one mandatory relationship.

### 7.4.1 Implemented v0.1 aggregation precedence

The Milestone 2 categorical aggregator applies mandatory constraints in this order:

1. any `UNSATISFIED` mandatory constraint -> `INCOMPATIBLE`;
2. otherwise any `UNRESOLVED` mandatory constraint -> `INDETERMINATE`;
3. otherwise no applicable mandatory constraint -> `INDETERMINATE`;
4. otherwise explicit conditions -> `COMPATIBLE_WITH_CONDITIONS`;
5. otherwise -> `COMPATIBLE`.

Advisory constraints remain visible in evaluations/findings but do not veto a positive verdict. `NOT_APPLICABLE` mandatory constraints are neutral when another mandatory relationship is actually satisfied; a bundle with no applicable mandatory relationship does not receive vacuous compatibility. Conditions qualify only an otherwise-positive conclusion and never upgrade an incompatible or indeterminate result. The aggregation retains mandatory constraint-state partitions plus finding/condition IDs for traceability and performs no numeric scoring or voting.

Later hardening: if findings are extended to span multiple constraints, verdict-basis selection must distinguish which cited constraints are actually decisive rather than treating any constraint-ID intersection as sufficient.

### 7.4.2 Conflict-core extraction

Conflict-core extraction projects only the decisive non-positive verdict basis into compact resource/evidence traces. `INCOMPATIBLE` yields contradiction cores for unsatisfied mandatory constraints; unresolved `INDETERMINATE` yields unresolved cores; positive verdicts and indeterminate results with no applicable mandatory basis yield none. Each current core corresponds to one decisive finding and retains only direct constraint, requirement, finding, evidence, and resource IDs. Multiple independent failures remain separate small cores rather than being merged into a mismatch wall or reduced to one arbitrary global minimum.

The core layer does not re-evaluate scientific truth, score evidence, or duplicate transitive capability/observation/binding provenance already carried by `Evidence`. If future findings span multiple constraints, core projection and verdict-basis selection must be tightened together to retain only actually decisive trace.

### 7.5 Analysis status

Separately:

- `COMPLETE`
- `PARTIAL`
- `INVALID_INPUT`

A malformed mandatory input is not a biological incompatibility. Where no meaningful compatibility evaluation can be formed, the report may have `verdict = None` and `analysis_status = INVALID_INPUT`.

Per-check execution may additionally distinguish `COMPLETE`, `PARTIAL`, `SKIPPED`, and `INVALID_INPUT`.

---

## 8. Explicit initial check specifications

The normative detailed contracts live in `docs/check-specifications.md`.

### RCHECK-000 — resource inventory and provenance

Capture metadata and claims, assess them against stronger evidence, and detect incoherent bundle provenance without treating labels as proof.

### RCHECK-010 — FASTA anchor identity

Obtain local sequence names, lengths, ordering, refget sequence identities, SeqCol identity/relationships, bounds, and base-lookup capability.

### RCHECK-020 — FASTA ↔ `.fai`

Verify exact companion-index structure, including byte-layout/index geometry when supported. Verified biological aliases do not make a differently represented `.fai` valid.

### RCHECK-030 — FASTA ↔ `.dict`

Compare sequence names, lengths, order, M5, aliases, and provenance fields. Distinguish biological sequence relationships from exact companion-artifact correctness.

### RCHECK-040 — BAM/CRAM ↔ FASTA

Reconcile alignment `@SQ` reference context with the anchor. Header-only inspection does not establish actual read use of every declared sequence. Milestone 4 now copies parser-visible `@HD`, ordered `@SQ`, and `@PG` metadata from BAM/CRAM into RefCompat-owned observation values and projects each declared `SN`/`LN` plus any `M5` into mandatory core-format presence, length, and identity requirements. The M5 requirement can be assessed only against content-derived anchor identity; the alignment declaration is not anchor authority. Conservative cross-name bindings are derived only from `DECLARED_METADATA` M5 claims that uniquely identify one sequence in the complete FASTA anchor, remain inside anchor-sequence scope, and agree with the target length. A descriptive relationship layer now keeps membership, naming, relative order, M5 content, and length-conflict dimensions separate so exact identity, verified naming-only differences, reorder, subset/superset/overlap, content conflicts, and unresolved cases remain distinguishable without creating a second alignment-specific verdict. `AN` and familiar name patterns remain non-authoritative. CRAM header reasoning remains reference-independent. Because external-reference dependency and embedded-reference state live below the SAM header, RefCompat does not infer from header facts whether record decoding requires an external reference. If a later operation genuinely needs reference bases, the deterministic offline plan may select only the explicitly chosen, readable FASTA anchor when the declared CRAM dictionary is exact-name addressable, M5-verified, length-consistent, and fully covered by that anchor; otherwise reference-dependent decoding remains deferred. The planner never selects ambient `REF_PATH`/`REF_CACHE`, header `UR`, or network lookup. Because explicit FASTA configuration gives the anchor priority but does not itself disable all provider fallbacks, a future decoder adapter must preserve that isolation explicitly and fail closed if the observed anchor artifact is no longer valid.

### RCHECK-050 — VCF ↔ FASTA

Use header/reference metadata plus **exhaustive** REF allele checking in authoritative v0.1 mode. A proven REF mismatch is a hard local conflict; mismatch rate aids interpretation rather than cancelling the conflict.

The implemented direct-validation boundary streams every record, converts VCF one-based POS explicitly to a zero-based half-open FASTA REF span, preserves exact-name failures as `UNRESOLVED_SEQUENCE`, and retains every non-match record while counting successful matches. FASTA random access uses FAI geometry recomputed from the supplied FASTA in a temporary index rather than trusting an adjacent `.fai`. VCF 4.5 IUPAC reduction rules are applied before base comparison; telomere sentinel positions remain explicit `OUT_OF_BOUNDS` direct-comparison states rather than being mislabeled REF mismatches. Threshold-free mismatch-pattern interpretation and verified sequence-binding revalidation are now implemented separately; stable report/CLI presentation remains deferred.

The next implemented bridge projects actual CHROM usage into mandatory sequence-presence requirements, declared lengths for used contigs into mandatory sequence-length requirements, and the exhaustive direct check into one scalable `ReferenceBaseRequirement` that names the selected anchor plus an anchor-owned `ReferenceBaseValidationCapability`. Generic comparability requires those anchor IDs to agree, so pair-derived evidence from another FASTA cannot satisfy the requirement. A directly comparable declared-length mismatch remains a structural contradiction even when all checked REF records match. Any REF mismatch yields Tier-A contradiction evidence regardless of the number of matches; unresolved/bounds-only direct checks remain `UNRESOLVED`, and an empty record set is `NOT_APPLICABLE`. The original `VcfRefValidationResult` retains local non-match details. A VCF-specific pattern layer now classifies complete direct checks as `NONE`, `ISOLATED`, `LOCALIZED`, `DISTRIBUTED`, or `SYSTEMATIC` without a mismatch-rate threshold; any unresolved-sequence or out-of-bounds record leaves the pattern `UNCLASSIFIED` while preserving any proven hard contradiction.

Whole-bundle orchestration now accepts these pair-derived validation capabilities through an explicit supplemental-capability channel rather than through peer `ResourceContract` capabilities. Supplemental reference-base capabilities must be owned by the selected FASTA anchor, describe a scoped resource, match an in-scope `ReferenceBaseRequirement`, and be uniquely applicable to that requirement. `BundleReasoningResult` retains the supplemental capabilities separately and verifies that bundle constraints cite only ordinary anchor capabilities, reasoner-derived exhaustive absence capabilities, or explicitly supplied supplemental capabilities. This permits the existing categorical verdict and conflict-core layers to consume direct REF evidence without changing their policy: all-match validation can contribute to `COMPATIBLE`, a proven mismatch remains a hard `INCOMPATIBLE` basis, and incomplete direct validation remains `INDETERMINATE`. The VCF-specific pattern layer is descriptive only: it does not change generic constraint truth, bundle verdicts, conflict cores, or infer a cause. Verified VCF aliases are now derived only from uniquely matched `##contig` MD5 identity (with complete anchor MD5 coverage, full-anchor uniqueness, and length-consistency checks), and exhaustive REF comparison can use those bindings while preserving any hard mismatch. A syntactically valid MD5 declaration on an actually used contig is also projected as a mandatory sequence-identity requirement, so a directly comparable contradictory header digest cannot disappear merely because it failed to produce a binding. Report/CLI presentation remains deferred.

### RCHECK-060 — GTF/GFF3 ↔ FASTA

Treat GTF/GFF3 as sparse coordinate-bearing resources whose feature-used seqids—and any additional GFF3 seqids named by `##sequence-region`—impose directional requirements on the explicitly selected FASTA anchor. Preserve native one-based closed coordinates in observations, project each referenced seqid into a mandatory sequence-presence requirement, and summarize feature/declared-region coordinate validation through one scalable `CoordinateBoundsRequirement` rather than one generic requirement per coordinate statement. Pair-derived coordinate validation is owned by the selected anchor and may use only exact-name or verified `SequenceBinding` resolution; familiar aliases are not inferred. A resolved ordinary interval outside the anchor sequence is a hard structural conflict, while an unresolved local name remains unresolved rather than being mislabeled as proven absence. The ordinary exact-name path is implemented end to end: exhaustive feature validation preserves per-seqid counts plus bounded representative problem detail, projects one anchor-owned coordinate capability, accepts sparse annotations against FASTA supersets, and keeps unfamiliar names unresolved. GFF3 circular-origin handling is now landmark-aware: only a `region` feature with one exact `Is_circular=true` control attribute can supply structural landmark evidence, and a wrap is satisfied only when that unique landmark starts at coordinate 1, its length matches the resolved anchor, and the extended end follows the standard single-wrap representation. Feature `ID` is not used to identify the landmark because GFF3 does not require `ID == seqid` and NCBI generates landmark IDs independently of the column-1 seqid. Malformed, repeated, contradictory, or non-`true` `Is_circular` forms are invalid input; unrelated circular child features no longer defer ordinary bounds conflicts.

For GFF3, `##sequence-region` describes the sequence segment referred to by the file and is not an exact whole-sequence length declaration. The implemented Slice 5 rejects duplicate logical region declarations, checks each declared segment against the selected FASTA, folds region statements into the same exhaustive coordinate capability as feature rows, and treats ordinary feature/region self-contradiction as invalid input rather than biological incompatibility. The circular exception applies to feature/region self-consistency only when the same landmark-aware single-wrap rules establish the exception; arbitrary `Is_circular=true` observations do not suppress malformed-input detection. Relevant GFF3/GTF provider, release, assembly, and species metadata remain provenance claims and do not alter the annotation contract by themselves.

GFF3 `##FASTA` marks a parser boundary and may provide actual embedded sequence content. The implemented binding slice streams those sequences into bounded name/length/MD5 summaries using the refget sequence-normalization rule and exposes content-derived identity only when an embedded FASTA identifier exactly matches a feature-used or `##sequence-region` logical seqid. Those identities become mandatory annotation sequence-identity requirements and annotation-owned content-derived capabilities; the existing binding reasoner may map a local seqid to a differently named anchor sequence only when that identity scheme is available for every sequence in the complete FASTA anchor, the target is unique there, and it remains in scope. Annotation projection independently derives the expected binding and rejects stale coordinate validation that omitted or substituted it. The same verified binding is then used to re-evaluate feature/region coordinates. Embedded content can therefore prove an exact-name sequence contradiction, but it never replaces or competes with the explicitly selected FASTA anchor. Because the embedded content already has a mandatory identity requirement, its exact-name no-match case retains that single Tier-A identity contradiction rather than adding a redundant presence contradiction. Independently established annotation-owned `CONTENT_DERIVED` identity that is not an intrinsic format declaration may instead establish a binding or, when at least one identity scheme has complete full-anchor coverage and no local content-derived identity matches anywhere in the anchor, an exhaustive Tier-A absence of required sequence content. Exact-name coordinate compatibility does not require embedded sequence identity and does not prove that an annotation came from a particular named assembly. Matching embedded sequence length is also an input-validity constraint: ordinary features or sequence-region declarations beyond that content are malformed rather than external-FASTA incompatibilities. A valid circular-origin feature may extend beyond matching embedded sequence length only when the established landmark length equals that embedded sequence length and the standard single-wrap encoding is satisfied.

RefCompat does not validate gene-model biology, repair feature hierarchy, normalize attributes, infer build aliases from naming conventions, or enforce consumer-specific GTF/GFF3 dialect rules.

See [`docs/annotation-coordinate-compatibility.md`](docs/annotation-coordinate-compatibility.md) for the standards-derived Milestone 5 invariants that pin this implementation boundary.

### RCHECK-100 — whole-bundle coherence

Evaluate all in-scope mandatory requirements against the FASTA-anchored reference context and aggregate the top-level verdict. Identify the smallest useful conflict/evidence core.

### Shared alias infrastructure

Alias/name resolution is shared evidence infrastructure, not a standalone validator. Familiar string patterns alone are insufficient for verification.

---

## 9. v0.1 scope

### 9.1 Anchor requirement

Authoritative multi-resource `check` SHOULD require an explicit FASTA anchor in v0.1.

A reference-free `inspect` mode may report facts, claims, and relationships that can be established without an anchor, but it must not overclaim full bundle compatibility.

### 9.2 Formats

Initial supported formats should be limited to:

- FASTA;
- `.fai`;
- SAM/Picard-style `.dict`;
- VCF/bgzipped VCF;
- SAM/BAM/CRAM headers/dictionaries;
- GTF;
- GFF3.

Deferred:

- BED;
- chain/liftover files;
- bigBed/bigWig;
- full UCSC hubs;
- arbitrary tabular coordinates;
- complex tool-specific indexes.

### 9.3 Diagnostic-only behavior

v0.1 SHALL NOT automatically:

- rename sequence identifiers;
- reheader BAM/CRAM;
- rewrite REF/ALT;
- perform liftover;
- remove ALT/decoy/patch sequences;
- regenerate alignments;
- alter annotation structure.

---

## 10. Output contract

### 10.1 Human report order

Prefer:

1. resources evaluated;
2. reference context: verified, observed, claimed, unresolved;
3. scoped verdict and analysis status;
4. failed/unresolved mandatory constraints;
5. meaningful relationships/differences;
6. evidence and provenance conflicts;
7. explicit conditions;
8. safest non-mutating next diagnostic action.

### 10.2 Machine-readable report

Milestone 7 owns the stable report boundary. The public machine-readable shape must be an explicit RefCompat-owned reporting contract rather than a recursive serialization of internal dataclasses or upstream/provider objects. Report assembly consumes already-derived reasoning outputs, validates their cross-object consistency, and preserves traceability; it does not inspect files again, rebuild constraints, or introduce a second scientific verdict engine. Schema versioning is independent of the package version. The report root and explicit deterministic draft JSON projection are implemented, and Slice 4 scientific/API review hardened global requirement/capability ID uniqueness plus cross-wired trace rejection, removed local `ArtifactIdentity.path` from the portable projection, and canonicalized condition exclusion IDs before freezing stable core schema `1.0.0`. Slice 5 advances the current stable schema additively to `1.1.0`: report-owned observations, BAM/CRAM dictionary relationship summaries, and UCSC provider/source/profile provenance are projected from already-derived values without leaking implementation objects or creating new verdict logic. Exact schema `1.0.0` remains packaged; its over-escaped refget pattern is corrected as a schema-only erratum to accept the already-frozen `SQ.<32-character>` identity representation. The draft surface advances separately to revision 3.

The Milestone 7 stable schema family must ultimately include:

- tool/schema version;
- evaluation request/scope/profile;
- resource identities and optional artifact byte sizes/digests, without treating local filesystem paths as stable identity;
- observations and source locations;
- provenance/relation claims and assessments;
- refget/SeqCol evidence;
- sequence-collection snapshots/reference contexts;
- contracts;
- constraints/evaluations;
- findings;
- conditions;
- evidence strength/polarity;
- verdict;
- analysis status;
- unresolved questions.

Every conclusion must trace to evidence IDs and, where profile/provider facts materially authorize that conclusion, to report-owned provenance/context records. Scientifically meaningful order must be preserved; collections that are semantically sets must be canonicalized for deterministic machine output.

`AnalysisStatus` is a separate execution/completeness axis from `CompatibilityVerdict`. `COMPLETE` means the requested implemented analysis ran to completion, not that it proved compatibility; a complete analysis may legitimately end `INDETERMINATE` because evidence is insufficient or ambiguous. `PARTIAL` is reserved for a requested analysis operation that could not actually complete, and `INVALID_INPUT` identifies input that cannot support a scientifically interpretable requested evaluation. Missing or ambiguous evidence that was successfully modeled by the reasoner is not, by itself, partial execution. A partial/invalid analysis must never be presented as unconditional positive compatibility.

Before that stable report model exists, Milestone 1 may expose provisional human and JSON diagnostics for local identity and derived-artifact checks. Those diagnostics must serialize only facts already represented by the implemented result models and must not synthesize whole-bundle verdicts, findings, conditions, or evidence IDs that the reasoner has not established. Milestone 7 does not silently change those legacy diagnostic commands; migration occurs only through an explicit CLI/reporting slice.

See [`docs/compatibility-report-contract.md`](docs/compatibility-report-contract.md) for the normative Milestone 7 reporting boundary.

---

## 11. Profile architecture

Profiles model consumer-specific operational requirements without changing the facts.

A profile may add requirements such as:

- exact sequence ordering;
- required local namespace;
- explicit assembly declaration;
- consumer-required metadata;
- accepted resource subset semantics.

A profile may not:

- redefine refget/SeqCol identity;
- declare `chr1`/`1` aliases without evidence;
- mutate observations;
- silently downgrade a content contradiction.

### UCSC preflight

Milestone 6 pins `ucsc-preflight` as the first concrete profile. Its first scope is native UCSC Genome Browser databases selected explicitly by database identifier. Assembly hubs, GenArk-specific behavior, bigBed/bigWig reference-property checks, persistent provider caching, and full track-hub reasoning remain later work; structural hub integrity should continue to be delegated to UCSC tooling such as `hubCheck` where appropriate.

The profile consumes a deterministic provider snapshot rather than allowing generic reasoning code to make network calls. The snapshot keeps canonical sequence names/lengths, authoritative aliases, optional content-derived target identities, dimension-specific completeness, and source/freshness provenance distinct. A UCSC database label, canonical name, alias, matching length, assembly accession, or download location is never sequence identity.

A fully positive UCSC-target relationship requires an independently comparable content identity linking each provider target sequence needed for a mandatory in-scope relationship to exactly one sequence in the complete FASTA anchor. Exact UCSC names do not bypass that rule. An authoritative provider alias may then resolve a resource-local name only when the alias is unique in complete provider naming context—requiring both a complete canonical catalog and complete alias evidence—and points to that content-bound target. Scope is applied only after provider-name uniqueness and full-anchor target uniqueness have been established. Distinct required UCSC canonical targets remain distinct coordinate axes even if provider content identities are equal; the profile cannot positively collapse them onto one FASTA sequence. Advisory relationships may remain unresolved without indirectly blocking an otherwise valid mandatory relationship.

Profile projection adds `RequirementOrigin.PROFILE` requirements or evidence-backed relationships and then reuses existing generic/core presence, length, identity, coordinate-bounds, VCF REF, BAM/CRAM dictionary, finding, and verdict behavior. It must not suppress a core-format requirement to obtain a positive result, and a direct content contradiction always outranks provider support. Milestone 6 uses a generic `SequenceBindingRequirement` plus anchor-owned `SequenceBindingValidationCapability` for consumers that require an authenticated local-to-anchor relationship rather than mere exact-name coincidence. `SequenceBindingMethod.AUTHORITATIVE_NAME` records the distinct provider-authorized naming path only after that provider target is independently content-bound to the anchor; its identity trace authenticates the provider-target-to-anchor leg and does not invent peer-owned sequence identity. Slice 5 reuses completed bundle bindings in BAM/CRAM dictionary classification so authoritative naming can resolve declared membership/order without being relabeled as M5 evidence; the independent M5-content dimension remains unresolved when the header lacks M5, and CRAM offline-reference planning retains its stricter exact-name/M5 requirement. Slice 6 makes provider acquisition an explicit deterministic snapshot boundary, and Slice 7 closes the adversarial exit matrix without adding provider-specific policy to generic reasoning.

Provider acquisition is an adapter concern. The same fixed snapshot must yield the same reasoning result with or without network access. Slice 6 makes that boundary concrete with a strict versioned JSON representation for already-materialized provider snapshots; loading frozen bytes and parsing the same materialized document produce the same immutable `UcscProviderSnapshot`, and callers may optionally pin the exact snapshot-file SHA-256. This artifact format is an adapter/reproducibility boundary, not a compatibility-report schema and not a live UCSC client. Failure to acquire provider evidence is represented by an unavailable snapshot at profile projection time: the profile still adds its mandatory binding requirements but contributes no provider validation capability, so those requirements remain unresolved rather than becoming biological incompatibilities. The ordinary quality gate uses frozen redistributable snapshots/fixtures, with any live-UCSC smoke path kept separate.

See [`docs/ucsc-preflight-profile.md`](docs/ucsc-preflight-profile.md) and RCHECK-070 in [`docs/check-specifications.md`](docs/check-specifications.md).

---

## 12. Validation strategy

### 12.1 Synthetic corpus-derived fixtures

Create small redistributable fixtures covering at least the 30 families in `docs/check-specifications.md`, including:

- exact identity;
- rename-only identity;
- same-name/different-content;
- order-only difference;
- subset/superset;
- stale `.fai`/`.dict`;
- M5 conflict;
- BAM/FASTA exact, alias, unresolved, and decoy-superset cases;
- VCF exact plus isolated, localized, distributed, and systematic REF conflicts;
- GTF/GFF exact, verified-alias, unresolved-name, proven-absence, bounds, and circular cases;
- contradicted provenance;
- non-model/custom references;
- negative controls;
- cases that must remain `INDETERMINATE`.

### 12.2 Cross-tool validation

Where relevant, compare behavior against:

- GA4GH/refget/SeqCol reference/compliance behavior;
- GATK `CheckReferenceCompatibility`;
- bcftools reference checks;
- SAM/Picard tooling;
- UCSC authoritative alias data;
- appropriate GFF/GTF validators.

RefCompat need not match another tool's final wording when its scope differs, but conflicting underlying facts require investigation.

### 12.3 Safety properties

Target properties include:

- zero false `COMPATIBLE` results on known hard conflicts in the fixture suite;
- near-zero/zero false verified aliases;
- no metadata-to-verified promotion without appropriate evidence;
- correct `INDETERMINATE` behavior when evidence is insufficient;
- conflict localization;
- non-human/custom-reference operation;
- deterministic offline core behavior.

---

## 13. Security, privacy, and reproducibility

- Local analysis should not upload genomic content by default.
- Optional network enrichment should be explicit and report what was queried.
- Artifact and standards identities should be recorded distinctly.
- A future portable compatibility/reference manifest may record exact identities, resource roles, derivations, and evaluation metadata without pretending to solve whole-workflow reproducibility.

---

## 14. Implementation principles

1. Model facts before workflows.
2. Keep external library types at adapter boundaries.
3. Prefer small typed domain objects over generic dictionaries.
4. Add parsers/checks one format at a time.
5. Preserve source locations/provenance for scientific transparency.
6. Make uncertainty explicit.
7. Keep comments/docstrings focused on non-obvious scientific and coordinate invariants.
8. Reference standards/primary sources near materially derived implementation rules.
9. Resist plugin/manager/factory frameworks until a concrete second implementation requires them.
10. Use synthetic or clearly redistributable fixtures derived from observed failure patterns.

---

## 15. Licensing and dependency policy

RefCompat is licensed under Apache-2.0. Runtime dependencies should preferentially use permissive licenses such as Apache-2.0, MIT, BSD-2-Clause, or BSD-3-Clause. Dependencies with copyleft, source-available, noncommercial, or custom/restrictive terms require explicit review before adoption.

The current direct runtime dependency set is deliberately narrow:

```text
refget>=0.12,<0.13
pysam>=0.24,<0.25
```

The upper bound protects the adapter boundary while the pre-1.0 `refget` Python API is evolving. `refget` itself brings transitive runtime dependencies; "narrow" here describes RefCompat's direct dependency surface, not the total installed package count. Optional refget server/database extras are not required.

Format dependencies are introduced by milestone rather than preinstalled speculatively. `.fai` and `.dict` begin with narrow readers; VCF and BAM/CRAM use bounded `pysam>=0.24,<0.25` behind narrow adapter boundaries; GTF/GFF3 begins with a narrow streaming parser for the fields and directives RefCompat actually evaluates.

See [`docs/dependency-policy.md`](docs/dependency-policy.md).

---

## 16. Python, packaging, CLI, and model baseline

The initial repository baseline is:

- Python >=3.10, with Python 3.11+ recommended for new environments;
- repository development interpreter pinned to Python 3.14.7;
- CI on Python 3.10, 3.11, 3.12, 3.13, and 3.14;
- `uv` for environment management, locking, command execution, and builds;
- `uv_build` as the pure-Python build backend;
- committed `uv.lock`;
- pytest for tests;
- Ruff for linting and formatting;
- mypy in strict mode;
- standard-library immutable dataclasses/enums/typed value objects for the core domain model;
- standard-library `argparse` for the initial CLI;
- explicit RefCompat-owned serialization for machine-readable reports.

A stable JSON Schema is not frozen before the report model stabilizes. Schema/versioning remains a compatibility boundary, but the project will not add a validation framework merely to generate an early schema.

The source distribution explicitly excludes local/private research and maintainer-note directories as defense in depth in addition to `.gitignore`.

See [`docs/development.md`](docs/development.md), ADR 0012, and ADR 0013.

---

## 17. Remaining implementation decisions

No unresolved tooling choice blocks the next implementation slice. The remaining decisions are deliberately milestone-specific and should be resolved when their evidence exists, including:

1. the first stable machine-readable report schema/versioning commitment;
2. whether later performance or format requirements justify additional parser/storage dependencies.

---

## 18. Next implementation sequence

1. implement RefCompat-owned resource/observation/identity/evidence vocabulary (complete);
2. implement `ReferenceIdentityProvider` and the local refget/SeqCol adapter (complete);
3. implement FASTA ↔ `.fai` and FASTA ↔ `.dict` checks (complete);
4. build deterministic known-answer and corpus-derived Milestone 1 exit fixtures (complete);
5. produce human + minimal machine-readable reports (complete);
6. implement the core requirements/capabilities reasoning slice (complete);
7. implement generalized evidence aggregation, structured interpretation, FASTA-anchored reference-context/bundle reasoning, top-level verdict aggregation, and conflict-core extraction (complete);
8. implement exhaustive VCF reference reasoning, conservative sequence binding, and whole-bundle projection (complete);
9. implement BAM/CRAM header observation, contract projection, sequence binding, dictionary relationships, and conservative offline CRAM planning (complete);
10. implement GTF/GFF3 observation, generic coordinate-bounds reasoning, anchor validation, verified sequence binding where evidence exists, and GFF3-specific region/circular semantics in reviewable slices (complete);
11. implement the Milestone 6 `ucsc-preflight` provider snapshot, authoritative-alias relationship, profile projection, and representative end-to-end paths in reviewable slices;
12. incorporate implementation feedback into the design as concrete edge cases expose missing constraints or evidence types.

---

## References

Primary/standards references should be preferred in implementation documentation.

- GA4GH Refget Sequence Collections v1.0.0: https://ga4gh.github.io/refget/seqcols/
- Refget Python project documentation: https://refgenie.org/refget/
- Local digest documentation: https://refgenie.org/refget/using-services/digests/
- Refget Python source: https://github.com/refgenie/refget
- GA4GH/Samtools HTS specifications index: https://samtools.github.io/hts-specs/
- SAM specification: https://samtools.github.io/hts-specs/SAMv1.pdf
- VCF v4.5 specification: https://samtools.github.io/hts-specs/VCFv4.5.pdf
- Sequence Ontology GFF3 specification: https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
- Ensembl GFF/GTF format documentation: https://www.ensembl.org/info/website/upload/gff.html
- GENCODE GTF format documentation: https://www.gencodegenes.org/pages/data_format.html
- NCBI GFF3 format notes: https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/file-formats/annotation-files/about-ncbi-gff3/
- UCSC custom-track FAQ (`chromAlias` and supported alternate chromosome names): https://genome.ucsc.edu/FAQ/FAQcustom
- UCSC Assembly Hub User Guide (`chromAlias.txt` format): https://genome.ucsc.edu/goldenPath/help/assemblyHubHelp.html
- UCSC REST API: https://genome.ucsc.edu/goldenpath/help/api.html
- UCSC `hg38` bigZips distribution notes: https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/
- UCSC Track Hub User Guide (`hubCheck` boundary): https://genome.ucsc.edu/goldenPath/help/hgTrackHubHelp

---

## Design status

The broad research, implementation-readiness, repository-tooling, Milestone 1 identity/derived-artifact work, Milestone 2 reasoning foundation, Milestone 3 VCF reasoning, and Milestone 4 BAM/CRAM reasoning are complete. RefCompat now implements explicit anchor-driven evaluation scope; typed requirements/capabilities and constraint evaluations; qualitative evidence aggregation; structured findings/conditions; a complete-FASTA `ReferenceContext` with content-verified `SequenceBinding` and whole-bundle orchestration; categorical mandatory-constraint verdict aggregation; and compact decisive conflict-core extraction. VCF support adds exhaustive REF validation plus conservative MD5-backed cross-name binding. BAM/CRAM support adds declared dictionary projection, conservative M5-backed binding, multidimensional dictionary relationship classification, and deterministic offline-reference planning without reheadering or realignment.

Milestone 5's annotation contract, implementation slices, integration/adversarial exit coverage, internal-review hardening, external milestone-boundary review, MAJOR circular-landmark correction, and targeted external follow-up are complete; the follow-up confirmed the structural `region` landmark correction and closed Milestone 5. GTF/GFF3 are observed through a narrow streaming boundary that preserves native one-based closed coordinates, summarizes sparse used seqids without constructing gene-model hierarchy, preserves raw plus decoded GFF3 seqids, records reference-relevant sequence-region/provenance/circular facts, recognizes embedded-FASTA boundaries, streams embedded sequence name/length/MD5 summaries, and supports gzip input without relying on a filename suffix. The generic reasoning layer includes scalable anchor-named `CoordinateBoundsRequirement` values, anchor-owned exhaustive validation capabilities, Tier-B structural coordinate evidence, reasoner-owned exhaustive sequence-identity absence, bundle supplemental-capability handling, coordinate-conflict findings, and normal verdict/conflict-core propagation without embedding GTF/GFF3 policy in generic code. Annotation projection creates mandatory referenced-seqid presence requirements, mandatory identity requirements for relevant embedded sequence content, and one exhaustive coordinate requirement. Exact names or full-anchor-unique content-verified bindings resolve feature/region coordinates; scope cannot manufacture uniqueness or absence; embedded-content conflicts produce Tier-A identity evidence when directly comparable and may otherwise produce Tier-A exhaustive presence-absence evidence; FASTA supersets remain compatible with sparse annotations; and raw unfamiliar names remain unresolved. GTF/GFF3 may additionally receive annotation-owned `CONTENT_DERIVED` identity capabilities from an independently verified upstream source for conservative binding or exhaustive absence proof; those capabilities do not become invented format declarations or requirements. Absence requires complete full-anchor coverage for at least one local content-identity scheme and no positive full-anchor match from any local content-derived identity, is retained separately from caller-supplied supplemental validations, and becomes Tier-A contradiction to mandatory presence. GFF3 circular-origin bounds are interpreted only from structural circular `region` landmark evidence with one well-formed `Is_circular=true` control attribute; malformed/repeated controls are invalid input, proven standard single-wrap features are circular-representable, ambiguous landmark evidence remains unresolved, and unrelated circular features do not weaken ordinary conflicts. The planned Slices 1–4 internal-review checkpoint is complete, Slice 5 region/provenance, Slice 6 embedded-FASTA identity/binding, Slice 7 circular semantics, and Slice 8 exit fixtures are integrated, and the final internal review hardened malformed circular metadata plus the documented proven-absence exit guarantee. Missing candidate evidence remains unresolved unless explicit evidence proves a contradiction, ambiguous sequence identity never manufactures a binding or absence, peer resources do not vote on reference identity, advisory constraints do not veto mandatory compatibility, evidence is never converted into a numeric score, conditions qualify only otherwise-positive verdicts, and failure reporting excludes non-decisive mismatch noise. Milestone 7 now pins analysis status and stable `CompatibilityReport` serialization as the next implementation boundary. The Milestone 6 UCSC-preflight scientific contract is implemented through its adversarial exit suite: native UCSC database selection is explicit, provider facts are consumed through a deterministic provenance-bearing snapshot, authoritative aliases remain naming evidence, and a fully positive UCSC target relationship requires an independent content-derived bridge to the selected FASTA anchor before provider aliases can resolve peer names. The first end-to-end VCF path passed its planned internal scientific/code checkpoint and targeted external review; Slice 5 reuses the same validated relationship boundary in BAM/CRAM dictionary interpretation without weakening CRAM offline-reference requirements; Slice 6 pins network-independent snapshot behavior; and Slice 7 exercises the milestone proof chain across insufficient, contradictory, ambiguous, scoped, and unavailable evidence. The final internal milestone review additionally hardened incomplete-catalog alias authorization, distinct-canonical-target collapse, and advisory isolation across that collision guard; the required external milestone review is complete, found no MAJOR issue, and assessed the repository safe to begin M7. Milestone 7 therefore begins with a stable report/workflow contract rather than new scientific-format reasoning. Slices 2–3 implement the immutable analysis-status/issues and `CompatibilityReport` root plus an explicit deterministic draft JSON projection. Slice 4 internal scientific/API review hardened the report boundary and froze the first stable core schema at `1.0.0` with a separate stable serializer, packaged JSON Schema, and known-answer fixtures. Slice 5 now advances the stable report additively to `1.1.0` with report-owned observations, alignment relationship summaries, and UCSC provider/source/profile provenance while retaining exact schema `1.0.0`; draft revision 3 remains explicitly provisional. Human/CLI workflow reporting is the next M7 surface. Additional broad corpus collection is not currently justified unless implementation exposes a new unresolved category, a profile requires targeted evidence, or a separate prevalence study becomes a project goal.
