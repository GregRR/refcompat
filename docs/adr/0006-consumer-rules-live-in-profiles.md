
# ADR 0006 — Consumer-specific rules live in profiles

**Status:** Accepted
**Date:** 2026-08-13

## Context

Resources can be reference-coordinate compatible while still failing a particular consumer because that tool requires specific naming, ordering, metadata, dialect, or bundle composition.

## Decision

Core RefCompat establishes resource facts and generic reference-coordinate constraints. Consumer/ecosystem-specific requirements belong in explicit profiles (for example a future UCSC or GATK-oriented profile).

Profiles may add requirements and policy rules. They may not rewrite observations or redefine sequence identity.

## Consequences

The core remains scientifically general while profiles can model real operational interfaces without contaminating universal compatibility semantics.
