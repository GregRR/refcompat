# Changelog

All notable project changes will be documented in this file once implementation begins.

The project is currently pre-release and still establishing its design and repository foundation.

## Unreleased

### Foundation

- Selected Apache-2.0 and added durable citation/provenance metadata.
- Established Python >=3.12, `uv`/`uv_build`, pytest, Ruff, strict mypy, and a Python 3.12–3.14 CI matrix.
- Set the initial runtime dependency boundary to `refget>=0.12,<0.13`; later format dependencies are added only when implementation requires them.

### Design

- Established RefCompat as a reference/resource interoperability reasoning layer above GA4GH refget Sequences and SeqCol.
- Completed a 200-incident design corpus in two independent 100-case batches.
- Formalized immutable observations, provenance claims, resource contracts, requirements/capabilities, evidence, constraints, findings, conditions, and scoped verdicts.
- Split per-resource sequence-collection snapshots from reasoner-established reference contexts.
- Established explicit v0.1 check specifications for FASTA, `.fai`, `.dict`, BAM/CRAM, VCF, GTF/GFF3, provenance, and whole-bundle reasoning.
- Established a local-first refget/SeqCol adapter boundary and optional remote metadata-enrichment boundary.
- Established safety rules prohibiting silent rename, reheader, allele rewrite, coordinate lift, realignment, and other semantic repair.
