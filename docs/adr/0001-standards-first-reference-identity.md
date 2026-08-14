
# ADR 0001 — Standards-first reference identity

**Status:** Accepted
**Date:** 2026-08-13

## Context

RefCompat needs exact sequence and sequence-collection identity, but defining another digest/comparison scheme would duplicate an active GA4GH standard and create incompatible semantics.

## Decision

- Delegate individual biological sequence identity to GA4GH refget Sequences.
- Delegate sequence-collection identity and comparison to GA4GH Refget Sequence Collections (SeqCol).
- Consume SAM/VCF checksums, names, lengths, and metadata as additional evidence without redefining standardized identity.
- Translate external library objects into RefCompat-owned immutable values at a narrow adapter boundary.

## Consequences

RefCompat owns interoperability semantics above sequence identity, not identity itself. Upstream API changes should be isolated to the adapter. Remote SeqCol discovery is optional enrichment, not a prerequisite for local analysis.

## References

- https://ga4gh.github.io/refget/seqcols/
- https://refgenie.org/refget/
