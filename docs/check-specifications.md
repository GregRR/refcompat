
# RefCompat initial check specifications

These are **implementation contracts**, not runtime `ResourceContract` objects. Each check specification defines what an implementation is allowed to observe, what requirements/capabilities it may produce, how it affects evidence and constraints, and what it must not infer.

## Shared execution model

Every implemented check should expose, directly or through the report model:

- check ID/version;
- purpose;
- applicable resources;
- prerequisites;
- observations extracted;
- capabilities emitted;
- requirements emitted;
- constraints evaluated;
- evidence generated;
- findings generated;
- check execution status;
- compatibility effect through constraint evaluations;
- indeterminate cases;
- safety/prohibited inferences.

Per-check execution status is separate from compatibility and should distinguish at least:

- `COMPLETE`
- `PARTIAL`
- `SKIPPED`
- `INVALID_INPUT`

An unexpected software exception is an implementation failure and must not be converted into scientific evidence.

---

## RCHECK-000 — Resource inventory and provenance

### Purpose

Establish what supplied artifacts claim to be, what can be directly observed about those claims, and which claimed relationships among resources are supported, verified, contradicted, or unresolved.

### Inputs

All supplied resources.

### Typical observations/claims

- path, filename, type, size, optional artifact checksum;
- VCF `##reference` and `##contig` metadata;
- SAM/BAM/CRAM `@SQ AS`, `UR`, `SP`, `AN`, `M5` where present;
- GFF3 assembly/provider directives;
- annotation provider/release metadata;
- embedded source URLs;
- user/collaborator declarations.

Filenames such as `GRCh38.fa` remain heuristic context, not proof.

### Possible findings

- `DECLARED_REFERENCE_SUPPORTED`
- `DECLARED_REFERENCE_VERIFIED`
- `DECLARED_REFERENCE_CONTRADICTED`
- `RESOURCE_PROVENANCE_UNRESOLVED`
- `MIXED_DECLARED_REFERENCE_CONTEXT`
- `DERIVATION_CLAIM_CONTRADICTED`

### Verdict rules

Conflicting labels alone do not prove incompatibility. Content evidence governs identity when metadata conflicts.

If resources are otherwise proven reference-compatible but carry materially false provenance, the result may be `COMPATIBLE_WITH_CONDITIONS` or an advisory finding depending on whether the provenance is an in-scope mandatory requirement. Conflicting claims with inadequate identity evidence can contribute to `INDETERMINATE`.

### Must not infer

- filename says `hg38`, therefore content is hg38;
- provider mismatch means reference incompatibility;
- many matching metadata fields outweigh a content-derived contradiction.

---

## RCHECK-010 — FASTA anchor identity

### Purpose

Establish the strongest local description of the v0.1 reference anchor.

### Observations/capabilities

Per sequence:

- local name;
- ordinal/order;
- length;
- refget sequence identity;
- legacy MD5 where useful and available.

At collection level:

- SeqCol identity;
- SeqCol component relationships/digests needed by RefCompat;
- sequence order;
- coordinate-system representation.

Capabilities include sequence presence, length, identity, name binding, coordinate bounds, base lookup, and order.

### Verdict effect

FASTA inspection primarily establishes capabilities and reference context. By itself it normally does not answer a multi-resource compatibility question.

Malformed/unreadable anchor input affects analysis status (`INVALID_INPUT`) rather than becoming an `INCOMPATIBLE` biological verdict. A usable authoritative FASTA anchor must contain at least one named sequence and must not reuse the same local sequence name for multiple records; ambiguous local identifiers are an input error, not a naming relationship for the reasoner to guess through.

### Must not infer

A content identity does not establish that the reference is scientifically preferable for a study.

---

## RCHECK-020 — FASTA ↔ `.fai` integrity

### Purpose

Determine whether a supplied FASTA index is actually the index of the supplied FASTA representation.

### `.fai` observations

- sequence name;
- sequence length;
- byte offset;
- bases per FASTA line;
- bytes per FASTA line.

