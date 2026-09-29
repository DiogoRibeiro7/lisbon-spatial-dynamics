# Spatial analysis

Spatial analysis is a core part of the project rather than a visualisation step added at the end.

## Reference geography

The canonical project geography is the **24-freguesia map of the municipality of Lisboa**, acquired from DGT's official CAOP2025 parish layer.

CAOP exposes the INE-assigned `DTMNFR` unique freguesia identifier together with the parish name, municipality, NUTS fields and official geometry. The project requests the Lisbon subset directly from DGT as GeoJSON in EPSG:4326.

Acquire an immutable raw snapshot with:

```bash
poetry run fetch-caop-lisbon
```

Then build the stable project reference artifacts:

```bash
poetry run build-reference-geography \
  data/raw/dgt/caop2025/lisbon_freguesias/<timestamp>.geojson \
  data/processed/reference
```

This produces:

```text
data/processed/reference/
├── lisbon_freguesias.csv
└── lisbon_freguesias.geojson
```

The CSV is the canonical identifier table. The GeoJSON contains the same 24 records and geometry, with project-owned property names. Both are sorted by `freguesia_id`, which is the CAOP `DTMNFR` identifier.

### Canonical reference fields

| Field | Meaning |
| --- | --- |
| `freguesia_id` | Official CAOP/INE `DTMNFR` identifier |
| `name` | Official freguesia designation |
| `simplified_name` | Simplified CAOP designation when available |
| `municipality` | Municipality, required to be Lisboa |
| `district` | District/island designation |
| `nuts3_code` | CAOP NUTS 3 code |
| `nuts3_name` | CAOP NUTS 3 designation |
| `nuts2_name` | CAOP NUTS 2 designation |
| `nuts1_name` | CAOP NUTS 1 designation |
| `area_ha` | Official CAOP area in hectares |

The raw acquisition validates that exactly 24 Lisbon features are returned and that upstream identifiers, geometry, and configured fields remain valid. The transformation repeats the core integrity checks before creating the canonical artifacts.

## Harmonisation rule

Every spatial dataset must retain both:

- its original source geography and identifier;
- the canonical project geography used after harmonisation.

Source records must never be joined by a guessed prefix or by parish name alone when an authoritative identifier or spatial crosswalk is available.

For the planned study period beginning after Lisbon's 2012 administrative reorganisation, the 24-freguesia system provides the reference framework. Any dataset with a different historical geography requires an explicit crosswalk before entering the longitudinal panel.

## Core outputs

The initial spatial analysis should support:

- choropleth maps of levels and changes;
- neighbourhood trajectories over time;
- local and global spatial autocorrelation diagnostics;
- accessibility and network-derived measures;
- comparison of housing change with mobility and urban-context layers.

## Change measures

Absolute and relative change answer different questions. Both may be useful:

\[
\Delta x_{i,t} = x_{i,t} - x_{i,t-k}
\]

and

\[
r_{i,t} =
\frac{x_{i,t} - x_{i,t-k}}
{x_{i,t-k}}.
\]

For highly skewed positive variables, log differences may provide a more interpretable proportional-change measure.

## Spatial joins

Spatial joins must be reproducible and explicit about:

- geometry validity;
- point-on-boundary behaviour;
- many-to-one relationships;
- area weighting;
- population weighting;
- unmatched records.

A successful join is not sufficient evidence that the resulting measure is meaningful.

## Maps as analysis

Maps should expose uncertainty, missing coverage, and boundary changes where relevant. Missing observations must not be rendered in a way that makes them look like zero values.


## Annual map-ready layers

The annual comparison panel can be joined back to the canonical CAOP geometry without a spatial overlay because both datasets already use the same `freguesia_id`.

Build one GeoJSON layer per year with:

```bash
poetry run build-annual-map-layers \
  data/processed/urban/lisbon_annual_urban_change.csv \
  data/processed/reference/lisbon_freguesias.geojson \
  data/processed/maps/annual
```

The output directory contains files such as:

```text
lisbon_urban_change_2019.geojson
lisbon_urban_change_2020.geojson
...
```

Every year must contain exactly the same canonical freguesia identifiers as the reference geometry. Missing or extra freguesias fail the export.

The geometry is unchanged from the canonical CAOP layer. Annual analytical properties are attached to each feature, including:

- housing level;
- housing YoY change;
- housing cumulative change from baseline;
- annual RNAL registration/cessation flows when complete;
- RNAL active stock and cumulative stock change;
- known/missing capacity fields.

Exact decimal values remain authoritative in the CSV panel. GeoJSON exports convert decimal analytical properties to JSON numbers for mapping interoperability.

