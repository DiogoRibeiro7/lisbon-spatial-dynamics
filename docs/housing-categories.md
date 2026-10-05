# Housing changes by dwelling category

The median parish increase for **existing dwellings** between **2019 Q4 and 2025 Q4** is **47.64%**, compared with **47.52% for Total dwellings** across the same 24 parishes. Similar overall medians conceal local differences: existing-dwelling growth ranges from **15.76 percentage points below Total in Parque das Nações** to **13.74 points above Total in Misericórdia**.

This comparison asks whether the previously reported Total trend also appears within INE's dwelling categories. It uses a new capture of the same official indicator, `0012234`, with **H1 (Total), H11 (Novos / New), and H12 (Existentes / Existing)**. All **168 Total observations exactly match** the [earlier audited housing evidence](housing-history.md). The [new evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/housing-categories/2026-10-05) preserves matched comparisons, coverage, a figure and provenance.

![Matched parish comparisons of Total and existing/new dwelling median changes](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/housing-categories/2026-10-05/housing_categories.png)

## Matched endpoint comparisons

Each category is compared with Total over **the same parishes with both category endpoints published**. Parish changes receive equal weight; none of these statistics is a municipality-wide transaction median.

| Category | Matched parishes | Median category change | Median Total change in the matched parishes | Median paired gap, category minus Total |
| --- | ---: | ---: | ---: | ---: |
| Total | 24 | 47.52% | 47.52% | 0.00 pp |
| Existing | 24 | 47.64% | 47.52% | −0.76 pp |
| New | 14 | 45.02% | 44.45% | −1.24 pp |

The **median paired gap** is the median of the 24 or 14 parish-level differences. It is not generally the difference between the two median changes. For example, Existing's paired median gap is −0.76 pp even though its median change is slightly above Total's.

The new-dwelling comparison excludes ten parishes with an unpublished endpoint. Its 45.02% median must therefore be compared with the **44.45% Total median for those same 14 parishes**, rather than with the 24-parish headline. Lumiar illustrates why individual comparisons matter: its new-dwelling median rises **139.11%**, against **65.74% for Total**, a **73.37 pp** gap. This does not identify the contribution of new sales to the pooled median.

## Coverage and missing values

The request contains **504 keys: 24 parishes × seven Q4 periods × three categories**. Every key is returned, including observations for which INE publishes no numerical median.

| Category | Published medians / 168 requested | Unpublished medians | Parishes with all seven years | Parishes with both endpoints |
| --- | ---: | ---: | ---: | ---: |
| Total | 168 | 0 | 24 | 24 |
| Existing | 167 | 1 | 23 | 24 |
| New | 100 | 68 | 6 | 14 |

The sole unpublished Existing median is **Marvila, 2020 Q4**; both endpoint values are published. An endpoint comparison does not require every intervening value. Conversely, complete endpoints do not establish a complete annual series.

The capture identifies missing medians with the source flag `-` and description **“Dado nulo ou não aplicável”**. The canonical CSV retains both fields and leaves `value_eur_m2` blank. A blank median is not a zero price or evidence of zero transactions. This analysis does not infer a suppression threshold or distinguish reasons that the source groups under this flag.

New-dwelling endpoint exclusions are Ajuda, Alcântara, Beato, Benfica, Carnide, Olivais, Alvalade, Areeiro, Penha de França and Santa Clara. Their available endpoint values and the flags for missing endpoints remain in `endpoint_changes.csv`; only change calculations and matched summaries exclude them. `annual_coverage.csv` gives all 21 category/year coverage counts.

## What the comparison establishes

For parish `i` and category `c`, nominal endpoint change is `100 × [P(i,c,2025 Q4) / P(i,c,2019 Q4) − 1]`. The paired gap subtracts the corresponding Total change in **percentage points**. Each category uses its own parish-specific baseline. Q4 medians cover the preceding 12 months, so these endpoints compare calendar-year transaction windows.

The Existing median change resembles the Total median change across all 24 parishes, while the matched parish gaps show material local variation. The New comparison is restricted to observed endpoints and is not representative of all parishes by construction.

Separating categories does **not** hold property quality, size, exact location or the mix of transactions constant within a category. Category medians cannot recover category sales shares, reconstruct the pooled median, or decompose its change into price and composition effects. Transaction counts and distributions are not included. These are nominal descriptive comparisons; no inflation adjustment, hypothesis tests, new spatial claims, RNAL effect, or causal estimate is produced. The [separate CPI analysis](housing-inflation.md) retains its existing interpretation.

## Source and reproduction

The INE capture was made on **2026-10-04**, using `configs/ine_housing_categories.toml`. Its metadata specifies methodology 2022, NUTS 2024 geography, quarterly frequency, EUR/m² and integer precision. The [official catalogue](https://dados.gov.pt/datasets/valor-mediano-das-vendas-de-alojamentos-familiares-nos-ultimos-12-meses-metodologia-2022-eur-m2) identifies the category dimension and **CC BY 4.0** licence. Attribution: **Instituto Nacional de Estatística (INE)**.

The [canonical category reference](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/data/reference/ine-housing-categories/2026-10-04) contains the 504 observations and acquisition/extraction provenance. Raw JSON remains locally retained outside Git. A fresh API request can contain revisions and is not a substitute for that snapshot.

With the locked dependencies installed, run from the repository root:

```bash
poetry run python scripts/analyse_housing_categories.py --output data/processed/housing-categories-recheck
```

The default `configs/housing_categories_2026-10-05.toml` pins six committed inputs: the category CSV and provenance, original housing quarterly aggregates, canonical parish reference, nominal housing report and source audit. Replay verifies input hashes/sizes and provenance links, consumes the verified bytes, reproduces the original nominal summary and checks all 168 newly captured Total values before calculating category comparisons. Changed Total values fail rather than silently revising the earlier evidence.

| Artifact | Contents |
| --- | --- |
| `endpoint_changes.csv` | All 72 parish/category endpoint records, original prices/flags, completeness, changes and paired gaps |
| `annual_coverage.csv` | Published and unpublished median counts for each of 21 category/year combinations |
| `matched_comparisons.csv` | Three summaries, including matched/excluded parish counts, full-series coverage and paired differences |
| `housing_categories.png` | Existing and New comparisons, each restricted to its matched endpoint sample |
| `analysis.json` | Summary, excluded endpoint identities, interpretation, software versions and input/code/output fingerprints |

Output directories must be new. Calculations use a fresh precision-28 Decimal context; CSVs retain decimal results and use UTF-8/LF, while JSON summaries use numeric floats. Paths and image bytes can vary across environments. Offline integration tests intentionally depend on the immutable committed aggregate inputs; later data require new bundles. Extraction from the pinned raw capture is separately reproducible with `scripts/build_housing_category_reference.py`, as described in the reference README.

Historical RNAL coverage remains unresolved, and this housing comparison does not complete the joint v1.2 study.

The [sales-volume follow-up](housing-sales.md) adds Total counts for the same annual windows. They describe parish transaction activity but have no New/Existing breakdown, so they do not identify the category shares or missing-value reasons discussed here.