### Mandatory requirements for an explicitly paired `.fai`

- same sequence count;
- same local names;
- same order;
- same lengths;
- same byte-layout/index geometry where the representation permits verification.

### Findings

- `FAI_VERIFIED`
- `FAI_SEQUENCE_COUNT_MISMATCH`
- `FAI_NAME_MISMATCH`
- `FAI_LENGTH_MISMATCH`
- `FAI_ORDER_MISMATCH`
- `FAI_LAYOUT_MISMATCH`
- `STALE_FASTA_INDEX` only when separate provenance evidence supports the stale-artifact interpretation

The structural checker itself reports exact differences rather than guessing why the index differs. The initial implementation computes expected byte geometry for uncompressed FASTA; gzip/BGZF reference-index verification is explicitly unsupported until a compatible compressed-reference path is implemented. A named zero-length FASTA sequence is likewise reported as a geometry-computation limitation because the current refget/gtars calculator supplies no FAI line metadata for that record.

### Critical rule

Verified biological aliases do **not** satisfy an exact derived-artifact requirement. An index naming `1` is not the valid `.fai` for a FASTA whose indexed local identifier is `chr1`, even if those labels can be proven to denote the same biological sequence elsewhere.

A proven mismatch in an explicitly evaluated FASTA/FAI pair is an in-scope hard incompatibility for operations relying on that pair.

---

## RCHECK-030 — FASTA ↔ SAM/Picard sequence dictionary (`.dict`)

### Purpose

Determine whether a supplied sequence dictionary exactly represents the supplied FASTA anchor while keeping structural correspondence, sequence-content identity, declared aliases, and provenance metadata distinct.

### Observations

For each `@SQ`, where present:

- `SN`;
- `LN`;
- `M5`;
- `AN`;
- `AS`;
- `UR`;
- `SP`;
- `TP`;
- `AH`;
- ordinal/order.

The initial parser accepts an optional first `@HD` plus `@SQ` records and deliberately does not become a general SAM parser. SAM requires `SN` and `LN`; all primary `SN` and individual `AN` names across the dictionary must be distinct; `LN` must be in `[1, 2^31-1]`; and `@SQ` order defines reference ordering.

### Expected dictionary

Expected `SN`/`LN`/`M5` records are built from the already-computed complete FASTA `SequenceCollectionSnapshot`. The `.dict` check does not reread or rehash the FASTA.

A FASTA sequence that lacks a usable local name, positive SAM-representable length, or M5 cannot form the authoritative expected dictionary for this check. In particular, SAM `LN` cannot represent a zero-length sequence; that is a computation limitation, not a provider incompatibility or biological contradiction.

### Evidence

- conflicting `M5`: Tier-A content contradiction under SAM M5 semantics;
- unique matching M5 under different primary names and with matching lengths: Tier-A content-identity support, but **not** exact companion-artifact satisfaction;
- unique cross-name matching M5 with disagreeing lengths: retain an explicit M5/LN inconsistency rather than dropping the relationship or promoting it to clean identity support;
- name/membership/order/length conflict: Tier-B structural contradiction;
- exact name/length/order agreement with missing dictionary M5: structural support with unresolved content verification;
- `AN`, `AS`, `UR`, `SP`, `TP`, and `AH`: preserved metadata/claims for later reasoning.

A declared alias never overrides exact primary-name correspondence. Likewise, assembly/species/URI metadata cannot override an M5 contradiction.

### Structural differences

The evaluator localizes:

- record-count differences;
- missing sequences;
- extra sequences;
- order-only differences when sequence membership is otherwise identical;
- length conflicts;
- M5 conflicts.

Missing/extra records do not also generate spurious order findings merely because record indices shift.

### Missing M5

Missing `M5` is an evidence gap, not an incompatibility by itself. A dictionary can therefore be structurally verified while exact content correspondence remains unverified.

### Cross-name M5 identity

