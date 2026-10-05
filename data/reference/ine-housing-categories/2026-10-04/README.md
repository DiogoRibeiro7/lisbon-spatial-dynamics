# INE dwelling-category housing medians, 2019–2025 Q4

`category_panel.csv` preserves **504 aggregate observations**: 24 Lisbon parishes × seven Q4 periods × Total (`H1`), New (`H11`, *Novos*) and Existing (`H12`, *Existentes*) dwellings. The measure is the median sale value per square metre during the preceding 12 months, INE indicator **0012234**, methodology 2022, NUTS 2024.

**Attribution:** Instituto Nacional de Estatística (INE). **Data licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), identified by the [official catalogue](https://dados.gov.pt/datasets/valor-mediano-das-vendas-de-alojamentos-familiares-nos-ultimos-12-meses-metodologia-2022-eur-m2). The data licence is separate from the repository's software licence.

The raw responses were acquired on 2026-10-04 using `configs/ine_housing_categories.toml` and retained under ignored `data/raw/ine/housing/0012234/categories_2019_2025/20261004T223654Z.*`. `provenance.json` records the capture's exact timestamp, source URLs, hashes, byte sizes, acquisition manifest, extraction code/configuration and canonical CSV fingerprint. Raw JSON is not committed or publicly archived.

Published prices remain exact positive integers. For 69 keys, INE returns no numerical median and the flag `-`, described as “Dado nulo ou não aplicável”. These keys retain a blank `value_eur_m2` and the original flag/description. Neither zero prices nor transaction counts are inferred. Missing rows, duplicate keys, mismatched geography/category labels, undocumented flags and changed metadata contracts fail extraction.

Parish identities are pinned to `results/source-audit/2026-10-01/census_context.csv`. Source geography codes are explicitly validated as `1A0` plus the canonical six-digit parish identifier for this captured indicator. The downstream category analysis independently checks that all 168 Total medians match the earlier housing audit.

Re-extract from the locally retained exact raw capture into a new directory:

```bash
poetry run python scripts/build_housing_category_reference.py --output data/processed/housing-category-reference-recheck
```

For a **new acquisition**, use:

```bash
poetry run fetch-ine-housing --config configs/ine_housing_categories.toml --timeout 60
```

A new capture does not reproduce the pinned snapshot; using it requires a reviewed extraction configuration and a new bundle. The [category comparison](../../../../docs/housing-categories.md) replays offline from this committed reference and the original housing evidence.
