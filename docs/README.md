
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