When an expected missing primary name and an observed extra primary name carry the same M5 and length, RefCompat may surface that content identity only when the digest is unique on both sides. Repeated identical sequence content is not force-matched across names.

If a unique cross-name pair carries the same M5 but disagreeing `LN` values, RefCompat retains that M5/LN inconsistency explicitly. It does not silently drop the shared-digest relationship, does not promote the pair to an uncomplicated identity match, and does not infer which field or upstream artifact is wrong.

Even an unambiguous cross-name M5 identity does not make the `.dict` an exact companion because the primary `SN` values still differ.

### Provenance and stale-artifact rule

The structural/content checker reports what differs and preserves metadata. It does not label the dictionary `stale` merely because it conflicts with the FASTA. `STALE_SEQUENCE_DICTIONARY` requires separate provenance evidence that the dictionary was derived from an earlier or different reference artifact.

### Safety

RefCompat does not automatically rename dictionary sequences, rewrite `@SQ` metadata, regenerate the dictionary, or modify the FASTA.

---

## RCHECK-040 — BAM/CRAM ↔ FASTA reference context

### Purpose

Determine what reference environment the alignment header declares and whether its sequence requirements reconcile with the FASTA anchor.

### v0.1 scope

Header/reference-dictionary focused. It does not validate alignment correctness, mapping quality, read biology, or perform reheadering/remapping.

### Observations

From `@SQ`, where present:

- `SN`, `LN`, `M5`, `AN`, `AS`, `UR`, `SP`, `AH`, `TP`, order.

`@PG` records may contribute provenance claims but do not establish sequence identity.

### Requirements

For each declared reference sequence:

- a compatible sequence must exist when the evaluation scope requires it;
- declared length must be compatible;
- M5 must agree where comparable;
- local name must resolve exactly or through verified sequence binding;
- order is represented separately and becomes mandatory only when scope/profile requires it.

### Completeness caution

The header describes the declared alignment reference environment; header-only inspection does not establish whether reads actually use every declared sequence.

A BAM declaring primary+decoy sequences against a primary-only FASTA should therefore report verified shared scope plus unresolved/unsatisfied additional-sequence requirements according to the explicit evaluation scope. RefCompat must not guess that decoys are irrelevant.

### Representative outcomes

- same name, conflicting content checksum -> `UNSATISFIED` hard conflict;
- same content identity, different local name -> `SATISFIED` via verified sequence identity/alias;
- same name+length without content checksum -> strong structural compatibility, not exact proof;
- different names, same length, no identity/alias evidence -> `UNRESOLVED`.

### Safety

Do not recommend blind `samtools reheader` or equivalent solely from familiar-looking naming patterns.

---

## RCHECK-050 — VCF ↔ FASTA

### RCHECK-050A — header/reference context

**Implementation status:** VCF/VCF.gz header metadata and exhaustive CHROM-usage observation are implemented; compatibility interpretation remains in later RCHECK-050 slices.

Inspect:

- `##reference`;
- `##contig ID`;
- contig length;
- contig md5 where present;
- contig assembly/URL metadata;
- actual `CHROM` usage.

`##reference` is a provenance claim, not proof. Missing `##contig` declarations do not by themselves prove that a valid VCF/reference relationship cannot be evaluated from the records.

### RCHECK-050B — exhaustive REF ↔ FASTA validation

**Implementation status:** exhaustive direct record classification is implemented for exact-name
resolution against an uncompressed FASTA anchor. Format-neutral contract/evidence projection is
implemented in RCHECK-050C; whole-bundle ingestion is implemented in RCHECK-050D; threshold-free
conflict-pattern interpretation is implemented in RCHECK-050E; verified-binding revalidation remains
later Milestone 3 work.

Authoritative v0.1 REF checking is **exhaustive**.

Each record contributes requirements for:

- sequence resolution;
- coordinate validity;
- FASTA bases at POS matching REF.

Per-record outcomes include:

- `MATCH`
- `MISMATCH`
- `OUT_OF_BOUNDS`
- `UNRESOLVED_SEQUENCE`

