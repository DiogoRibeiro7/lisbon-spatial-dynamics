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
