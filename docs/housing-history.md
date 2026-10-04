# Housing values across Lisbon's parishes, 2019–2025

All 24 parishes have higher published housing values in **2025 Q4 than in 2019 Q4** in the audited INE capture. The median of their individual nominal increases is **47.52%**, ranging from **5.15% in Santa Maria Maior** to **87.01% in Beato**. This is a housing-only comparison; it does not estimate an association with RNAL or complete the definitive v1.1 study.

The analysis was produced on **2026-10-04** from the [2026-10-01 primary-source audit](source-audit.md). Its [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-history/2026-10-04) contains 168 annual observations, 24 parish comparisons, seven yearly summaries, a figure and a provenance report. It can be reproduced entirely from committed aggregate inputs, without fetching raw data or relying on access to the local RNAL archive.

![Housing levels and nominal changes for all 24 Lisbon parishes, ordered by percentage increase from 2019 Q4 to 2025 Q4](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-history/2026-10-04/housing_changes.png)

[View or download the full-resolution figure](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/results/housing-history/2026-10-04/housing_changes.png).

## What the values measure

INE indicator `0012234`, category `H1` (Total dwellings), reports the median dwelling sale value per square metre for sales in the **preceding 12 months**. Q4 identifies the reference period, not a sample restricted to sales during October–December. The source audit already matched the INE identifiers and parish names against the CAOP2025 reference.

This analysis selects seven Q4 observations per parish from the audited 624-row quarterly panel. It excludes the 18 intervening non-Q4 periods and 2026 Q1: 456 rows remain outside this annual comparison. The original 26-quarter input is preserved. No Q1 value is relabelled as Q4 or substituted for a missing endpoint.

For each parish, nominal change is `100 × (value_2025Q4 − value_2019Q4) / value_2019Q4`. These are changes in published medians, without inflation or transaction-composition adjustment. Different properties may have been sold in each period; the change is not an estimate of appreciation for a fixed dwelling, nor a measure of affordability relative to income.

## Endpoint comparison

The three largest and three smallest percentage increases are shown below. The complete ordering is in the figure and `parish_changes.csv`.

| Parish | 2019 Q4, EUR/m² | 2025 Q4, EUR/m² | Nominal change |
| --- | ---: | ---: | ---: |
| Beato | 2,325 | 4,348 | +87.01% |
| Marvila | 2,797 | 5,029 | +79.80% |
| Campolide | 3,079 | 5,346 | +73.63% |
| Santo António | 5,140 | 6,819 | +32.67% |
| Misericórdia | 4,933 | 5,569 | +12.89% |
| Santa Maria Maior | 4,755 | 5,000 | +5.15% |

Santo António has the highest 2025 Q4 level, although its percentage increase is among the three smallest. Starting levels and percentage growth describe different aspects of the comparison.

## The intervening years

The endpoint increases do not imply uninterrupted growth. Nine parishes had lower Q4 values in 2021 than in 2020; three had lower Q4 values in 2025 than in 2024.

| Q4 year | Median of the 24 parish values, EUR/m² | Minimum parish value | Maximum parish value | Parishes below their previous Q4 value |
| --- | ---: | ---: | ---: | ---: |
| 2019 | 3,296.5 | 2,325 | 5,140 | — |
| 2020 | 3,454.5 | 2,259 | 5,682 | 8 |
| 2021 | 3,429.5 | 2,501 | 5,435 | 9 |
| 2022 | 3,969.0 | 2,622 | 5,753 | 0 |
| 2023 | 4,281.5 | 2,783 | 6,458 | 2 |
| 2024 | 4,642.5 | 3,416 | 5,879 | 3 |
| 2025 | 4,878.5 | 3,727 | 6,819 | 3 |

Each parish receives equal weight in these summaries. **The median of parish medians is not Lisbon's municipality-wide transaction median**; that requires the underlying transactions or a separately published municipal statistic. Similarly, the 47.52% headline is the median of 24 parish-specific changes, not the percentage change between the two median levels in this table. The first year's previous-Q4 comparison is unavailable in the selected window and remains null, not zero.

## Files and reproducibility

| File | Rows / content |
| --- | --- |
| `annual_q4.csv` | 168 parish-year observations: reference date, published EUR/m², absolute and percentage change from the baseline, and change from the preceding Q4 |
| `parish_changes.csv` | 24 parish comparisons: explicit baseline/latest years, endpoint EUR/m², absolute EUR/m² difference and percentage change |
| `yearly_summary.csv` | Seven yearly summaries: equal-parish median/minimum/maximum levels, median parish-specific baseline change, and count below the preceding Q4 |
| `housing_changes.png` | Endpoint levels and nominal changes, ordered by unrounded percentage change; parish code breaks any ties |
| `analysis.json` | Window, exclusions, headline statistics, interpretation, original housing acquisition metadata, and input/code/configuration/output hashes |

Run from the repository root using the locked dependencies:

```bash
poetry sync --with docs
poetry run python scripts/analyse_housing_history.py --output data/processed/housing-history-recheck
```

The [pinned configuration](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/configs/housing_history_2026-10-04.toml) identifies the housing CSV, parish reference and parent source-audit report. All three are committed. The command verifies hashes and sizes, checks that the parent audit identifies both aggregate inputs, and parses the exact verified bytes. It requires a complete Q4 matrix, unique parish-quarter keys, matching canonical identities and indicator/category, and finite positive values. Missing observations are not interpolated or converted to zeros.

The existing housing-change calculation supplies year-on-year comparisons. Decimal arithmetic uses a fresh context with precision 28; CSV files preserve the calculated decimals, while JSON headline percentages use numeric floating-point values. Tables above round percentages to two decimal places and the figure to one. A successful replay should reproduce the three CSV hashes and numeric summary. JSON paths and software fingerprints reflect the replay environment; figure bytes can vary with rendering libraries or fonts. All artifacts are staged and published together into a new directory; failures leave no partial bundle and existing output is preserved.

This replay verifies the committed aggregates and their link to the original audit. It does not independently re-transform the raw INE response. The [source-audit instructions](source-audit.md#reproduce-the-audit) describe that earlier transformation; those raw snapshots remain locally retained and have not been deposited in a public archive. A fresh INE request can contain revisions and constitutes a new capture.

## Relationship to the study

This Q4-2019→Q4-2025 series is distinct from the curated Q1-2019→Q1-2026 comparison in [v1.0.1](results.md#committed-empirical-correction-v101). Neither its dates nor its values are silently substituted into that release.

The housing evidence is ready for inspection independently of RNAL. The joint housing/accommodation analysis still needs an accepted historical RNAL series, geographic/status definitions, a reviewed integration and durable input archiving. The [provider request package](rnal-history-request.md) remains the next step for that missing evidence.

The [spatial follow-up](housing-spatial.md) maps these same endpoint changes and applies the existing Global and Local Moran methods, with all geographic inputs now available in the repository.
