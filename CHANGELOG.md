# Changelog

All notable project changes will be documented in this file once implementation begins.

The project is currently pre-release and still establishing its design and repository foundation.

## Unreleased

- Project VCF CHROM usage and exhaustive REF validation into scalable format-neutral `ResourceContract` requirements, anchor-scoped generic reference-base constraints, and Tier-A direct evidence without introducing mismatch-pattern verdict policy.
- Broaden supported Python compatibility to >=3.10 while retaining Python 3.14.7 as the development pin; add CI coverage for 3.10 and 3.11 and replace 3.11/3.12-only enum, exhaustiveness, and type-alias syntax with RefCompat-owned/3.10-compatible equivalents.
- Add exhaustive direct VCF REF-to-FASTA validation with streaming record observations, exact-name unresolved states, coordinate-bounds outcomes, VCF 4.5 IUPAC handling, non-match traceability, and temporary computed FASTA indexing that cannot trust or rewrite an adjacent `.fai`.
- Start Milestone 3 VCF support with a pysam-backed observation layer for VCF/VCF.gz fileformat, `##reference`, `##contig` metadata, and exhaustive CHROM-usage scanning without yet making REF compatibility conclusions.
- Add compact deterministic conflict-core extraction that reports only decisive mandatory constraint/finding/evidence/resource traces for incompatible or unresolved verdicts without scoring, voting, or arbitrary global-minimum selection.
- Add categorical whole-bundle verdict aggregation over mandatory constraints, with hard-conflict precedence, conservative indeterminate handling, advisory isolation, explicit-scope conditional compatibility, and traceable finding/condition IDs without numeric scoring.
- Add RefCompat-owned resource and sequence-identity value types.
- Add the local refget/SeqCol FASTA identity adapter and GA4GH known-answer tests.
- Harden FASTA identity ingestion after independent review: reject empty/headerless, anonymous, and duplicate-name anchors; separate malformed-input, unsupported-usage, and provider-shape errors; constrain collection-level digests to complete snapshots; and add offline/determinism/error-boundary regression tests.
- Add exact FASTA ↔ `.fai` structural verification for uncompressed references, including five-column FAI parsing, refget-backed expected geometry, localized count/name/order/length/offset/line-width differences, HTSlib known-answer coverage, conservative zero-length/compressed-reference handling, and wrapping/CRLF/determinism/error-boundary regression tests.
- Add FASTA ↔ SAM/Picard `.dict` integrity verification, including narrow SAM-header parsing, exact name/order/length checks, Tier-A M5 conflicts and unambiguous cross-name identity evidence, explicit cross-name M5/LN inconsistency reporting, preserved alias/provenance metadata, missing-M5 evidence gaps, and GA4GH/refget known-answer coverage.
- Add provisional human-readable and explicit JSON diagnostics for FASTA identity, FASTA/`.fai`, and FASTA/`.dict` results, with CLI subcommands that preserve the boundary between local evidence and later whole-bundle compatibility verdicts.
- Complete the Milestone 1 domain/fixture exit boundary with format-neutral resource observations and source locations plus deterministic corpus-derived identity, stale-by-construction `.fai`/`.dict`, alias-only, order-difference, and same-name/different-sequence fixtures.
- Begin Milestone 2 with explicit evaluation requests/scope, typed sequence presence/length/identity/order requirements and capabilities, context-specific resource contracts, and separate exact constraint/evaluation objects that preserve unresolved evidence gaps without numeric scoring.
- Add generalized qualitative evidence items and deterministic evidence IDs, propagate optional observation traceability through capabilities, and aggregate supporting/contradicting evidence without numeric voting or bundle verdicts.
- Add structured compatibility findings for typed conflicts/unresolved questions and explicit resource/anchor-sequence scope conditions, retaining traceability without assigning a bundle verdict.
- Add FASTA-anchored `ReferenceContext`, content-verified `SequenceBinding`, binding-aware constraint/evidence traceability, and deterministic whole-bundle orchestration that evaluates every scoped typed requirement against the selected anchor without peer-resource voting or a top-level verdict.

### Foundation

- Selected Apache-2.0 and added durable citation/provenance metadata.
- Established `uv`/`uv_build`, pytest, Ruff, strict mypy, and the Python compatibility policy; support is now Python >=3.10 with CI on 3.10–3.14.
- Set the initial runtime dependency boundary to `refget>=0.12,<0.13`; later format dependencies are added only when implementation requires them.

### Design

- Established RefCompat as a reference/resource interoperability reasoning layer above GA4GH refget Sequences and SeqCol.
- Completed a 200-incident design corpus in two independent 100-case batches.
- Formalized immutable observations, provenance claims, resource contracts, requirements/capabilities, evidence, constraints, findings, conditions, and scoped verdicts.
- Split per-resource sequence-collection snapshots from reasoner-established reference contexts.
- Established explicit v0.1 check specifications for FASTA, `.fai`, `.dict`, BAM/CRAM, VCF, GTF/GFF3, provenance, and whole-bundle reasoning.
- Established a local-first refget/SeqCol adapter boundary and optional remote metadata-enrichment boundary.
- Established safety rules prohibiting silent rename, reheader, allele rewrite, coordinate lift, realignment, and other semantic repair.
