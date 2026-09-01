# Changelog

All notable project changes are documented in this file.

The project is currently pre-release; entries under `Unreleased` describe ongoing development toward the first substantial release.

## Unreleased

- Harden the Milestone 6 final internal-review boundary: require complete canonical-catalog plus alias evidence before an alternate UCSC name can authorize a relationship, prevent distinct required UCSC canonical targets with identical content from collapsing onto one FASTA coordinate sequence, preserve advisory isolation, stronger peer-content conflicts, and same-target multi-alias behavior, and document resource-local filtering when bundle-wide profile bindings are passed to format-specific validators.
- Complete the Milestone 6 adversarial exit suite with network-independent coverage for explicit target selection, content-before-name proof, exhaustive target absence, ambiguous/incomplete/cross-wired provider evidence, full-anchor uniqueness before scope, stronger peer-content precedence, deterministic offline equivalence, provider unavailability, mixed hard/unresolved evidence, explicit scope conditions, and a non-reference invalid-hub negative control.

- Harden Milestone 6 provider/offline behavior with a strict deterministic UCSC snapshot artifact boundary, frozen network-independent fixtures, exact artifact-digest verification, and an explicit unavailable-provider path that leaves profile requirements unresolved rather than manufacturing incompatibility.

- Extend Milestone 6 UCSC preflight across BAM/CRAM dictionary reasoning: reuse validated authoritative-name bindings in alignment relationship summaries while keeping M5 content claims separate and preserving strict CRAM offline-reference deferral for cross-name/provider-backed relationships.

- Record the targeted external review of the first Milestone 6 `ucsc-preflight` path: no MAJOR correctness or proof-chain defect was found, and add direct plus profile-level regression coverage proving that a same-scheme peer identity contradiction blocks authoritative provider naming without being promoted into a false hard conflict.

- Add the first end-to-end Milestone 6 `ucsc-preflight` path: introduce a generic profile/policy sequence-binding requirement plus anchor-owned pair validation, compose UCSC authoritative names only after their provider target is content-bound to the selected FASTA, block provider naming from overriding conflicting or differently matching peer identity evidence, preserve unresolved/absence semantics plus direct peer-identity conflicts through ordinary verdict aggregation, context-qualify provider-derived validation IDs, and reuse the existing exhaustive VCF REF evaluator with the resulting verified binding instead of adding a UCSC-specific validator.

- Add Milestone 6 UCSC target-content and authoritative-name reasoning: factor the reviewed complete-anchor identity/absence rules into a reusable anchor resolver, content-bind provider targets only through exhaustive comparable identity, preserve exact-name/content disagreement, require complete alias evidence for authoritative alternate-name resolution, and leave ambiguous, incomplete, out-of-scope, or provider-length-conflicting relationships unresolved.

- Add the Milestone 6 UCSC provider-snapshot model with immutable canonical sequence, alias, dimensional completeness, and per-fact provenance values; reject cross-wired database/provider-context evidence and unsupported completeness claims while preserving duplicate sequence content and ambiguous aliases for later conservative reasoning.

- Pin the Milestone 6 UCSC-preflight contract: require explicit native database selection, consume deterministic provenance-bearing provider snapshots, keep provider aliases separate from content identity, require a content-derived UCSC-target-to-FASTA bridge before authoritative aliases can resolve peer names, preserve generic core checks/verdicts, keep network acquisition outside reasoning, define adversarial/exit coverage and review checkpoints, and synchronize Milestone 5 documentation with its completed targeted external follow-up.

- Harden the Milestone 5 review boundary: reject malformed or repeated GFF3 `Is_circular` control attributes before they can activate circular-coordinate reasoning; derive anchor-owned `SequenceIdentityAbsenceCapability` only when annotation `CONTENT_DERIVED` identity has at least one scheme covering the complete selected FASTA and no local content-derived identity matches anywhere in that full anchor; treat that proof as Tier-A `EXHAUSTIVE_SEQUENCE_IDENTITY_ABSENCE` contradiction to mandatory presence; and keep raw name misses, metadata-only identity, insufficient coverage, ambiguous matches, scope-hidden matches, and conflicting local identity unresolved. Exact-name embedded-content identity conflicts retain their existing single Tier-A identity contradiction rather than gaining a redundant missing-sequence finding. The final audit also prevents a verified binding when an identity from another, incompletely covered scheme positively matches a different anchor target.

- Complete Milestone 5 integration/adversarial exit coverage with redistributable synthetic GTF/GFF3 fixtures spanning exact sparse coordinates, content-verified GTF cross-name binding, unresolved names, hard bounds conflicts, GFF3 sequence-region and circular cases, embedded-content identity conflict, provenance-vs-identity claims, duplicate-identity ambiguity, non-model scaffolds, and mixed hard/unresolved problems. Annotation projection can now accept independently established annotation-owned `CONTENT_DERIVED` identity capabilities for conservative binding or exhaustive absence reasoning without turning GTF metadata or familiar strings into alias authority.

- Complete Milestone 5 GFF3 circular-origin reasoning: require structural `region` landmark evidence rather than feature-ID equality, distinguish valid single-wrap coordinates from unresolved/invalid circular interpretations, prevent unrelated `Is_circular=true` features from suppressing bounds conflicts, and preserve ordinary GTF/GFF3 semantics outside the standard exception.

