
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

**Implementation status:** header observation, core `@SQ` contract projection, conservative M5-backed cross-name binding, descriptive dictionary relationship reasoning, and deterministic offline CRAM reference planning are implemented.

### Purpose

Determine what reference environment the alignment header declares and whether its sequence requirements reconcile with the FASTA anchor.

### v0.1 scope

Header/reference-dictionary focused. It does not validate alignment correctness, mapping quality, read biology, or perform reheadering/remapping.

### Observations

From the parser-visible SAM header, where present:

- `@HD` `VN`, `SO`, `GO`, and `SS`;
- ordered `@SQ` `SN`, `LN`, `M5`, `AN`, `AS`, `UR`, `SP`, `AH`, and `TP`;
- `@PG` `ID`, `PN`, `CL`, `PP`, `DS`, and `VN` as provenance observations.

The implemented observation boundary does not scan alignment records. Valid extension tags are ignored rather than treated as parse failures, and BAM's binary reference-name/length dictionary is retained when textual `@SQ` lines are absent. `@PG` records may contribute provenance claims but do not establish sequence identity. `@SQ M5` remains declared metadata; the contract bridge projects it as an identity requirement, and the binding bridge may expose only a conservative `DECLARED_METADATA` capability for name resolution. It never becomes anchor authority or candidate reference evidence.

### Requirements

For each declared reference sequence, the implemented core contract creates mandatory presence and length requirements and, when M5 is present, a mandatory MD5 identity requirement. Generic evaluation can already satisfy or contradict directly comparable same-name requirements against the content-derived FASTA anchor.

Cross-name local names now resolve only through verified M5-backed sequence binding with complete-anchor uniqueness, scope, and length-consistency checks. `AN` remains observational rather than binding authority.

The descriptive relationship layer separately reports declared membership (`EXACT`, `ALIGNMENT_SUBSET`, `ALIGNMENT_SUPERSET`, `OVERLAP`, `DISJOINT`, `UNRESOLVED`), verified naming differences, relative shared-sequence order, M5 verification/conflict state, length conflicts, unresolved names, and non-bijective local-to-anchor mappings. An unfamiliar name is not promoted to an extra sequence merely from string difference; M5-distinct extra classification requires complete anchor MD5 coverage and a declared M5 absent from the complete anchor. `AN` never establishes a binding, and an `AN` value that names an anchor sequence blocks M5-distinct-extra classification because the header contains a competing, unresolved naming claim. These summaries do not replace generic constraint evaluation or the bundle verdict.

Order remains a policy boundary rather than a universal hard requirement:

- relative shared-sequence order is described here and becomes mandatory only when an explicit scope/profile requires it.

### CRAM offline reference policy

Header-only CRAM inspection does not require a reference FASTA. The SAM header also does not expose enough information to decide whether every CRAM container/slice can be restored without external reference content: the CRAM compression-header `RR` preservation flag and embedded-reference state live below this observation boundary. RefCompat therefore does not infer that an external reference is required or unnecessary from `@SQ` alone.

If a future operation genuinely needs reference bases, deterministic offline handling has only two actions:

- use the explicitly selected local FASTA anchor as `reference_filename` when the CRAM dictionary is fully covered by that anchor using exact primary names, every resolved sequence has M5 verified against content-derived anchor identity, declared lengths agree, and the anchor path is locally readable; or
- defer reference-dependent decoding.

Verified cross-name M5 identity is sufficient for RefCompat semantic binding but is deliberately insufficient to claim that an external parser can address the selected FASTA by those local names. The planner never selects `@SQ UR`, ambient `REF_PATH`/`REF_CACHE`, or network retrieval. Because an explicit FASTA path has priority but does not itself disable every HTSlib fallback, any future decoder adapter must preserve the deterministic no-fallback boundary explicitly. The plan also assumes the selected FASTA has not changed since the anchor context was derived. Missing offline reference availability is not itself an incompatibility verdict; already-established header constraints and relationships remain valid.

### Completeness caution

The header describes the declared alignment reference environment; header-only inspection does not establish whether reads actually use every declared sequence.

A BAM declaring primary+decoy sequences against a primary-only FASTA should therefore report verified shared scope plus unresolved/unsatisfied additional-sequence requirements according to the explicit evaluation scope. RefCompat must not guess that decoys are irrelevant.

