# INE annual housing quartiles for Lisbon municipality

Attribution: **Instituto Nacional de Estatística (INE)**, indicator **0013042**, methodology 2022, NUTS 2024. Licence: **CC BY 4.0**, as stated in the [official catalogue](https://dados.gov.pt/pt/datasets/vendas-de-alojamentos-familiares-metodologia-2022-eur-m2).

`quartiles.csv` preserves **21 published observations**: Q1, Q2 and Q3 for each calendar year 2019–2025. These are municipal transaction-distribution quartiles in nominal EUR/m². Q2 is the median; Q1–Q3 is a distribution range, not a confidence interval. The captured metadata includes Lisbon municipality but no Lisbon parish quartiles, and no spatial allocation is performed.

| Column | Meaning |
| --- | --- |
| `year` | Original annual reference period |
| `indicator_code` | `0013042` |
| `geography_code` | Original INE municipality code `1A01106` |
| `geography_name` | `Lisboa` |
| `quartile_code` | `1`, `2` or `3` |
| `quartile_name` | Original Portuguese quartile label |
| `value_eur_m2` | Published positive integer value in nominal EUR/m² |

Captured at **2026-10-05T10:04:08.217852+00:00**; the metadata source-update date is **2026-06-20**. `provenance.json` records exact request URLs, the acquisition manifest, extraction/configuration fingerprints and the canonical CSV hash. Raw JSON remains locally retained outside Git rather than in a public raw archive.

To extract from the same raw snapshot, run from the repository root:

```bash
poetry run python scripts/build_housing_quartile_reference.py --output data/processed/housing-quartile-reference-recheck
```

The default `configs/housing_quartile_reference_2026-10-05.toml` pins four inputs: raw data, metadata, acquisition manifest and acquisition configuration. Extraction verifies hashes/sizes and manifest links before consuming those same bytes. It requires annual frequency, EUR/m² units, no scaling, integer precision, exact municipality/period/quartile identities, complete positive values and `Q1 ≤ Q2 ≤ Q3`. Output directories must be new; publication is atomic.

A fresh request can be made with the existing generic INE acquisition command:

```bash
poetry run fetch-ine-housing --config configs/ine_housing_quartiles.toml
```

A fresh capture may contain revisions and cannot replace this pinned evidence. See the [distribution analysis](../../../../docs/housing-distribution.md) for offline replay, formulas and interpretation limits. No changes in fixed-quality dwelling values, affordability, income inequality or RNAL effects are identified.
