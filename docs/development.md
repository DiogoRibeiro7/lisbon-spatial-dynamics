# Development

The repository follows a small-PR workflow and keeps reusable logic inside the Python package.

## Environment

The project targets Python 3.12 and uses Poetry for dependency management.

Development tooling includes:

- Ruff for linting and formatting;
- mypy in strict mode;
- pytest for tests;
- pre-commit for local checks;
- MkDocs Material for documentation.

## Before opening a pull request

Run:

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
```

## Code organisation

Prefer focused modules with explicit interfaces over large notebooks or scripts.

New data-source integrations should separate:

1. acquisition;
2. parsing;
3. validation;
4. harmonisation;
5. persistence.

This makes source-specific assumptions visible and testable.

## Type discipline

Public functions should use precise type annotations. Avoid weakening type checking merely to silence errors; isolate unavoidable third-party typing gaps instead.

## Pull requests

Keep pull requests small enough that data assumptions, methodological changes, and code changes can be reviewed independently whenever possible.
