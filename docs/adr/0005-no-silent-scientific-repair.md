
# ADR 0005 — No silent scientific repair

**Status:** Accepted
**Date:** 2026-08-13

## Context

Many apparent reference problems tempt automatic changes such as contig renaming, BAM reheadering, allele swapping, or liftover. Those operations can change scientific meaning when the diagnosis is wrong.

## Decision

The initial RefCompat core is diagnostic. It must not silently rename contigs, reheader BAM/CRAM, rewrite VCF REF/ALT, perform liftover, delete reference sequences, realign data, or repair annotation structure.

Lossless/reversible normalization may be identified when proven by strong evidence, but mutation remains a separate explicit operation outside the initial scope.

## Consequences

RefCompat favors traceable diagnosis and safe next actions over convenience-based mutation.
