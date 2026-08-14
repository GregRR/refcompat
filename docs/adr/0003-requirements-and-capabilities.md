
# ADR 0003 — Model compatibility as requirements and capabilities

**Status:** Accepted
**Date:** 2026-08-13

## Context

Reference resources need not be identical to be interoperable. A GTF can require only a subset of a larger FASTA, while a BAM may declare additional decoys. Equality-based comparisons are therefore too blunt.

## Decision

Model each resource, in an evaluation context, as typed capabilities and requirements. Evaluate compatibility by satisfying mandatory requirements with adequately evidenced capabilities.

Requirements/capabilities must be typed rather than generic string dictionaries.

## Consequences

Compatibility can be directional and scoped. Subset/superset relationships can be represented without collapsing them into “different = incompatible.”
