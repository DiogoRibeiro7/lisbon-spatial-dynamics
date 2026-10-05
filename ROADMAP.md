# Roadmap

Lisbon Spatial Dynamics is now past the initial repository-building phase.

Version **v1.0.1** established the first stable research-software release with committed empirical evidence and generated findings. Version **v1.1.0** adds an independently reproducible housing component and a documented audit of the RNAL sources. Development should continue to be driven by substantive research milestones rather than incremental repository polish.

## Current status

**Current stable release:** `v1.1.0`

The v1.1.x line contains:

- the reusable acquisition and transformation pipeline;
- canonical Lisbon freguesia geography;
- housing, RNAL, Census, and spatial-analysis components;
- pre-specified multivariable modelling;
- reproducibility and provenance contracts;
- committed empirical evidence and descriptive findings;
- a primary-source audit and dated, offline-reproducible housing and RNAL evidence bundles.

Further `v1.1.x` releases should be limited to:

- genuine software defects;
- incorrect empirical values;
- provenance or attribution corrections;
- documentation errors that materially affect interpretation or reproducibility;
- security or dependency fixes.

New research capabilities belong in later minor or major releases.

---

## v1.1.0 — housing evidence and RNAL source audit

**Released 2026-10-05.** Originally, v1.1.0 was to be the definitive joint study run. The source audit showed that the available RNAL feeds cannot supply the required historical series, so that run moved to [v1.2.0](#v120--definitive-primary-source-joint-study-run). Version 1.1.0 releases the evidence produced while establishing why.

Each bundle below is dated, committed under `results/` with its inputs under `data/reference/` or `data/benchmarks/`, and reproducible offline with hash-verified provenance. None of them is the canonical joint housing/RNAL run.

### Primary-source audit

The [primary-source audit](docs/source-audit.md) (2026-10-01) captured all four source families, fixed the longitudinal housing request to 24 parishes × 26 quarters for 2019 Q4–2026 Q1, and added support for the official Census XLSX archive. The snapshots are retained locally with hashes; no public source archive has been designated.

### Housing component

| Bundle | Evidence |
| --- | --- |
| [Q4 comparison](docs/housing-history.md), 2026-10-04 | 168 observations for 2019–2025. All 24 parishes have higher endpoint values; the median parish increase is 47.52%. |
| [Spatial patterns](docs/housing-spatial.md), 2026-10-04 | 54-pair queen graph from an archived CAOP2025 Lisbon subset. Positive global association (Moran's I 0.3421; permutation p 0.0029); no FDR-significant local clusters. |
| [Spatial sensitivity](docs/housing-spatial-sensitivity.md), 2026-10-04 | Positive global association for percentage, log and absolute changes after Holm correction. Queen and rook give identical graphs; Santa Maria Maior materially influences the magnitude. |
| [CPI context](docs/housing-inflation.md), 2026-10-04 | The median endpoint change is 23.59% after national CPI adjustment; two parishes fall below baseline. |
| [Dwelling categories](docs/housing-categories.md), 2026-10-05 | 504 Total/New/Existing observations with 69 unpublished values retained. Existing median change 47.64%; New has only 14 complete endpoint pairs. |
| [Sales volume](docs/housing-sales.md), 2026-10-05 | 175 INE counts reconciling exactly to Lisbon totals. Sales fall 4.96% between 2019 and 2025; 17 parishes record fewer sales alongside higher nominal medians. |
| [Municipal distribution](docs/housing-distribution.md), 2026-10-05 | 21 published quartiles. The municipal median rises 48.36%; the interquartile range widens in €/m² but narrows relative to the median. |

### RNAL source evidence

| Bundle | Evidence |
| --- | --- |
| [Coverage investigation](docs/rnal-coverage.md), 2026-10-01 | Seven early registration dates confirmed in both official interfaces; 172 conflicting parish assignments. The retained SOAP cohort reconstructs 11,525 registrations at end-November 2022 versus the municipal report's 20,134. |
| [Coordinate follow-up](docs/rnal-geography.md), 2026-10-01 | All 172 disputed points fall inside their GIS-labelled CAOP2025 parish; 67 are within 25 metres of a boundary. No automatic corrections follow. |
| [Parish-label sensitivity](docs/rnal-parish-sensitivity.md), 2026-10-02 | Both GIS scenarios preserve municipality totals and the top four record-pressure ranks; six parishes move one position. Local count/capacity effects can change direction. |
| [Municipal benchmarks](docs/cml-historical-benchmarks.md), 2026-10-03 | 96 parish values from the November 2019/2022 weighted-AL and capacity tables. Capacity reconciles exactly; weighted values retain displayed-arithmetic discrepancies. |
| [Community archive](docs/rnal-archive-coverage.md), 2026-10-03 | 13 captures from May 2025 to October 2026. Missing earlier years, observation gaps and unverified status semantics prevent promotion to a study input. |
| [Capture gaps](docs/rnal-capture-gaps.md), 2026-10-03 | Two entirely empty registration-month groups (May 2018, September 2014) isolate 383 missing records in the October 2025 and February 2026 exports. Nothing is imputed. |
| [Historical capacity](docs/historical-capacity.md), 2026-10-05 | November 2019/2022 capacity per 1,000 fixed Census 2021 residents. The four largest-capacity parishes' share falls from 64.30% to 61.32%; they lose 417 places while the other 20 gain 5,143. |
| [Provider request package](docs/rnal-history-request.md), 2026-10-04 | Portuguese drafts for CML and Turismo de Portugal, a technical annex and 600 requested parish-quarter keys for 2019 Q4–2025 Q4. Not yet sent. |

---

## v1.2.0 — definitive primary-source joint study run

**Status: next, blocked on a historical RNAL series.** The current official feeds retain survivors rather than history, and the community archive starts in 2025. Neither can supply the 2019–2025 parish stock the joint study needs. The next action is to send the [provider request package](docs/rnal-history-request.md); its assessment table defines how a return would be validated. An accepted series also needs a reviewed importer, because `build-study-v1` consumes registry records and has no historical-aggregate adapter.

### Goal

Produce one canonical Lisbon study run generated end-to-end from a fixed set of archived primary-source snapshots.

The objective is to move from a repository that can run the study to a release that contains a **fully traceable empirical study instance**.

### Scope

#### Archive definitive study inputs

Preserve one exact set of source snapshots:

- INE housing indicator `0012234`;
- a validated historical RNAL Lisboa series, after the existing privacy-minimisation step;
- INE Censos 2021 synthesis archive;
- DGT CAOP reference geography;
- versioned multivariable model configuration.

The original files must be retained outside normal Git history when size, licensing, or redistribution constraints make direct versioning inappropriate.

#### Run the complete study pipeline

Use the existing:

```bash
poetry run build-study-v1
```

workflow to generate the study from those archived inputs.

The run must use documented parameters for:

- freguesia count;
- permutation count;
- random seed;
- Local Moran FDR threshold;
- model configuration.

#### Preserve provenance

The release must include a complete `study_manifest.json` recording:

- source-file hashes;
- generated-file hashes;
- software version;
- analysis parameters;
- study interpretation contract.

Where raw snapshots cannot be committed, release documentation must state how they are archived and how their hashes map to the manifest.

#### Commit compact research outputs

Commit small, reusable analysis-ready artifacts where redistribution is appropriate, including the definitive:

- annual housing/RNAL pressure panel;
- Census context table;
- common-window trajectory table;
- model input table;
- final result tables;
- machine-readable findings.

Large raw or intermediate files should remain outside Git.

#### Publish final figures and findings

The release should contain the actual generated:

- housing/RNAL association figure;
- housing-change map;
- RNAL-pressure map;
- Local Moran/LISA maps;
- coefficient comparison figure;
- primary residual diagnostic;
- final descriptive table;
- spatial-results table;
- model-results table;
- diagnostics table.

The documentation results page should report values directly from this canonical run rather than from separately curated evidence tables.

### Definition of done

`v1.2.0` is complete when:

- a historical RNAL series has been obtained, validated against the municipal benchmarks, and ingested through a reviewed importer;
- one archived input set is designated as the canonical study input;
- `build-study-v1` completes from those inputs;
- the manifest verifies every input and output;
- all final tables and figures come from that single run;
- compact analysis-ready datasets are committed where appropriate;
- large source assets are archived or attached separately with documented hashes;
- documentation reports the canonical run's actual results;
- the release can be independently reconstructed by someone with the archived inputs.

---

## v1.3.0 — mobility and accessibility extension

### Goal

Add a second substantive urban-change dimension beyond housing, local accommodation, and static Census context.

The preferred extension is **mobility and accessibility**.

### Research questions

Potential questions include:

- Do freguesias with larger housing-value changes also show changes in accessibility?
- Is local-accommodation pressure associated with changes in public-transport access or mobility intensity?
- Are housing/RNAL trajectories spatially concentrated around highly accessible areas?

### Candidate dimensions

Subject to data availability and licensing:

- public-transport accessibility;
- walking or cycling infrastructure;
- active-mobility indicators;
- transport-stop density;
- travel-time accessibility;
- road-network or pedestrian-network measures;
- other reproducible public mobility datasets.

Strava or other proprietary datasets should only be included if access, reproducibility, and redistribution conditions are clear.

### Methodological requirements

The extension should:

- preserve the canonical freguesia geography;
- use explicit temporal alignment;
- document coverage and missingness;
- avoid combining incompatible periods into a single headline metric;
- keep new variables interpretable rather than constructing opaque composite scores;
- extend spatial diagnostics before introducing more complex models.

### Definition of done

`v1.3.0` is complete when at least one defensible mobility/accessibility dimension is integrated into the canonical panel and produces reproducible descriptive and spatial results.

---

## v2.0.0 — broader longitudinal urban-change study

### Goal

Evolve the project from a focused housing/local-accommodation study into a broader longitudinal analysis of Lisbon neighbourhood change.

### Possible dimensions

Future major-version work may include:

- time-varying demographic structure;
- accessibility and mobility;
- urban infrastructure;
- land-use change;
- housing transaction activity;
- tourism intensity beyond RNAL;
- neighbourhood-level economic indicators;
- additional built-environment measures.

### Modelling direction

A v2 study may introduce longitudinal and spatial models beyond the current cross-sectional trajectory analysis, for example:

- panel regression;
- freguesia and time fixed effects;
- spatial error or spatial lag diagnostics where justified;
- hierarchical models;
- uncertainty-aware temporal models;
- explicit causal designs only when identification assumptions can be defended.

The project should continue to prefer mathematically transparent, interpretable methods over unnecessary machine learning.

### Definition of done

`v2.0.0` requires a materially broader research question, a revised data contract, and a coherent longitudinal analytical design. It should not be used simply as a version label for incremental features.

---

## Deferred or excluded work

### Fine-grained crime analysis

Neighbourhood-level crime was considered earlier but suitable consistent Lisbon data at the required spatial and temporal granularity were not available.

Crime should remain outside the active roadmap unless a reliable public dataset becomes available with:

- reproducible access;
- sufficiently fine geography;
- longitudinal coverage;
- clear definitions across time.

### Machine learning for its own sake

The project should not add predictive ML merely to increase technical complexity.

Any future model should be motivated by the research question and compared against simpler statistical alternatives.

### Repository cosmetics

Documentation, CI, packaging, badges, templates, and automation are now mature enough for the current research scope.

Further repository-polish work should be secondary to empirical research unless it fixes a concrete usability or reproducibility problem.

---

## Release sequence

| Release | Primary objective | Status |
| --- | --- | --- |
| `v1.0.1` | Stable pipeline + committed empirical correction | Released |
| `v1.1.0` | Housing evidence and RNAL source audit | Released |
| `v1.2.0` | Definitive primary-source joint study run | Next; blocked on historical RNAL data |
| `v1.3.0` | Mobility/accessibility extension | Planned |
| `v2.0.0` | Broader longitudinal urban-change study | Future |

## Guiding principle

The repository now has enough infrastructure.

The next releases should primarily add **better evidence, better data, and stronger analysis**, not more scaffolding.
