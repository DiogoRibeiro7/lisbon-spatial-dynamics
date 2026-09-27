# Methodology

The project builds a longitudinal spatial panel before estimating relationships between urban variables.

## Unit of analysis

The target representation is:

\[
(i,t)
\]

where `i` is one canonical Lisbon freguesia and `t` is one INE reference quarter.

The canonical spatial key is `freguesia_id`, defined by CAOP's `DTMNFR` identifier.

## Housing-to-freguesia join

Current INE housing observations are admitted to the canonical panel only when the source geography code maps uniquely to a known `freguesia_id` and the source label agrees with the CAOP freguesia name.

A published null price remains missing data. A freguesia that disappears entirely from a source period fails the coverage check.

## Temporal normalization

INE quarter labels are parsed strictly from the source form, for example:

```text
1.º Trimestre de 2026
```

The normalized panel adds:

- `year`;
- `quarter`;
- `period_end`;
- quarter-on-quarter absolute and percentage change;
- year-on-year absolute and percentage change.

Build these metrics with:

```bash
poetry run build-housing-changes \
  data/processed/housing/lisbon_freguesia_panel.csv \
  data/processed/housing/lisbon_freguesia_changes.csv
```

The original `period_code` is retained in every row.

### Interpretation of change

The INE housing indicator is the median sale value per square metre over the **previous 12 months**, reported quarterly. Consequently, adjacent quarterly observations have heavily overlapping windows.

For that reason:

- **year-on-year change** is the primary longitudinal comparison;
- **quarter-on-quarter change** is retained as a descriptive short-horizon movement in the rolling statistic, not as a price change for a non-overlapping quarter.

No change metric is calculated when either the current or comparison value is missing.

## Descriptive analysis first

The first analytical stage should establish:

- spatial distributions;
- temporal trends;
- change maps;
- missingness patterns;
- coverage differences;
- outliers and discontinuities;
- correlations and spatial autocorrelation.

Only after these checks should multivariable models be introduced.

## Longitudinal models

A possible later-stage specification is:

\[
\log(P_{i,t}) =
\alpha_i + \gamma_t +
\beta^\top X_{i,t} +
\varepsilon_{i,t},
\]

where `\alpha_i` captures time-invariant spatial effects, `\gamma_t` captures common period effects, and `X_{i,t}` contains observed time-varying neighbourhood characteristics.

This is a modelling framework, not a causal claim. Identification assumptions must be stated separately for any causal interpretation.

## Spatial dependence

Neighbouring areas are not statistically independent by default. Spatial autocorrelation should be diagnosed explicitly and, where necessary, incorporated into inference or modelling rather than ignored.
