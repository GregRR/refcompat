
# ADR 0004 — Categorical verdicts; no global compatibility score

**Status:** Accepted
**Date:** 2026-08-13

## Context

A numeric score can make a hard contradiction appear compensable by many weak matches. Scientific interoperability questions often contain veto conditions.

## Decision

Use categorical top-level verdicts:

- `COMPATIBLE`
- `COMPATIBLE_WITH_CONDITIONS`
- `INCOMPATIBLE`
- `INDETERMINATE`

Do not produce a single global numeric compatibility score.

Per-check counts/percentages may be reported when they describe measurements (for example VCF REF mismatch rate), but they do not mathematically average away hard conflicts.

## Consequences

Reports emphasize evidence, failed/unresolved constraints, and scope rather than a misleading scalar rank.
