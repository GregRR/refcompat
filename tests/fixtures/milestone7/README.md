# Milestone 7 report fixtures

`draft-compatible-report.json` pins the provisional revision-3 M7 projection
retained for draft callers. It has no stable compatibility guarantee.

`stable-compatible-report-1.0.0.json` and
`stable-incompatible-report-1.0.0.json` remain the frozen core known-answer
fixtures for exact stable schema `1.0.0`. The packaged 1.0.0 schema is retained
as an exact-version validator; its refget-pattern correction is a schema-only
erratum that makes the validator accept the already-defined `SQ.<32-character>`
identity representation and does not change these report bytes.

`stable-compatible-report-1.1.0.json` and
`stable-incompatible-report-1.1.0.json` pin the additive current stable shape.
`stable-ucsc-alignment-report-1.1.0.json` additionally pins report-owned resource
observations, BAM/CRAM dictionary relationship context, and UCSC provider/source/
profile provenance for a content-authorized authoritative-name binding. All
1.1.0 headers map to the packaged
`refcompat.schemas/compatibility-report-1.1.0.schema.json` resource.
