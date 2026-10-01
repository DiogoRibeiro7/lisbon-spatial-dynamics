# Primary-source audit: 2026-10-01

The four official source families were acquired and checked against Lisbon's 24-parish geography. Housing and Census inputs now transform successfully. **This is a source audit, not a definitive v1.1 study:** the RNAL snapshot does not establish complete historical accommodation stock or closure coverage.

The [committed audit bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/source-audit/2026-10-01) contains `audit.json`, the 624-row housing panel, the 24-row Census context table, and a 24-row RNAL snapshot summary. The JSON records the exact input hashes, acquisition manifests, source URLs, fetch timestamps, code/dependency hashes, and CSV output hashes. It contains no establishment-level records.

## Coverage actually observed

| Source | Capture time (UTC, 2026-10-01) | Result |
| --- | --- | --- |
| INE `0012234`, explicit study request | 10:39:17 | 24 parishes × 26 quarters = 624 observations; 2019 Q4–2026 Q1; zero missing values; Total dwellings |
| DGT CAOP2025 | 10:36:03 | 24 canonical parish boundaries and identifiers |
| INE Censos 2021 synthesis ZIP | 10:36:03 | XLSX workbook; 24 aggregated parish rows; 545,796 residents |
| Turismo de Portugal RNAL, Lisboa | 10:38:59 | 11,865 unique records across all 24 parishes; zero populated cessation dates; no missing bed/user counts |

The housing annual Q4 window is **2019–2025**. The 2026 Q1 observation remains in the quarterly panel but is not a 2026 Q4 observation. This is a housing coverage window; RNAL's historical completeness has not been established for it.

The Census population and context transformations agree for every parish. The audit independently reads the workbook's municipality total and compares it with the sum of the parish populations: both are 545,796, with a difference of zero. Missing, duplicate, or mismatched municipality totals fail the audit. The context's age bands sum to population, and its dwelling/building count consistency checks pass. These figures describe this exact snapshot and should not be silently substituted for differently dated or revised published totals.

## Defects resolved by the live audit

### Housing needs explicit period filters

The unfiltered `fetch-ine-housing` request returned only 2026 Q1. Its metadata listed 26 available quarters beginning in 2019 Q4. `configs/ine_housing_study.toml` now selects those periods, the 24 metadata-verified parish codes, and Total dwellings (`H1`). All identifier and parish-name joins pass.

The fixed query is repeatable, but the provider can revise its values. Reproducing these exact observations requires the captured file with SHA-256 `89d6beae57e94401078e006534d7606ad90647fc5ceeb73ecf7ad54cc96a80f7`.

### The Census ZIP contains a mixed-hierarchy workbook

The official [INE synthesis download](https://mapas.ine.pt/download/2021FicheiroSintese/FS2021SubSeccaoTot.zip) contained an XLSX file, which the earlier CSV/TXT reader could not open. The reader now locates the worksheet header after its title, maps explicit official column labels, and includes only non-empty `SUBSECCAO` rows. National, regional, municipal, parish, and section totals are excluded from aggregation.

The national file contains both leading-zero and alphanumeric parish identifiers. These are preserved as strings. Identifier cells must contain text; numeric cells are rejected explicitly rather than inferring leading zeros from their number format. Duplicate subsection rows and inconsistent parish/subsection identifiers are rejected through the context/population transformation's public error type. Offline regression tests reproduce these cases without downloading the national workbook.

The archive's member name has no UTF-8 flag and contains legacy bytes `87 c6` for the accented letters. The acquisition manifest preserves Python `zipfile`'s CP437 lookup name (`FS 2021 SubSecç╞o Tot.xlsx`); this name resolves successfully with `ZipFile.getinfo` and `read`. CP850 gives the plausible display spelling `FS 2021 SubSecção Tot.xlsx`, but the acquisition does not guess an encoding or rewrite the original manifest. The original ZIP bytes and hash remain unchanged.

## RNAL interpretation remains unresolved

**Follow-up:** the [RNAL coverage investigation](rnal-coverage.md) confirms the seven early dates upstream, identifies 172 parish disagreements between official feeds, and quantifies a discrepancy against the municipal November 2022 benchmark. This original audit bundle remains unchanged.

The [official SOAP operation](https://webservices.turismodeportugal.pt/RNT_External/WS_RNT.asmx?op=list_RNAL) accepts a municipality filter and documents registration and cessation fields. It does not document a historical-date or cancelled-record selector. In this capture, **all 11,865 cessation fields are empty**. That observation does not prove that no establishments closed, or that cancelled establishments remain in the response.

Registration dates range from **1930-06-02 to 2026-09-30**. Seven records date before 2000: two in 1930, one in 1947, two in 1965, one in 1985, and one in 1992. The year-2000 threshold is a transparent screening rule, not an asserted registry inception date. The date meanings need provider clarification; records and dates have been retained unchanged.

The existing pipeline can reconstruct counts among records present in the snapshot. If historical establishments have been removed, those counts can suffer survivorship bias. Neither valid dates nor a successful model run establishes that this reconstruction measures the complete historical stock. Missing closure records cannot be repaired by imputing zero cessations.

The RNAL CSV therefore reports **snapshot record counts by parish**, not a historical stock-change panel. No canonical model findings or release tag were generated from this input set.

## Reproduce the audit

Use the code and locked dependencies from the revision containing this audit. Restore the exact local snapshots and manifests named in `configs/source_audit_2026-10-01.toml`, and the reference CSV/GeoJSON generated from the captured CAOP file. Then run from the repository root:

```bash
poetry sync --with docs
poetry run python scripts/audit_primary_sources.py --output data/processed/source-audit-recheck
```

The output directory must be new. The script verifies each acquisition resource against its recorded SHA-256 and size before transformation. It requires the configured 2019 Q4–2026 Q1 period set and all 624 housing rows; a single latest quarter, truncated endpoints, interior gaps, and extra quarters fail validation. It also validates RNAL identifiers and names, internal Census aggregates, and the independently read municipality total. Compare the regenerated CSV hashes with `audit.json`; JSON path fields differ when the output location differs. No live requests are made by the audit script.

Fresh acquisition is documented in [Getting started](getting-started.md). The RNAL request timed out at 60 seconds during this audit and succeeded with `--timeout 180`.

**Archive status:** exact raw snapshots and metadata are retained in the local ignored data workspace. They have not been deposited in a public archive or attached to a release. Committed hashes identify them but do not provide a downloadable copy. Source data remain subject to their providers' terms; the repository's software licence does not change those terms.

## What is needed before v1.1

1. Establish whether the RNAL source includes ceased/cancelled records; obtain archived observations or a documented historical extract where needed.
2. Resolve the unusually early registration dates and document any justified correction or exclusion. Preserve original records and a correction log.
3. Confirm the estimand and common window against those findings. A snapshot-cohort analysis would need an explicitly revised interpretation throughout the outputs.
4. Designate and durably archive the exact canonical inputs with access/redistribution information, then run `build-study-v1` with the versioned model settings and preserve its complete manifest and outputs.

The v1.1 milestone remains open until those evidence and archival requirements are met.
