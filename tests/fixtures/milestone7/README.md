# Milestone 7 report fixtures

`draft-compatible-report.json` originated in M7 and now pins provisional draft
revision 4 after M8 adds the `bcf` resource-kind wire value. Draft output has no
stable compatibility guarantee.

`stable-compatible-report-1.0.0.json` and
`stable-incompatible-report-1.0.0.json` remain the frozen core known-answer
fixtures for exact stable schema `1.0.0`. The packaged 1.0.0 schema is retained
as an exact-version validator; its refget-pattern correction is a schema-only
erratum that makes the validator accept the already-defined `SQ.<32-character>`
identity representation and does not change these report bytes.

`stable-compatible-report-1.1.0.json` and
`stable-incompatible-report-1.1.0.json` pin the retained additive M7 stable shape.
`stable-ucsc-alignment-report-1.1.0.json` additionally pins report-owned resource
observations, BAM/CRAM dictionary relationship context, and UCSC provider/source/
profile provenance for a content-authorized authoritative-name binding.
`stable-ucsc-content-conflict-report-1.1.0.json` pins the adversarial case where
provider target content conflicts with an independently identity-bound peer and
ensures the target-anchor plus validation capabilities cited by profile provenance
remain present in the serialized capability partition. All 1.1.0 headers map to
the packaged `refcompat.schemas/compatibility-report-1.1.0.schema.json` resource.

`human-compatible-report.txt` pins the current deterministic plain-text view of a
simple compatible report. Human text is for people rather than machine parsing; the
versioned JSON Schema remains the stable machine contract.
