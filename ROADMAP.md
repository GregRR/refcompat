
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
- [ ] Define conservative CRAM behavior when required reference content is unavailable offline.
- [ ] Do not reheader or realign data.

## Milestone 5 — GTF/GFF3

**Goal:** determine whether annotation coordinate requirements are satisfiable by the anchor reference.

- Inspect seqids and feature coordinate bounds.
- Handle exact and verified-alias name resolution.
- Inspect GFF3 `##sequence-region` and relevant provenance directives.
- Quantify affected features for missing sequences and out-of-bounds coordinates.
- Handle defined circular-origin semantics conservatively.
- Keep annotation biology, hierarchy repair, and consumer-specific dialect requirements out of core scope.

## Milestone 6 — First ecosystem profile

**Preferred first showcase:** UCSC preflight, after the core is stable.

Potential checks:

- explicit assembly/database selection;
- sequence-name resolution using authoritative alias evidence;
- coordinate bounds against the selected assembly;
- VCF REF evidence;
- BAM/CRAM dictionary coherence;
- later bigBed/bigWig and hub-specific reference checks;
- delegation of structural hub validation to existing UCSC tools such as `hubCheck` where appropriate.

Profiles add consumer requirements. They do not redefine sequence identity or rewrite facts established by the core.

## v1.0 target

A stable v1.0 should additionally include:

- BCF support;
- BED support;
- stable machine-readable report schema;
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