- Add Milestone 5 GFF3 embedded-FASTA identity and verified annotation binding: stream embedded sequence summaries with refget-normalized MD5, project relevant content-derived identity requirements/capabilities, require complete anchor identity-scheme coverage plus full-anchor uniqueness for cross-name `SequenceBinding`, revalidate annotation bounds through independently derived verified bindings, and expose exact-name embedded-content contradictions as Tier-A conflicts without displacing the selected FASTA anchor.

- Add Milestone 5 GFF3 sequence-region validation and provenance boundaries: enforce unique logical `##sequence-region` declarations, check declared segments against the selected FASTA, reject ordinary feature/region self-contradiction as invalid input, fold region statements into the scalable coordinate capability, and keep build/provider/species claims non-authoritative.

- Add ordinary Milestone 5 GTF/GFF3-to-FASTA coordinate validation: sparse used-seqid presence requirements, exact-name anchor resolution, exhaustive one-based closed bounds checks, bounded representative problem diagnostics, Tier-B coordinate capability projection, unresolved unfamiliar names, strict GFF3 seqid escaping, and conservative deferral of possible circular GFF3 bounds.

- Add the format-neutral Milestone 5 coordinate-bounds reasoning dimension: scalable anchor-named requirements, anchor-owned exhaustive validation capabilities, Tier-B structural evidence, bundle supplemental-capability integration, coordinate-conflict findings, and verdict/conflict-core propagation without annotation-specific policy.

- Add the Milestone 5 streaming GTF/GFF3 observation layer with sparse seqid/coordinate summaries, raw-plus-decoded GFF3 identifiers, sequence-region and provenance observations, `Is_circular=true` feature observations, embedded-FASTA boundary detection, gzip support, and exhaustive feature iteration without building gene-model hierarchy.

- Pin the Milestone 5 GTF/GFF3 contract before implementation: sparse one-based closed annotation coordinates, exact-or-verified seqid resolution, scalable anchor-owned coordinate-bounds evidence, `##sequence-region` segment semantics, conservative circular-origin handling, provenance/embedded-FASTA boundaries, and staged review checkpoints.

- Pin external Milestone 4 review conclusions with end-to-end many-to-one alignment binding coverage, explicit empty-`@SQ` relationship semantics, duplicate-target M5 assertions, and a reporting requirement to surface non-bijective dictionary context alongside future alignment verdicts.

- Harden the Milestone 4 review boundary with stricter alignment-relationship result invariants, corrected CRAM provider-fallback semantics, an explicit FASTA artifact-stability caveat, and mapped-CRAM integration coverage proving an approved selected anchor can actually restore records.

- Close Milestone 4 with an explicit BAM/CRAM non-mutation boundary: alignment inspection and reasoning are read-only diagnostics, verified sequence bindings do not rename data, CRAM reference plans do not rewrite files, and RefCompat does not reheader or realign alignments.

- Define deterministic offline CRAM reference planning: header-only reasoning never requires reference retrieval, while future reference-dependent decoding may use only an explicitly selected readable FASTA anchor with exact-name, M5-verified, length-consistent header coverage; otherwise decoding is deferred without ambient or network lookup.

- Add descriptive BAM/CRAM header-dictionary relationship reasoning that separates exact identity, verified naming differences, shared-sequence order, subset/superset/overlap membership, M5 conflicts, length conflicts, and unresolved cases without introducing an alignment-specific verdict.

- Add conservative BAM/CRAM cross-name sequence binding from uniquely matched `@SQ M5` identity with full-anchor uniqueness, scope, length-consistency, declared-metadata provenance, and generic whole-bundle reuse while leaving `AN` non-authoritative.

- Project BAM/CRAM `@SQ` names, lengths, and M5 declarations into mandatory format-neutral presence, length, and identity requirements while keeping order policy deferred.

- Add bundled third-party notices for redistributed refget and HTSlib known-answer test fixtures and include those notices in built distributions.

- Begin Milestone 4 with BAM/CRAM header observation for ordered `@SQ` reference metadata, `@HD` ordering claims, and `@PG` provenance, including extension-tag-tolerant parsing, BAM binary reference-dictionary fallback, and header-only CRAM inspection that does not require reference content.

- Distinguish content-derived sequence identities from declared metadata claims, require explicit identity provenance, reject declared identities as candidate reference evidence, harden FASTA anchor identity invariants, and pin conservative VCF binding edge cases before BAM/CRAM M5 work.

- Add mandatory sequence-length requirements for declared `##contig` lengths on used VCF contigs, so direct same-name length contradictions cannot be hidden by otherwise matching REF records.

- Add VCF verified sequence-name binding from uniquely matched `##contig` MD5 identity, mandatory identity requirements for valid used-contig MD5 declarations, binding-aware exhaustive REF revalidation, stale-validation rejection, and generic whole-bundle reuse without string alias guessing.

- Add threshold-free VCF REF conflict-pattern interpretation that distinguishes isolated, localized, distributed, and systematic distributions only after complete direct comparison, while leaving incomplete patterns unclassified and preserving generic hard-conflict semantics.

- Integrate anchor-owned pair-derived reference-base validation capabilities into generic whole-bundle reasoning while rejecting wrong-anchor, out-of-scope, duplicate, unused, or competing exhaustive supplemental evidence.

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
