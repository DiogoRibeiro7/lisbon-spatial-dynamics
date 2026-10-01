# RNAL coverage investigation: 2026-10-01

The current RNAL snapshots do not support designation of a complete historical stock panel. Comparing two official feeds confirms the early registration dates, reveals conflicting parish assignments, and fails to reproduce a published historical total. The [aggregate evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/rnal-coverage/2026-10-01) records the comparison and exact input, code, configuration and output hashes. No establishment-level records are committed.

## Two official interfaces, one provider

The [TravelBI accommodation page](https://travelbi.turismodeportugal.pt/alojamento/alojamento-local-oferta/) links to the [RNAL open-data item](https://dadosabertos.turismodeportugal.pt/datasets/4e62eb1977564991bd01e61d7aa8266f_6/explore) and describes daily updates. Its [GIS layer](https://geo.turismodeportugal.pt/server/rest/services/TDP/OpenData_AL/MapServer/6) exposes separate registration and public-opening dates. The captured schema has no cessation/status field or historical time configuration. Agreement with the SOAP feed is a consistency check within the same provider, not independent validation of the registry.

| Check | Observed result |
| --- | --- |
| SOAP capture | 2026-10-01 10:38:59 UTC; 11,865 records |
| GIS capture | 2026-10-01 13:47:54–13:48:01 UTC; 11,870 records |
| Shared registry numbers | 11,865 |
| SOAP-only / GIS-only registry numbers | 0 / 5 |
| Registration-date disagreements among shared records | 0 |
| User-capacity disagreements among shared records | 0 |
| Parish-identifier disagreements among shared records | **172** |
| Parish names inconsistent with their own feed's parish identifier | 0 in either feed |
| SOAP populated cessation dates | 0 |

The five GIS-only records have registration years 2014, 2015, 2016, 2017 and 2018. The captures were not simultaneous; membership differences are not labelled as additions or closures. GIS acquisition verifies the complete object-ID roster before and after retrieval and rejects truncated or inconsistent batches. This detects membership changes during capture but cannot guarantee an atomic snapshot of all field values.

Both feeds cover all 24 canonical parishes. The 172 conflicting assignments affect about 1.45% of shared registrations. `parish_comparison.csv` separates missing registry numbers from shared records assigned to different parishes; disagreements are attributed to the SOAP parish. `audit.json` also contains counts for each conflicting parish pair. Neither name consistency nor feed agreement elsewhere establishes which assignment is correct. No geographic reassignment has been made.

## Early dates are present upstream

Both interfaces give the same registration date for all seven records before 2000: two in 1930, one in 1947, two in 1965, one in 1985 and one in 1992. The year-2000 threshold is a screening rule, not an assertion about the legal inception of RNAL. Four of these seven records also have public-opening dates before 2000. The separate opening field therefore provides no general correction rule. Original dates remain unchanged.

GIS dates are integer milliseconds from the Unix epoch and are interpreted in UTC. The captured metadata does not specify a date-field time reference; the audit reports this limitation. Exact agreement with the SOAP calendar dates supports this comparison, but does not explain the dates' administrative meaning.

## A historical benchmark the snapshot does not reproduce

The original municipal PDF returned HTTP 404 during this investigation. An [Arquivo.pt capture of the official December 2022 monitoring report](https://arquivo.pt/noFrame/replay/20260216185851id_/https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf) was recovered and retained locally. Printed page 38 (PDF page 50) reports **20,134 unweighted registrations at the end of November 2022**. Printed pages 39–40 report 2,468 new and 1,247 ceased registrations during the monitoring period since November 2019. Pages 2 and 87 describe monthly transfers of existing, new, changed, ceased and cancelled records between Turismo de Portugal and municipal monitoring.

| End-November 2022 comparison | Registrations |
| --- | ---: |
| Published municipal stock | 20,134 |
| Reconstructed among records retained in the 2026 SOAP snapshot | 11,525 |
| Snapshot cohort minus published stock | −8,609 |
| Snapshot cohort as a percentage of the published stock | 57.24% |

The reconstruction counts snapshot members registered by 2022-11-30 whose cessation date is empty or later than that date. The discrepancy is not a count of individually identified closures: revisions, definitions and record retention must be reconciled. The report's weighted counts and tables dated 1 November are not substituted for its end-November unweighted benchmark. Registered establishments also need not be operating businesses.

The PDF's SHA-256 is `1e446b0b71d55a3f0086b539278810f1875d5e4244174786295489b40fea8195`. The pinned configuration records its archive capture, retrieval manifest, page reference and benchmark definition.

## Reproduce or extend the investigation

Restore the exact ignored input files named in `configs/rnal_coverage_2026-10-01.toml`, including the SOAP/GIS acquisition manifests, reference CSV and archived report. The committed benchmark bundle was generated at [revision 9266cf5](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/commit/9266cf5266e21757f68c4dfb6720928d4da931d0) and remains unchanged. Use that revision for its recorded code provenance, or replay with the current writer, which produces identical aggregates and CSV hashes. From the repository root:

```bash
poetry sync --with docs
poetry run python scripts/audit_rnal_coverage.py audit --output data/processed/rnal-coverage-recheck
```

The output directory must be new. This command makes no network requests. It checks the pinned input hashes and sizes, then checks snapshot resources against their acquisition manifests before computing aggregates. The current writer prepares files in a temporary sibling directory and publishes them together only after every write succeeds. A failed write removes its temporary files and leaves the requested output path available for retry. Existing outputs are preserved. The CSV hashes should reproduce; JSON paths, code fingerprints and Python version reflect the chosen output directory and replay environment.

For a fresh GIS capture, choose a new directory under the ignored raw workspace:

```bash
poetry run python scripts/audit_rnal_coverage.py fetch --output data/raw/turismo_portugal/rnal_geodata/lisboa/<new-capture>
```

The request selects only `OBJECTID`, `NrRNAL`, `DataRegisto`, `DataAberturaPublico`, `DTMNFR`, `Freguesia`, `Concelho` and `NrUtentes`, with geometry disabled. Unexpected feature attributes are discarded before persistence. The manifest hashes every HTTP response; feature responses are not saved verbatim. Metadata and the analytical snapshot are retained. A new capture needs a new pinned audit configuration; it must not replace the original evidence.

**Archive status:** raw inputs remain in the ignored local workspace. Hashes do not make those files publicly available. GIS item licence information was empty and redistribution terms have not been verified; no raw-data release is implied by the software licence.

## Evidence needed for the definitive study

### Public historical source search

An additional [GIS item published by Lisboaenova](https://www.arcgis.com/sharing/rest/content/items/4216d9ecb47b4cfe9c91e648e725e6e9?f=json) attributes its data to DMU/Divisão de Monitorização and describes establishments at 3 September 2018. The inspected [layer](https://services-eu1.arcgis.com/Jy1PfwTjLp1CBgCI/arcgis/rest/services/Alojamento_Local/FeatureServer/0) contains 2,551 records, while its registration-date maximum is 20 May 2020 and its last data edit is in October 2020. It has no time-series configuration. The date discrepancy and unverified geographic completeness prevent using it as a historical municipal panel.

The [discovery record](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/results/rnal-coverage/2026-10-01/historical-source-discovery.json) preserves exact query URLs, response hashes, metadata and aggregate observations. Responses are retained in the ignored local workspace; no establishment rows were acquired. This search has not identified a public replacement for the historical monitoring extract. It does not establish that no such extract is published elsewhere.

### Required extract

The next source to pursue is the historical municipal monitoring extract documented in the report. No request has been sent to the provider. A usable extract or equivalent published aggregates should include:

- Quarterly or monthly snapshots covering the 2019 Q4–2025 Q4 analysis endpoints, with capture dates, scope and revision policy.
- Registry identifiers, effective registration/cessation/cancellation dates and definitions, plus the retention rules for cancelled or reinstated records. Proprietor/contact fields are unnecessary.
- Parish identifiers with their assignment method and boundary vintage, enough to reconcile the 172 observed conflicts against CAOP2025.
- Capacity histories or an explicit statement that only current capacity is available; current values must not silently become past capacity.
- Explanations of the seven early dates, original values and a documented correction policy.
- Reconciliation with the published 2022 total and permission/access conditions for durable archiving. Parish aggregates must distinguish raw establishments, weighted counts, registered capacity and actual operation.

Until then, snapshot-cohort outputs can describe surviving records only. A definitive historical stock study remains open; agreement between current feeds and successful software tests do not resolve the missing evidence.