### Representative outcomes

- same name, conflicting content checksum -> `UNSATISFIED` hard conflict plus `M5_CONFLICT` relationship content;
- same content identity, different local name -> `SATISFIED` via verified sequence identity/alias and, when all other dictionary dimensions agree, a verified naming-only difference;
- same complete set and M5 identities in different order -> exact membership with `DIFFERENT` shared-sequence order;
- strict resolved shared set -> `ALIGNMENT_SUBSET`; complete shared set plus M5-distinct declared records -> `ALIGNMENT_SUPERSET`; partial shared set plus M5-distinct declared records -> `OVERLAP`;
- same name+length without content checksum -> strong structural compatibility, not exact identity proof;
- different names, same length, no identity/alias evidence -> `UNRESOLVED`.

### Safety

The Milestone 4 alignment path is diagnostic-only. RefCompat may describe a
verified name correspondence, a dictionary relationship, or a safe local FASTA
for a future CRAM decode, but those conclusions are not mutation instructions.
The implementation does not rewrite `@SQ`, rename references, reheader BAM/CRAM,
remap records, or realign reads.

Do not recommend blind `samtools reheader` or equivalent solely from familiar-looking naming patterns.
See [`alignment-non-mutation-boundary.md`](alignment-non-mutation-boundary.md).

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
conflict-pattern interpretation is implemented in RCHECK-050E; verified-binding revalidation is implemented in RCHECK-050F.

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
Verified-binding revalidation is implemented in RCHECK-050F. Whole-bundle ingestion of
pair-derived reference-base capabilities is implemented in RCHECK-050D, and threshold-free
conflict-pattern interpretation is implemented in RCHECK-050E.

Projection rules:

- each actually used `CHROM` name creates one mandatory `SequencePresenceRequirement`;
- a declared `##contig` length for an actually used contig creates one mandatory
  `SequenceLengthRequirement`; a directly comparable length mismatch is structural
  contradiction evidence, while an unresolvable cross-name declaration remains unresolved;
- a syntactically valid `##contig` MD5 declaration for an actually used contig creates one
  mandatory `SequenceIdentityRequirement`; a directly comparable MD5 conflict is Tier-A
  contradiction evidence, while an unresolvable cross-name declaration remains unresolved;
- unused `##contig` declarations do not create presence, length, or identity requirements;
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
revalidation is implemented in RCHECK-050F.

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

**Implementation status:** implemented for exhaustive direct validation, including RCHECK-050F verified-binding revalidation. Stable report/CLI presentation remains deferred.

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

### RCHECK-050F — verified sequence binding and REF revalidation

**Implementation status:** implemented for used VCF contigs with usable `##contig` MD5 identity.

VCF 4.5 defines the reserved `md5` contig attribute as the MD5 checksum of the referenced
sequence. RefCompat may use that declaration to establish a cross-name `SequenceBinding` only
when the digest is valid, every sequence in the complete FASTA anchor snapshot has MD5 identity
available, the digest identifies exactly one sequence in that complete snapshot, the target remains
inside explicit anchor scope, and any declared contig length agrees. Exact
same-name identity does not create an unnecessary binding. Scope cannot manufacture uniqueness by
hiding a duplicate-content anchor sequence.

The declaration does not satisfy the aggregate reference-base requirement by itself. For every
used contig with a syntactically valid MD5, the VCF contract also carries a mandatory
`SequenceIdentityRequirement`. A directly comparable same-name MD5 conflict is therefore a
Tier-A identity contradiction; an unbound cross-name declaration stays unresolved.
Separately, an accepted MD5 may serve as binding evidence. `evaluate_vcf_ref_records()` can apply
the explicit binding to FASTA lookup
and then performs the same exhaustive coordinate/base comparison. A bound mismatch remains a hard
`MISMATCH`; a missing bound target is rejected as cross-wiring. The validation retains deterministic
IDs for bindings actually used.

