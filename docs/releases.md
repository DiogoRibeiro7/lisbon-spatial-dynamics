# Releases

## v1.0.0 — first stable research release

Version 1.0.0 packages the Lisbon Spatial Dynamics study pipeline. The GitHub release contains the source code, with no attached input snapshots or computed results. It should be distinguished from an archived empirical study bundle.

### Scope

The release includes:

- canonical Lisboa freguesia geography;
- INE housing-value trajectories;
- RNAL flows, stock, and capacity;
- Censos-2021 population normalization;
- demographic, tenure, vacancy, building-age, and repair context;
- normalized descriptive analysis;
- spatial autocorrelation diagnostics;
- pre-specified adjusted OLS models;
- influence and leave-one-freguesia-out sensitivity;
- publication-style final tables and figures;
- SHA-256 provenance manifest.

### Interpretation boundary

The release studies descriptive and adjusted associations. It does not claim causal identification.

### Reproduce

Use `poetry run build-study-v1` with the original archived study snapshots, reference geography, and model configuration. To create a new run from current sources, follow [Getting started](getting-started.md). New downloads are not guaranteed to reproduce an earlier result.

## Versioning

Stable releases use semantic versioning:

- **major** — incompatible data contracts or methodology/output interfaces;
- **minor** — backward-compatible analytical capabilities;
- **patch** — backward-compatible fixes, validation, or documentation.

Changes to source snapshots are tracked in provenance manifests even if package code remains unchanged.

## Future releases

Mobility, accessibility, infrastructure, and additional longitudinal demographic dimensions are future extensions rather than unfinished v1 requirements.
