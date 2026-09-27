# Methodology

The methodological objective is to build a consistent longitudinal spatial panel before estimating relationships between urban variables.

## Unit of analysis

The target representation is:

\[
(i,t)
\]

where `i` identifies one canonical Lisbon freguesia and `t` identifies a source period.

The canonical spatial key is `freguesia_id`, defined by CAOP's `DTMNFR` identifier.

## Housing-to-freguesia join

The current INE housing series (`0012234`) embeds the freguesia identifier inside the INE geography code. The project does **not** hard-code a NUTS prefix. Instead, a housing observation is admitted to the freguesia panel only when:

1. its INE geography code ends with exactly one known canonical `freguesia_id`;
2. its INE geography label agrees with the canonical CAOP freguesia name after conservative Unicode/case normalisation;
3. the record belongs to the requested dwelling category;
4. every canonical freguesia is represented in the source period.

A published null value is retained as missing data. A completely absent freguesia record fails the period-level coverage check.

Build the current freguesia housing panel with:

```bash
poetry run build-housing-freguesia-panel \
  data/raw/ine/housing/0012234/<timestamp>.data.json \
  data/processed/reference/lisbon_freguesias.csv \
  data/processed/housing/lisbon_freguesia_panel.csv
```

The output retains both canonical identifiers and original INE geography codes so the join remains auditable.

## Temporal consistency

The housing panel preserves INE period labels verbatim at this stage. Calendar parsing and ordering are separate transformations and should be tested against the source convention rather than inferred ad hoc.

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
