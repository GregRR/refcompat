# Milestone 9 fixtures

Milestone 9 introduces standard BED as a distinct sparse coordinate resource.

`stable-empty-bed-report-3.0.0.json` is the first schema-3.0.0 known answer. It
represents a completed empty-BED analysis: the report carries the explicit
`bed3` layout as a generic resource observation, contains no fabricated feature
requirements, and is therefore scientifically indeterminate rather than
incompatible. Slice 3's inspector likewise observes no features from a valid
empty or comment-only resource. The same payload is rejected by exact schema
2.0.0 because that retained schema's closed resource-kind enum predates BED
support.

Schema 3.0.0 otherwise preserves the exact 2.0.0 report body. Slice 2 changes
only the schema identity and adds the `bed` resource-kind wire value; exact
schemas and known answers from Milestones 7 and 8 remain byte-for-byte retained.
