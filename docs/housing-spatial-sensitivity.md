# How sensitive is the housing spatial result?

The positive global association in [2019 Q4–2025 Q4 housing changes](housing-spatial.md) persists for percentage change, log change and nominal euro-per-square-metre change after adjustment across six declared comparisons. **Queen and rook generate identical graphs for these boundaries**, so they do not provide independent evidence of robustness to neighbour choice. The statistic remains positive when each parish is omitted in turn, although **Santa Maria Maior has a substantial influence on its magnitude**.

This is an exploratory follow-up to an already known primary result. The three measures, two contiguity definitions, **9,999 permutations, seed 42**, six-test Holm correction and 24 descriptive omissions were fixed before computing this follow-up. They are not a preregistration of the original study or an exhaustive search over reasonable specifications.

![Six global housing comparisons and Moran statistics after each parish omission](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-spatial-sensitivity/2026-10-04/sensitivity.png)

The [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-spatial-sensitivity/2026-10-04) contains every scenario, parish metric, neighbour pair and omission, plus the figure and provenance report. The original housing and spatial bundles remain unchanged.

## Measures and neighbour definitions

All scenarios use the same 24 complete parishes, the same nominal INE rolling-12-month sale medians, and the same two Q4 endpoints. With baseline value `B` and latest value `L`, the measures are:

| Measure | Definition | Meaning |
| --- | --- | --- |
| Percentage change | `100 × (L − B) / B` | Change relative to each parish's starting value; reproduces the primary specification |
| Log change | `ln(L) − ln(B)` | Natural logarithm of the endpoint ratio; dimensionless and not a percentage |
| Absolute change | `L − B` | Nominal increase in EUR/m²; gives a different interpretation from relative change |

Log change is a nonlinear transformation of percentage change, so Moran's I need not be identical. Absolute change asks a different question: parishes with the same percentage gain can have different euro gains. These are transparent sensitivity comparisons, not interchangeable estimates of one effect. CSV endpoint strings preserve the audited values; the statistics use double-precision numbers.

