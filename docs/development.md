# Development

The repository targets Python 3.12 and uses Poetry.

## Tooling

- Ruff for linting and formatting;
- mypy in strict mode;
- pytest;
- pre-commit;
- MkDocs Material;
- NumPy/SciPy;
- Shapely.

## Before a pull request

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
```

## Code organisation

Reusable logic belongs in `src/lisbon_spatial_dynamics/`.

Research outputs should come from package commands rather than hidden notebook state.

## Pull-request scope

Prefer coherent reviewable milestones. A larger PR is appropriate when one research milestone genuinely spans data contracts, analysis, tests, and documentation; avoid splitting one logical result into many trivial PRs.

## Release discipline

Stable releases must preserve immutable source snapshots, build into a fresh output root, write a provenance manifest, keep model specifications versioned, pass repository checks, and update release/citation metadata when needed.