`project_vcf_contract()` independently derives the expected bindings and rejects a stale validation
that did not use them. Bound presence requirements use the generic `VERIFIED_ALIAS` path, while
declared-MD5 identity requirements use the generic `VERIFIED_SEQUENCE_IDENTITY`/Tier-A identity
path. The VCF contract retains the accepted peer identity capability with
`DECLARED_METADATA` provenance for generic whole-bundle `SequenceBinding` derivation. Declared
identity capabilities cannot satisfy identity requirements as candidate evidence; peer resources
still do not supply candidate reference facts or vote on the FASTA anchor.

No string alias guessing, MD5/refget cross-comparison, assembly-name inference, or data rewriting is
introduced.

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

Determine whether every in-scope reference-coordinate statement made by the annotation can be represented against the explicitly selected FASTA anchor.

A positive result establishes structural reference-coordinate compatibility for the statements the annotation actually makes. It does not establish that the annotation and FASTA have identical whole-reference membership, prove a named genome build, or validate gene-model biology.

The standards-derived implementation invariants are also summarized in [`annotation-coordinate-compatibility.md`](annotation-coordinate-compatibility.md).

### Coordinate convention

GTF and GFF3 feature columns 4 and 5 are interpreted as positive one-based closed coordinates. RefCompat preserves those native values in observations. Any zero-based/half-open conversion needed for FASTA access is an explicit validation-layer operation rather than a change to the observed annotation coordinates.

GFF3 seqids obey the format's percent-encoding rules. Preserve the raw field for traceability, but use the decoded logical seqid for comparison with the FASTA namespace and for matching the same seqid across feature/directive records. Characters permitted unescaped by the GFF3 seqid grammar must not be percent-encoded; invalid, missing, or disallowed escaping is an input-validity issue rather than a reason to guess the intended name.

GFF3 additionally defines an origin-crossing representation for features on an explicitly circular landmark. That exception is format-specific and is resolved before generic coordinate-bounds evidence is produced. Coordinates in the GFF3 `Target` attribute describe the aligned target sequence, not the column-1 landmark, and must not participate in RCHECK-060 anchor-coordinate bounds.

### Observations

The annotation inspector streams feature rows and records, at minimum:

- seqids actually used by features;
- feature count by seqid;
- minimum start and maximum end by seqid;
- enough source location/ordinal information to explain non-matching features;
- recognizable provider/release/assembly claims without promoting them to verified identity.

For GFF3, where present, also observe:

- `##sequence-region`;
- standard genome-build/species/provenance directives relevant to reference context;
- useful provider-specific provenance directives such as NCBI's `#!genome-build` and `#!genome-build-accession` without treating them as standard GFF3 identity evidence;
- the `##FASTA` boundary plus streaming name/length/content-MD5 summaries for embedded FASTA sequences;
- explicit `Is_circular=true` landmark evidence needed to interpret circular-origin coordinates.

The narrow parser does not need to construct transcript/gene hierarchy merely to perform these observations.

**Implementation status:** the streaming GTF/GFF3 observation boundary is implemented. It exposes a compact per-seqid snapshot plus exhaustive feature iteration, preserves raw and decoded GFF3 seqids, recognizes gzip content without relying on filename suffixes, records the reference-relevant directives above, stops annotation parsing at explicit or backward-compatible implied GFF3 FASTA boundaries, and streams embedded FASTA sequence summaries without retaining complete bases in memory.

### Sparse annotation semantics

GTF/GFF3 are treated as sparse/partial coordinate-bearing resources. A file that uses only `chr1` does not assert that its underlying reference contains only `chr1`, and a FASTA containing additional chromosomes, ALT loci, decoys, patches, or unplaced sequences is not incompatible merely because the annotation has no features on them.

Scope can exclude sequences only when the caller explicitly requests that scope. RefCompat does not infer that a patch, haplotype, ALT, decoy, mitochondrial, or unplaced sequence is irrelevant.

### Contract projection

For each distinct in-scope seqid actually used by a feature, and for any additional GFF3 seqid named only by `##sequence-region`, project a mandatory `SequencePresenceRequirement`. Name resolution uses an exact local name or an explicit verified `SequenceBinding`; a missing candidate capability by itself is not proof that the biological sequence is absent.

