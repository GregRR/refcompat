# ADR 0010 — License RefCompat under Apache-2.0

**Status:** Accepted

## Context

RefCompat is intended as interoperability infrastructure that may be embedded in academic, open-source, workflow, infrastructure, and commercial environments. Broad adoption is better served by a permissive license than by reciprocal/copyleft requirements.

The surrounding reference-genome interoperability ecosystem also predominantly uses permissive licenses.

## Decision

RefCompat is licensed under the Apache License 2.0.

The project will:

- include the standard Apache-2.0 `LICENSE` text;
- include a `NOTICE` file for project provenance;
- include `CITATION.cff` so scholarly citation is straightforward;
- prefer permissively licensed runtime dependencies;
- explicitly review dependencies with materially different redistribution or copyleft obligations before adoption.

## Consequences

Downstream users may incorporate RefCompat into proprietary or open systems without being required by RefCompat's license to open-source those systems.

Apache-2.0 also provides an explicit patent grant from contributors.

Software licensing does not guarantee scholarly citation, so citation metadata is maintained separately from license notices.
