# Releases

## v1.0.1 — empirical data/results correction

Version 1.0.1 corrects the main omission in v1.0.0: the repository now contains small, inspectable empirical datasets and generated result tables.

Committed evidence lives under:

- `data/release/v1.0.1/`;
- `results/release/v1.0.1/`.

Large raw source snapshots remain outside Git. The accompanying documentation identifies each curated table's source and period, with limitations noted where applicable.

The empirical correction does not change the project's interpretation boundary: reported relationships are descriptive and do not establish causality.

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