Queen neighbours touch at any boundary point. Rook neighbours must also share a boundary segment of positive length, consistent with the [rook contiguity definition](https://pysal.org/libpysal/stable/generated/libpysal.weights.Rook.html). The implementation first obtains the validated queen graph, then tests the length of each pair's boundary intersection in the original coordinates. No distance threshold, snapping, buffering or replacement link is used. Length is tested only for positivity, not interpreted as metres. Every graph is row standardized after construction.

**All 54 queen pairs also satisfy rook contiguity.** The two binary graphs, row weights, and corresponding statistics are exactly identical, with no islands. This check rules out dependence on corner-only contacts in this archive; it does not test a different effective neighbourhood, distance weights or historical boundaries. All six declared scenarios remain in the correction family, including the duplicates.

## All global comparisons

| Neighbours | Measure | Moran's I | Permutation p | Holm-adjusted p |
| --- | --- | ---: | ---: | ---: |
| Queen | Percentage change | 0.342108 | 0.0029 | 0.0116 |
| Queen | Log change | 0.361316 | 0.0016 | 0.0096 |
| Queen | Absolute change | 0.240144 | 0.0186 | 0.0372 |
| Rook | Percentage change | 0.342108 | 0.0029 | 0.0116 |
| Rook | Log change | 0.361316 | 0.0016 | 0.0096 |
| Rook | Absolute change | 0.240144 | 0.0186 | 0.0372 |

All six adjusted p-values are below 0.05. The result is weaker for absolute change than for either relative measure. This supports a positive global pattern across the selected measures, subject to the declared permutation assumptions and the limited set of specifications.

The statistic is `I = (n / S0) × (zᵀ W z) / (zᵀ z)`, where `z` contains centred values and `S0` is the sum of row-standardized weights. The test compares distance from the randomization expectation `−1 / (n − 1)`, exactly as in the primary analysis. Every scenario restarts the same seeded shuffle sequence in sorted parish-code order. These are correlated comparisons of the same observations, not six independent replications. Pseudo-p-values use `(extreme + 1) / (9,999 + 1)`.

[Holm adjustment](https://www.statsmodels.org/v0.14.4/generated/statsmodels.stats.multitest.multipletests.html) uses step-down Bonferroni factors for the complete family of six global tests. For sorted p-values, the adjusted value at rank `i` is the maximum of `(6 − j + 1) × p(j)` over ranks `j ≤ i`, capped at one. This is distinct from the earlier 24-test local Benjamini–Hochberg correction. The previous finding of **no FDR-significant local clusters** remains unchanged; local tests are not rerun here.

## Influence of individual parishes

For the primary queen/percentage specification, each diagnostic removes one parish and its incident links, then recalculates row weights, the mean, variance and the `n / S0` factor on the remaining 23 observations. It does not retain the original weights or recalculate a new proximity graph. Any islands would remain as zero-weight rows; none occurs in these 24 actual omissions.

| Diagnostic | Result |
| --- | ---: |
| All 24 parishes | 0.342108 |
| Lowest omission statistic: Santa Maria Maior removed | 0.196039 |
| Change after removing Santa Maria Maior | −0.146069 |
| Highest omission statistic: Areeiro removed | 0.395134 |
| Change after removing Areeiro | +0.053026 |
| Omissions retaining a positive statistic | 24 / 24 |

Santa Maria Maior is influential, and no single omission reverses the statistic's sign. **Positive omission statistics do not establish significance after each removal.** No omission p-values, confidence intervals or jackknife standard errors are calculated. These cases change both the observed values and the geographic graph; the displayed range is an influence diagnostic, not an uncertainty interval or a basis for excluding a parish.

## Reproduce and inspect

From the repository root with the locked dependencies installed:

```bash
poetry sync --with docs
poetry run python scripts/analyse_housing_spatial_sensitivity.py --output data/processed/housing-spatial-sensitivity-recheck
```

The [configuration](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/configs/housing_spatial_sensitivity_2026-10-04.toml) pins four committed inputs by SHA-256 and byte size: the housing endpoint table, archived polygons, parish reference and primary spatial report. The script validates their links to that report and its window/coverage, then parses the exact verified bytes. The existing housing join validates identities, completeness, geometry and endpoint arithmetic. This replay follows the primary report's provenance; it does not independently reacquire or transform the raw sources.

The matrix implementation checks the primary Moran statistic against the pinned report. When permutation count and seed match, it also requires the primary p-value to reproduce. Tests additionally compare the matrix implementation and induced-graph omissions with the existing neighbour-list implementation, including a synthetic omission that creates an island. The new calculations do not change the primary Moran interfaces.

| Artifact | Contents |
| --- | --- |
| `global_scenarios.csv` | All six global statistics, graph coverage, raw/adjusted p-values, seeds and permutation counts |
| `parish_metrics.csv` | The 24 endpoint pairs and all three computed measures |
| `neighbor_pairs.csv` | Each queen pair once, its rook membership, and both directed weights for each graph |
| `leave_one_out.csv` | Omitted parish, retained count, induced graph size, island codes, statistic and difference from the full result |
| `sensitivity.png` | All scenarios and descriptive omission statistics |
| `analysis.json` | Summary, interpretation, parameters, primary-reproduction checks, attribution, software versions and input/code/output fingerprints |

An empty `islands` CSV cell means no isolated parish; multiple codes would be separated by semicolons. `significant_holm` applies the configured 0.05 threshold to adjusted global p-values. The command requires a new output directory and publishes the bundle together; failed runs leave no partial bundle. CSV/JSON use UTF-8 and LF endings. Numeric reproduction allows normal floating-point tolerance; code/path fingerprints and image bytes can vary across environments.

These results remain descriptive. They do not address inflation, transaction composition, alternate observation windows, other spatial weights, causal identification or historical RNAL completeness. The joint v1.2 study still requires an accepted historical RNAL series.
