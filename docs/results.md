# Multivariable analysis

This page documents the interpretation contract for the project's pre-specified multivariable models. Numerical results are generated from the processed data rather than hard-coded into the documentation.

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
