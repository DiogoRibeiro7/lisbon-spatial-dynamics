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

Because both `DataRegisto` and `CessadoEm` are available, the project reconstructs registrations, cessations and active local-accommodation stock by freguesia on the same quarterly grid as the housing panel. Turismo de Portugal documents these date fields as strings, so the transformation accepts only explicit supported date forms and rejects unknown representations.


## Population reference: Censos 2021

The project uses the official INE Censos 2021 **subsection synthesis file** as the population reference. The source contains `DTMNFR21`, which links each subsection to its freguesia, and `N_INDIVIDUOS`, the total resident-individual count used for aggregation.

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
