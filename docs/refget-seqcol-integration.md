
# GA4GH refget / SeqCol integration boundary

**Investigation snapshot:** 2026-08-13

This document records how RefCompat should integrate with the current GA4GH refget/SeqCol Python ecosystem without coupling its domain model to a rapidly evolving pre-1.0 implementation.

## Standards ownership

RefCompat does not define:

- individual biological sequence identity;
- sequence-collection digest algorithms;
- SeqCol comparison semantics;
- alternative rules for name-relaxed/order-relaxed collection identity.

Those responsibilities belong to GA4GH refget Sequences and Refget Sequence Collections (SeqCol).

RefCompat begins after those relationships are available: it determines what heterogeneous resources require/provide and whether those relationships are sufficient for the requested use.

## Current Python implementation

The upstream `refget` Python project provides:

- local Rust-backed GA4GH digest computation;
- FASTA/sequence-collection digest functions;
- local `RefgetStore` functionality;
- remote sequence/sequence-collection clients;
- optional server/database extras separated from the light base install.

At the investigation date, upstream had moved to the 0.12 development/release line and remained pre-1.0. That is useful functionality but also a reason to keep a narrow adapter boundary.

Primary upstream references:

- https://refgenie.org/refget/
- https://refgenie.org/refget/using-services/digests/
- https://ga4gh.github.io/refget/seqcols/
- https://github.com/refgenie/refget

## Required architectural boundary

```text
RefCompat domain
    ^
    |
ReferenceIdentityProvider
    ^
    |
Ga4ghRefgetIdentityProvider
    ^
    |
external refget / gtars implementation
```

External `refget`, `gtars`, HTTP-client, or server-model objects should be translated immediately into RefCompat-owned immutable values.

### Why

- upstream is still pre-1.0 and actively evolving;
- RefCompat report serialization should not depend on an external object's layout;
- normalized error behavior must remain stable;
- an alternative standards-conforming implementation should be substitutable later;
- reasoning code should express RefCompat semantics, not library-specific mechanics.

## Proposed core port

Conceptually:

```python
class ReferenceIdentityProvider(Protocol):
    def inspect_fasta(
        self,
        resource: Resource,
    ) -> SequenceCollectionSnapshot: ...

    def compare_complete_collections(
        self,
        a: SequenceCollectionSnapshot,
        b: SequenceCollectionSnapshot,
    ) -> SequenceCollectionComparison: ...
```

Exact signatures should be frozen only during the first implementation slice.

## Local first; remote optional

The deterministic core should work with network access disabled.

Local FASTA content can provide:

- sequence names;
- lengths;
- per-sequence GA4GH identity;
- collection identity;
- collection component digests/relationships;
- base lookup for later VCF verification.

Remote SeqCol services can later enrich:

- known aliases;
- assembly/distribution metadata;
- discovery of known collections;
- external metadata records.

Remote enrichment is not allowed to become a prerequisite for a local compatibility verdict when sufficient local evidence exists.

## Separate remote metadata port

Do not overload `ReferenceIdentityProvider` with HTTP behavior. Introduce a separate optional abstraction when needed, conceptually:

```python
class ReferenceMetadataResolver(Protocol):
    def resolve_collection_alias(...): ...
    def resolve_sequence_alias(...): ...
    def lookup_collection_metadata(...): ...
```

A remote outage should mean “optional enrichment unavailable,” not “local analysis invalid.”

## Sequence and collection identifier types

RefCompat should have distinct immutable types for:

- artifact-level digest;
- `RefgetSequenceId` (`SQ.`-prefixed identity);
- raw SHA512t24u digest where an external API exposes one;
- SeqCol top-level digest;
- SeqCol component/attribute digest;
- legacy MD5/M5.

A generic `digest: str` field is too error-prone.

## Preserve SeqCol comparison facets

SeqCol comparison exposes multiple dimensions of relationship. RefCompat should not collapse them immediately into one enum such as `SAME_REFERENCE`.

Preserve enough information to reason independently about:

- exact collection identity;
- sequence-content overlap;
- name overlap;
- length overlap;
- order agreement;
- sequence subset/superset;
- coordinate-system relationships.

Human-friendly relationship labels can be derived later as findings.

## Complete versus partial resources

Do not manufacture a full SeqCol identity from a sparse resource merely because it mentions several sequences.

Examples:

- a GTF using `chr1`, `chr2`, and `chrX` does not prove that its underlying reference consists of only those three sequences;
- a VCF containing variants only on chromosome 7 does not prove a one-chromosome reference genome.

`SequenceCollectionSnapshot.completeness` must represent this distinction explicitly.

## `.fai` opportunity

The current refget/gtars surface includes FASTA-index computation functionality. RefCompat can use standards/library-backed FASTA parsing to compare a supplied `.fai` against the exact FASTA representation, including byte-layout fields where supported, rather than checking only sequence names and lengths.

Derived-artifact verification remains a RefCompat responsibility: biological sequence equivalence does not make an index for a differently represented FASTA a valid companion artifact.

## `RefgetStore` is not required for v0.1

For the first implementation slice, direct FASTA inspection is sufficient. A store may become useful later for caching, content retrieval by digest, repeated analyses, or remote-backed reference inventories.

Do not introduce it until those needs are demonstrated.

## Normalized errors

The adapter should convert external failures into a small stable RefCompat vocabulary, such as:

```text
ReferenceIdentityError
├── ReferenceUnreadableError
├── ReferenceParseError
├── IdentityComputationError
└── IdentityProviderIncompatibleError
```

Remote metadata errors belong to a separate hierarchy such as service unavailable, not found, invalid response, or timeout.

## Initial adapter tests

Required cases include:

- deterministic identity for the same FASTA;
- rename-only relationship;
- order-only relationship;
- one-base content change;
- sequence subset/superset;
- malformed FASTA;
- non-human/custom FASTA;
- no network attempted during local inspection;
- raw digest and `SQ.` identifier never confused;
- artifact digest never substitutable for biological identity;
- upstream object types do not escape the adapter boundary;
- optional remote service failure does not invalidate local results.

Known-answer test values should be anchored to GA4GH/refget compliance fixtures or specification examples where redistribution permits.
