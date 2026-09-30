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


## Across-years comparison panel

The annual comparison layer is anchored on **Q4** rather than averaging the four quarterly housing values. This matches the research question—how freguesias change across years—while avoiding four overlapping rolling-12-month housing windows per year.

Build it with:

```bash
poetry run build-annual-urban-panel \
  data/processed/urban/lisbon_urban_change_panel.csv \
  data/processed/urban/lisbon_annual_urban_change.csv
```

A year is included only when Q4 exists for the freguesia. The Q4 row supplies:

- year-end housing level and YoY change;
- year-end active RNAL stock and capacity;
- the year-end comparison to the freguesia's earliest available Q4 baseline.

RNAL registrations, cessations and net registrations are **annual flows**, so they are summed only when all four quarters of that year are present. The field `flow_quarters_observed` makes coverage explicit. If fewer than four quarters are available, the annual flow fields remain null rather than presenting a partial-year total as a full-year statistic.

For the first year of the current housing series, Q4 can therefore serve as the year-end baseline even when the project does not observe the preceding quarters. Later years with complete quarter coverage provide full annual RNAL flows.

The annual panel keeps two distinct housing changes:

- `housing_yoy_*` — change relative to the same quarter one year earlier;
- `housing_change_from_baseline_*` — cumulative change relative to the earliest available Q4 for that freguesia.

Likewise, active RNAL stock includes an absolute and percentage change from the same baseline. Percentage change is left null when the baseline stock is zero.


## Freguesia trajectories

The annual panel can be reduced to one baseline-to-latest descriptive row per freguesia:

```bash
poetry run build-freguesia-trajectories \
  data/processed/urban/lisbon_annual_urban_change.csv \
  data/processed/urban/lisbon_freguesia_trajectories.csv
```

By default all freguesias must share the same baseline year and latest year. This prevents cross-freguesia comparisons from silently mixing different observation windows.

The trajectory table keeps housing and local-accommodation change as separate dimensions. It reports:

- baseline and latest housing €/m²;
- absolute and percentage housing change over the full window;
- latest housing YoY change;
- baseline and latest active RNAL registrations;
- absolute and percentage active-stock change;
- baseline/latest known bed and user capacity;
- latest missing-capacity counts;
- latest annual registration, cessation and net flows when available.

No composite score or ordering is generated. The table is intended as a compact descriptive input for maps, plots, and later statistical analysis.


### Trajectory summary metadata

A compact machine-readable summary can be generated alongside the trajectory table:

```bash
poetry run build-trajectory-summary \
  data/processed/urban/lisbon_freguesia_trajectories.csv \
  data/processed/urban/lisbon_freguesia_trajectory_summary.json
```

The summary records the common comparison window, data-completeness counts, median housing percentage change among complete observations, city-wide RNAL active-stock totals, known capacity totals, and whether the latest RNAL annual flows have complete four-quarter coverage.

It contains no freguesia ranking or composite score.


## Descriptive housing–local-accommodation association

The first relationship analysis uses the common-window freguesia trajectory table, so every observation represents one freguesia over the same baseline-to-latest interval.

Run:

```bash
poetry run build-descriptive-association \
  data/processed/urban/lisbon_freguesia_trajectories.csv \
  data/processed/analysis/housing_rnal_association.json \
  data/processed/analysis/housing_rnal_scatter.png
```

The comparison uses:

- housing percentage change in median transaction value per m² over the full trajectory window;
- percentage change in active RNAL registrations over the same window.

The JSON report contains Pearson correlation, Spearman rank correlation, complete-case counts, explicit exclusion counts, and the exact freguesia points used in the calculation.

Spearman ranks use average ranks for ties. If either variable is constant over the complete cases, the relevant correlation is recorded as null rather than forcing a numerical value.

The scatter plot places RNAL active-stock percentage change on the horizontal axis and housing-price percentage change on the vertical axis. Freguesia labels can be disabled with `--no-labels`.

These are descriptive cross-sectional associations only. They do not estimate a causal effect of local accommodation on housing prices and do not control for demographic, spatial, tourism, infrastructure, or other confounding factors.


## Population-normalized RNAL pressure

Raw RNAL counts are useful for longitudinal stock accounting but are not directly comparable across freguesias of very different population size. The project therefore derives a second RNAL panel using the static 2021 Census resident population as the denominator.

