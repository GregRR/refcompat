# Development

RefCompat uses `uv` for project environments, dependency locking, builds, and local command execution.

## Python support

The package currently supports Python 3.10–3.14; Python 3.11+ is recommended for new environments. The repository's development interpreter remains pinned in `.python-version`; CI exercises Python 3.10, 3.11, 3.12, 3.13, and 3.14.

## Environment setup

From the repository root:

```bash
uv sync --all-groups
```

The committed `uv.lock` is the reproducible development lockfile. After dependency metadata changes, regenerate it with:

```bash
uv lock
```

## Required checks

Run these before proposing a change:

```bash
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv build
```

`ruff format .` may be used to apply formatting before re-running the checks.

## Dependency discipline

Initial runtime dependencies are intentionally minimal. A package should be added only when implementation needs it directly; transitive availability is not a reason to import it without declaring it.

See [`dependency-policy.md`](dependency-policy.md) for licensing and adoption policy.
