# Data sources

The project uses a source-first data catalogue. A dataset is not accepted merely because it is available; it must also support the spatial and temporal comparisons required by the research design.

## Source priorities

Sources are evaluated in this order:

1. official statistical and administrative data;
2. municipal open data;
3. documented research or mobility datasets;
4. commercial or platform-derived data when methodology and usage conditions are sufficiently clear.

## Candidate source families

### Housing

The preferred housing layer is based on transaction-oriented official statistics where possible. Useful variables include:

- median transaction price per square metre;
- number of transactions;
- dwelling characteristics when consistently available;
- quarterly or annual reference period.

Asking-price datasets may be retained as a separate market-expectations layer, but they should not be silently combined with transaction prices.

### Population and demographics

Candidate variables include:

- resident population;
- age structure;
- household composition;
- employment and socioeconomic indicators;
- population density.

Census variables can provide richer detail but require care when comparing periods with different reference years.

### Mobility

Mobility is intentionally source-agnostic. Candidate layers may include:

- public transport accessibility;
- cycling and pedestrian infrastructure;
- counts or aggregated movement data;
- Strava Metro, if access and historical coverage are suitable.

Platform-derived activity should be interpreted as activity among platform users, not as a direct estimate of the full population.

### Tourism and local accommodation

Potential variables include:

- registered local accommodation;
- accommodation density;
- tourism intensity;
- changes in tourism-oriented land use.

### Urban infrastructure

Potential layers include:

- transport stops and stations;
- cycling infrastructure;
- pedestrian network characteristics;
- accessibility measures;
- public-space interventions.

## Acceptance criteria

Each source should record:

| Field | Requirement |
| --- | --- |
| Provider | Named source organisation |
| Dataset | Stable dataset name or identifier |
| Spatial unit | Geometry or administrative level |
| Temporal coverage | First and last usable period |
| Frequency | Annual, quarterly, monthly, or event-based |
| Update policy | Known publication/update cadence |
| Licence | Reuse conditions |
| Provenance | Download URL or acquisition procedure |
| Transformations | Reproducible processing steps |

## Raw data policy

Raw source files are not committed to Git. Acquisition scripts and metadata should make the source reproducible without pretending that third-party data can be redistributed when its licence does not allow that.
