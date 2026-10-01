# Changelog

All notable repository-level changes are documented here.

## [Unreleased]

### Added

- Code-quality CI, offline tests on Linux and Windows, and an installed-wheel smoke check.
- A committed Poetry lockfile, standard package metadata, and dependency stubs for strict typing.
- A complete installation and data-acquisition walkthrough, contribution guide, and issue/PR templates.
- Full-study integration and failure-cleanup tests using synthetic source snapshots.

### Fixed

- Census context module initialization that prevented CLI imports and test collection.
- Missing validation arguments in CAOP configuration loading.
- Census GeoJSON metrics serialized as strings, and numeric context rejected when only CSV formatting differed.
- Study parish-count overrides not reaching the multivariable stage.
- Existing lint, formatting, and strict typing failures.
- Raise the pytest minimum to 9.0.3 to exclude versions affected by the reported temporary-directory vulnerability.
- Documentation that implied a published empirical results bundle was available with the software release.

### Changed

- Documentation builds use locked dependencies and grant deployment permissions only to the deployment job.
- Pre-commit hooks use the project's locked linting and typing tools.

## [1.0.0] - 2026-09-30

First stable research release.

### Added

- canonical 24-freguesia Lisboa reference geography;
- reproducible INE housing acquisition/transformation contracts;
- longitudinal housing change panel;
- privacy-minimized RNAL acquisition and stock reconstruction;
- RNAL registrations, cessations, active stock, beds, and users;
- Censos 2021 population reference;
- RNAL pressure metrics per 1,000 residents;
- annual Q4 comparison panels;
- common-window freguesia trajectories;
- annual housing + RNAL pressure research panel;
- Censos 2021 demographic, tenure, vacancy, building-age, and repair context;
- descriptive Pearson/Spearman analyses;
- map-ready GeoJSON and choropleths;
- Global Moran's I;
- FDR-controlled Local Moran/LISA analysis and cluster maps;
- pre-specified multivariable OLS models;
- HC3 robust uncertainty;
- VIF, condition-number, Breusch-Pagan, leverage, Cook's distance, and residual Moran diagnostics;
- leave-one-freguesia-out sensitivity analysis;
- normalized analysis bundle;
- final publication-style tables, figures, and generated findings;
- end-to-end `build-study-v1` release command;
- SHA-256 input/output provenance manifest;
- stable citation metadata.

### Methodological scope

Version 1.0.0 reports descriptive and adjusted associations.

It does not claim causal identification of the effect of local accommodation on housing prices.

### Deferred beyond v1

- mobility;
- accessibility;
- urban infrastructure;
- additional longitudinal demographic sources;
- alternative causal-identification designs.
