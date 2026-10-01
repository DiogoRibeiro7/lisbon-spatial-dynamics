# Data sources

The project uses a source-first catalogue and keeps raw acquisition separate from transformation.

## Housing series

INE changed the geographic standard used by the local housing-price series:

| Indicator | Geography | Role |
| --- | --- | --- |
| `0011364` | NUTS 2013 | Historical quarterly 2022-methodology series |
| `0012234` | NUTS 2024 | Current quarterly 2022-methodology series |

The two indicators are not merged by guessing geographic-code prefixes. Geographic harmonisation belongs to a later crosswalk step.

### Raw acquisition

The default command now uses the current NUTS 2024 series:

```bash
poetry run fetch-ine-housing
```

Acquire the historical NUTS 2013 series explicitly with:

```bash
poetry run fetch-ine-housing --config configs/ine_housing.toml
```

Each run stores immutable timestamped data, metadata, and a provenance manifest under `data/raw/ine/housing/<indicator>/`.

The unfiltered current API request returned **only 2026 Q1** on 2026-10-01. For a multi-period study, use:

```bash
poetry run fetch-ine-housing --config configs/ine_housing_study.toml
```

This versioned request fixes `Dim1` to 26 quarters (2019 Q4–2026 Q1), `Dim2` to the 24 official Lisbon parish codes, and `Dim3` to Total dwellings (`H1`). The codes were selected from captured INE metadata and checked against CAOP identifiers and names. It writes to `0012234/study_2019q4_2026q1/`. Fixed filters do not freeze revised values: retain the resulting snapshot and manifest.

### Stable housing contract

Raw INE records are flattened to:

| Column | Meaning |
| --- | --- |
| `indicator_code` | INE diffusion indicator |
| `period_code` | Original INE period key, preserved verbatim |
| `geography_code` | Original INE geographic code |
| `geography_name` | Original INE geographic label |
| `category_code` | Original dwelling-category code |
| `category_name` | Original dwelling-category label |
| `value_eur_m2` | Published median €/m², nullable |

Transform a current snapshot for Lisboa / Total with:

```bash
poetry run transform-ine-housing \
  data/raw/ine/housing/0012234/<timestamp>.data.json \
  data/processed/housing/lisbon.csv
```

Missing values remain missing. No imputation occurs during ingestion or transformation.

## Other source families

The catalogue also tracks INE census/geography data, Lisboa Aberta, and Strava Metro. Every integrated source must document provider, spatial unit, temporal coverage, access conditions, licence, provenance, and interpretation limits.

## Raw data policy

Raw source files are not committed to Git. Acquisition scripts and manifests provide reproducibility without treating third-party source files as repository assets.


## Local accommodation: RNAL

Turismo de Portugal exposes the Registo Nacional de Alojamento Local through a municipality-filtered SOAP operation. The response includes the fields needed for longitudinal neighbourhood analysis, notably registration date, cessation date, modality, capacity, freguesia, concelho and `DTMNFR`.

Acquire Lisboa records with:

```bash
poetry run fetch-rnal-lisboa
```

The resulting snapshot is intentionally **privacy-minimised**. The upstream service also returns proprietor/contact information under `TitulardaExploracao`, including names, tax identifiers, phone numbers and email addresses. Those fields are not required for this project and are discarded in memory before any file is written.

Stored records contain establishment-level analytical fields only:

- RNAL registration identifier;
- registration date;
- cessation date;
- establishment name;
- modality;
- beds and users/capacity fields;
- establishment address/postcode/locality;
- freguesia, concelho and district;
- `DTMNFR`.

The raw SOAP response itself is never written to disk. The manifest stores only its SHA-256 digest and records the privacy filtering applied.

The service schema includes `DataRegisto` and `CessadoEm`. The project uses their populated values to reconstruct registrations, cessations and active local-accommodation stock by freguesia on the housing quarter grid. Schema availability does not establish historical completeness: the 2026-10-01 response contained 11,865 records with **zero populated cessation dates**. Missing cessation dates cannot establish that no establishments closed. Stocks reconstructed from a current snapshot may omit establishments that disappeared before acquisition.

The [official operation contract](https://webservices.turismodeportugal.pt/RNT_External/WS_RNT.asmx?op=list_RNAL) exposes a municipality filter, with no documented historical-date or cancelled-record selector. Date fields are strings; the transformation accepts explicit supported forms and rejects unknown representations. The audit found seven registration dates before 2000, including 1930, which require clarification. No dates were corrected or records silently removed. See the [source audit](source-audit.md) for the evidence and release implications.


## Population reference: Censos 2021

The project uses the official INE Censos 2021 **subsection synthesis file** as the population reference. The ZIP retrieved on 2026-10-01 contains an XLSX workbook with `FREGUESIA`, `SUBSECCAO`, and `N_INDIVIDUOS`. The reader maps `FREGUESIA` to the existing `DTMNFR21` contract and explicitly maps the workbook's demographic/building labels. Legacy CSV/TXT archives remain supported.

The workbook mixes national, regional, municipal, parish, section, and subsection rows. Only rows with a non-empty `SUBSECCAO` are aggregated, avoiding double-counting totals. Parish identifiers remain strings, including leading zeros and alphanumeric codes outside Lisbon. Inconsistent parish/subsection identifiers and duplicate subsections fail validation.

Acquire the official ZIP with:

```bash
poetry run fetch-census2021-population
```

Then aggregate it to the canonical 24 Lisboa freguesias:

```bash
poetry run build-census2021-population-reference \
  data/raw/ine/census2021/subsections/<timestamp>.zip \
  data/processed/reference/lisbon_freguesias.csv \
  data/processed/reference/lisbon_population_2021.csv
```

The output contains:

- `freguesia_id`;
- canonical freguesia name;
- `census_year = 2021`;
- resident population;
- official CAOP area in hectares;
- resident-population density per km².

This is a **static 2021 census reference**. It is suitable for cross-sectional normalization, such as active RNAL registrations per 1,000 residents, but it must not be interpreted as annual population exposure for every year in the housing/RNAL panel.


## Censos 2021 neighbourhood structure

The same official INE subsection synthesis archive used for the resident-population reference also contains demographic and housing-structure variables that can be aggregated to the canonical 24 Lisboa freguesias.

The neighbourhood-context transform uses the official subsection fields for:

- resident population;
- classic buildings;
- buildings constructed before 1945;
- buildings needing repair;
- total/family/usual-residence dwellings;
- vacant or secondary-residence family dwellings;
- owner-occupied and rented usual-residence dwellings;
- private households;
- resident age bands 0–14, 15–24, 25–64 and 65+.

The raw counts remain in the context table. Derived variables include:

- age-band shares;
- owner-occupied share;
- rented share;
- vacant-or-secondary family-dwelling share;
- pre-1945 building share;
- repair-needs building share;
- dwellings per classic building.

No synthetic deprivation, gentrification, or neighbourhood-quality score is created.
