# Releases

## v1.1.0 — housing evidence and RNAL source audit

Released 2026-10-05. Version 1.1.0 adds dated, committed evidence bundles produced while auditing the primary sources for the definitive joint study:

- a [primary-source audit](source-audit.md) of all four source families, with a fixed 24-parish × 26-quarter housing request and support for the official Census XLSX archive;
- a housing component for 2019–2025: the [Q4 comparison](housing-history.md), [CPI context](housing-inflation.md), [dwelling categories](housing-categories.md), [sales volume](housing-sales.md), [municipal distribution](housing-distribution.md), [spatial patterns](housing-spatial.md) and [spatial sensitivity](housing-spatial-sensitivity.md);
- RNAL source evidence: the [coverage investigation](rnal-coverage.md), [coordinate follow-up](rnal-geography.md), [parish-label sensitivity](rnal-parish-sensitivity.md), [municipal benchmarks](cml-historical-benchmarks.md), [historical capacity](historical-capacity.md), [community archive](rnal-archive-coverage.md), [capture gaps](rnal-capture-gaps.md) and a [historical data request package](rnal-history-request.md).

Housing bundles reproduce offline from committed aggregate inputs with verified provenance. RNAL audits commit aggregates only; record-level snapshots stay outside Git. The release also fixes intermittent figure-writing failures on Windows desktops with Tk installed.

### Scope change

Version 1.1.0 was planned as the definitive joint housing/RNAL study run. The audit showed that the current RNAL feeds and the community archive cannot supply the required 2019–2025 parish history: the retained registry cohort reconstructs 11,525 registrations at end-November 2022 against the municipality's published 20,134. That run is now the v1.2.0 milestone, pending a historical series from CML or Turismo de Portugal; see the [roadmap](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/ROADMAP.md).

### Interpretation boundary

The housing evidence describes published sales statistics and does not estimate RNAL effects. No result in this release establishes causality.

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

The definitive joint study run (v1.2.0) and the mobility and accessibility extension (v1.3.0) are described in the [roadmap](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/ROADMAP.md). Infrastructure and additional longitudinal demographic dimensions are future extensions rather than unfinished v1 requirements.
