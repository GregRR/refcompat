
# Architecture Decision Records

ADRs record stable decisions that should not be silently changed during implementation.

| ADR | Decision |
|---|---|
| [0001](0001-standards-first-reference-identity.md) | Delegate sequence and sequence-collection identity to GA4GH refget/SeqCol |
| [0002](0002-separate-inspection-from-reasoning.md) | Separate format inspection from compatibility reasoning |
| [0003](0003-requirements-and-capabilities.md) | Model compatibility as typed requirements versus capabilities |
| [0004](0004-categorical-verdicts-no-global-score.md) | Use categorical verdicts; no global compatibility score |
| [0005](0005-no-silent-scientific-repair.md) | Diagnose but do not silently repair scientific resources |
| [0006](0006-consumer-rules-live-in-profiles.md) | Put consumer-specific requirements in profiles |
| [0007](0007-offline-capable-core.md) | Keep the deterministic core offline-capable |
| [0008](0008-conditions-require-explicit-scope.md) | Conditional compatibility requires explicit scope |
| [0009](0009-fasta-anchor-for-v0-1-bundle-reasoning.md) | Use an explicit FASTA anchor for v0.1 bundle reasoning |
| [0010](0010-apache-2-license.md) | License RefCompat under Apache-2.0 |
| [0011](0011-python-packaging-and-quality-tooling.md) | Use Python >=3.12, uv, pytest, Ruff, and strict mypy |
| [0012](0012-minimal-runtime-dependencies-and-format-parsing.md) | Keep runtime dependencies minimal and add parsers by milestone |

ADRs use the statuses `Proposed`, `Accepted`, `Superseded`, or `Rejected`. The initial records are `Accepted` design decisions; implementation may reveal a need to supersede them, but changes should be explicit and justified.
