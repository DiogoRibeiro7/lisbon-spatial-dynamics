# Housing changes after national CPI adjustment

The median parish increase between **2019 Q4 and 2025 Q4** is **23.59% after adjustment by Portugal's annual consumer price index**, compared with **47.52% nominally**. Twenty-two parishes remain above their baseline; **Misericórdia (−5.42%)** and **Santa Maria Maior (−11.91%)** are below it. Beato has the largest adjusted increase, **56.67%**.

These are CPI-adjusted **published sale medians**, using the [audited housing series](housing-history.md) and seven official annual national CPI observations captured on 2026-10-04. The [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-inflation/2026-10-04) contains all 168 adjusted parish-year observations, 24 endpoint comparisons, seven yearly summaries, a figure and provenance. Previously published nominal evidence is preserved.

![Nominal and national-CPI-adjusted housing changes for all 24 parishes, with annual median parish changes](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-inflation/2026-10-04/housing_inflation.png)

## Deflator and timing

The source is **INE indicator 0014642**, annual CPI, **base 2025**, **Portugal (`PT`)**, **Total (`T`)**. The [official catalogue](https://dados.gov.pt/pt/datasets/indice-de-precos-no-consumidor-ipc-base-2025-0014642) identifies this annual series and its CC BY 4.0 licence. The [committed reference](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/data/reference/ine-cpi/2026-10-04) preserves the exact published index values and their acquisition/extraction provenance.

| Year | Annual national CPI, 2025 = 100 |
| --- | ---: |
| 2019 | 83.775 |
| 2020 | 83.764 |
| 2021 | 84.825 |
| 2022 | 91.469 |
| 2023 | 95.412 |
| 2024 | 97.717 |
| 2025 | 100 |

The index rose **19.36735%** between the two annual averages. This is a ratio of published index levels, not the sum of annual inflation rates. All years come from one 2025-base series; no splice with the former 2012-base indicator is made.

The Q4 housing observation covers sales in the preceding 12 months, rather than only October–December. The annual CPI average provides matching calendar-year context. Using December CPI would answer a different timing question. The adjustment remains an approximation at the aggregate level: dividing an annual sale median by an annual average CPI does not recreate the median of individually deflated transactions. Monthly sale timing and transaction-level values are unavailable here.

The reference README also records a small discrepancy with INE's separate annual value-update calculator: it displays cumulative inflation about 0.01307 percentage points above the explicit published-index ratio. Its cause is unverified. This analysis uses the pinned annual-index series consistently; neither that alternative coefficient nor a rounded headline inflation rate is substituted.

## Calculation and interpretation

For housing value `H(i,t)` in parish `i`, annual CPI `C(t)`, and baseline year `b = 2019`:

```text
Adjusted housing value(i,t) = H(i,t) × C(b) / C(t)
Adjusted change(i,t) = 100 × [Adjusted housing value(i,t) / H(i,b) − 1]
```

All adjusted EUR/m² values are expressed in **2019 euros under the national CPI convention**. The CPI's **2025 index base** only sets its numerical scale; it does not make these housing values 2025 euros. For 2025, the conversion to 2019 euros is `83.775 / 100 = 0.83775`.

The adjustment divides nominal growth factors by CPI growth factors. Simply subtracting 19.37 from a nominal percentage change is incorrect. Each parish retains its own housing baseline. The headline is the median of 24 individual adjusted changes; it is not the percentage change in a municipality-wide transaction median. All parish summaries remain equally weighted.

| Parish | Nominal endpoint change | CPI-adjusted endpoint change |
| --- | ---: | ---: |
| Beato | +87.01% | +56.67% |
| Misericórdia | +12.89% | −5.42% |
| Santa Maria Maior | +5.15% | −11.91% |
| Median of all 24 parish changes | +47.52% | +23.59% |

National CPI describes consumer-price movements. It is not a Lisbon parish cost-of-living series, a construction-price index, or an index of housing asset values. The adjusted medians do not control for the quality, size or location mix of properties sold. No household income, financing cost or rent burden is included, so the result is not an affordability measure or appreciation of a fixed dwelling.

## Relationship to spatial findings

A common endpoint deflator changes the size and sign of growth without changing its relative ordering. If `x(i)` is nominal percentage change and `f = C(2019) / C(2025)`, then adjusted percentage change is `f × x(i) + 100 × (f − 1)`. Since `f > 0`, this is a positive affine transformation of the complete parish vector.

Under the same complete observations and spatial weights, standardized values, Global and Local Moran statistics, and their permutation results are therefore unchanged mathematically, up to floating-point precision. This is an algebraic consequence of the common deflator, **not independent spatial confirmation**. No spatial tests are rerun or new hotspot claims added. The earlier [global association and absence of FDR-significant local clusters](housing-spatial.md) retain their original interpretation. CPI adjustment of absolute EUR/m² differences is not generally the same affine transformation, because housing baselines differ.

## Reproduce and inspect

From the repository root, with the locked dependencies installed:

```bash
poetry sync --with docs
poetry run python scripts/analyse_housing_inflation.py --output data/processed/housing-inflation-recheck
```

The [configuration](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/configs/housing_inflation_2026-10-04.toml) pins six committed inputs: the original housing quarterly aggregates, canonical parish reference, nominal housing report, source audit, annual CPI CSV and CPI provenance. The script verifies hashes, byte sizes and report links, consumes the verified bytes, and reproduces the complete nominal summary before applying CPI. Wrong index bases, geographic scopes, missing/duplicate CPI years, invalid values and inconsistent housing coverage fail validation.

| Artifact | Contents |
| --- | --- |
| `annual_adjusted.csv` | 168 Q4 observations: nominal and adjusted EUR/m², annual CPI, conversion factor, nominal/adjusted baseline changes and adjusted previous-Q4 changes |
| `parish_changes.csv` | 24 endpoint comparisons with dates, nominal endpoint levels, adjusted latest level and both percentage changes |
| `yearly_summary.csv` | Seven equal-parish summaries, cumulative CPI change, nominal/adjusted medians and counts below the adjusted baseline/previous Q4 |
| `housing_inflation.png` | All parish endpoint changes and the yearly median parish changes |
| `analysis.json` | Summary, units, limitations, verified nominal summary flag, attribution, software versions and input/code/output fingerprints |

The first year's previous-Q4 comparison remains missing, not zero. Decimal calculations use a fresh precision-28 context. CSVs preserve decimal results; JSON summary values are numeric floats. The command publishes the complete bundle into a new directory and refuses overwrite. Files use UTF-8 and LF endings; image bytes and environment/path fingerprints can vary across environments.

The offline replay starts from committed canonical aggregates. `scripts/build_cpi_reference.py` separately reproduces the CPI extraction when the locally retained, pinned raw responses are available. A fresh API capture can contain revisions and is not a substitute for the recorded snapshot. Historical RNAL coverage and the definitive joint v1.1 study remain unresolved.
