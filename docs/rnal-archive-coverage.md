# Community RNAL archive: coverage and membership changes

A public community archive provides **13 dated exports from May 2025 to October 2026**. After explicit duplicate handling, its Lisbon subset falls from **18,958 to 11,856 registry numbers**. It adds evidence of earlier membership that the latest feed cannot recover, but also contains duplicate rows and records that disappear and reappear. It is a candidate for further historical validation, not the definitive 2019–2025 stock series.

The [aggregate evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/rnal-archive/2026-10-03) contains snapshot totals, consecutive membership comparisons, 312 parish observations and full acquisition/audit provenance. No establishment-level data are committed.

## Source and observation dates

The source is [sztanko/al-pulse at revision 50322b0](https://github.com/sztanko/al-pulse/tree/50322b0ae5680d24013fae4ee19d757350a8ba2c/downloads/al). Its [README](https://github.com/sztanko/al-pulse/blob/50322b0ae5680d24013fae4ee19d757350a8ba2c/README.md) and [collector](https://github.com/sztanko/al-pulse/blob/50322b0ae5680d24013fae4ee19d757350a8ba2c/scripts/fetch_al_list.py) attribute the exports to the official [RNAL search interface](https://rnt.turismodeportugal.pt/RNT/Pesquisa_AL.aspx). These are community-maintained copies, not institutionally certified historical extracts. Their identity in the pinned Git revision is verified; source completeness and collection timestamps are not independently established.

The collector at that revision starts its registration-date requests at **2007-01-01**, queries successive registration months, and assigns one timestamp at the start of the run. Its naive local timestamp has no stated timezone. This audit preserves the timestamp from each filename and checks it against every CSV row, without asserting UTC or an atomic point-in-time snapshot. Inspection of the current collector does not prove which code or arguments generated each historical file.

All 13 assessed files contain records assigned to the 24 canonical parishes. Names are matched using Unicode normalization, case folding and whitespace normalization; no coordinate reassignment occurs.

| Publisher timestamp date | Lisbon source rows | Repeated rows collapsed | Unique Lisbon registry numbers | Reported user capacity |
| --- | ---: | ---: | ---: | ---: |
| 2025-05-25 | 18,958 | 0 | 18,958 | 109,973 |
| 2025-06-07 | 18,948 | 0 | 18,948 | 109,992 |
| 2025-07-03 | 18,755 | 0 | 18,755 | 108,965 |
| 2025-08-04 | 18,583 | 0 | 18,583 | 107,805 |
| 2025-09-01 | 18,579 | 0 | 18,579 | 107,801 |
| 2025-10-01 | 18,539 | **329** | 18,210 | 105,796 |
| 2025-11-08 | 18,549 | 0 | 18,549 | 107,674 |
| 2025-12-11 | 18,528 | 0 | 18,528 | 107,590 |
| 2026-01-03 | 17,916 | 0 | 17,916 | 103,976 |
| 2026-02-01 | 11,743 | **10** | 11,733 | 68,803 |
| 2026-03-07 | 11,775 | 0 | 11,775 | 69,005 |
| 2026-09-16 | 11,853 | 0 | 11,853 | 69,590 |
| 2026-10-02 | 11,856 | 0 | 11,856 | 69,600 |

These dates label irregular captures, not month-end or quarter-end observations. The **193-day gap** from March to September 2026 is retained. There are no observations before May 2025 in this assessed file set. No quarter-end values are interpolated or carried forward. The archive cannot replace the [November 2019/2022 municipal benchmarks](cml-historical-benchmarks.md).

Capacity is the sum of the retained exports' `Nº Utentes` field after duplicate handling. Every assessed Lisbon row has a populated value. One record has zero capacity in each capture through January 2026; zero is preserved as reported. These are registered capacities, not occupied places or verified operation. Capacity totals reflect both membership and recorded-capacity changes.

The CSVs retain their original column names and hashes. Their capacity fields have the following definitions, also supplied in the [machine-readable column dictionary](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/results/rnal-archive/column_definitions.json):

| Column | Quantity | Unit |
| --- | --- | --- |
| `users_known` | Sum of declared capacity over unique registry numbers in the capture/geography; missing values excluded, zero included | Reported accommodation places |
| `users_missing_records` | Unique registry numbers whose declared capacity is missing; zero is not missing | Registry records |
| `users_zero_records` | Unique registry numbers whose declared capacity is exactly zero; missing values excluded; municipality summary only | Registry records |

These fields do not count people or user accounts. Current replay reports embed this dictionary under `column_definitions` in `audit.json`. The original dated audit predates that metadata field and remains unchanged; the companion dictionary documents its CSVs without rewriting the evidence bundle.

## Duplicates and reappearances matter

The October 2025 export contains **329 repeated Lisbon rows**, and February 2026 contains **10**. Repeated normalized registry numbers agree on all retained analytical fields: registration date, parish and capacity. They are counted once, with the repeated-row counts reported separately. This does not assert that discarded contact or proprietor fields are identical. Conflicting analytical duplicates cause acquisition to fail; none were found in these files.

Between September and October 2025, 369 registry numbers are absent from the later export. Between October and November, **349 previously seen numbers reappear**. Across the series there are **418 reappearance observations**, summed across consecutive comparisons; this is not asserted to be 418 distinct establishments. An export absence is therefore insufficient evidence of a permanent closure. Reinstatement, source revisions and acquisition omissions cannot be distinguished with these files.

The largest consecutive difference is **6,183 earlier-only numbers** between the January and February 2026 captures, with no later-only numbers in that comparison. This is a difference in archived membership. It does not identify legal cancellation dates, business closures, or the cause of the change, and it does not reconcile the earlier 8,609-record discrepancy against the municipal 2022 benchmark.

The first and last captures share **11,740 registry numbers**. There are **7,218 first-only** and **116 last-only** numbers, giving a net change of **−7,102**. Among shared numbers, registration dates and parish labels agree; **103 capacity values differ**. Current capacity therefore must not silently be assigned to earlier observations. No registration-date or parish-label changes occur among shared numbers in the consecutive comparisons either; agreement does not independently verify those fields.

## Comparison with the official SOAP capture

The [official snapshot acquired on 2026-10-01](rnal-coverage.md) contains 11,865 records. All **11,856** registry numbers in the community export labelled 2026-10-02 are present in SOAP. There are no archive-only numbers; SOAP has **nine additional numbers**, registered in 1930 (two), 1947 (one), 1965 (two), 1985 (one), 1992 (one) and 2003 (two).

All nine precede the collector's documented 2007 start date, which is consistent with a date-filter exclusion. The comparison does not establish each historical run's exact filters. Shared records have identical registration dates and parish labels, and **one capacity disagreement**. The captures are not simultaneous, so this difference is not labelled an error. Agreement with SOAP also does not resolve the already documented SOAP/GIS parish conflicts.

## Reproduce the assessment

The configuration pins the community Git revision, all 13 export blob identities and compressed sizes, the acquisition manifest, canonical parish reference, and the SOAP snapshot and manifest. Original national CSVs may contain proprietor, tax, address and contact information. Acquisition processes them in memory and writes only Lisbon registry numbers, registration dates, parish IDs and user capacity, plus aggregate source metadata. Publisher documentation is retained separately for provenance and never executed.

Restore the exact ignored files named in `configs/rnal_archive_2026-10-03.toml`, including the minimized JSONs and publisher documents identified by its acquisition manifest. Then run from the repository root:

```bash
poetry sync --with docs
poetry run python scripts/audit_rnal_archive.py audit --output data/processed/rnal-archive-recheck
```

Replay is offline. It checks hashes and sizes, manifest/resource identities, the complete expected file set, canonical parishes and analytical field validity. The minimized JSON parser rejects malformed document/record shapes and invalid field types with `ValueError`, including non-string dates/parish identifiers and non-integer row counts. Analytical inputs are parsed from the exact bytes verified; publisher documents are checked for identity only. The three CSVs and `audit.json` are published together after successful preparation. Existing outputs are preserved; failures leave no partially published bundle. CSV hashes and numerical findings reproduce; output paths and code/software provenance reflect the replay environment.

To acquire the same pinned public exports again into a new ignored directory:

```bash
poetry run python scripts/audit_rnal_archive.py fetch --output data/raw/community/rnal_al_pulse/recheck
```

Each download must match the Git blob identity and size in the configuration. Its SHA-256 and the minimized file's SHA-256 are recorded in the new manifest. A fresh acquisition has new retrieval timestamps and therefore a different manifest hash: use a separate configuration copy pointing to and pinning that manifest for replay. Do not overwrite the original capture or its pinned configuration.

`snapshot_summary.csv` records source rows, duplicate counts, unique counts, date ranges, capacity and missingness. `snapshot_changes.csv` records shared/earlier-only/later-only numbers and field changes for consecutive captures. `parish_snapshots.csv` contains counts and capacity for each capture/parish. Acquisition and audit hashes are in `audit.json`. National row counts describe downloaded CSV rows, not independently validated national totals.

The original exports remain available at the pinned third-party Git URLs as of acquisition. This is not a project-controlled durable archive, and redistribution terms have not been established. Minimized establishment files remain local and ignored; only aggregate findings and provenance are committed.

## Decision for the definitive study

This archive is useful diagnostic evidence and supplies earlier registry membership, with explicit quality limitations. It remains **outside the canonical study inputs**: the assessed set lacks 2019–2024 captures and exact quarter-end observations, has a long 2026 gap, excludes records consistent with a date filter, and contains duplicates and unexplained reappearances. The next source requirement is still a documented historical extract or consistently defined parish aggregates, with status/date semantics, capacity histories and durable access conditions. No provider request has been sent.