The direct result aggregates counts and affected sequences while retaining every non-match record
for traceability. Matching records are counted rather than retained individually.

VCF POS is converted explicitly to a zero-based half-open FASTA interval using POS and `len(REF)`.
VCF 4.5 telomere sentinel positions 0 and N+1 are represented as `OUT_OF_BOUNDS` in this direct
comparison layer because no ordinary FASTA REF interval exists there; that state alone is not a
claim that the VCF syntax is invalid. FASTA IUPAC ambiguity codes outside A/C/G/T/N are reduced to
the alphabetically first represented concrete base as required for VCF REF representation.

Authoritative base access computes temporary FAI geometry from the supplied FASTA itself and does
not trust or modify an adjacent user-supplied `.fai`.

### RCHECK-050C — format-neutral contract/evidence projection

**Implementation status:** implemented for actual CHROM usage and exhaustive direct REF results.
Verified-binding revalidation remains later Milestone 3 work. Whole-bundle ingestion of
pair-derived reference-base capabilities is implemented in RCHECK-050D, and threshold-free
conflict-pattern interpretation is implemented in RCHECK-050E.

Projection rules:

- each actually used `CHROM` name creates one mandatory `SequencePresenceRequirement`;
- unused `##contig` declarations do not create presence requirements;
- the complete VCF record set creates one mandatory `ReferenceBaseRequirement` that names the
  selected FASTA anchor, not one requirement per record;
- exhaustive REF checking creates one FASTA-anchor-owned
  `ReferenceBaseValidationCapability` describing the VCF/FASTA pair;
- any proven REF mismatch makes the generic reference-base constraint `UNSATISFIED` and emits
  Tier-A conclusive contradiction evidence;
- unresolved-name or out-of-bounds-only direct results remain `UNRESOLVED` and do not fabricate
  support or contradiction evidence;
- a non-empty all-match validation is `SATISFIED` with `EXHAUSTIVE_DIRECT`;
- an empty VCF has a `NOT_APPLICABLE` reference-base requirement.

The pair-derived capability is deliberately kept outside the VCF `ResourceContract`: it belongs
to the selected FASTA anchor and is evidence produced by comparing the two resources. Generic
comparability also requires that capability owner to match the anchor named by the requirement,
so a capability from another FASTA is filtered out rather than allowed to satisfy the constraint.
Peer resources still cannot vote against or replace the FASTA anchor.

The original `VcfRefValidationResult` remains attached to the projection. RCHECK-050E derives a
VCF-specific conflict-pattern summary from those local outcomes without weakening the generic
hard-conflict rule or expanding large VCFs into per-record contract objects.

### RCHECK-050D — pair-derived whole-bundle orchestration

**Implementation status:** implemented for supplemental exhaustive reference-base capabilities.
Threshold-free mismatch-pattern interpretation is implemented in RCHECK-050E; verified-alias
revalidation remains later Milestone 3 work.

The generic `reason_bundle()` orchestrator accepts pair-derived
`ReferenceBaseValidationCapability` values through an explicit supplemental-capability channel.
They are not inserted into any peer resource contract and therefore cannot become competing
reference authorities. The orchestrator requires each supplemental capability to:

- belong to the selected FASTA anchor;
- describe a resource inside the explicit evaluation scope;
- match at least one in-scope `ReferenceBaseRequirement`;
- have a unique capability ID; and
- be the only exhaustive supplemental candidate for any one reference-base requirement.

Every `ReferenceBaseRequirement` encountered by whole-bundle reasoning must itself name the
request's selected FASTA anchor. A missing supplemental capability remains `UNRESOLVED`; an
unused or cross-wired capability is rejected rather than silently ignored.

`BundleReasoningResult` retains the supplemental capabilities separately from the per-resource
contracts and independently verifies that constraints cite only ordinary anchor capabilities or
explicitly supplied supplemental capabilities. The existing evidence, interpretation, verdict, and
conflict-core layers then operate unchanged: all-match exhaustive validation can support a positive
mandatory result, any proven mismatch remains a decisive hard contradiction, and incomplete
validation remains unresolved without fabricated evidence.

