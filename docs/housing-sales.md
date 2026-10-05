# Housing sales volume, 2019–2025

Lisbon recorded **8,235 dwelling sales in 2025**, down from **8,665 in 2019**: **430 fewer sales (−4.96%)**. **Seventeen of the 24 parishes** had fewer sales at the endpoint, although all 24 had higher nominal sale medians. These are separate descriptive changes in transaction activity and published prices; they do not establish why either changed.

This [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-sales/2026-10-05) adds **INE indicator `0014363`**, the number of sales in the preceding 12 months, to the [audited Total dwelling medians](housing-history.md). The capture supplies **175 published counts: seven Q4 periods × 24 parishes plus Lisbon municipality**. Parish counts sum exactly to the separately published city total in every year. No observation is missing or imputed.

![Changes in sales volume and nominal sale medians across Lisbon's 24 parishes](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-sales/2026-10-05/housing_sales.png)

## Municipality totals

| Calendar-year sales window | Published Lisbon sales | Sum of 24 parishes | Change from previous year |
| --- | ---: | ---: | ---: |
| 2019 | 8,665 | 8,665 | — |
| 2020 | 7,291 | 7,291 | −15.86% |
| 2021 | 7,934 | 7,934 | +8.82% |
| 2022 | 8,083 | 8,083 | +1.88% |
| 2023 | 7,215 | 7,215 | −10.74% |
| 2024 | 8,300 | 8,300 | +15.04% |
| 2025 | 8,235 | 8,235 | −0.78% |

**Q4 is the observation point for a rolling 12-month count.** A 2025 Q4 value describes sales over 2025, not only October–December. These seven annual windows do not overlap. Summing all four quarterly observations of this indicator would double-count overlapping windows and is not done here. The first year-on-year entry is blank because the selected evidence begins in 2019.

The municipality's −4.96% change uses its total counts. It is distinct from the **−4.87% median parish change**, which weights each parish equally. Seven parishes have more sales, 17 have fewer, and none is unchanged.

## Parish differences

| Parish | 2019 sales | 2025 sales | Sales change | Nominal sale-median change |
| --- | ---: | ---: | ---: | ---: |
| Carnide | 166 | 111 | −33.13% | +52.39% |
| Santo António | 455 | 360 | −20.88% | +32.67% |
| Santa Maria Maior | 398 | 320 | −19.60% | +5.15% |
| Parque das Nações | 308 | 410 | +33.12% | +52.14% |
| Beato | 169 | 193 | +14.20% | +87.01% |
| Campolide | 243 | 273 | +12.35% | +73.63% |

The table shows the three largest proportional decreases and increases in sales counts. All 24 parishes appear in the figure and downloadable tables. Carnide and Parque das Nações have similar median-price growth but opposite changes in sales activity; the price trend alone does not describe transaction volume.

For parish `i`, sales change is `100 × [N(i,2025) − N(i,2019)] / N(i,2019)`. Its city share is `100 × N(i,t) / N(Lisboa,t)`, with share changes expressed in percentage points. A genuine zero baseline would leave percentage change undefined while retaining absolute change; none occurs in this capture. The extractor requires published nonnegative integer counts and rejects missing, flagged, duplicate, inconsistent or unreconciled observations rather than converting them to zeros.

## Interpretation and limits

Counts describe **sales**, not unique dwellings, buyers, resident households, listings or unsold stock. The series has no new/existing category dimension, so it cannot explain the missing New medians in the [dwelling-category comparison](housing-categories.md), estimate category sales shares, or identify a sales-composition contribution to the pooled median. Even category counts would not, by themselves, recover a median from category medians.

The existing median values and changes are preserved. No municipality price is reconstructed by weighting parish medians by transaction counts. Changes remain nominal and may reflect property mix, quality and location. This comparison does not estimate liquidity, affordability, a constant-quality price index, an RNAL association or a causal effect, and adds no hypothesis tests. The [separate CPI analysis](housing-inflation.md) remains the source for inflation-adjusted comparisons.

Counts were captured on **2026-10-05 at 08:58:15 UTC**; the paired medians come from the **2026-10-01 audit**. Both use methodology 2022, NUTS 2024 and the same Q4 windows, but they are separate source vintages. Exact count reconciliation establishes internal consistency, not a common extraction date or immunity to future source revisions.

## Source and reproduction

Attribution: **Instituto Nacional de Estatística (INE)**, indicators `0014363` (counts) and `0012234` (medians). The [official count-series catalogue](https://dados.gov.pt/pt/datasets/vendas-de-alojamentos-familiares-nos-ultimos-12-meses-metodologia-2022-n-o) specifies the rolling-year measure and **CC BY 4.0**. Acquisition settings are in `configs/ine_housing_sales.toml`; metadata checks require quarterly frequency, number units, no power-of-ten scaling, integer precision and the exact geography/period labels.

The [committed count reference](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/data/reference/ine-housing-sales/2026-10-05) includes the canonical CSV and extraction/acquisition provenance. The original JSON responses are retained locally outside Git; they are not a public raw archive. A fresh request can contain revised values.

With the locked dependencies installed, run from the repository root:

```bash
poetry run python scripts/analyse_housing_sales.py --output data/processed/housing-sales-recheck
```

The default `configs/housing_sales_2026-10-05.toml` pins six committed inputs: sales CSV/provenance, housing quarterly panel, parish reference, nominal report and source audit. Replay checks hashes and sizes, verifies provenance links, reproduces the earlier nominal summary and consumes the verified bytes. It needs no network or raw downloads. The reference README gives the separate raw-extraction command.

| Artifact | Contents |
| --- | --- |
| `annual_parish.csv` | 168 parish/year rows: count, published city total, city sales share and audited median EUR/m² |
| `endpoint_changes.csv` | 24 rows: endpoint counts/medians, absolute and percentage sales changes, city shares and share changes |
| `municipality_sales.csv` | Seven published totals, parish sums, reconciliation differences, baseline-100 count index and annual changes |
| `housing_sales.png` | Parish endpoint changes in counts and medians, with separate labelled axis scales |
| `analysis.json` | Summary, capture dates, interpretation, software versions and input/code/output fingerprints |

Output directories must be new. Calculations use a fresh precision-28 Decimal context; CSVs use UTF-8/LF and preserve decimal results, while JSON summaries use numeric floats. Figure bytes may vary across software environments. Offline tests cover source contracts, arithmetic, zero/missing semantics and immutable aggregate replay.

The missing accepted historical RNAL series remains a prerequisite for the definitive joint v1.1 study.
