# INE annual-window housing sales counts

Attribution: **Instituto Nacional de Estatística (INE)**, indicator **0014363**, methodology 2022, NUTS 2024. Licence: **CC BY 4.0**, as stated in the [official catalogue](https://dados.gov.pt/pt/datasets/vendas-de-alojamentos-familiares-nos-ultimos-12-meses-metodologia-2022-n-o).

`sales_panel.csv` contains **175 published observations** for 2019–2025: Lisbon municipality and all 24 canonical parishes at Q4. Each value counts sales in the **preceding 12 months**, not one quarter. The municipality is a separate row, never added to its parish components. All seven parish sums exactly reconcile with the published municipality counts.

| Column | Meaning |
| --- | --- |
| `year` | Calendar year of the Q4 observation and preceding 12-month sales window |
| `period_code` | Original INE Portuguese Q4 label |
| `geography_level` | `municipality` or `parish` |
| `geography_id` | `1106` for Lisboa, otherwise the six-character canonical parish identifier |
| `geography_name` | Validated source/canonical name |
| `indicator_code` | `0014363` |
| `source_geography_code` | Original INE code, validated against captured metadata |
| `sales` | Published nonnegative integer count; no missing values in this capture |

The response was captured **2026-10-05T08:58:15.726236+00:00**, with source metadata last updated **2026-07-17**. `provenance.json` retains the acquisition manifest, exact request URLs and hashes/sizes for the raw data, metadata, acquisition configuration, canonical reference, extraction code and resulting CSV. The raw JSON remains in the ignored local workspace rather than in Git; the committed CSV supports offline analysis. There is no claim that the raw responses are publicly archived.

To extract again from the exact locally retained raw snapshot, run from the repository root:

```bash
poetry run python scripts/build_housing_sales_reference.py --output data/processed/housing-sales-reference-recheck
```

The default `configs/housing_sales_reference_2026-10-05.toml` pins the raw responses and related inputs. The builder verifies hashes, sizes, manifest links, indicator identity, units/scaling/precision, geography names, Q4 periods and complete reconciled counts. It rejects unpublished or flagged counts; it does not interpret them as zeros. Extraction uses the bytes already verified and publishes a new directory atomically.

A fresh capture can be requested with the existing generic INE acquisition command:

```bash
poetry run fetch-ine-housing --config configs/ine_housing_sales.toml
```

The command name is historical; the configuration selects indicator `0014363`. A new request may contain source revisions and does not replace this pinned snapshot. Later evidence belongs in a new dated bundle.

See [sales-volume context](../../../../docs/housing-sales.md) for findings and the offline analysis command. Total counts have no dwelling-category breakdown and cannot decompose the changes in pooled price medians.
