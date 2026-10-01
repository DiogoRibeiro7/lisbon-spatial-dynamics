# Getting started

This guide takes you from a fresh checkout to a study build. Use Python 3.12 or newer, Git, and Poetry 2.2.1. Commands run from the repository root. Multiline examples use Bash syntax; PowerShell users can enter each command on one line.

## Install and check the environment

```bash
git clone https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics.git
cd lisbon-spatial-dynamics
poetry sync --with docs
poetry run build-study-v1 --help
poetry run pytest -q
```

Poetry installs the versions recorded in `poetry.lock`. If it selects the wrong Python interpreter, run `poetry env use 3.12` (or the path to your interpreter) before syncing.

The test suite runs with local fixtures. It does not need the official datasets, credentials, or live source services. A passing test suite verifies software behaviour; it does not validate a particular empirical study.

## Choose the inputs

To reproduce an existing full pipeline study, use its archived snapshots, reference geography, model configuration, software revision, and dependency lockfile. Version 1.0.1 also commits a small empirical evidence layer under `data/release/v1.0.1/` and `results/release/v1.0.1/`, but those curated tables do not replace the archived raw inputs required for a full pipeline reproduction.

To create a new study, acquire fresh snapshots as described below. The source services require network access. Preserve the fetched files and acquisition manifests: future downloads can contain revised records or different coverage.

## Acquire source snapshots

```bash
poetry run fetch-caop-lisbon
poetry run fetch-ine-housing
poetry run fetch-rnal-lisboa
poetry run fetch-census2021-population
```

Each command prints the files it saved. Keep the exact paths; each fetch has its own timestamp.

| Command | Input needed by later stages |
| --- | --- |
| `fetch-caop-lisbon` | `data/raw/dgt/caop2025/lisbon_freguesias/<timestamp>.geojson` |
| `fetch-ine-housing` | `data/raw/ine/housing/0012234/<timestamp>.data.json` |
| `fetch-rnal-lisboa` | `data/raw/turismo_portugal/rnal/lisboa/<timestamp>.records.json` |
| `fetch-census2021-population` | `data/raw/ine/census2021/subsections/<timestamp>.zip` |

The housing default is indicator `0012234` under NUTS 2024. The v1 parish panel expects this indicator. The historical `0011364` series has a separate acquisition configuration and is not a substitute for this input.

See [Data sources](data-sources.md) for source contracts and privacy handling. Downloaded files stay outside version control.

## Prepare the reference geography

Replace the placeholder with the GeoJSON path printed by `fetch-caop-lisbon`:

```bash
poetry run build-reference-geography \
  data/raw/dgt/caop2025/lisbon_freguesias/<timestamp>.geojson \
  data/processed/reference
```

This produces `lisbon_freguesias.csv` and `lisbon_freguesias.geojson` in the reference directory. The transformation checks the official identifiers and parish coverage. Preserve both files with your study inputs.

## Build the study

Replace the three snapshot placeholders with your selected files:

```bash
poetry run build-study-v1 \
  data/raw/ine/housing/0012234/<timestamp>.data.json \
  data/raw/turismo_portugal/rnal/lisboa/<timestamp>.records.json \
  data/raw/ine/census2021/subsections/<timestamp>.zip \
  data/processed/reference/lisbon_freguesias.csv \
  data/processed/reference/lisbon_freguesias.geojson \
  data/processed/releases/my-study
```

The output root must be new. A failed processing stage removes the partial output root. Keep original inputs outside it.

| Option | Default | Purpose |
| --- | --- | --- |
| `--model-config` | `configs/multivariable_models.toml` | Versioned regression specifications |
| `--expected-freguesias` | `24` | Expected reference geography coverage |
| `--permutations` | `999` | Spatial permutation count |
| `--seed` | `42` | Random seed for spatial analysis |
| `--local-alpha` | `0.05` | Local Moran FDR significance threshold |

The Census population reference and neighbourhood context are built from the same archive during this command; separate population/context commands are optional intermediate workflows.

## Inspect and retain the outputs

```text
data/processed/releases/my-study/
├── reference/
├── panels/
├── context/
├── analysis/
│   ├── normalized/
│   └── multivariable/
├── results/final/
└── study_manifest.json
```

Read `results/final/findings.md` and the [results guide](results.md) together. `findings.json` and the CSV tables provide machine-readable values. The manifest records analysis parameters and SHA-256 digests of inputs and generated files.

Retain the source snapshots, acquisition manifests, reference geography, model configuration, software revision, `poetry.lock`, and full output directory. A digest identifies a file; it does not replace an archived copy. See [Reproducibility](reproducibility.md).

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| A fetch command times out | Check the provider service and retry with a larger `--timeout`. Reuse a verified archived snapshot when reproducing a previous study. |
| Missing input file | Replace every placeholder with an existing file; use the paths printed by acquisition. |
| Output directory already exists | Choose a new output name so the previous run remains intact. |
| Parish coverage or name mismatch | Check that the reference is Lisboa CAOP2025 and the housing input is `0012234`; inspect the reported missing or conflicting records. |
| Missing context or singular model | Inspect source completeness and model diagnostics. Do not silently drop parishes or change predictors to obtain a result. |

## Preview documentation

```bash
poetry run mkdocs serve
```

For local development checks and pull requests, see [Development](development.md).
