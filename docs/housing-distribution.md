# Lisbon's municipal housing-price distribution

Between **2019 and 2025**, Lisbon's published lower sale-price quartile rose **59.21%**, its median **48.36%**, and its upper quartile **40.52%**. The middle-half range widened from **€1,815 to €2,085 per m²**, while falling from **55.23% to 42.77% of the median**. Absolute and relative dispersion therefore moved in different directions.

This [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-distribution/2026-10-05) uses **INE indicator `0013042`**, annual dwelling-sale quartiles under methodology 2022/NUTS 2024. All **21 observations** are published: three quartiles for each of seven calendar years. They describe **Lisbon municipality**; this indicator's captured metadata does not provide Lisbon parish quartiles. No municipal value is assigned to a parish.

![Published Lisbon municipality quartiles and their separate baseline indices](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-distribution/2026-10-05/housing_distribution.png)

**Q1, Q2 and Q3 here mean quartiles**, not quarters: the 25th, 50th and 75th percentiles of the sale-value-per-m² distribution. Q2 is the median. The shaded band spans Q1 to Q3 and represents the middle part of that distribution; it is **not a confidence interval**. Lines connect annual observations for readability and do not supply within-year measurements.

## Endpoint comparison

| Measure | 2019 (€/m²) | 2025 (€/m²) | Absolute change (€/m²) | Nominal change |
| --- | ---: | ---: | ---: | ---: |
| Lower quartile, Q1 | 2,491 | 3,966 | +1,475 | +59.21% |
| Median, Q2 | 3,286 | 4,875 | +1,589 | +48.36% |
| Upper quartile, Q3 | 4,306 | 6,051 | +1,745 | +40.52% |
| Interquartile range, Q3 − Q1 | 1,815 | 2,085 | +270 | +14.88% |

The lower quartile has the largest **proportional** increase, while the upper quartile has the largest **euro-per-m²** increase. Different baselines make these compatible. Neither statement says that the same lower- or higher-priced dwellings appreciated by those amounts: each year's distribution contains that year's transactions.

The municipal median change of **48.36%** is a different statistic from the **47.52% median parish change** in the [earlier housing comparison](housing-history.md). The former compares two published municipal medians; the latter calculates change separately in each parish, then takes the median across 24 changes with equal parish weight. Municipal medians and quartiles are not reconstructed from parish medians or weighted by the [sales counts](housing-sales.md). The observations also come from separately dated captures.

## Annual dispersion

| Year | Q1 (€/m²) | Median (€/m²) | Q3 (€/m²) | IQR (€/m²) | IQR as % of median |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2019 | 2,491 | 3,286 | 4,306 | 1,815 | 55.23% |
| 2020 | 2,586 | 3,415 | 4,552 | 1,966 | 57.57% |
| 2021 | 2,750 | 3,531 | 4,500 | 1,750 | 49.56% |
| 2022 | 3,015 | 3,872 | 4,977 | 1,962 | 50.67% |
| 2023 | 3,308 | 4,167 | 5,376 | 2,068 | 49.63% |
| 2024 | 3,498 | 4,340 | 5,575 | 2,077 | 47.86% |
| 2025 | 3,966 | 4,875 | 6,051 | 2,085 | 42.77% |

For year `t`, absolute dispersion is `IQR(t) = Q3(t) − Q1(t)`. Relative dispersion is `100 × IQR(t) / Q2(t)`, expressed as a percentage of the same year's median. Its endpoint change is **−12.47 percentage points**; this differs from the **+14.88% change in the absolute IQR**. Neither path is monotonic throughout the period.

Endpoint percentage change is `100 × (latest − baseline) / baseline`. Each plotted index is `100 × Qk(t) / Qk(2019)` and uses that quartile's own baseline. Equal quartiles are permitted: an IQR of zero is valid, and a zero baseline IQR leaves its percentage change undefined while preserving absolute change. No zero IQR occurs in this capture.

## Interpretation limits

These are nominal distributions of recorded sale values per m², not total dwelling prices, an income distribution or a measure of household affordability. A smaller IQR relative to the median does not establish improving affordability, lower income inequality or convergence among parishes.

The series does not hold property quality, size, location or sales composition constant. Quartile movements cannot identify which dwellings moved within the distribution, separate price and composition effects, or track appreciation of the same properties. No new/existing category breakdown, inflation adjustment, spatial test, RNAL association or causal estimate is produced. The [separate CPI context](housing-inflation.md) retains its original scope.

## Source and reproduction

Attribution: **Instituto Nacional de Estatística (INE)**, annual indicator `0013042`, Lisbon municipality (`1A01106`). The [official catalogue](https://dados.gov.pt/pt/datasets/vendas-de-alojamentos-familiares-metodologia-2022-eur-m2) identifies the annual quartile measure and **CC BY 4.0** licence. The capture was made on **2026-10-05 at 10:04:08 UTC**; its metadata reports a source update date of **2026-06-20**. The request is fixed in `configs/ine_housing_quartiles.toml`.

The [committed reference](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/data/reference/ine-housing-quartiles/2026-10-05) includes all 21 values and acquisition/extraction provenance. Original JSON responses remain locally retained outside Git, with hashes and sizes; no public raw archive is claimed. A fresh request can contain revisions.

With locked dependencies installed, run from the repository root:

```bash
poetry run python scripts/analyse_housing_distribution.py --output data/processed/housing-distribution-recheck
```

The default `configs/housing_distribution_2026-10-05.toml` pins the quartile CSV and provenance. Replay verifies hashes/sizes, the parent output link, source identity and annual window. It parses the verified bytes and requires complete positive integer quartiles with `Q1 ≤ Q2 ≤ Q3`. Unpublished, flagged, duplicate or inconsistent observations fail extraction rather than becoming zeros or interpolated values. The reference README documents raw extraction separately.

| Artifact | Contents |
| --- | --- |
| `annual_distribution.csv` | Seven rows: published quartiles, absolute/relative IQR and three baseline-100 indices |
| `endpoint_changes.csv` | Four rows: Q1, Q2, Q3 and IQR endpoint levels, absolute changes and percentage changes |
| `housing_distribution.png` | Published level/range panel and indexed quartile trajectories |
| `analysis.json` | Summary, capture date, interpretation, software versions and input/code/output fingerprints |

Output directories must be new. Calculations use a fresh precision-28 Decimal context; UTF-8/LF CSVs preserve decimals and JSON summaries use numeric floats. Figure bytes may vary across environments. Offline tests use synthetic source contracts and this immutable reference, including zero-spread and failure-cleanup cases.

The accepted historical RNAL series and the definitive joint v1.1 run remain outstanding.
