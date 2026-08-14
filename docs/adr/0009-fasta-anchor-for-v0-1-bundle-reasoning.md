
# ADR 0009 — Explicit FASTA anchor for v0.1 bundle reasoning

**Status:** Accepted
**Date:** 2026-08-13

## Context

Whole-bundle analysis needs a candidate reference context. Choosing a “dominant” reference by majority could let several mutually consistent but mislabeled resources overrule stronger sequence content.

## Decision

Authoritative multi-resource `check` in v0.1 uses an explicitly selected FASTA as the reference anchor. Its locally derived sequence/SeqCol identity defines the candidate reference context. Other resources are evaluated against it.

Resources do not vote on reference identity.

Reference-free comparison may be introduced later when available evidence is sufficient and its semantics are designed explicitly.

## Consequences

The first implementation has a clear authority model, enables direct REF/base/bounds checks, and avoids confidence inflation from metadata consensus.
