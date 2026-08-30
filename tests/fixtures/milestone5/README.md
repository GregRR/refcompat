# Milestone 5 annotation fixtures

These are small synthetic GTF/GFF3 resources used to exercise RefCompat's
Milestone 5 reference-coordinate contract. They are intentionally not tied to
any real organism or assembly unless a provenance directive is being tested.

The fixture family covers exact sparse coordinates, evidence-backed cross-name
binding, unresolved naming differences, hard bounds conflicts, GFF3
`##sequence-region`, circular-origin wrapping including provider-generated
landmark IDs that differ from the seqid, embedded-sequence identity,
provenance-vs-identity claims, duplicate identity ambiguity, and mixed hard/unresolved
problems.
