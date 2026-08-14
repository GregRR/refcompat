
# ADR 0008 — Conditional compatibility requires explicit scope

**Status:** Accepted
**Date:** 2026-08-13

## Context

It is tempting to treat ALT, decoy, patch, mitochondrial, unplaced, or other sequences as “probably irrelevant” and downgrade conflicts automatically. RefCompat generally cannot infer the user's biological or operational intent.

## Decision

`COMPATIBLE_WITH_CONDITIONS` requires an explicit evaluation scope or profile rule that defines the bounded claim. RefCompat does not silently exclude sequence classes because they appear secondary.

## Consequences

Conditions become structured, testable statements of what compatibility was actually established for. Unknown relevance remains unresolved rather than guessed.
