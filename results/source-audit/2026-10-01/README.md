# Primary-source audit, 2026-10-01

This bundle records source coverage and validation, not definitive v1.1 findings.

| File | Contents |
| --- | --- |
| `audit.json` | Exact acquisition manifests, verified input hashes, code/dependency hashes, coverage summaries, and CSV output hashes |
| `housing_quarter_panel.csv` | 624 INE Total-dwelling observations: 24 Lisbon parishes × 26 quarters, 2019 Q4–2026 Q1 |
| `census_context.csv` | 24 parish aggregates from official Census 2021 subsection rows; 545,796 residents in total |
| `rnal_snapshot_by_parish.csv` | Aggregate counts of records returned on the capture date; no establishment-level rows |

RNAL returned 11,865 records, no populated cessation dates, and seven registration dates before 2000. Complete historical stock and closure coverage remain unestablished. The CSV counts describe the captured snapshot, not a validated longitudinal stock series.

See the [full audit](../../../docs/source-audit.md) for source interpretation, defects resolved, reproduction commands, and the remaining v1.1 requirements. The [fixed audit config](../../../configs/source_audit_2026-10-01.toml) selects exact locally retained inputs. A fresh download may differ; no public raw-data archive has been deposited yet. The original providers' terms continue to apply to their data.
