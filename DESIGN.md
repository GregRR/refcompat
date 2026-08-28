
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
9. **Consumer-specific requirements belong in profiles.** A future UCSC preflight profile is a preferred early showcase after the core stabilizes.
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

Evidence-backed mapping from a resource-local name to one anchor-local sequence. The first implementation derives a binding only from comparable content identity that resolves uniquely across the complete FASTA anchor snapshot; explicit sequence scope may hide a unique target but must never manufacture uniqueness by hiding duplicate-content alternatives. Conflicting local identities remain unbound. Alias relationships are derived from bindings rather than blind string substitution.

Sequence identity capabilities carry required explicit provenance. `CONTENT_DERIVED` identities may satisfy sequence-identity requirements and may appear in the FASTA anchor context; `DECLARED_METADATA` identities are claims that may support conservative binding but cannot become candidate reference authority. `ReferenceContext` independently verifies that its anchor identity capabilities exactly match the selected FASTA snapshot. This distinction applies to VCF `##contig md5` now and is the required boundary for BAM/CRAM `@SQ M5` in Milestone 4.

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

Whole-bundle orchestration now accepts these pair-derived validation capabilities through an explicit supplemental-capability channel rather than through peer `ResourceContract` capabilities. Supplemental reference-base capabilities must be owned by the selected FASTA anchor, describe a scoped resource, match an in-scope `ReferenceBaseRequirement`, and be uniquely applicable to that requirement. `BundleReasoningResult` retains the supplemental capabilities separately and verifies that bundle constraints cite only ordinary anchor capabilities or those explicitly supplied supplemental capabilities. This permits the existing categorical verdict and conflict-core layers to consume direct REF evidence without changing their policy: all-match validation can contribute to `COMPATIBLE`, a proven mismatch remains a hard `INCOMPATIBLE` basis, and incomplete direct validation remains `INDETERMINATE`. The VCF-specific pattern layer is descriptive only: it does not change generic constraint truth, bundle verdicts, conflict cores, or infer a cause. Verified VCF aliases are now derived only from uniquely matched `##contig` MD5 identity (with complete anchor MD5 coverage, full-anchor uniqueness, and length-consistency checks), and exhaustive REF comparison can use those bindings while preserving any hard mismatch. A syntactically valid MD5 declaration on an actually used contig is also projected as a mandatory sequence-identity requirement, so a directly comparable contradictory header digest cannot disappear merely because it failed to produce a binding. Report/CLI presentation remains deferred.

### RCHECK-060 — GTF/GFF3 ↔ FASTA

Resolve in-scope seqids, verify coordinate bounds, inspect GFF3 sequence-region/provenance directives, quantify affected features, and conservatively handle circular-coordinate semantics. Do not become a gene-model validator.

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

The eventual stable schema should include:

- tool/schema version;
- evaluation request/scope/profile;
- resource identities and optional artifact digests;
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

Every conclusion must trace to evidence IDs.

Before that stable report model exists, Milestone 1 may expose provisional human and JSON diagnostics for local identity and derived-artifact checks. Those diagnostics must serialize only facts already represented by the implemented result models and must not synthesize whole-bundle verdicts, findings, conditions, or evidence IDs that the reasoner has not established.

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

After core stability, UCSC is the preferred early showcase profile. Likely checks include explicit assembly/db selection, authoritative alias resolution, bounds, VCF REF evidence, BAM/CRAM dictionary coherence, and later big* reference properties. Structural track-hub checks should be delegated to existing UCSC tools where appropriate rather than duplicated.

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
- GTF/GFF exact, alias, missing-sequence, bounds, and circular cases;
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

No unresolved tooling choice blocks the first implementation slice. The remaining decisions are deliberately milestone-specific and should be resolved when their evidence exists, including:

1. exact CRAM offline behavior when required reference content is unavailable;
2. exact first UCSC profile subset;
3. the first stable machine-readable report schema/versioning commitment;
4. whether later performance or format requirements justify additional parser/storage dependencies.

---

## 18. Next implementation sequence

1. implement RefCompat-owned resource/observation/identity/evidence vocabulary (complete);
2. implement `ReferenceIdentityProvider` and the local refget/SeqCol adapter (complete);
3. implement FASTA ↔ `.fai` and FASTA ↔ `.dict` checks (complete);
4. build deterministic known-answer and corpus-derived Milestone 1 exit fixtures (complete);
5. produce human + minimal machine-readable reports (complete);
6. implement the core requirements/capabilities reasoning slice (complete);
7. implement generalized evidence aggregation, structured interpretation, FASTA-anchored reference-context/bundle reasoning, top-level verdict aggregation, and conflict-core extraction (complete);
8. add VCF, BAM/CRAM, and GTF/GFF inspectors one at a time;
9. incorporate implementation feedback into the design as concrete edge cases expose missing constraints or evidence types.

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
- NCBI GFF3 format notes: https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/file-formats/annotation-files/about-ncbi-gff3/

---

## Design status

The broad research, implementation-readiness, repository-tooling, Milestone 1 identity/derived-artifact work, and Milestone 2 reasoning foundation are complete. Milestone 3 core VCF reasoning now covers VCF/VCF.gz context observation, exhaustive REF validation, verified MD5-backed cross-name binding/revalidation, format-neutral projection, whole-bundle ingestion, and descriptive conflict-pattern interpretation. RefCompat now implements explicit anchor-driven evaluation scope; typed requirements/capabilities and constraint evaluations; qualitative evidence aggregation; structured findings/conditions; a complete-FASTA `ReferenceContext` with content-verified `SequenceBinding` and whole-bundle orchestration; categorical mandatory-constraint verdict aggregation; and compact decisive conflict-core extraction. Missing candidate evidence remains unresolved unless an explicit capability proves a contradiction, ambiguous sequence identity never manufactures a binding, peer resources do not vote on reference identity, advisory constraints do not veto mandatory compatibility, evidence is never converted into a numeric score, conditions qualify only otherwise-positive verdicts, and failure reporting excludes non-decisive mismatch noise. Analysis status and stable `CompatibilityReport` serialization remain later boundaries. Additional broad corpus collection is not currently justified unless implementation exposes a new unresolved category, a profile requires targeted evidence, or a separate prevalence study becomes a project goal.
