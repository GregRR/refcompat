
# ADR 0002 — Separate inspection from compatibility reasoning

**Status:** Accepted
**Date:** 2026-08-13

## Context

Format parsers can easily accumulate interpretation rules, making it difficult to distinguish directly observed facts from conclusions and difficult to reuse observations across evaluation scopes.

## Decision

Inspectors emit immutable observations and provenance/relation claims. They do not emit top-level compatibility verdicts or infer facts such as “wrong assembly” or “verified alias.”

Scope-dependent contract construction and compatibility reasoning occur in later layers.

## Consequences

The same inspected resource can participate in multiple profiles/scopes without re-parsing or mutating facts. Every conclusion can trace back to source observations.
