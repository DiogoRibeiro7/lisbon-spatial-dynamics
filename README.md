# Lisbon Spatial Dynamics

Reproducible spatial analysis of neighbourhood-level urban change in Lisbon.

Version 1.0.0 focuses on how housing-value change relates to local-accommodation pressure across the 24 canonical Lisboa freguesias, using official public data and explicit spatial/statistical diagnostics.

## v1 study scope

The release combines:

- INE housing-value data;
- Turismo de Portugal RNAL local-accommodation records;
- Censos 2021 population and neighbourhood structure;
- CAOP canonical freguesia geometry;
- population-normalized RNAL pressure;
- descriptive association analysis;
- Global and Local Moran diagnostics;
- pre-specified OLS models with HC3 robust uncertainty;
- leave-one-freguesia-out sensitivity;
- publication-style final tables and figures.

The project reports **descriptive and adjusted associations**. It does not identify a causal effect of local accommodation on housing prices.

## Reproduce the complete study

```bash
poetry run build-study-v1 \
  data/raw/ine/housing/<snapshot>.json \
  data/raw/turismo_portugal/rnal/lisboa/<snapshot>.records.json \
  data/raw/ine/census2021/subsections/<snapshot>.zip \
  data/processed/reference/lisbon_freguesias.csv \
  data/processed/reference/lisbon_freguesias.geojson \
  data/processed/releases/v1
```

The build writes all processed panels, analyses, final result tables/figures, and a SHA-256 provenance manifest.

## Final outputs

```text
results/final/
├── table_1_descriptive.csv
├── table_2_spatial.csv
├── table_3_models.csv
├── table_4_diagnostics.csv
├── findings.json
├── findings.md
├── figure_1_pressure_association.png
├── figure_2_pressure_coefficients.png
└── figure_3_primary_residuals.png
```

## Development

```bash
poetry install --with docs
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run mkdocs build --strict
```

## Future work

Mobility, accessibility, infrastructure, and additional longitudinal demographic sources are intentionally outside v1.

## Citation

Citation metadata is provided in `CITATION.cff`.

## Licence

Source code is MIT licensed. Dataset licences and attribution requirements remain with their respective providers.