Build it with:

```bash
poetry run build-rnal-population-pressure \
  data/processed/rnal/lisbon_rnal_quarter_panel.csv \
  data/processed/reference/lisbon_population_2021.csv \
  data/processed/rnal/lisbon_rnal_population_pressure.csv
```

The output preserves every raw RNAL count and adds:

- registrations per 1,000 residents;
- cessations per 1,000 residents;
- net registrations per 1,000 residents;
- active registrations per 1,000 residents;
- known active beds per 1,000 residents;
- known active users per 1,000 residents;
- the 2021 resident-population denominator;
- 2021 population density;
- the explicit population reference year.

For count (C_{i,t}) in freguesia (i) and quarter (t),

\[
R_{i,t}
=
1000
\frac{C_{i,t}}{N_{i,2021}},
\]

where (N_{i,2021}) is the Censos 2021 resident population.

This normalization is intended for **cross-freguesia comparability**. Because the denominator is fixed at the 2021 Census population, a change in the normalized RNAL rate over time still reflects changes in RNAL counts relative to a static population reference. It must not be interpreted as an annual per-capita rate using contemporaneous population.


## Annual population-normalized RNAL pressure

For across-years comparison, the quarterly pressure panel is reduced to a Q4-anchored annual panel:

```bash
poetry run build-annual-rnal-pressure \
  data/processed/rnal/lisbon_rnal_population_pressure.csv \
  data/processed/rnal/lisbon_annual_rnal_pressure.csv
```

A year is included only when Q4 exists.

The Q4 row supplies year-end:

- active registrations per 1,000 Census-2021 residents;
- known active beds per 1,000 residents;
- known active users per 1,000 residents;
- the corresponding raw counts;
- the static population denominator and population density.

Annual registration, cessation, and net-flow rates are reported only when all four quarters are observed. Partial years keep the Q4 pressure level but leave annual flow fields null.

The panel also includes pressure-point change from each freguesia's earliest available Q4 baseline. For active registrations:

\[
\Delta R_i
=
R_{i,T} - R_{i,0},
\]

where each (R) is measured as active RNAL registrations per 1,000 Census-2021 residents.

Because the denominator is fixed within each freguesia, this pressure-point change is useful for comparing how strongly RNAL stock expanded relative to neighbourhood size. It should still not be interpreted as a contemporaneous annual per-capita measure.


## Annual housing + RNAL pressure research panel

The annual housing panel and the annual population-normalized RNAL pressure panel are joined only after both have been built independently:

```bash
poetry run build-annual-housing-pressure-panel \
  data/processed/urban/lisbon_annual_urban_change.csv \
  data/processed/rnal/lisbon_annual_rnal_pressure.csv \
  data/processed/urban/lisbon_annual_housing_pressure.csv
```

The join is exact on `freguesia_id × year`. Both key sets must be identical.

The build also cross-checks all RNAL raw values duplicated across the two annual inputs:

- annual registrations;
- annual cessations;
- annual net registrations;
- year-end active registrations;
- year-end known/missing beds;
- year-end known/missing users;
- flow-quarter coverage.

A disagreement fails the build rather than reconciling one source into the other.

The resulting research table combines:

- annual/Q4 housing level;
- housing YoY change;
- cumulative housing change from baseline;
- Censos-2021 resident population and density;
- raw annual/year-end RNAL counts;
- RNAL annual flow rates per 1,000 residents;
- year-end RNAL stock/capacity per 1,000 residents;
- RNAL pressure-point change from baseline.

This table is the preferred annual input for descriptive association work involving local-accommodation **pressure** rather than raw local-accommodation counts. The population denominator remains the static 2021 census reference.


## Housing change versus normalized RNAL pressure

The preferred cross-freguesia association analysis uses the annual housing-pressure research panel rather than raw RNAL growth.

Run:

```bash
poetry run build-pressure-association \
  data/processed/urban/lisbon_annual_housing_pressure.csv \
  data/processed/analysis/housing_rnal_pressure_association.json \
  data/processed/analysis/housing_rnal_pressure_scatter.png
```

For every freguesia, the analysis selects the **latest year common to all freguesias**. This prevents the comparison window from silently varying when one freguesia has fewer annual observations.

