# Annual Portugal CPI, 2019–2025

`annual_cpi.csv` contains the seven published annual index values from **Instituto Nacional de Estatística (INE), indicator 0014642, base 2025, Portugal (`PT`), Total (`T`)**. The index is 100 in its base year. Index-base year and the housing comparison's currency-reference year are separate concepts.

**Attribution:** Instituto Nacional de Estatística (INE), Índice de preços no consumidor. **Data licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), recorded by the [official open-data catalogue](https://dados.gov.pt/pt/datasets/indice-de-precos-no-consumidor-ipc-base-2025-0014642), checked 2026-10-04. This data licence is separate from the repository's MIT software licence.

The source data and metadata were captured together at `2026-10-04T21:27:49.958318+00:00` using `configs/ine_cpi_annual.toml`. Metadata identifies annual frequency, three decimal places, the 2025 base, the selected geography/aggregate, and an update date of 2026-02-11. The canonical table preserves the published numeric values without combining index bases or compounding rounded inflation rates. The older `0003863` endpoint was unavailable during discovery; it was not used.

`provenance.json` records both source-response fingerprints, acquisition URLs, the acquisition manifest, extraction configuration/code and the canonical CSV fingerprint. Original JSON responses remain under ignored `data/raw/ine/cpi/0014642/2019_2025/`; the canonical table and provenance are committed. All downstream housing adjustments replay offline from this reference. Re-extracting the reference itself requires those retained raw captures:

```bash
poetry run python scripts/build_cpi_reference.py --output data/processed/cpi-reference-recheck
```

For a **new capture**, the existing configurable INE downloader accepts this source configuration:

```bash
poetry run fetch-ine-housing --config configs/ine_cpi_annual.toml
```

This creates a new timestamped capture; it does not reproduce the pinned bytes. A reviewed new extraction configuration is needed to use a later snapshot. The historical command name does not alter the explicitly configured indicator.

As a supplementary check on 2026-10-04, INE's [annual CPI value-update calculator](https://www.ine.pt/ine/ipc/ipc_b_novo.jsp?opc1=05%7CA), with Portugal/Total, initial year 2019, final year 2025 and EUR 100, displayed factor `1.19380422921614`. The explicit published annual-index ratio used here is `100 / 83.775 = 1.1936735302894658`. The difference is about **0.01307 percentage points** of cumulative inflation. The reason for the discrepancy has not been established; calculator coefficients are not substituted into this series. Both choices leave the two below-baseline parishes unchanged. The analysis is defined by the pinned, published annual-index observations.

`calculator_check.json` records the submitted form fields, displayed calculator outputs and the locally retained HTML fingerprint. It is a supplementary source check, separate from the seven-value analysis input.