Project annotation-coordinate validation through one scalable, resource-level `CoordinateBoundsRequirement` that names the selected FASTA anchor and counts all in-scope coordinate statements. GTF contributes feature rows; GFF3 also contributes `##sequence-region` declarations. Do not create one generic requirement per feature or directive. The corresponding anchor-owned `CoordinateBoundsValidationCapability` summarizes representable, conflicting, and unresolved statements while the annotation-specific validation result keeps feature/per-seqid counts, bounded representative feature problems, and the finite set of region checks.

The pair-derived capability can satisfy only a coordinate requirement for the same annotation resource and the same selected FASTA anchor. Peer resources cannot provide coordinate capability for one another or vote on the anchor.

The implementation now follows this projection end to end using exact names or explicit verified `SequenceBinding` values. Bound local seqids are projected into the verified anchor namespace before feature and sequence-region bounds checks; FASTA sequences absent from both feature usage and sequence-region declarations create no requirement; unfamiliar annotation seqids without content-backed binding remain unresolved; and proven ordinary feature or region bounds conflicts populate the shared capability conflict count. Potential circular GFF3 feature/region-consistency questions remain unresolved until the circular-specific semantics are implemented.

### Name resolution and missing sequences

`1` versus `chr1`, `MT` versus `chrM`, version stripping, accession resemblance, and other familiar naming patterns are not aliases by themselves. `SatisfactionMode.VERIFIED_ALIAS` requires evidence-backed `SequenceBinding` using the existing binding rules. GFF3 feature `Alias` attributes describe feature aliases and are not sequence-binding authority for the column-1 seqid.

When no exact-name or verified binding resolves a used annotation seqid, the feature remains `UNRESOLVED_SEQUENCE` and the mandatory relationship remains unresolved. RefCompat must not relabel an unfamiliar local name as a proven missing sequence merely because the selected FASTA uses different strings.

If independent evidence actually establishes what sequence the annotation seqid denotes and establishes that the in-scope anchor lacks that required sequence, the mandatory presence relationship is unsatisfied. Explicit scope may make an otherwise relevant sequence out of scope, but scope must never manufacture alias uniqueness or hide duplicate anchor identities to create a binding.

### Ordinary coordinate bounds

For a resolved non-circular feature interval, `1 <= start <= end <= anchor_length` is required. A feature interval proven outside that range is a hard structural conflict. One proven conflict is not cancelled by any number or proportion of in-bounds features; counts describe impact rather than vote on truth.

Unresolved-sequence features are not also labeled out of bounds because no anchor coordinate system has been established for them.

### GFF3 `##sequence-region`

The GFF3 `##sequence-region seqid start end` directive declares the sequence segment referred to by the file. It is not an assertion that the full biological sequence has length `end`, so it must not be projected as an exact `SequenceLengthRequirement` merely because it ends at a particular coordinate.

Only one `##sequence-region` directive is valid for a given decoded/logical seqid. RefCompat rejects duplicates as malformed annotation input. A region-only seqid still creates a presence requirement because the directive itself refers to that coordinate system. When the directive seqid resolves to the selected FASTA anchor, its declared segment must itself be representable against that anchor and participates in the same exhaustive coordinate capability as feature rows; an unresolved region seqid remains unresolved. Independently, GFF3 requires ordinary features on that landmark to lie within the supplied region, subject to its circular-landmark exception. A non-circular feature/region contradiction stops coordinate evaluation as invalid input instead of becoming a biological `INCOMPATIBLE` verdict. If circular evidence is present but the landmark relationship has not yet been established, the affected feature remains unresolved pending the dedicated circular slice.

### GFF3 circular-origin semantics

GFF3 permits an origin-crossing feature on a circular landmark to retain `start <= end` by adding the landmark length to the wrapped end coordinate. Consequently, `end > anchor_length` is not automatically a coordinate conflict in GFF3.

RefCompat applies that exception only when the GFF3 document supplies the standard landmark evidence needed to establish the relevant sequence as circular and the extended interval is valid under the defined circular representation. It must not infer circularity from organism type, sequence name, feature type, or a convenient coordinate pattern. If the available data cannot establish whether the exception applies safely, the coordinate relationship remains unresolved rather than being forced to compatible or incompatible.

GTF has no corresponding core circular-origin rule in the supported GFF2-derived coordinate model; ordinary GTF intervals therefore use the normal resolved-sequence bounds rule.

### Provenance and embedded GFF3 FASTA