The comparison is:

- **housing** — cumulative percentage change in median housing value per m² from the common baseline;
- **local-accommodation pressure** — absolute change in active RNAL registrations per 1,000 Censos-2021 residents from the same baseline.

The RNAL exposure is therefore a **pressure-point change**, not a percentage growth rate. This matters because a fixed denominator leaves within-freguesia percentage growth mathematically unchanged from the raw-count percentage growth; the per-1,000 pressure scale instead improves the substantive comparison of absolute neighbourhood exposure.

The JSON report records:

- baseline year;
- latest common year;
- complete-case count;
- excluded housing-missing count;
- Pearson correlation;
- Spearman rank correlation;
- every freguesia point used in the calculation;
- resident population and population-reference year.

The scatter plot places RNAL pressure-point change per 1,000 residents on the horizontal axis and cumulative housing-price percentage change on the vertical axis.

This remains descriptive cross-sectional analysis. The static 2021 denominator improves comparability across freguesias, but the association does not establish a causal effect of local accommodation on housing prices.


## Normalized analysis milestone bundle

The population-normalized analysis layer can now be built in one step instead of running a sequence of small commands:

```bash
poetry run build-normalized-analysis-bundle \
  data/processed/urban/lisbon_annual_housing_pressure.csv \
  data/processed/reference/lisbon_freguesias.geojson \
  data/processed/analysis/normalized
```

The command selects the common baseline and latest year shared by every freguesia and writes:

```text
normalized_trajectories.csv
normalized_trajectories.geojson
normalized_summary.json
normalized_association.json
normalized_association.png
housing_change_pct.png
rnal_pressure_change_per_1000.png
global_morans_i.json
local_morans_i.json
```

This milestone therefore combines, in one reproducible run:

- one common-window normalized trajectory per freguesia;
- map-ready normalized trajectory GeoJSON;
- compact coverage and descriptive summary;
- housing-change versus RNAL-pressure association analysis;
- Pearson and Spearman correlations;
- association scatter plot;
- housing-change choropleth;
- RNAL pressure-point-change choropleth;
- Global Moran's (I) for both variables;
- Local Moran's (I) with the existing conditional-permutation and FDR procedure.

The normalized RNAL spatial metric is:

```text
rnal_pressure_change_per_1000
```

which is the baseline-to-latest change in active RNAL registrations per 1,000 Censos-2021 residents.

The spatial-statistics engine reuses the already tested queen-contiguity and permutation implementation. Bundle outputs relabel the second metric explicitly as RNAL pressure change rather than raw RNAL percentage growth.

Default spatial settings remain:

- 999 permutations;
- seed 42;
- Local Moran FDR threshold 0.05.

They can be changed with `--permutations`, `--seed`, and `--alpha`.

This bundle is intended to close the normalized descriptive-analysis milestone. It still does not make causal claims or construct a composite neighbourhood-change score.


## Censos 2021 neighbourhood context milestone

The next substantive urban dimension is static demographic and built-environment context from the official Censos 2021 subsection synthesis file.

Build the complete context milestone with:

```bash
poetry run build-census2021-context-bundle \
  data/raw/ine/census2021/subsections/<timestamp>.zip \
  data/processed/reference/lisbon_freguesias.csv \
  data/processed/reference/lisbon_freguesias.geojson \
  data/processed/urban/lisbon_annual_housing_pressure.csv \
  data/processed/context/census2021
```

This writes:

```text
lisbon_census2021_context.csv
lisbon_census2021_context.geojson
lisbon_annual_housing_pressure_context.csv
```

### Static context variables

The context table preserves official 2021 counts and adds transparent derived measures:

- resident age shares: 0–14, 15–24, 25–64, 65+;
- owner-occupied usual-residence share;
- rented usual-residence share;
- vacant-or-secondary family-dwelling share;
- pre-1945 classic-building share;
- repair-needs classic-building share;
- dwellings per classic building.

The annual research panel is enriched by repeating these **static 2021** variables across every year for the same freguesia. The build verifies that the census population exactly matches the population denominator already carried by the annual housing-pressure panel.

These variables are neighbourhood context, not annual trajectories. They can be used later for stratification, descriptive comparison, or multivariable adjustment, but must not be interpreted as changing annually.

No composite neighbourhood score is produced.