### RCHECK-050E — REF conflict-pattern interpretation

**Implementation status:** implemented for exhaustive exact-name direct validation. Verified-alias
revalidation and stable report/CLI presentation remain later Milestone 3 work.

`classify_vcf_ref_conflicts()` interprets the distribution of already-proven direct REF mismatches
without changing the generic `ReferenceBaseRequirement` state or bundle verdict. It uses no
mismatch-rate threshold and makes no causal inference.

For a complete direct validation:

- no mismatch -> `NONE`;
- exactly one mismatch -> `ISOLATED`;
- multiple mismatches confined to one sequence or a strict subset of the directly compared
  sequence scope -> `LOCALIZED`;
- multiple mismatches affecting every sequence in a directly compared multi-sequence scope,
  while at least one record matches -> `DISTRIBUTED`;
- every directly comparable record mismatches across a multi-sequence scope -> `SYSTEMATIC`.

If any record is `UNRESOLVED_SEQUENCE` or `OUT_OF_BOUNDS`, the pattern is `UNCLASSIFIED` because
RefCompat cannot claim to know the complete distribution. Any already-proven mismatch remains a
hard contradiction; only the VCF-specific pattern label is withheld.

`SYSTEMATIC` is a strong threshold-free claim that every directly comparable record mismatches
across a multi-sequence scope. `DISTRIBUTED` covers broad cross-sequence conflict where some direct
matches remain. Neither label infers a wrong assembly or other cause. The pattern summary retains
directly compared/mismatch/unresolved counts plus deterministic compared and affected sequence-name
sets for later reporting.

### Hard-conflict rule

A proven REF mismatch is a hard local reference conflict. A small mismatch fraction does not mathematically cancel it. The distribution of mismatches may support interpretation such as isolated versus systematic conflict.

VCF-specific descriptive pattern labels are `ISOLATED`, `LOCALIZED`, `DISTRIBUTED`, and
`SYSTEMATIC` as defined
in RCHECK-050E. They are not additional generic findings or verdict states.

### Safety

Do not automatically swap REF/ALT, flip strand, rewrite alleles, delete mismatches, or “fix” records.

---

## RCHECK-060 — GTF/GFF3 ↔ FASTA

### Purpose

Determine whether every in-scope reference-coordinate statement made by the annotation can be represented against the supplied FASTA.

This is not a biological gene-model validator.

### Observations

Per resource:

- seqids used;
- feature count by seqid;
- minimum/maximum coordinates;
- provider/release/assembly claims.

For GFF3, where present:

- `##sequence-region`;
- genome-build/provenance directives.

### Requirements

For each in-scope seqid/feature:

- sequence presence;
- exact or verified alias/name resolution;
- coordinate bounds;
- annotation-declared region bounds where applicable.

### Alias handling

`1` versus `chr1` can be satisfied through `SatisfactionMode.VERIFIED_ALIAS` only when evidence verifies the relationship. String resemblance is insufficient.

### Missing sequence

Under default whole-resource scope, a feature on a missing patch/unplaced sequence is an unsatisfied mandatory requirement. It becomes conditional only if the evaluation scope explicitly excludes that sequence class.

### Bounds and circular sequences

Ordinary feature coordinates extending beyond sequence length are a hard bounds conflict. Defined circular-origin semantics must be handled explicitly or conservatively reported unresolved; RefCompat must not produce a false out-of-bounds finding for a valid circular case.

### Explicit non-goals

Core v0.1 does not judge:

- exon/transcript biological correctness;
- feature hierarchy repair;
- gene naming quality;
- GENCODE versus Ensembl biological equivalence;
- featureCounts/Cell Ranger/other consumer-specific dialect requirements.

Those belong to dedicated annotation validators or consumer profiles.

---

