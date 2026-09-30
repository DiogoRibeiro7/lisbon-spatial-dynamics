# Reproducibility

Reproducibility is part of the v1 release contract.

## Immutable release inputs

A v1 build starts from archived local snapshots:

1. INE housing JSON;
2. RNAL privacy-minimized records JSON;
3. official Censos 2021 synthesis ZIP;
4. canonical CAOP freguesia CSV;
5. canonical CAOP freguesia GeoJSON;
6. versioned multivariable-model configuration.

This isolates a stable research release from later upstream API changes.

The v1.0.0 GitHub release does not attach these inputs or a results bundle. Preserve them separately for every empirical run. Hashes identify files but do not make missing inputs recoverable.

## Software environment

Use the same software tag or commit and its committed `poetry.lock`, then run `poetry sync --with docs`. Record the Python version and operating system alongside the study manifest. The manifest records data hashes and analysis parameters; it does not currently capture the Git revision or full installed environment.

The offline test suite validates software contracts using fixtures. A successful test run does not substitute for validating coverage, data quality, and findings from official snapshots.

## One-command build

```bash
poetry run build-study-v1 \
  <housing-snapshot.json> \
  <rnal-snapshot.records.json> \
  <census-snapshot.zip> \
  <lisbon_freguesias.csv> \
  <lisbon_freguesias.geojson> \
  <output-root>
```

The output root must be new. If any stage fails, the partial release directory is removed.

## Provenance manifest

Each successful build writes `study_manifest.json` with:

- study release version;
- expected freguesia count;
- permutation count;
- random seed;
- Local Moran FDR alpha;
- input path, byte size, and SHA-256;
- output path, byte size, and SHA-256;
- interpretation contract.

## Default analysis settings

```text
canonical freguesias: 24
spatial permutations: 999
random seed: 42
Local Moran FDR alpha: 0.05
```

Model specifications live in `configs/multivariable_models.toml`.

## Traceability

The final-results layer synthesizes existing machine-readable outputs. It does not silently refit models or recompute spatial statistics.

## Repository checks

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
```

Notebooks may support exploration or communication, but v1 release results must be reproducible without hidden notebook state.
