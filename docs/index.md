<div class="lisbon-hero" markdown="1">

# Lisbon Spatial Dynamics

A reproducible spatial study of how housing values and local-accommodation pressure changed across Lisbon's 24 canonical freguesias.

[Reproduce v1](getting-started.md){ .md-button .md-button--primary }
[Understand the outputs](results.md){ .md-button }

</div>

## Version 1.0.0

Version 1.0.0 provides the study software and acquisition commands. The GitHub release has no attached source snapshots or computed results; reproducing a particular empirical run requires its archived inputs and model configuration.

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
