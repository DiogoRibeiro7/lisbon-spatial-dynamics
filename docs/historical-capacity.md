# Historical accommodation capacity and population context

Lisbon's reported local-accommodation user capacity rises from **111,492 places in November 2019 to 116,218 in November 2022**, an increase of **4,726 (4.24%)**. Relative to the same **545,796 Census 2021 residents** at both dates, that is **204.27 to 212.93 capacity places per 1,000 reference residents**.

The four parishes with the largest reported capacity at the 2019 baseline—**Santa Maria Maior, Misericórdia, Arroios and Santo António**—hold **64.30%** of municipality capacity then and **61.32%** in 2022. Their combined capacity falls by **417 places**, while combined capacity in the other 20 parishes rises by **5,143**. Membership of this comparison group is fixed at baseline.

The [evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/historical-capacity/2026-10-05) contains all 24 parish comparisons, municipality totals, the fixed-group concentration table, a figure and reproducible provenance. It uses the [audited municipal benchmarks](cml-historical-benchmarks.md) and [audited Census context](source-audit.md), without reconstructing history from current registry membership.

![Reported capacity levels and changes per 1,000 fixed Census 2021 residents for all 24 Lisbon parishes](https://raw.githubusercontent.com/DiogoRibeiro7/lisbon-spatial-dynamics/main/results/historical-capacity/2026-10-05/historical_capacity.png)

## Two different denominators

For parish `i`, capacity `C` and Census 2021 resident population `P`:

```text
Capacity relative to population(i,t) = 1000 × C(i,t) / P(i,2021)
Change relative to population(i) = 1000 × [C(i,2022-11) − C(i,2019-11)] / P(i,2021)

Parish share of municipality capacity(i,t) = 100 × C(i,t) / sum_j C(j,t)
```

The first denominator is **fixed population**. It makes parish sizes comparable without implying that the 2021 population was also observed in 2019 or 2022. The municipality ratio divides total capacity by total reference population; it is not the unweighted average of parish ratios.

The second denominator is **municipality capacity at each source month**. This produces shares expressed as percentages; changes in those shares are expressed in percentage points. A group's share can fall because its own capacity falls, capacity elsewhere grows, or both.

| Fixed baseline group | Parishes | November 2019 capacity | November 2022 capacity | Capacity change | Share in 2019 | Share in 2022 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Four largest-capacity parishes in 2019 | 4 | 71,685 | 71,268 | −417 | 64.30% | 61.32% |
| Remaining parishes | 20 | 39,807 | 44,950 | +5,143 | 35.70% | 38.68% |

The first group's share declines by **2.97 percentage points**. The declared configuration selects four parishes by baseline **capacity**, with ascending parish identifier as a deterministic tie-breaker. Membership stays fixed at the later date. This is a descriptive concentration comparison, not a spatial-autocorrelation test or evidence of displacement between parishes.

## Parish differences

Reported capacity increases in **20 parishes** and decreases in **four**. The median parish change is **+7.33 places per 1,000 Census 2021 residents**; the municipality change is **+8.66** using its aggregate denominator. These are distinct summaries.

The largest population-normalized increases occur in **Alcântara (+38.99)** and **Ajuda (+36.56)**, followed by Campo de Ourique (+28.82), Estrela (+28.42) and Campolide (+25.36). The declines occur in **Santa Maria Maior (−70.84)**, **Santo António (−26.76)**, **São Vicente (−14.12)** and **Parque das Nações (−0.04)**, all in capacity places per 1,000 fixed reference residents. The CSV preserves the underlying counts, denominators and full decimal values.

Santa Maria Maior's 2022 ratio is **2,495.37 reported capacity places per 1,000 Census 2021 residents**. A value above 1,000 is possible because the numerator is accommodation capacity, not a subset of the resident population. This is not a percentage of residents, a count of visitors, or evidence that all places were occupied.

## Source and interpretation limits

Capacity comes from **table 19**, printed page 95 / PDF page 107 of Câmara Municipal de Lisboa's December 2022 *Relatório de Caracterização e Monitorização do Alojamento Local*, whose underlying data are attributed to Turismo de Portugal/RNAL. The previous benchmark audit preserves the [source identity, archived URL and reviewed transcription](cml-historical-benchmarks.md#source-and-meaning). Population comes from INE's Censos 2021 parish aggregates, independently reconciled with the municipality total in the source audit.

The source table identifies **November 2019 and November 2022**, without exact observation days. These remain month-level references. They are not quarter-end stocks, interpolated observations, or a seven-year history. The user-capacity measure is separate from the report's capacity-weighted AL units and from unweighted registration counts. Table 19's parish values and changes reconcile with its municipality totals; the known arithmetic discrepancies in weighted table 18 remain recorded in the parent audit.

Reported administrative capacity does not establish actual operation, occupancy, unique visitors or overnight stays. A decline does not identify individual closures, and a change can reflect revisions as well as administrative events. The analysis neither corrects parish assignments using the later GIS snapshot nor treats 2026 capacity as historical capacity. There is no housing-price association or causal estimate here, and the [historical RNAL request](rnal-history-request.md) remains necessary for the definitive joint study.

## Reproduction and output contract

With the locked dependencies installed, run from the repository root:

```bash
poetry run python scripts/analyse_historical_capacity.py --output data/processed/historical-capacity-recheck
```

`configs/historical_capacity_2026-10-05.toml` pins four committed inputs: the municipal transcription, its benchmark audit, the Census context CSV and the primary-source audit. The command verifies every input's hash and byte size, checks the audit links, reads the verified bytes, reproduces the complete benchmark summary and verifies the Census denominator. Non-reconciling capacity totals or changes, invalid populations, duplicate/missing parishes and altered source links fail validation.

| Artifact | Contents |
| --- | --- |
| `parish_capacity.csv` | 24 parish rows with original capacity endpoints, fixed population denominator, changes, capacity shares and baseline-group membership |
| `municipality_capacity.csv` | One separate municipality row, formed from sums before normalization |
| `concentration.csv` | Two fixed groups with capacity levels, changes, municipality shares and share changes |
| `historical_capacity.png` | Parish capacity levels and changes relative to the fixed population reference |
| `analysis.json` | Summary, group membership, source attribution, interpretation, software versions and input/code/output fingerprints |

The output directory must be new. A fresh Decimal context at precision 28 isolates calculations from caller settings; CSVs preserve decimal results and use UTF-8/LF. JSON summaries use numeric floats. A zero parish baseline produces a missing percentage change while retaining its absolute and population-normalized changes. Nonpositive populations and zero municipality capacity totals are rejected.

Offline replay starts from committed aggregate facts. It does not reopen the original PDF or Census workbook and does not recheck source cells visually; their identities and earlier validation are retained through the pinned reports. Those original files remain locally retained outside Git, and no source-document redistribution licence is asserted. The figure and tables reproduce within the tested environment; image bytes and path/software fingerprints may vary elsewhere. Integration tests deliberately use the dated committed inputs; a revised source requires a new bundle.
