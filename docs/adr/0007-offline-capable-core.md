
# ADR 0007 — Offline-capable deterministic core

**Status:** Accepted
**Date:** 2026-08-13

## Context

Genomic resources may be large, private, or processed on HPC systems without reliable internet access. Sequence identity can be computed locally.

## Decision

Basic RefCompat analysis must work without network access. Local content-derived refget/SeqCol identity is preferred when sequence content is available.

Remote services may provide optional alias, metadata, or known-reference discovery. Their failure must not invalidate otherwise sufficient local analysis.

For CRAM, header-only analysis must not trigger reference retrieval. A future reference-dependent decode may use an explicit local FASTA only when RefCompat has verified that anchor as eligible for exact-name provider lookup; otherwise the decode remains deferred. The planner does not select ambient `REF_PATH`/`REF_CACHE`, `@SQ UR`, or network retrieval. A future decoder adapter must explicitly preserve that isolation because supplying a FASTA path gives it priority but does not itself disable every provider fallback.

## Consequences

Remote identity/metadata enrichment is isolated behind optional interfaces and normalized failure behavior.
