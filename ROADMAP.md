
# RefCompat Roadmap

This roadmap is capability-driven rather than date-driven. Milestones may be split further as implementation evidence accumulates.

## Guiding scope

RefCompat should solve one problem well: determine whether heterogeneous genomic resources can share a coherent reference-coordinate context for a stated use case, and explain why.

The roadmap intentionally avoids turning RefCompat into a universal genomics validator, asset manager, liftover engine, workflow manager, or scientific repair tool.

## Milestone 0 — Foundation

**Goal:** establish a coherent, reviewable project baseline before substantive implementation.

- [x] Complete 200-incident discovery/validation corpus.
- [x] Establish product thesis and prior-art boundary.
- [x] Establish GA4GH refget/SeqCol standards boundary.
- [x] Define domain model and invariants.
- [x] Define evidence hierarchy and provenance model.
- [x] Define explicit v0.1 check specifications.
- [x] Record initial architectural decisions.
- [x] Select software license: Apache-2.0.
- [x] Select supported Python version and compatibility policy: Python >=3.10; CI on 3.10–3.14, with Python 3.11+ recommended for new environments.
- [x] Finalize initial packaging/dependency approach: `uv`/`uv_build`, committed lockfile, minimal runtime dependencies.
- [x] Configure `uv`, pytest, Ruff, strict mypy, packaging, and CI.

## Milestone 1 — Reference identity and derived artifacts

**Goal:** prove the standards boundary and the first deterministic checks with small redistributable fixtures.

- [x] Implement stable RefCompat-owned domain types for resources, observations, sequence identity, and evidence.
- [x] Implement `ReferenceIdentityProvider` protocol.
- [x] Implement local GA4GH refget/SeqCol adapter.
- [x] Inspect FASTA into `SequenceCollectionSnapshot` without leaking upstream library types.
- [x] Implement FASTA ↔ `.fai` verification.
- [x] Implement FASTA ↔ `.dict` verification.
- [x] Add human-readable and minimal JSON diagnostic output for this slice.
- [x] Cross-check initial FASTA identity against GA4GH/refget known-answer behavior.

**Exit criteria:** complete. Deterministic tests cover identity, same-name/different-sequence, alias-only, order-difference, and `.fai`/`.dict` artifacts that are stale by construction. The checks report only observable structural/content evidence; they do not infer staleness as a cause without provenance evidence.

## Milestone 2 — Reasoning foundation and bundle report

**Goal:** demonstrate that RefCompat is more than a collection of pairwise validators.

- [x] Implement evaluation requests and explicit scope.
- [x] Implement typed requirements and capabilities.
- [x] Implement compatibility constraints and evaluations.
- [x] Implement evidence aggregation without numeric compatibility scoring.
- [x] Implement structured findings and conditions.
- [x] Implement anchor-driven whole-bundle reasoning.
- [x] Implement `COMPATIBLE`, `COMPATIBLE_WITH_CONDITIONS`, `INCOMPATIBLE`, and `INDETERMINATE` aggregation.
- [x] Implement conflict-core reporting sufficient to identify the smallest useful conflicting resource/evidence set.

## Milestone 3 — VCF

**Goal:** establish variant/reference compatibility using both metadata and direct base evidence.

- [x] Parse VCF/bgzipped VCF header reference information.
- [x] Inspect `##contig` metadata and actual `CHROM` usage.
- [x] Exhaustively verify REF alleles against FASTA in authoritative mode.
- [x] Project actual CHROM usage and exhaustive REF results into format-neutral requirements and Tier-A evidence.
- [x] Inject anchor-owned pair-derived REF validation into whole-bundle reasoning without peer voting.
- [x] Distinguish isolated/localized/distributed/systematic REF conflict patterns without averaging hard conflicts away.
- [x] Preserve unresolved sequence-name cases as `INDETERMINATE` unless verified aliases exist.
- [x] Do not rewrite REF/ALT.

## Milestone 4 — BAM/CRAM