Provider/release/build/species metadata are provenance claims. `GRCh38`, `GRCm39`, a provider name, an assembly accession, or a familiar filename can support explanation but cannot independently establish sequence identity or an alias. The annotation contract and coordinate capability are invariant to these claims; a claim change alone does not alter compatibility reasoning.

`##FASTA` ends the GFF3 feature/directive portion and begins embedded sequence content. The parser recognizes this boundary so sequence lines are never interpreted as feature rows; the GFF3 backward-compatibility rule that a line beginning with `>` implies the FASTA section is handled at the same parser boundary. Embedded FASTA sequence content is normalized for MD5 identity using the refget checksum rule: non-sequence formatting is discarded and letters are uppercased before hashing. An embedded record with no normalized sequence content is invalid rather than being assigned an empty-sequence identity. Only an embedded FASTA identifier that exactly matches a feature-used or `##sequence-region` logical seqid contributes RCHECK-060 identity; other bundled sequences remain observationally irrelevant to the reference-coordinate check.

Each relevant embedded sequence projects a mandatory `SequenceIdentityRequirement` plus an annotation-owned `SequenceIdentityCapability` with `CONTENT_DERIVED` provenance. The existing sequence-binding reasoner may use that capability to establish a cross-name mapping only when the matching identity scheme is available for every sequence in the complete FASTA anchor, the identity is unique across that complete anchor, and the target remains in explicit scope. Missing anchor identity or scope must not create uniqueness by hiding a possible duplicate. The resulting verified binding is supplied to feature/region coordinate validation. `project_annotation_contract()` independently derives the expected bindings for the same snapshot/context and rejects stale validation that did not use exactly those bindings before projecting presence/identity constraints; no string alias heuristic is added. An exact-name embedded-content mismatch against the anchor is a Tier-A sequence-identity contradiction. Embedded content never replaces, selects, or outranks the explicitly selected FASTA anchor, and annotations without embedded FASTA remain eligible for structural coordinate compatibility.

When an embedded FASTA identifier exactly matches a logical annotation seqid, its normalized sequence length also constrains the GFF3 document itself. An ordinary feature or `##sequence-region` extending beyond that matching embedded sequence is invalid annotation input, not evidence that the selected external FASTA is incompatible. A feature that could require the GFF3 circular-landmark exception remains unresolved until the dedicated circular slice proves that exception; `##sequence-region` itself does not use the wraparound feature encoding.

### Evidence and verdict effect

Resolved in-bounds annotation coordinates are Tier-B structural evidence. They support the statement that the annotation's observed coordinates are representable against the selected anchor; they are not Tier-A proof that every anchor base is the sequence against which the annotation was originally produced.

A proven ordinary out-of-bounds coordinate is a hard structural contradiction for that mandatory coordinate requirement. Unresolved names or unresolved circular interpretation keep the corresponding requirement unresolved and can therefore produce `INDETERMINATE`. A sparse annotation does not create absence evidence for unmentioned anchor sequences.

### Explicit non-goals

Core v0.1 does not judge or perform:

- exon/transcript/gene biological correctness;
- `ID`/`Parent` hierarchy repair or general GFF3 conformance validation;
- CDS phase/codon validation or transcript reconstruction;
- gene naming or attribute normalization;
- GTF ↔ GFF3 conversion;
- sequence-name rewriting, version stripping, or heuristic `chr` prefix handling;
- coordinate clipping, liftover, feature deletion, or other mutation;
- GENCODE versus Ensembl biological equivalence;
- build guessing from coordinates, filenames, or familiar sequence names;
- featureCounts, Cell Ranger, STAR, UCSC, Ensembl-import, or other consumer-specific dialect requirements.

Those belong to dedicated annotation validators, later transformations, or explicit consumer profiles.

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
21. GTF unresolved cross-name seqid;
22. GTF feature out of bounds;
23. GFF3 `##sequence-region` conflict;
24. valid GFF3 circular-origin exception;
25. annotation requiring an in-scope sequence whose absence from the anchor is independently established;
26. declared assembly contradicted by verified identity;
27. mixed bundle with multiple independent problems;
28. non-model organism with no known registry entry;
29. negative control where reference checks pass but workflow still fails;
30. sparse/incomplete evidence producing `INDETERMINATE`.
