# Milestone 7 report fixtures

`draft-compatible-report.json` pins the provisional revision-2 M7 projection
retained for draft callers. It has no stable compatibility guarantee.

`stable-compatible-report-1.0.0.json` and
`stable-incompatible-report-1.0.0.json` pin exact deterministic bytes for
representative positive and decisive-conflict reports under the first stable core
compatibility-report schema. Their headers name schema version `1.0.0`, which
maps to the packaged `refcompat.schemas/compatibility-report-1.0.0.schema.json`
resource. Later M7 relationship/provenance additions must advance the stable
schema version rather than mutate these fixtures in place.
