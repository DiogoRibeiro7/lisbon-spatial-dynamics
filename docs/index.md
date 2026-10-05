<div class="lisbon-hero" markdown="1">

# Lisbon Spatial Dynamics

A reproducible spatial study of how housing values and local-accommodation pressure changed across Lisbon's 24 canonical freguesias.

[Reproduce v1](getting-started.md){ .md-button .md-button--primary }
[Understand the outputs](results.md){ .md-button }

</div>

## Version 1.1.0

Version 1.1.0 adds a [primary-source audit](source-audit.md), an independently reproducible housing component for 2019–2025, and a documented investigation of the RNAL sources, each as a dated evidence bundle; see [Releases](releases.md). The definitive joint housing/RNAL study run is the [v1.2.0 milestone](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/ROADMAP.md) and awaits a historical RNAL series.

The small empirical evidence layer added in version 1.0.1 under `data/release/v1.0.1/` and `results/release/v1.0.1/` is unchanged. Large raw source snapshots are still not committed, so reproducing a full pipeline run requires its archived inputs and model configuration.

It combines official housing, RNAL, Census, and CAOP sources to build a common neighbourhood-level research panel, then applies descriptive, spatial, and pre-specified multivariable analyses.

## Research question

The core question is whether freguesias with larger increases in population-normalized local-accommodation pressure also show larger cumulative housing-value changes, before and after adjustment for a compact set of Censos-2021 neighbourhood characteristics.

The analysis is descriptive and adjusted, not causal.

## What v1 contains

- canonical 24-freguesia geometry;
- longitudinal housing and RNAL panels;
- population-normalized RNAL pressure;
- Census demographic/tenure/built-environment context;
- Pearson/Spearman association analysis;
- Global and FDR-controlled Local Moran diagnostics;
- four pre-specified OLS specifications;
- HC3 robust uncertainty;
- VIF, condition-number, Breusch-Pagan, influence, and residual-Moran diagnostics;
- leave-one-freguesia-out sensitivity;
- final result tables, figures, and machine-readable findings.

## Future extensions

Mobility, accessibility, infrastructure, and additional time-varying demographic covariates are intentionally deferred beyond v1.
