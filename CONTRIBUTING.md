
# Contributing to RefCompat

RefCompat is in early development. Architectural, scientific, and implementation contributions should follow these principles.

## Review priorities

Reviewers are encouraged to challenge whether:

1. a proposed RefCompat responsibility is already solved adequately by an existing standard or tool;
2. a compatibility conclusion is stronger than the evidence actually supports;
3. a provenance claim is accidentally being promoted to verified identity;
4. a rule incorrectly treats similarity as compatibility;
5. a condition depends on RefCompat guessing user intent rather than explicit evaluation scope;
6. a format-specific rule belongs in the core or in a consumer profile;
7. a proposed repair could change scientific meaning;
8. a negative-control case would be misdiagnosed as a reference problem;
9. the same model works for non-human and custom references rather than only familiar human assemblies.

## Scientific transparency

Non-obvious coordinate, sequence-identity, provenance, evidence, completeness, and interpretation decisions should be documented near the implementation. Comments and docstrings should explain *why* a rule exists and what must not be inferred, rather than restating obvious code.

When a rule, algorithm, or scientific interpretation is materially derived from a standard or primary source, include an appropriate reference near the implementation or in the associated design documentation.

## Scope discipline

RefCompat should be liberal in diagnosis and conservative in repair. Core code must not silently:

- rename contigs;
- reheader BAM/CRAM files;
- rewrite VCF REF/ALT alleles;
- perform liftover;
- delete ALT/decoy/patch sequences;
- realign data;
- repair annotation structures.

Lossless normalization may be described when it is evidence-backed and reversible, but transformation is a distinct operation and is not part of the initial implementation.

## Development workflow

RefCompat uses `uv` and supports Python 3.10–3.14; Python 3.11+ is recommended for new environments. The repository development interpreter is pinned in `.python-version`.

Before proposing a change, run:

```bash
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv build
```

See [`docs/development.md`](docs/development.md) for setup details.

## Dependency licensing

Runtime dependencies should preferably use permissive licenses such as Apache-2.0, MIT, BSD-2-Clause, or BSD-3-Clause. Dependencies with copyleft, source-available, noncommercial, or custom/restrictive terms require explicit review before adoption. See [`docs/dependency-policy.md`](docs/dependency-policy.md).
