# Curated v1.0.1 data snapshot

This directory contains small, human-inspectable data tables committed as a post-release correction to v1.0.0.

The original v1.0.0 release contained the reproducible pipeline but no committed derived data or generated results. These files make the empirical evidence inspectable directly from GitHub while keeping large raw source snapshots out of version control.

## Files and provenance

### `housing_sales_2019q1_2026q1.csv`

Parish-level median dwelling sale values in EUR/m².

- **2019 Q1:** values published in Antunes & Seixas (2022), Table 3, sourced there from INE local housing-price statistics.
- **2026 Q1:** values displayed by Casanest from INE indicator 0012234.
- `change_pct` is derived as `100 * (Q1_2026 / Q1_2019 - 1)`.

Sources:

- https://doi.org/10.15847/cct.25960
- https://casanest.eu/precos/lisboa/lisboa

**Important:** this comparison is Q1 2019 → Q1 2026 and is a curated release evidence table. It is not identical to the package pipeline's Q4-2019 baseline contract.

### `rnal_weighted_2019_2022.csv`

Weighted number of Local Accommodation (AL) establishments by parish for November 2019 and November 2022.

Source: Câmara Municipal de Lisboa, *Relatório de Caracterização e Monitorização do Alojamento Local*, Quadro 18; underlying source Turismo de Portugal RNAL.

- https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf

The report defines the weighted AL count as `N.º Utentes / 5`; when users are fewer than five, the establishment takes value 1.

Displayed parish values are rounded. The report's published Lisboa total is calculated by the source and can therefore differ slightly from the sum/difference of displayed parish rows.

### `rnal_capacity_2019_2022.csv`

AL registered capacity by parish for November 2019 and November 2022.

Source: the same CML monitoring report, Quadro 19; underlying source Turismo de Portugal RNAL.

### `census_population_al_pressure_2021.csv`

Population change 2011→2021 and the 2021 AL / classic-family-dwelling ratio by parish.

Source: the same CML monitoring report, Quadro 12; underlying sources INE Censos 2011/2021 and Turismo de Portugal.

The source explicitly cautions that 2021 classic-family-dwelling counts exclude Local Accommodation considered active at the Census reference date.

### `housing_al_cross_section_2018.csv`

Published same-period cross-section of local-accommodation counts (30 June 2018) and housing EUR/m² values (June 2018).

Source: Martins (2019), *Turismo, gentrificação urbana e (des) alojamento local na cidade de Lisboa - Portugal*, Quadro 1.

- https://periodicos.ufsm.br/geografia/article/view/37424

The paper attributes the housing values to Pinto (2018) and AL counts to Gomes (2018). This file is retained as a **supplementary published cross-section**, not as a primary-source replacement for INE/RNAL.

## Scope

These committed tables are deliberately small derived/reported evidence tables. Full raw snapshots remain excluded from Git because of size, provenance, and redistribution considerations.