**Goal:** reconcile alignment reference dictionaries with the FASTA anchor.

- [x] Inspect `@SQ` names, lengths, order, M5, aliases, assembly, URI, and species metadata where available.
- [x] Project declared `@SQ` names, lengths, and M5 values into mandatory core-format presence, length, and identity requirements without promoting M5 to anchor authority.
- [x] Use `@SQ M5` only as explicitly declared metadata when deriving conservative cross-name sequence bindings.
- [x] Distinguish exact identity, verified naming-only differences, order differences, subset/superset relationships, and content conflicts.
- [x] Keep header-only completeness limitations explicit.
- [x] Define conservative CRAM behavior when required reference content is unavailable offline.
- [x] Do not reheader or realign data.

**Exit criteria:** complete. BAM/CRAM support observes declared header facts, projects generic requirements, derives only evidence-backed cross-name bindings, classifies dictionary relationships without creating a second verdict system, and defines deterministic offline CRAM reference deferral. The alignment path is diagnostic-only: it opens resources for reading, never rewrites headers or sequence names, and never remaps or realigns records.

## Milestone 5 — GTF/GFF3

**Goal:** determine whether annotation coordinate requirements are satisfiable by the anchor reference.

**Implementation status:** complete. Core implementation, integration/adversarial exit coverage, internal-review hardening, the external milestone-boundary review, correction of its one MAJOR circular-landmark identification defect, and the targeted external follow-up are complete. The follow-up confirmed the correction and closed Milestone 5. GTF/GFF3 remain sparse resources; exact names or content-verified `SequenceBinding` values can resolve reference seqids; feature and declared-region coordinates project through one anchor-owned `CoordinateBoundsValidationCapability`; relevant embedded GFF3 FASTA sequences contribute content-derived MD5 identity requirements/capabilities; independently established annotation-owned content identities may support conservative binding or exhaustive full-anchor absence proof without becoming intrinsic format claims; full-anchor identity coverage/uniqueness prevents scope-manufactured aliases or absence; contradictory embedded content can produce Tier-A identity conflict without replacing the selected FASTA anchor; and circular wrapping is accepted only for a unique structural circular `region` landmark under the standard single-wrap encoding with well-formed `Is_circular=true` control metadata.

- Stream GTF/GFF3 feature rows and summarize used seqids, feature counts, and native one-based closed coordinate bounds without constructing a gene-model database.
- Treat annotations as sparse/partial resources: an unmentioned anchor sequence is not evidence that the annotation's underlying reference lacks that sequence.
- Resolve seqids by exact name or verified `SequenceBinding` evidence only; honor GFF3 percent-encoded seqid syntax while preserving raw identifiers, and leave familiar naming patterns such as `1` versus `chr1` unresolved without evidence.
- Project used seqids into generic sequence-presence requirements and annotation coordinates into a scalable generic `CoordinateBoundsRequirement` evaluated against the selected FASTA anchor.
- Distinguish an unresolved local sequence name from a sequence that is actually proven absent; insufficient name-resolution evidence remains `INDETERMINATE`, while independently established `CONTENT_DERIVED` identity may prove mandatory absence only when at least one local identity scheme completely covers the selected FASTA and no local content-derived identity matches anywhere in the full anchor. **Implemented and hardened in internal review.**
- Treat an ordinary feature interval that is proven outside a resolved anchor sequence as a hard coordinate conflict and quantify affected features without allowing counts to vote away contradictions.
- Interpret GFF3 `##sequence-region` as a declared annotated segment, not an exact whole-sequence length; validate unique declared regions against the anchor, include region-only seqids in presence requirements, and keep malformed self-contradictory annotation input separate from biological incompatibility. **Implemented.**
- Observe GFF3 build/provider directives and recognizable GTF provider/release metadata as provenance claims only; they do not establish sequence identity or alter compatibility by themselves. **Implemented.**
- Recognize the GFF3 `##FASTA` boundary. Derive refget-normalized MD5 identity only for embedded FASTA sequences whose identifier exactly matches a reference-relevant logical annotation seqid; use that content-derived evidence for mandatory identity checks and conservative `SequenceBinding` only with complete anchor identity-scheme coverage plus full-anchor uniqueness, validate ordinary matching-sequence bounds as input consistency, and never displace the explicitly selected FASTA anchor. **Implemented.**
- Apply the GFF3 circular-origin exception only when one well-formed `Is_circular=true` attribute is carried by a `region` feature representing the landmark, the unique candidate begins at coordinate 1, its length matches the resolved anchor, and the extended coordinate uses at most one standard wrap; do not require feature `ID == seqid`, and reject malformed/repeated `Is_circular` control metadata rather than letting it activate the exception. **Implemented, hardened internally, and corrected after external review.**
- Exercise the complete annotation contract through redistributable integration/adversarial fixtures covering exact sparse GTF/GFF3 coordinates, externally content-verified GTF binding, exhaustive content-identity absence, unresolved naming differences, hard bounds conflicts, sequence-region/circular rules, malformed circular metadata, embedded-content identity conflict, provenance-vs-identity claims, duplicate identity ambiguity, non-model scaffolds, and mixed hard/unresolved problems. **Implemented.**
- Hold an internal review after the streaming observation, generic coordinate-bounds, and ordinary exact-name anchor-validation slices are integrated, before building verified annotation binding and circular semantics on top. **Completed after Slice 4.**
- Hold an external milestone-boundary review after the complete GTF/GFF3 integration and adversarial coverage, before Milestone 6 depends on annotation semantics. **Completed, including targeted follow-up after the one MAJOR correction.**
- Keep annotation biology, hierarchy repair, broad format conformance, and consumer-specific dialect requirements out of core scope.

