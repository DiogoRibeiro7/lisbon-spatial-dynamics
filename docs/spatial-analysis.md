# Spatial analysis

Spatial analysis is a core part of the project rather than a visualisation step added at the end.

## Reference geography

Every spatial dataset should be normalised to a documented coordinate reference system and linked to a stable geographic identifier.

The project should retain both:

- the original source geography;
- the analysis geography used after harmonisation.

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
