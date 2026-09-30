# Contributing

Contributions should make the study easier to reproduce, inspect, or extend. Report bugs and propose changes through [GitHub issues](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/issues/new/choose). For a methodological change, describe the research question and assumptions before implementing a new model or data source.

## Set up

Use Python 3.12 or 3.13 and Poetry 2.2.1. From a checkout:

```bash
poetry sync --with docs
poetry run pre-commit install
git switch -c your-change
```

Commit `poetry.lock` when changing dependencies. Use `poetry lock` to refresh it after editing dependency constraints, then `poetry sync --with docs`. Keep unrelated dependency upgrades out of a focused fix.

## Validate changes

```bash
poetry check --lock --strict
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest -q
poetry run mkdocs build --strict
poetry build
```

Run `poetry run ruff format .` to apply the shared formatting rules. Tests must run offline with small, deterministic fixtures. Network acquisition should be mocked at the request boundary. Use the non-interactive Matplotlib backend (`MPLBACKEND=Agg`) in headless environments.

CI checks Linux with Python 3.12/3.13 and Windows with Python 3.13. Formatting and type checks are required; do not disable them to hide a failure. The documentation workflow builds every pull request and deploys the main branch.

## Code and data conventions

- Put reusable code in `src/lisbon_spatial_dynamics/`; command entry points belong in `cli.py` and `pyproject.toml`.
- Keep acquisition, transformation, panel construction, statistical analysis, and presentation separate.
- Preserve missing values and validate identifiers, geographic coverage, units, and time windows explicitly.
- Treat snapshots and generated study directories as immutable. Add tests for failure paths where a change can damage outputs or invalidate provenance.
- Keep raw datasets, generated results, credentials, and RNAL proprietor/contact information out of commits and issue attachments. Use minimal synthetic reproductions.
- Document new sources in the source catalogue and explain their temporal/spatial coverage and reuse conditions.

## Research changes

Explain changes to the estimand, comparison window, geography, population denominator, predictor definitions, spatial weights, or uncertainty calculation in the methodology documentation. Update affected regression tests and output contracts. Preserve the distinction between descriptive association and causal inference.

The Census 2021 denominator is static, and the model sample is small. Do not select specifications based on significance or present synthetic fixtures as empirical results. A change to input data requires a new run and manifest, even if the software version is unchanged.

## Pull requests

Describe the problem, resulting behaviour, and validation performed. Include documentation with user-visible changes and add an entry under `Unreleased` in `CHANGELOG.md`. Use the pull-request template to identify effects on study outputs and reproducibility.

## Releases

Build and test from a clean checkout. Align package and citation versions, update the changelog, and document whether a release contains software only or an archived study bundle. A research bundle needs retained input snapshots (where redistribution is permitted), model configuration, software revision, dependency lockfile, acquisition manifests, computed outputs, and `study_manifest.json`. Record how restricted inputs can be obtained when they cannot be redistributed.
