# Are housing changes spatially clustered?

Housing percentage changes across Lisbon's 24 parishes show **positive global spatial association** under the project's queen-neighbour definition: **Moran's I = 0.3421**, with a two-sided permutation **p = 0.0029**. However, **no parish passes the 5% false-discovery threshold** for the 24 local tests. The overall pattern does not justify labelling individual parishes as statistically supported local clusters.

The comparison uses the [audited 2019 Q4–2025 Q4 housing changes](housing-history.md) and the retained CAOP2025 geography. It was run on **2026-10-04**, using **9,999 permutations and seed 42**. The [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-spatial/2026-10-04) and its small geographic input are committed, so the complete spatial analysis can be reproduced offline from a fresh checkout.

![Nominal housing changes across Lisbon and the local Moran classification map, with every parish classified as not significant after FDR correction](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-spatial/2026-10-04/housing_spatial.png)

The grey map records a tested, non-significant result for each parish; it does not indicate missing data or zero housing change. [Download the full-resolution map](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/results/housing-spatial/2026-10-04/housing_spatial.png).

## Geography and weights

The [archived Lisbon reference](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/data/reference/caop2025-lisbon) contains all 24 canonical parishes, with attribution to **Direção-Geral do Território (DGT), CAOP2025, CC BY 4.0**. Its README and provenance record link the licence sources, original acquisition and source-audit fingerprints. Compact JSON serialization preserves the exact parsed reference document, including coordinates; no simplification or geometric repair was applied.

Two parishes are queen neighbours when their boundaries touch at any point. Tests use the original EPSG:4326 coordinates, without snapping, buffering or a distance threshold. Empty, invalid and non-polygonal geometries are rejected, as are intersecting polygon interiors, including identical or contained polygons. No parish is excluded, and no neighbour link is added to connect isolated units.

The resulting graph has **54 undirected pairs**, **108 directed links**, and **no isolated parishes**. Each parish has between **two and six neighbours**. The binary graph is symmetric; row standardization assigns each directed link weight `1 / neighbour_count`, so reciprocal weights can differ. `queen_pairs.csv` records each undirected pair once, with both directed weights.

The maps alone reproject the polygons to **ETRS89 / Portugal TM06 (EPSG:3763)** for display. CAOP2025 provides a fixed comparison geography; this analysis does not establish that all historical boundary versions were identical.

## Global and local results

| Check | Result |
| --- | ---: |
| Complete housing observations | 24 / 24 |
| Global Moran's I | 0.3421078150 |
| Randomization expectation, `−1 / (n − 1)` | −0.0434782609 |
| Two-sided global permutation p | 0.0029 |
| Local tests with unadjusted p ≤ 0.05 | 3 |
| Local tests with Benjamini–Hochberg q ≤ 0.05 | 0 |
| Smallest adjusted q | 0.2196 |

The three unadjusted local results are shown for transparency, rather than promoted to cluster claims:

| Parish | Descriptive quadrant | Local I | Unadjusted p | Adjusted q | Published classification |
| --- | --- | ---: | ---: | ---: | --- |
| Santa Maria Maior | Low–low | 2.3627 | 0.0178 | 0.2196 | Not significant |
| Arroios | Low–low | 0.4845 | 0.0183 | 0.2196 | Not significant |
| Parque das Nações | High–high | 0.2500 | 0.0453 | 0.3024 | Not significant |

High and low refer to **percentage change relative to the mean parish change**, not to price levels. Every parish's endpoint percentage change is positive. A low–low quadrant therefore does not imply declining prices. The local table retains all 24 values, quadrants, p-values and adjusted q-values, including the non-significant results.

## Test definitions

The existing Global Moran implementation centres housing changes across the 24 parishes and uses row-standardized neighbour weights. Its randomization test permutes values across the graph and counts simulated statistics at least as far from `−1 / (n − 1)` as the observed statistic. The reported pseudo-p is `(extreme + 1) / (permutations + 1)`, with resolution **0.0001** for this run.

The existing local implementation standardizes changes using the population variance across parishes and calculates each local I as the focal standardized value times its neighbours' mean standardized value. Conditional permutations hold the focal value fixed and sample other parish values without replacement, preserving the neighbour count. The two-sided statistic compares **absolute local I** against the observed absolute value. Each parish uses seed `42 + its zero-based position in sorted parish-code order`.

Benjamini–Hochberg adjustment is applied to the **24 housing local tests as one family**. A quadrant is assigned an HH/LL/HL/LH cluster label only if its adjusted q is at most 0.05. The global test is reported separately. These are Monte Carlo results under the stated spatial and randomization assumptions, not an exhaustive permutation enumeration. Global and local procedures test different aspects of the pattern; a significant global test can coexist with no FDR-significant local test.

The single-metric entry points use the existing calculations while leaving RNAL values absent. The joint housing/RNAL interfaces retain their previous behaviour and seed conventions. The queen-weight check now also rejects identical and contained polygons, which the previous overlap predicate alone missed; the accepted Lisbon graph is unchanged at 54 pairs.

## Reproduce and inspect

From the repository root, with the locked dependencies installed:

```bash
poetry sync --with docs
poetry run python scripts/analyse_housing_spatial.py --output data/processed/housing-spatial-recheck
```

The [configuration](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/configs/housing_spatial_2026-10-04.toml) pins six committed inputs by hash and size: housing changes, their report, the canonical parish reference, the archived polygons, geographic provenance and the original source audit. The script verifies the links between these reports, consumes the exact verified bytes and checks the endpoint arithmetic, comparison window, identities and coverage before computing statistics.

| Output | Contents |
| --- | --- |
| `global_moran.json` | One housing result, coverage, weights, test settings and interpretation |
| `local_moran.json` | One housing result with all 24 local observations and the test definition |
| `local_results.csv` | The same local observations with numbered map labels, change, standardized value, spatial lag, local I, degree, p, q, quadrant and final classification |
| `queen_pairs.csv` | 54 neighbour pairs and their reciprocal row-standardized weights |
| `housing_spatial.png` | Projected change and local-classification maps, with a parish key and source attribution |
| `analysis.json` | Summary, parameters, input/code/configuration/output hashes, software versions and interpretation |

`value` in the local CSV is housing percentage change; `spatial_lag_standardized` is the mean standardized change among that parish's neighbours. The CSV's `quadrant` is descriptive, whereas `cluster_class` applies the FDR decision. All 24 rows have `status=ok` and `significant_fdr=False` in this run.

The command requires a new output directory and publishes the complete bundle together. Existing results are preserved and failures leave no partial bundle. JSON/CSV files use UTF-8 with LF line endings. Compare numeric results and JSON/CSV hashes under the recorded software environment; the outer report's paths/code fingerprints and rendered image bytes may vary across environments. Reproduction uses the archived canonical subset and committed housing aggregates, without re-fetching or re-transforming the original raw acquisitions.

## What this establishes

Under one fixed geographic and neighbour definition, adjacent parishes tend to have more similar housing percentage changes than the global permutation null predicts. The result is descriptive and based on only 24 areas. It does not identify a causal mechanism, an RNAL effect, or a parish-specific hotspot surviving the chosen multiple-testing correction. Nominal values remain unadjusted for inflation or changes in the composition of sold properties.

Historical RNAL coverage and the remaining archival requirements still need resolution before the definitive joint v1.1 run.

The [sensitivity follow-up](housing-spatial-sensitivity.md) evaluates three change measures, queen/rook graphs and all 24 parish omissions. The selected global comparisons survive Holm correction, but queen and rook have identical neighbours, and Santa Maria Maior materially influences the statistic. The original local FDR result is unchanged.
