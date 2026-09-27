# Data sources

The project uses a source-first data catalogue. A dataset is not accepted merely because it is available; it must also support the spatial and temporal comparisons required by the research design.

The machine-readable registry lives in `configs/data_sources.toml`. It is parsed and validated by `lisbon_spatial_dynamics.catalog`, which keeps source metadata under version control before ingestion code is introduced.

## Catalogue lifecycle

Each entry has one of three states:

- **candidate** — potentially useful, but not yet sufficiently documented;
- **catalogued** — official metadata and provenance have been identified;
- **access_required** — scientifically relevant, but dependent on external access or approval.

A catalogue entry does **not** mean the dataset has already been downloaded or accepted into the final panel.

## Current source families

| Source | Domain | Current role |
| --- | --- | --- |
| INE local housing-price statistics | Housing | Preferred transaction-oriented housing anchor |
| INE census geographic/alphanumeric downloads | Population and demographics | Reference geography and long-run demographic structure |
| Lisboa Aberta | Municipal open data | Discovery portal for dataset-specific Lisbon infrastructure, mobility, tourism and planning sources |
| Strava Metro | Active mobility | Conditional mobility layer requiring suitable access and historical coverage |

Individual datasets discovered through a portal such as Lisboa Aberta should receive their own catalogue entry before they are used.

## Source priorities

Sources are evaluated in this order:

1. official statistical and administrative data;
2. municipal open data;
3. documented research or mobility datasets;
4. commercial or platform-derived data when methodology and usage conditions are sufficiently clear.

## Housing

The preferred housing layer is based on transaction-oriented official statistics where possible. Useful variables include:

- median transaction price per square metre;
- number of transactions;
- dwelling characteristics when consistently available;
- quarterly or annual reference period.

Asking-price datasets may be retained as a separate market-expectations layer, but they should not be silently combined with transaction prices.

### First ingestion: INE indicator 0011364

The first implemented acquisition is INE indicator `0011364`: the quarterly median value of dwelling sales per square metre over the previous 12 months, by geographical location and dwelling category.

The acquisition configuration is versioned in `configs/ine_housing.toml`. Run:

```bash
poetry run fetch-ine-housing
```

The command downloads both the indicator payload and its INE metadata. It stores a timestamped raw snapshot under:

```text
data/raw/ine/housing/0011364/
├── YYYYMMDDTHHMMSSZ.data.json
├── YYYYMMDDTHHMMSSZ.metadata.json
└── YYYYMMDDTHHMMSSZ.manifest.json
```

The manifest records the acquisition time, source URLs, byte counts, and SHA-256 checksums. Existing timestamped snapshots are never overwritten.

Raw acquisition deliberately does not reshape, filter, or interpret the INE payload. Lisbon-specific extraction and conversion to a stable tabular contract belong to the transformation layer so the original response remains auditable.

## Population and demographics

Candidate variables include:

- resident population;
- age structure;
- household composition;
- employment and socioeconomic indicators;
- population density.

Census variables can provide richer detail but require care when comparing periods with different reference years or boundary definitions.

## Mobility

Mobility is intentionally source-agnostic. Candidate layers may include:

- public transport accessibility;
- cycling and pedestrian infrastructure;
- counts or aggregated movement data;
- Strava Metro, if access and historical coverage are suitable.

Platform-derived activity should be interpreted as activity among platform users, not as a direct estimate of the full population.

## Tourism and local accommodation

Potential variables include:

- registered local accommodation;
- accommodation density;
- tourism intensity;
- changes in tourism-oriented land use.

## Urban infrastructure

Potential layers include:

- transport stops and stations;
- cycling infrastructure;
- pedestrian network characteristics;
- accessibility measures;
- public-space interventions.

## Acceptance criteria

Every dataset-specific source record must document:

| Field | Requirement |
| --- | --- |
| Provider | Named source organisation |
| Dataset | Stable dataset name or identifier |
| Domain | Research dimension served by the source |
| Spatial unit | Geometry or administrative/statistical level |
| Temporal coverage | First and last usable period, or an explicit statement that this must still be established |
| Frequency | Annual, quarterly, monthly, event-based, or dataset-specific |
| Access | Public download, API, partnership, request, or other acquisition mechanism |
| Licence | Reuse conditions or an explicit requirement to verify them |
| Provenance | Stable official landing page or acquisition procedure |
| Notes | Important limitations, role, or interpretation constraints |

## Raw data policy

Raw source files are not committed to Git. Acquisition scripts and metadata should make the source reproducible without pretending that third-party data can be redistributed when its licence does not allow that.

## Adding a source

Add a new `[[sources]]` table to `configs/data_sources.toml`, then run:

```bash
poetry run pytest tests/test_catalog.py
poetry run mypy src tests
```

The catalogue loader rejects malformed entries, duplicate identifiers, invalid lifecycle states, and non-HTTP(S) provenance URLs.
