
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
- `STALE_FASTA_INDEX`

### Critical rule

Verified biological aliases do **not** satisfy an exact derived-artifact requirement. An index naming `1` is not the valid `.fai` for a FASTA whose indexed local identifier is `chr1`, even if those labels can be proven to denote the same biological sequence elsewhere.

A proven mismatch in an explicitly evaluated FASTA/FAI pair is an in-scope hard incompatibility for operations relying on that pair.

---

## RCHECK-030 — FASTA ↔ SAM/Picard sequence dictionary (`.dict`)

### Purpose

Determine whether a supplied sequence dictionary represents the supplied FASTA and characterize any biological-versus-artifact distinction.

### Observations

For each `@SQ`, where present:

- `SN`
- `LN`
- `M5`
- `AN`
- `AS`
- `UR`
- `SP`
- `TP`
- ordinal/order.

### Evidence

- M5 conflict: hard content contradiction where checksum semantics are applicable;
- name/length conflict: hard structural contradiction;
- name/length agreement without content checksum: strong structural agreement, not exact identity proof;
- AS/UR/SP: provenance evidence.

### Findings

- `SEQUENCE_DICTIONARY_VERIFIED`
- `DICTIONARY_SEQUENCE_MISSING`
- `DICTIONARY_SEQUENCE_EXTRA`
- `DICTIONARY_LENGTH_CONFLICT`
- `DICTIONARY_M5_CONFLICT`
- `DICTIONARY_ORDER_DIFFERENCE`
- `STALE_SEQUENCE_DICTIONARY`

### Order-only differences

A verified order-only difference is not automatically a biological sequence incompatibility. Core behavior may report `COMPATIBLE_WITH_CONDITIONS` for reference-coordinate semantics while consumer profiles can require exact dictionary order.

### Derived-artifact rule

Verified alias equivalence does not make a dictionary an exact companion of a differently represented FASTA. RefCompat may simultaneously report biological sequence equivalence and derived-artifact incompatibility.

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

Inspect:

- `##reference`;
- `##contig ID`;
- contig length;
- contig md5 where present;
- contig assembly/URL metadata;
- actual `CHROM` usage.

`##reference` is a provenance claim, not proof. Missing `##contig` declarations do not by themselves prove that a valid VCF/reference relationship cannot be evaluated from the records.

### RCHECK-050B — exhaustive REF ↔ FASTA validation

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

The report should aggregate counts and affected sequences while retaining traceability to conflicting records.

### Hard-conflict rule

A proven REF mismatch is a hard local reference conflict. A small mismatch fraction does not mathematically cancel it. The distribution of mismatches may support interpretation such as isolated versus systematic conflict.

Candidate findings:

- `ISOLATED_VCF_REF_CONFLICT`
- `LOCALIZED_VCF_REF_CONFLICT`
- `SYSTEMATIC_VCF_REF_CONFLICT`

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

Reports should identify the smallest useful resource/evidence set causing the failure rather than presenting an undifferentiated wall of mismatches.

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
18. systematic VCF REF mismatch;
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
