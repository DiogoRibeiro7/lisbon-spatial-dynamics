# Spatial analysis

Spatial analysis is a core part of the project rather than a visualisation step added at the end.

## Reference geography

The canonical project geography is the **24-freguesia map of the municipality of Lisboa**, acquired from DGT's official CAOP2025 parish layer.

CAOP exposes the INE-assigned `DTMNFR` unique freguesia identifier together with the parish name, municipality, NUTS fields and official geometry. The project requests the Lisbon subset directly from DGT as GeoJSON in EPSG:4326.

Acquire an immutable raw snapshot with:

```bash
poetry run fetch-caop-lisbon
```

The acquisition validates that:

- exactly 24 features are returned;
- every feature belongs to the municipality `Lisboa`;
- every `DTMNFR` value is unique;
- configured CAOP fields still exist in the upstream layer;
- each feature has polygon or multipolygon geometry;
- the upstream layer still advertises GeoJSON query support.

The snapshot stores the raw GeoJSON, ArcGIS layer metadata, and a provenance manifest with source URLs and checksums.

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

[
Delta x_{i,t} = x_{i,t} - x_{i,t-k}
]

and

[
r_{i,t} =
rac{x_{i,t} - x_{i,t-k}}
{x_{i,t-k}}.
]

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