## Milestone 6 — First ecosystem profile

**Goal:** implement a conservative `ucsc-preflight` profile for an explicitly selected native UCSC Genome Browser database without allowing provider metadata, aliases, or familiar names to become sequence identity.

**Implementation status:** scientific/profile contract, immutable provider snapshot, shared full-anchor target-content resolution, authoritative UCSC canonical/alias name resolution, generic profile binding requirements, resource-local authoritative-name `SequenceBinding` projection, representative VCF and BAM/CRAM paths, and the provider/offline snapshot boundary are implemented; the first internal scientific/code checkpoint and targeted Slice 4 external review are complete, with its one non-blocking regression-coverage gap hardened before broader format integration. CRAM compatibility remains separate from stricter offline decoder-reference eligibility.

Committed scope:

- Require an explicit UCSC database identifier. Do not infer the target database from filenames, assembly labels, chromosome naming style, coordinates, species, or other heuristics.
- Consume a deterministic, provenance-bearing UCSC provider snapshot whose sequence-catalog, authoritative-alias, content-identity, and completeness dimensions remain distinguishable. Provider facts must remain tied to one database context; cross-wired source data are invalid provider evidence rather than biological incompatibility.
- Treat UCSC `chromAlias`-style relationships as authoritative provider naming evidence only. An alias can support name resolution only when it resolves uniquely in the complete provider alias context and its UCSC target sequence is independently content-bound to one FASTA-anchor sequence. The alias itself never becomes refget/MD5 identity.
- Require content-derived identity to establish the FASTA-anchor relationship to a UCSC target sequence before exact UCSC names or authoritative aliases can support a fully positive UCSC-target conclusion. Database names, canonical sequence names, matching lengths, download locations, assembly accessions, and alias declarations are insufficient by themselves.
- Search the complete FASTA anchor and complete relevant provider alias context before applying caller-selected sequence scope, so scope cannot manufacture target identity or alias uniqueness by hiding alternatives.
- Project UCSC-specific needs through profile-origin requirements and evidence-backed sequence relationships, then reuse generic sequence presence, length, identity, coordinate-bounds, VCF REF, BAM/CRAM dictionary, evidence, finding, and verdict machinery where their semantics fit. Provider-specific logic must not enter generic constraint or verdict policy.
- Reuse existing format semantics rather than adding UCSC-specific copies of VCF REF, BAM/CRAM dictionary, or GTF/GFF3 coordinate reasoning. Existing content contradictions retain precedence over weaker provider support.
- Reuse completed bundle `SequenceBinding` values in BAM/CRAM dictionary relationship classification so a profile-authorized cross-name relationship is reported as a verified naming difference without being mislabeled as M5-backed content identity; keep CRAM offline reference planning exact-name/M5-strict even when the compatibility bundle is positive. **Implemented in Slice 5.**
- Keep provider acquisition separate from compatibility reasoning. A fixed provider snapshot must produce the same scientific result online or offline; unavailable network enrichment yields missing/unresolved provider evidence, never `INCOMPATIBLE` by itself. Ordinary automated quality gates use frozen redistributable fixtures rather than live UCSC services. **Implemented in Slice 6 with a strict versioned snapshot artifact loader/renderer, optional exact SHA-256 verification, and an explicit unavailable-provider projection path.**
- Preserve provider source/freshness provenance. Snapshot age or a changed upstream resource is visible evidence context, not an automatic biological contradiction; independently acquired pieces that cannot be shown to belong to the selected database context must not be silently combined.
- Defer bigBed/bigWig reference-property checks, full track-hub reasoning, assembly hubs/GenArk-specific behavior, persistent provider caching, and structural hub validation. Structural hub integrity remains delegated to UCSC tooling such as `hubCheck` where appropriate.
- Hold an internal scientific/code review after the provider snapshot, authoritative-alias relationship, and one representative end-to-end profile path are implemented, before broadening the profile across additional format behavior. **Completed after Slice 4, including fixes for peer-identity precedence and provider-context-qualified validation IDs.**
- Perform a targeted independent review of the first end-to-end profile path before broader format integration. **Completed after Slice 4: no MAJOR finding; one MINOR direct peer-identity contradiction regression gap was hardened before Slice 5.**
- Hold an external milestone-boundary review after the complete M6 adversarial/exit suite and internal milestone review are clean, before beginning Milestone 7 work.

