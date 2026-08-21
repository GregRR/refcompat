# ADR 0013 — Broaden the Python compatibility floor to 3.10

**Status:** Accepted

## Context

ADR 0011 initially selected Python >=3.12 to keep the implementation baseline modern. RefCompat is intended to be easy to adopt in established bioinformatics, HPC, workflow, and conda-style environments, where interpreter upgrades often lag application development. Requiring 3.12 would exclude otherwise viable environments without providing a scientific or architectural benefit to RefCompat.

Python 3.10 is in security-fixes-only maintenance and reaches upstream end of life in October 2026, so it is not the preferred interpreter for new environments. It is nevertheless the useful compatibility floor for the current dependency set: `refget>=0.12,<0.13` requires Python >=3.10, while `pysam>=0.24,<0.25` supports Python >=3.8 and provides Python 3.10 wheels on the major platforms RefCompat targets. The current pytest and mypy development lines also support Python 3.10.

A source audit found four implementation features above Python 3.10: PEP 695 `type` alias statements, PEP 695 generic function type-parameter syntax, `enum.StrEnum`, and `typing.assert_never`. None is scientifically material or worth imposing a newer interpreter floor.

## Decision

RefCompat will:

- declare Python >=3.10 package compatibility;
- recommend Python 3.11 or newer for newly created environments;
- retain Python 3.14.7 as the repository development pin;
- test Python 3.10, 3.11, 3.12, 3.13, and 3.14 in CI;
- target Python 3.10 in Ruff and mypy so newer syntax/APIs are caught during normal development;
- use Python 3.10-compatible type-alias syntax and small RefCompat-owned compatibility helpers for the `StrEnum` and `assert_never` behavior the project needs;
- avoid adding `typing_extensions` solely for these two small compatibility needs; and
- reconsider the Python floor based on actual bioinformatics/dependency adoption rather than automatically dropping 3.10 at its upstream end-of-life date.

## Consequences

RefCompat remains developable on the current interpreter while becoming installable in a broader set of scientific environments. The compatibility helpers are intentionally tiny and internal; they do not change the public scientific model. CI becomes slightly more expensive because five interpreter versions are tested instead of three.

Python 3.10 support is a compatibility commitment, not a recommendation to create new 3.10 environments.

## References

- Python 3.10 release schedule / lifecycle: https://peps.python.org/pep-0619/
- `refget` package metadata: https://pypi.org/project/refget/
- `pysam` 0.24 package metadata and wheels: https://pypi.org/project/pysam/0.24.0/
