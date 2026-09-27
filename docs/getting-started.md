# Getting started

Lisbon Spatial Dynamics uses Python 3.12 and Poetry.

## Clone the repository

```bash
git clone https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics.git
cd lisbon-spatial-dynamics
```

## Install the development environment

```bash
poetry install --with docs
poetry run pre-commit install
```

## Run the checks

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
```

## Preview the documentation

```bash
poetry run mkdocs serve
```

MkDocs will print the local preview address in the terminal.

## Repository layout

```text
.
├── configs/                  # Reproducible configuration
├── data/
│   ├── raw/                  # Source data, not committed
│   ├── interim/              # Intermediate transformations
│   └── processed/            # Analysis-ready derived data
├── docs/                     # Project documentation
├── notebooks/                # Exploratory and research notebooks
├── scripts/                  # Reproducible command-line workflows
├── src/
│   └── lisbon_spatial_dynamics/
└── tests/
```

The package code should contain reusable data and analysis logic. Notebooks are for exploration, diagnostics, and communication rather than hidden production pipelines.
