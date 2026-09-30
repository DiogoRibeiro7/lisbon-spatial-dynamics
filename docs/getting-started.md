# Getting started

Lisbon Spatial Dynamics v1 uses Python 3.12 and Poetry.

## Install

```bash
git clone https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics.git
cd lisbon-spatial-dynamics

poetry install --with docs
poetry run pre-commit install
```

## Run checks

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
```

## Build the complete v1 study

The stable release starts from archived source snapshots rather than live network calls:

```bash
poetry run build-study-v1 \
  <housing-snapshot.json> \
  <rnal-snapshot.records.json> \
  <census-snapshot.zip> \
  <lisbon_freguesias.csv> \
  <lisbon_freguesias.geojson> \
  <output-root>
```

Optional release parameters:

```text
--model-config configs/multivariable_models.toml
--expected-freguesias 24
--permutations 999
--seed 42
--local-alpha 0.05
```

The output root must not already exist.

## Output structure

```text
<output-root>/
├── reference/
├── panels/
├── context/
├── analysis/
│   ├── normalized/
│   └── multivariable/
├── results/
│   └── final/
└── study_manifest.json
```

The manifest records SHA-256 digests for every input snapshot and generated file.

## Preview documentation

```bash
poetry run mkdocs serve
```
