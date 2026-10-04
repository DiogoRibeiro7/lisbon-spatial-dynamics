# Multivariable analysis

This page documents the interpretation contract for the project's pre-specified multivariable models. Numerical results are generated from the processed data rather than hard-coded into the documentation.

For independently reproducible housing evidence, see the [2019–2025 Q4 comparison](housing-history.md). It contains actual parish values, changes and a figure from the audited INE capture; it does not supply or substitute for the joint RNAL model results described below.

## Research question

The modelling stage asks whether freguesias with larger increases in population-normalized local-accommodation pressure also show larger cumulative housing-value changes after adjustment for a small set of pre-specified neighbourhood characteristics.

The analysis is cross-sectional over a common baseline-to-latest change window.

## Model sequence

The versioned model configuration contains four specifications:

| Model | Purpose |
| --- | --- |
| RNAL pressure only | Unadjusted reference association |
| RNAL pressure + baseline housing | Account for starting housing-value differences |
| Demographic/tenure context | Primary adjusted specification |
| Built-environment sensitivity | Alternative structural adjustment set |

The project does not perform stepwise selection or choose a specification based on statistical significance.

## Primary coefficient

All predictors are standardized. The coefficient for `rnal_pressure_change_per_1000` is therefore reported as:

> housing-change percentage points associated with a one-standard-deviation larger increase in active RNAL registrations per 1,000 Census-2021 residents, conditional on the other variables in the specification.

This wording describes an association, not a causal effect.

## Robustness outputs

The generated analysis directory contains:

```text
model_input.csv
coefficients.csv
residuals.csv
leave_one_out.csv
model_report.json
pressure_coefficients.png
primary_residuals.png
```

The coefficient plot compares the RNAL-pressure estimate and HC3 robust 95% confidence interval across all pre-specified models.

The primary residual plot supports visual checking of fitted-versus-residual structure. The machine-readable report additionally contains VIF, condition-number, Breusch–Pagan, influence and residual-Moran diagnostics.

## Small-sample caution

Lisbon has only 24 canonical freguesias in this study. The model set is intentionally compact, and inference should be read together with coefficient stability, confidence intervals, influence diagnostics and residual spatial autocorrelation.

The multivariable stage should be presented as adjusted descriptive evidence rather than definitive causal identification.


## Final results package

Once the normalized descriptive/spatial bundle and the multivariable milestone have been generated, the project can assemble a compact publication-style results package:

```bash
poetry run build-final-results \
  data/processed/analysis/normalized \
  data/processed/analysis/multivariable \
  data/processed/results/final
```

The command does not refit models or recompute spatial statistics. It reads the already generated machine-readable outputs and synthesizes them into:

```text
table_1_descriptive.csv
table_2_spatial.csv
table_3_models.csv
table_4_diagnostics.csv
findings.json
findings.md
figure_1_pressure_association.png
figure_2_pressure_coefficients.png
figure_3_primary_residuals.png
```

The synthesis validates that the descriptive, spatial, and multivariable artifacts all refer to the same baseline/latest comparison window before producing any final table or narrative.

The generated `findings.md` is intentionally concise. It reports:

- study window;
- median housing change;
- median RNAL pressure-point change;
- Pearson and Spearman associations;
- Global Moran diagnostics;
- count of FDR-significant local associations;
- the primary adjusted RNAL-pressure coefficient and HC3 robust confidence interval;
- primary-model diagnostics;
- leave-one-freguesia-out coefficient stability.

The narrative is generated directly from the analysis artifacts and preserves the interpretation contract: adjusted associations are descriptive and not causal.


## Committed empirical correction — v1.0.1

The v1.0.0 software release did not include committed empirical datasets or generated study results. Version 1.0.1 adds an inspectable evidence layer:

- `data/release/v1.0.1/` — curated 24-freguesia empirical tables with provenance;
- `results/release/v1.0.1/summary_metrics.csv`;
- `results/release/v1.0.1/association_results.csv`;
- `results/release/v1.0.1/findings.json`;
- `results/release/v1.0.1/findings.md`.

The committed evidence includes Q1-2019→Q1-2026 housing changes, Nov-2019→Nov-2022 weighted RNAL and capacity changes, a published June-2018 housing/AL cross-section, and 2011→2021 population change with the 2021 AL/AFC ratio.

These release tables are transparent empirical evidence, not replacements for the full raw-snapshot pipeline. Period definitions and source limitations are documented beside the data.