This makes year-to-year choropleths directly comparable because the geometry and property contract are stable across all exported years.


## Baseline-to-latest trajectory map

The common-window freguesia trajectory table can be joined to the canonical geometry as one map-ready GeoJSON:

```bash
poetry run build-trajectory-map \
  data/processed/urban/lisbon_freguesia_trajectories.csv \
  data/processed/reference/lisbon_freguesias.geojson \
  data/processed/maps/lisbon_freguesia_trajectories.geojson
```

The export requires the trajectory and reference key sets to match exactly and requires all trajectory rows to share the same baseline/latest comparison window.

The properties preserve housing and RNAL change as separate dimensions. No composite classification or ranking is attached to the geometry.


## Static trajectory choropleths

The baseline-to-latest trajectory GeoJSON can be rendered into two static choropleths:

```bash
poetry run build-trajectory-choropleths \
  data/processed/maps/lisbon_freguesia_trajectories.geojson \
  data/processed/plots/trajectory
```

This writes:

```text
housing_change_pct.png
rnal_active_change_pct.png
```

The first map shows full-window percentage change in median housing value per m². The second shows full-window percentage change in active RNAL registrations.

Missing analytical values use a neutral fill rather than being shown as zero. When a metric contains both positive and negative changes, the colour scale is centred on zero; otherwise it spans the observed range directly.

Freguesia labels are off by default to avoid clutter and can be enabled with `--labels`.

These choropleths are descriptive spatial views. They identify where measured changes are larger or smaller, but they do not by themselves establish spatial clusters, hotspots, or causal relationships.


## Global spatial autocorrelation

The trajectory choropleths can be followed by a formal Global Moran's (I) calculation:

```bash
poetry run build-global-morans-i \
  data/processed/maps/lisbon_freguesia_trajectories.geojson \
  data/processed/analysis/global_morans_i.json
```

The analysis is run separately for:

- full-window housing-price percentage change;
- full-window active RNAL percentage change.

Spatial weights use **queen contiguity** derived from the canonical freguesia polygons: two freguesias are neighbours when their boundaries touch at any point. The weights are row-standardized before Moran's (I) is calculated.

The output records:

- observed Global Moran's (I);
- the randomization expectation (E[I] = -1/(n-1));
- complete-case count;
- excluded missing observations;
- islands produced after metric-specific missing-value filtering;
- the number of induced neighbour edges;
- a deterministic two-sided permutation p-value.

The default test uses 999 permutations and seed 42. Both can be changed with `--permutations` and `--seed`.

The permutation test compares the absolute distance of the observed statistic from the randomization expectation with the corresponding distances under random permutation.

Global Moran's (I) answers whether the metric shows overall spatial autocorrelation under the selected weight matrix. It does **not** identify which freguesias form local clusters or hotspots, and it does not establish causality.


## Local spatial association: LISA

Global Moran's (I) answers whether a metric is spatially autocorrelated overall. Local Moran's (I) provides the next level of detail by evaluating each freguesia relative to its queen-contiguous neighbours.

Run:

```bash
poetry run build-local-morans-i \
  data/processed/maps/lisbon_freguesia_trajectories.geojson \
  data/processed/analysis/local_morans_i.json
```

The analysis is run separately for housing-price percentage change and active RNAL percentage change.

For each complete, non-island freguesia the output records:

- standardized local value;
- row-standardized spatial lag;
- Local Moran's (I_i);
- neighbour count;
- Moran-scatterplot quadrant: HH, LL, HL or LH;
- two-sided conditional permutation pseudo-(p);
- Benjamini–Hochberg FDR-adjusted (q);
- final local cluster class.

The conditional permutation test holds the focal freguesia's standardized value fixed and repeatedly samples an equal-sized neighbour set from all other complete-case standardized values.

Because 24 local tests are potentially evaluated for each metric, raw local pseudo-(p) values are corrected using the Benjamini–Hochberg false-discovery-rate procedure. A freguesia is labelled HH, LL, HL or LH in the final `cluster_class` only when its FDR-adjusted result is significant at the selected `--alpha` level. Otherwise it is recorded as `not_significant`.

Missing observations, metric-specific spatial islands and constant-value cases are represented explicitly and are never assigned a cluster class.

Defaults are:

- 999 conditional permutations per freguesia;
- seed 42;
- FDR threshold 0.05.

Local Moran's (I) identifies local spatial association under the selected weight matrix. HH/LL patterns are local clusters and HL/LH patterns are spatial outliers in the Moran-scatterplot sense; these are descriptive spatial statistics, not causal findings.