**Exit criteria:** an explicit native UCSC database target can be evaluated through a provenance-bearing deterministic provider snapshot; exact-name and authoritative-alias paths both require an independently established FASTA-to-UCSC target-content bridge; incomplete, ambiguous, cross-wired, unavailable, or insufficient provider evidence fails closed without manufacturing absence or identity; representative VCF and BAM/CRAM paths reuse the existing generic/core checks; online acquisition is outside scientific reasoning and the ordinary gate is network-independent; adversarial fixtures cover reassuring metadata with wrong content, unsupported/ambiguous aliases, incomplete provider data, scope-hidden alternatives, and mixed hard/unresolved evidence; the internal checkpoint and final external milestone review are complete.

The normative profile contract is recorded in [`docs/ucsc-preflight-profile.md`](docs/ucsc-preflight-profile.md) and RCHECK-070 in [`docs/check-specifications.md`](docs/check-specifications.md).

## v1.0 target

A stable v1.0 should additionally include:

- BCF support;
- BED support;
- stable machine-readable report schema;
- alignment reporting that surfaces dictionary relationship context alongside generic verdicts, including non-bijective mappings;
- portable reference/compatibility manifest;
- reference-free comparison when evidence is sufficient;
- stable profile interface;
- at least one production-quality ecosystem profile;
- non-human and custom-reference validation at useful scale;
- performance work for large resources;
- offline metadata/cache strategy;
- documented CI/workflow exit-code behavior.

## Explicitly beyond v1 unless evidence changes

- performing liftover;
- automatic remapping or realignment;
- general GFF/GTF repair;
- complete annotation semantic comparison;
- universal workflow/pipeline validation;
- arbitrary plugin auto-discovery framework;
- scientific-data rewriting;
- reference asset management competing with refgenie/genomepy;
- reference discovery service competing with refget/SeqCol tooling;
- general-purpose industrial-scale resource graphs.
