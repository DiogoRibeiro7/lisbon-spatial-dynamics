# Changelog

All notable repository-level changes are documented here.

## [Unreleased]

### Added

- A fixed-cohort RNAL parish-label sensitivity comparison, with three scenarios, count/capacity/pressure/rank changes, a generated figure, and an offline aggregate evidence bundle.
- A coordinate-based investigation of all 172 RNAL parish conflicts against CAOP2025, with metre-based boundary sensitivity, minimized acquisition, and aggregate provenance.
- A provenance record for the historical GIS source search, documenting why the inspected Lisboaenova layer is not accepted as a municipal time series.
- An RNAL cross-feed coverage investigation: reproducible GIS acquisition, offline comparisons, a historical municipal benchmark, and aggregate evidence for parish/date discrepancies.
- A primary-source coverage audit with retained acquisition provenance and compact housing, Census, and RNAL snapshot summaries for 2026-10-01.
- An explicit 24-parish, 26-quarter INE housing request for the 2019 Q4–2026 Q1 study window.
- Code-quality CI, offline tests on Linux and Windows, and an installed-wheel smoke check.
- A committed Poetry lockfile, standard package metadata, and dependency stubs for strict typing.
- A complete installation and data-acquisition walkthrough, contribution guide, and issue/PR templates.
- Full-study integration and failure-cleanup tests using synthetic source snapshots.

### Fixed

- RNAL geography audits now parse the exact verified input bytes and reuse the parsed SOAP cohort, preventing file changes during a run from separating reported hashes from analysed values. Default coordinate reports no longer duplicate their summary; replay tests require each mode's complete artifact set.
- RNAL coordinate audits now identify unknown SOAP/GIS parish codes before classifying any points, and coordinate acquisition reuses the GIS HTTP helper.
- Historical-source discovery now distinguishes epoch zero and non-null field counts from verified valid registration dates.
- Failed RNAL coverage audit writes no longer leave partial output directories that block retries.
- Source-catalogue claims that the current RNAL SOAP feed establishes a longitudinal source merely by exposing date fields.
- Audit acceptance of truncated housing windows and missing automated comparison with the published Census municipality total.
- Lazy Census workbook errors now use the public population/context exception types; numeric identifier cells fail explicitly without guessing leading zeros.
- Audit line-ending attributes now apply only to CSV/JSON files, preserving binary handling for figures and archives.
- Official Census XLSX ingestion, excluding mixed geographic totals and preserving alphanumeric parish identifiers; regression tests cover double-counting and identifier failures.
- Study instructions that used a latest-quarter-only housing download for longitudinal analysis.
- RNAL documentation that treated a schema field as evidence of complete cessation history.
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

## [1.0.1] - 2026-10-01

Post-release empirical data/results correction.

### Added

- Committed 24-freguesia housing sale-value table for Q1 2019 and Q1 2026.
- Committed published RNAL weighted-establishment counts for November 2019 and November 2022.
- Committed published RNAL capacity by freguesia for November 2019 and November 2022.
- Committed 2011→2021 population change and 2021 AL/AFC pressure ratio.
- Committed published June-2018 housing/local-accommodation cross-section.
- Source/provenance notes for every committed release table.
- Empirical summary metrics, association results, and machine/human-readable findings.

### Corrected

Version 1.0.0 contained the research pipeline and release machinery but no committed empirical datasets or generated study results. Version 1.0.1 corrects that release gap while keeping large raw snapshots outside Git.

### Interpretation

The committed results are descriptive evidence and do not identify causal effects.

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
