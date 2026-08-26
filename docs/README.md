
# RefCompat design documentation

The root [`DESIGN.md`](../DESIGN.md) is the normative project design baseline. Files in this directory expand specific parts of that design without changing its meaning.

- [`compatibility-model.md`](compatibility-model.md) — domain objects, ownership boundaries, and invariants.
- [`evidence-model.md`](evidence-model.md) — observations, claims, evidence strength, conflicts, and traceability.
- [`refget-seqcol-integration.md`](refget-seqcol-integration.md) — the GA4GH standards and Python integration boundary.
- [`check-specifications.md`](check-specifications.md) — explicit initial check contracts.
- [`architecture/package-layout.md`](architecture/package-layout.md) — approved package boundaries and source layout.
- [`dependency-policy.md`](dependency-policy.md) — dependency-license and adoption policy.
- [`development.md`](development.md) — supported Python versions, local setup, and required checks.
- [`adr/`](adr/) — architectural decision records.

If a supporting document and `DESIGN.md` disagree, `DESIGN.md` wins until the discrepancy is resolved explicitly.

- [`fasta-index-integrity.md`](fasta-index-integrity.md) — exact FASTA/`.fai` derived-artifact verification semantics.
- [`sequence-dictionary-integrity.md`](sequence-dictionary-integrity.md) — exact FASTA/`.dict` structure plus M5, alias, and provenance evidence semantics.
- [`diagnostic-output.md`](diagnostic-output.md) — provisional human and JSON diagnostics for Milestone 1 identity and integrity checks.
- [`reasoning-foundation.md`](reasoning-foundation.md) — first Milestone 2 request/scope, typed contract, and constraint/evaluation boundary.
- [`evidence-aggregation.md`](evidence-aggregation.md) — second Milestone 2 qualitative evidence and aggregation boundary.
- [`findings-conditions.md`](findings-conditions.md) — third Milestone 2 structured findings and explicit-scope conditions boundary.
- [`reference-context-bundle.md`](reference-context-bundle.md) — fourth Milestone 2 FASTA reference-context, verified-binding, and whole-bundle orchestration boundary.
- [`verdict-aggregation.md`](verdict-aggregation.md) — fifth Milestone 2 categorical mandatory-constraint verdict aggregation boundary.
- [`vcf-context.md`](vcf-context.md) — Milestone 3 VCF header/reference-context observations and pysam boundary.
- [`vcf-ref-validation.md`](vcf-ref-validation.md) — exhaustive Milestone 3 direct VCF REF-to-FASTA comparison boundary.
- [`vcf-contract-projection.md`](vcf-contract-projection.md) — Milestone 3 bridge from VCF usage/REF results into format-neutral contracts and Tier-A evidence.
- [`vcf-bundle-orchestration.md`](vcf-bundle-orchestration.md) — Milestone 3 ingestion of anchor-owned pair-derived REF evidence into whole-bundle reasoning.
- [`vcf-ref-conflict-patterns.md`](vcf-ref-conflict-patterns.md) — threshold-free Milestone 3 interpretation of isolated, localized, distributed, systematic, and incomplete REF-conflict distributions.
- [`vcf-sequence-binding.md`](vcf-sequence-binding.md) — Milestone 3 verified VCF cross-name binding from contig MD5 identity and binding-aware REF revalidation.
- [`conflict-core.md`](conflict-core.md) — sixth Milestone 2 compact decisive conflict/evidence-core extraction boundary.
