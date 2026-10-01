# RNAL parish conflicts: coordinate evidence

All **172 registrations with conflicting SOAP/GIS parish labels have GIS coordinates inside the GIS-labelled CAOP2025 parish**. None fall inside their SOAP-labelled parish. However, **67 points are within 25 metres of a parish boundary**. This establishes consistency between the published GIS coordinates and the reference boundaries; it does not independently verify an establishment's address or justify silently rewriting registry records.

The [aggregate audit bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/rnal-geography/2026-10-01) contains a 24-parish comparison CSV and a JSON report with input, configuration, software and output provenance. Coordinates and registry-level rows remain outside Git.

## Cohort and acquisition

The cohort is selected by normalized registry number from the exact snapshots in the [previous coverage investigation](rnal-coverage.md): the 172 shared records whose parish identifiers disagree. The five GIS-only records and all agreeing records are excluded. Results therefore describe this conflict cohort, not the accuracy of the whole registry.

The [official RNAL GIS layer](https://geo.turismodeportugal.pt/server/rest/services/TDP/OpenData_AL/MapServer/6) is queried for these registry numbers with only `NrRNAL`, `DTMNFR`, `Concelho`, `FiabilidadeGeo` and point geometry. Each batch must contain exactly its requested IDs, with no duplicates, truncation or changed GIS parish labels. The response must declare EPSG:4326. Non-finite or out-of-range coordinates fail validation; absent geometry is retained as missing. Unexpected attributes and extra geometry fields are discarded before writing.

The geometry capture is later than the two baseline captures. Its start/end timestamps and resource hashes are recorded in the report. Matching IDs and parish labels do not establish that coordinates are unchanged since the earlier captures.

The provider returns `Fiavel` for 164 records and `Fiável` for eight. Its metadata defines reliability codes and labels, but does not provide metre-based error estimates. Both forms are preserved verbatim. These labels are not interpreted as independently measured positional accuracy.

## Boundary comparison and sensitivity

Both points and the pinned 24-parish reference GeoJSON are transformed from WGS84 longitude/latitude to Portugal TM06 (EPSG:3763). Explicit longitude-first axis order prevents a latitude/longitude swap. PROJ network access is rejected during replay; package, PROJ/GEOS versions and projection details are recorded. Invalid, duplicate or overlapping parish polygons fail validation.

For each point, the audit tests which projected polygon covers it. Missing points, points outside the reference, boundary ties and points in a third parish remain separate categories. A boundary point is never assigned by choosing the first matching polygon. In this capture, all 172 have a unique interior match with their GIS parish.

The audit then measures distance to the nearest projected parish boundary. The margins below are diagnostic sensitivity screens chosen before the comparison. They are not confidence intervals or estimates of geocoding error. A point must be **strictly farther** than a margin to count in the last column.

| Margin | Points at or within the margin | GIS matches farther from all boundaries |
| --- | ---: | ---: |
| 0 m | 0 | 172 |
| 10 m | 48 | 124 |
| 25 m | 67 | 105 |
| 50 m | 102 | 70 |
| 100 m | 134 | 38 |

At every margin, zero points support the SOAP parish or a third parish. The parish CSV attributes each conflict to its original SOAP parish for comparison with the earlier audit; it does not redefine that parish's stock.

The coordinates and GIS labels come from the same provider and could share a geocoding process. CAOP independently supplies the administrative boundaries, not ground-truth establishment locations. Errors in the supplied coordinates could change the interpretation, particularly near boundaries. An administrative label based on a different address or boundary vintage would require its own reconciliation.

## Reproduce the result

Restore the exact files pinned in `configs/rnal_geography_2026-10-01.toml`, including both baseline snapshots, the CAOP reference, and the location acquisition manifest/resources. From the repository root with the locked dependencies:

```bash
poetry sync --with docs
poetry run python scripts/audit_rnal_geography.py audit --output data/processed/rnal-geography-recheck
```

The command is offline and requires a new output directory. It verifies hashes and sizes before deriving the cohort. CSV and JSON are staged together and published only when complete. Compare the output CSV hash and aggregate summary with the committed audit; paths and recorded software/code provenance can differ across replay environments.

To acquire a fresh coordinate observation for the pinned cohort:

```bash
poetry run python scripts/audit_rnal_geography.py fetch --output data/raw/turismo_portugal/rnal_locations/lisboa/<new-capture>
```

Use a new audit configuration with the resulting manifest's path, hash and size. Do not overwrite the original snapshots. Acquisition and audit publication both preserve existing destinations and clean their own temporary files on failure.

## Implications for v1.1

The coordinate evidence supports GIS parish assignments for this cohort, subject to positional verification. **No records have been corrected**, and the existing study pipeline's parish selection is unchanged. A canonical harmonisation policy still needs to specify coordinate quality, boundary vintage and treatment of uncertain locations, with an explicit correction log.

Historical RNAL completeness is a separate unresolved requirement. Coordinate agreement cannot recover missing ceased/cancelled records or historical capacity. The earlier November 2022 benchmark discrepancy remains. Raw snapshots are retained locally with hashes; they have not been placed in a public archive, and provider redistribution terms remain unverified.
