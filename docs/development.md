# Development

The repository requires Python 3.12 or newer and uses Poetry 2.2.1 with a committed lockfile. CI covers Python 3.12/3.13 on Linux and Python 3.13 on Windows.

Install with `poetry sync --with docs`, then enable hooks with `poetry run pre-commit install`. The hooks run the same locked Ruff and mypy installations as CI.

The full [contribution guide](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/CONTRIBUTING.md) covers issue reports, data handling, methodological changes, and releases.

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
poetry check --lock --strict
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
poetry build
```

## Code organisation

Reusable logic belongs in `src/lisbon_spatial_dynamics/`.

Research outputs should come from package commands rather than hidden notebook state.

## Pull-request scope

Prefer coherent reviewable milestones. A larger PR is appropriate when one research milestone genuinely spans data contracts, analysis, tests, and documentation; avoid splitting one logical result into many trivial PRs.

## Release discipline

Stable releases must preserve immutable source snapshots, build into a fresh output root, write a provenance manifest, keep model specifications versioned, pass repository checks, and update release/citation metadata when needed.
