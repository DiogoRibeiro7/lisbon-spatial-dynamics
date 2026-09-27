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


## Local-accommodation pressure panel

The RNAL panel is reconstructed on exactly the same quarter grid as the housing-change panel. This avoids an independent temporal resampling step.

For each freguesia and quarter the panel records:

- registrations during the quarter;
- cessations during the quarter;
- net registrations;
- registrations active at quarter-end;
- known active bed capacity;
- count of active registrations with missing bed capacity;
- known active user capacity;
- count of active registrations with missing user capacity.

A registration is active at quarter-end when:

```text
DataRegisto <= period_end
and
CessadoEm is empty or CessadoEm > period_end
```

Therefore a registration with `CessadoEm == period_end` is counted as a cessation in that quarter and is not active at quarter close.

Build the panel with:

```bash
poetry run build-rnal-quarter-panel \
  data/raw/turismo_portugal/rnal/lisboa/<timestamp>.records.json \
  data/processed/reference/lisbon_freguesias.csv \
  data/processed/housing/lisbon_freguesia_changes.csv \
  data/processed/rnal/lisbon_rnal_quarter_panel.csv
```

RNAL `DTMNFR` values must exist directly in the canonical CAOP reference, and the RNAL freguesia label must agree with the CAOP label. Unknown geographic identifiers fail the build rather than being silently dropped.

### Capacity missingness

Missing capacity is not converted to zero. The panel reports the sum of known capacity together with the number of active establishments whose capacity field is missing. This keeps incomplete administrative records distinguishable from true zero capacity.


## Combined urban-change panel

Housing and RNAL are joined only after each source has been independently normalised to the canonical `freguesia_id × quarter` key.

Build the combined dataset with:

```bash
poetry run build-urban-change-panel \
  data/processed/housing/lisbon_freguesia_changes.csv \
  data/processed/rnal/lisbon_rnal_quarter_panel.csv \
  data/processed/urban/lisbon_urban_change_panel.csv
```

The join is intentionally strict:

- the housing and RNAL key sets must be identical;
- each source must have at most one row per freguesia-quarter;
- period labels and quarter-end dates must agree;
- canonical freguesia names must agree.

No left or right join is used. A missing component row is treated as an upstream data-quality problem rather than silently converted into missing covariates.

### Variables retained

The combined panel keeps the source-domain measures separate.

Housing:

- median sale value per m²;
- quarter-on-quarter absolute and percentage movement;
- year-on-year absolute and percentage movement.

Local accommodation:

- registrations;
- cessations;
- net registrations;
- active registrations at quarter-end;
- known bed/user capacity;
- counts of active records with missing capacity.

The project does not construct a composite urban-change or gentrification score at this stage. Relationships between the variables belong to the analysis layer, not the data contract.
