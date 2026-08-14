# ADR 0011 — Python, packaging, and quality-tooling baseline

**Status:** Accepted

## Context

RefCompat needs a reproducible development environment, a packaging baseline suitable for PyPI, and automated checks before substantive implementation begins. The supported Python floor should avoid versions that are already in security-fixes-only maintenance while retaining useful scientific-Python compatibility.

## Decision

RefCompat will:

- support Python 3.12 and newer;
- use Python 3.14.7 as the repository development pin;
- test Python 3.12, 3.13, and 3.14 in CI;
- use `uv` for environment management, locking, command execution, and builds;
- use `uv_build` as the pure-Python build backend;
- commit `uv.lock`;
- use pytest for tests;
- use Ruff for linting and formatting;
- use mypy in strict mode for static type checking.

The initial package version is `0.1.0.dev0` to mark development toward the first 0.1 release without implying a stable public API.

## Consequences

The project has one reproducible dependency workflow and a small number of quality tools. Supporting Python 3.12 constrains syntax and typing features used in distributed code even when development occurs on 3.14.
