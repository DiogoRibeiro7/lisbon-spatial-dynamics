# Roadmap

Lisbon Spatial Dynamics is now past the initial repository-building phase.

Version **v1.0.1** established the first stable research-software release with committed empirical evidence and generated findings. From this point onward, development should be driven by substantive research milestones rather than incremental repository polish.

## Current status

**Current stable release:** `v1.0.1`

The v1.0.x line contains:

- the reusable acquisition and transformation pipeline;
- canonical Lisbon freguesia geography;
- housing, RNAL, Census, and spatial-analysis components;
- pre-specified multivariable modelling;
- reproducibility and provenance contracts;
- committed empirical evidence and descriptive findings.

The `v1.0.x` line is now considered **frozen for feature development**.

Further `v1.0.x` releases should be limited to:

- genuine software defects;
- incorrect empirical values;
- provenance or attribution corrections;
- documentation errors that materially affect interpretation or reproducibility;
- security or dependency fixes.

New research capabilities belong in later minor or major releases.

---

## v1.1.0 — definitive primary-source empirical run

**Progress, 2026-10-01:** the [primary-source audit](docs/source-audit.md) captured all four source families, fixed the longitudinal housing request, and added support for the official Census XLSX archive. RNAL historical completeness and early registration dates remain unresolved. The snapshots are retained locally with hashes; no public source archive or definitive study run has been designated.

The subsequent [RNAL coverage investigation](docs/rnal-coverage.md) confirms the seven early dates in both official interfaces, identifies 172 conflicting parish assignments, and finds that the retained SOAP cohort reconstructs 11,525 registrations at end-November 2022 versus the municipal report's 20,134. The report documents a monthly historical data exchange between Turismo de Portugal and CML. The next evidence requirement is that historical extract (or reconciled parish aggregates), plus documented parish/date semantics; the live GIS feed does not resolve the historical gap.

The [coordinate follow-up](docs/rnal-geography.md) locates all 172 disputed points inside their GIS-labelled CAOP2025 parish. Of those, 67 are within 25 metres of a boundary. This supports spatial consistency of the GIS labels while retaining positional uncertainty; no automatic corrections or historical-stock claims follow from it.

**Progress, 2026-10-02:** the [parish-label sensitivity analysis](docs/rnal-parish-sensitivity.md) compares the original SOAP labels with all GIS conflicts and the 105 conflicts supported more than 25 metres from a boundary. Both scenarios preserve municipality totals and the top four record-pressure ranks, with six parishes moving one position. Local count/capacity effects can change direction. The comparison informs geographic harmonisation but leaves historical completeness, verified assignments and durable archiving open.

**Progress, 2026-10-03:** the [historical municipal benchmarks](docs/cml-historical-benchmarks.md) preserve 96 parish-level values from the report's November 2019/2022 weighted-AL and capacity tables. The capacity table reconciles exactly; weighted values retain explicit displayed-arithmetic discrepancies. These benchmarks support validation of a future extract but do not replace the required quarterly, consistently defined series.

### Goal

Produce one canonical Lisbon study run generated end-to-end from a fixed set of archived primary-source snapshots.

The [community archive assessment](docs/rnal-archive-coverage.md), completed on 2026-10-03, adds 13 RNAL captures from May 2025 to October 2026. Explicit duplicate and reappearance diagnostics make these useful evidence of changing archive membership, but the missing earlier years, observation gaps and unverified status semantics prevent their promotion to the definitive quarterly input set.

The [registration-month follow-up](docs/rnal-capture-gaps.md) narrows two capture-quality flags to entirely empty May-2018 and September-2014 groups. Their 383 matched missing records require targeted validation of the October 2025 and February 2026 exports; no totals are repaired or interpreted as dated closures.

**Next evidence step, prepared 2026-10-04:** the [provider request package](docs/rnal-history-request.md) specifies 25 quarter ends across 24 parishes (600 requested observations), with Portuguese drafts, public routing contacts, a technical annex and criteria for assessing a return. Neither request has been sent. An accepted historical series will need a reviewed importer and explicit alignment of the study window before it can enter the definitive run; the existing registry-record command does not ingest aggregate histories.

The objective is to move from a repository that can run the study to a release that contains a **fully traceable empirical study instance**.

### Scope

#### Archive definitive study inputs

Preserve one exact set of source snapshots:

- INE housing indicator `0012234`;
- Turismo de Portugal RNAL Lisboa records after the existing privacy-minimisation step;
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

`v1.1.0` is complete when:

- one archived input set is designated as the canonical study input;
- `build-study-v1` completes from those inputs;
- the manifest verifies every input and output;
- all final tables and figures come from that single run;
- compact analysis-ready datasets are committed where appropriate;
- large source assets are archived or attached separately with documented hashes;
- documentation reports the canonical run's actual results;
- the release can be independently reconstructed by someone with the archived inputs.

---

## v1.2.0 — mobility and accessibility extension

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

`v1.2.0` is complete when at least one defensible mobility/accessibility dimension is integrated into the canonical panel and produces reproducible descriptive and spatial results.

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
| `v1.1.0` | Definitive primary-source empirical study run | Next |
| `v1.2.0` | Mobility/accessibility extension | Planned |
| `v2.0.0` | Broader longitudinal urban-change study | Future |

## Guiding principle

The repository now has enough infrastructure.

The next releases should primarily add **better evidence, better data, and stronger analysis**, not more scaffolding.