## RCHECK-100 — Whole-bundle reference-context coherence

### Purpose

Given a set such as:

```text
genome.fa
genome.fa.fai
genome.dict
sample.bam
variants.vcf.gz
genes.gtf
known-sites.vcf.gz
```

determine whether one explicit anchor reference context satisfies all in-scope mandatory requirements.

### v0.1 anchor rule

The explicitly selected FASTA anchor defines the candidate reference context. Resources do not vote on which reference is “dominant.”

### Aggregation

Conceptually, for each mandatory in-scope requirement:

1. identify candidate capabilities;
2. if adequate evidence contradicts it -> `UNSATISFIED`;
3. if adequate evidence satisfies it -> `SATISFIED`;
4. if evidence is insufficient -> `UNRESOLVED`.

The implemented Milestone 2 aggregator uses only mandatory requirements for the
top-level verdict. Advisory results remain visible but non-vetoing. Mandatory
`NOT_APPLICABLE` constraints are neutral when another mandatory relationship is
satisfied; if no mandatory relationship is applicable at all, the result is
`INDETERMINATE` rather than vacuously `COMPATIBLE`. Explicit conditions qualify
only an otherwise-positive result.

Top-level outcomes:

### `COMPATIBLE`

All mandatory in-scope constraints are satisfied and no unresolved mandatory issue can change the conclusion.

### `COMPATIBLE_WITH_CONDITIONS`

Compatibility is established only for an explicitly bounded scope. The structured condition records what is included and what has not been established.

### `INCOMPATIBLE`

At least one mandatory in-scope requirement is contradicted by sufficient evidence.

### `INDETERMINATE`

No hard contradiction is shown, but at least one mandatory relationship cannot be established.

### Conflict core

Reports should identify the smallest useful resource/evidence set causing the failure rather than presenting an undifferentiated wall of mismatches. The implemented v0.1 extraction keeps one compact core per decisive finding: contradiction cores for mandatory `UNSATISFIED` constraints and unresolved cores for decisive mandatory `UNRESOLVED` constraints. Positive verdicts and an indeterminate result with no applicable mandatory basis have no conflict core. Multiple independent failures remain separate small cores rather than being merged or reduced to one arbitrary chosen failure.

---

## Shared infrastructure — sequence-name/alias resolution

Alias resolution is evidence infrastructure used by multiple checks, not an independent validator.

Preference order:

1. common content-derived sequence identity;
2. independently comparable content checksum;
3. standardized/authoritative alias declaration tied to the sequence;
4. assembly-report/authority mapping;
5. string resemblance.

Only the first four can potentially establish a verified binding; string resemblance alone remains heuristic.

---

## Initial fixture families

The first redistributable synthetic fixture suite should cover at least:

1. exact FASTA identity;
2. same biological sequence, different names;
3. same name, different sequence content;
4. same collection, different order;
5. primary-only vs primary+ALT/decoy;
6. stale `.fai` length;
7. stale `.fai` byte layout;
8. stale `.dict` same name/different length;
9. `.dict` M5 conflict;
10. `.dict` order-only mismatch;
11. BAM/FASTA exact dictionary;
12. BAM/FASTA verified alias;
13. BAM/FASTA unresolved naming difference;
14. BAM reference superset with extra decoys;
15. exact VCF header+REF agreement;
16. VCF contig-header mismatch;
17. one VCF REF mismatch;
18. localized/distributed/systematic VCF REF mismatch patterns;
19. GTF exact seqid match;
20. GTF verified alias requirement;
21. GTF missing sequence;
22. GTF feature out of bounds;
23. GFF3 `##sequence-region` conflict;
24. valid GFF3 circular-origin exception;
25. annotation requiring missing patch/unplaced sequence;
26. declared assembly contradicted by verified identity;
27. mixed bundle with multiple independent problems;
28. non-model organism with no known registry entry;
29. negative control where reference checks pass but workflow still fails;
30. sparse/incomplete evidence producing `INDETERMINATE`.
