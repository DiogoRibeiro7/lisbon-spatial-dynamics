# How much do the RNAL parish disagreements matter?

Changing the 172 disputed parish labels changes six parishes' record-pressure ranks by one position; the top four remain unchanged. Local effects are less uniform: Estrela loses 30 records when all GIS labels are used, but 33 when only GIS-supported points more than 25 metres from a boundary are reassigned. These are scenarios within the same retained registry cohort, not corrections or historical-stock estimates.

This analysis was run on **2026-10-02 using the retained 2026-10-01 snapshots**. The [aggregate bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/rnal-parish-sensitivity/2026-10-02) contains 72 parish/scenario rows, the coordinate-support table, a comparison figure, and an audit report with input, code, configuration and output hashes.

## Comparison design

The [pinned configuration](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/configs/rnal_parish_sensitivity_2026-10-02.toml) specifies three scenarios before aggregation:

| Scenario | Assignment rule | Records reassigned | Captured user capacity reassigned |
| --- | --- | ---: | ---: |
| `soap` | Original SOAP parish for every record | 0 | 0 |
| `gis_all_conflicts` | GIS parish for every shared conflict | 172 | 982 |
| `gis_beyond_margin` | GIS parish only with unique interior support and distance **strictly greater than 25 m** from every reference boundary | 105 | 594 |

The 25-metre diagnostic margin comes from the [preceding coordinate investigation](rnal-geography.md); it is not an estimated location error or a confidence interval. The third scenario retains SOAP labels for all remaining conflicts, including missing, ambiguous, outside-reference, SOAP-supported or third-parish points. Provider reliability labels are not treated as measured accuracy. The all-GIS scenario follows labels regardless of coordinate support; in this particular capture all 172 points support GIS.

All scenarios retain exactly the same **11,865 SOAP records**, with **69,895 captured user-capacity places** and no missing user-capacity values in this snapshot. The five GIS-only records are excluded. Dates and capacities are unchanged, with no registration/cessation-date filtering. Thus, all retained members are counted, including any ceased members a different snapshot might contain. Capacity means the captured `NrUtentes` field; it does not measure occupancy, beds, past capacity, or verified operation.

Rates divide parish totals by **Census 2021 residents** and multiply by 1,000. The denominators sum to 545,796 and are fixed across scenarios; they do not estimate the population at the RNAL capture date. Known capacity and the number of records with missing capacity are reported separately. The software preserves that distinction even when a future input contains missing values.

## Observed changes

All differences below are **scenario minus original SOAP**. Gross incoming/outgoing counts in the CSV explain differences that would be hidden by net counts alone.

| Parish | Original records | All GIS: record change | Beyond 25 m: record change | All GIS: known capacity change | Beyond 25 m: known capacity change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Estrela | 744 | −30 | −33 | −105 | −136 |
| Misericórdia | 2,174 | +10 | +31 | −12 | +106 |
| Santa Maria Maior | 3,142 | +15 | +17 | +65 | +93 |
| São Vicente | 929 | +7 | −10 | +89 | −3 |
| Santo António | 922 | +13 | +2 | +62 | −5 |
| Santa Clara | 10 | +1 | +1 | +6 | +6 |

The first five rows illustrate large net changes and changes in direction; Santa Clara illustrates the effect of a small baseline. Its one additional record is the largest absolute percentage change, 10%, in both scenarios. A smaller reassigned cohort can produce a larger parish net change because incoming and outgoing movements cancel differently. These scenarios therefore do **not** bound the true parish totals or each other.

Using all GIS labels changes net record counts in 22 parishes; the boundary-screened scenario changes them in 20. Municipality totals are identical by construction. In each scenario, six parishes move one position in record pressure and six move one position in known-capacity pressure, with no larger rank changes. These are separate rankings and do not involve the same six parishes.

The record-pressure ordering of Santa Maria Maior, Misericórdia, Santo António and São Vicente remains first through fourth. Arroios and Estrela exchange fifth/sixth place, Ajuda and Campo de Ourique exchange ninth/tenth, and Carnide and Lumiar exchange twenty-first/twenty-second. Both scenarios produce those same rank exchanges. Ranks use exact, unrounded ratios: the greatest pressure ranks first, ties share a competition rank (`1, 1, 3`), and negative rank deltas mean movement toward first place. Relative record changes are undefined when the SOAP baseline is zero and are left empty in CSV.

[View or download the comparison figure](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/results/rnal-parish-sensitivity/2026-10-02/parish_sensitivity.png). It shows all 24 parishes in descending original record-pressure order, with count changes and known user-capacity changes per 1,000 Census 2021 residents.

## Reproduce the comparison

Restore the files identified by `configs/rnal_parish_sensitivity_2026-10-02.toml`. These include the original SOAP/GIS snapshots and manifests, the CAOP2025 reference, the conflict coordinates, the previously audited Census table and its provenance. From the repository root with the locked dependencies:

```bash
poetry sync --with docs
poetry run python scripts/audit_rnal_geography.py audit --config configs/rnal_parish_sensitivity_2026-10-02.toml --output data/processed/rnal-parish-sensitivity-recheck
```

The command is offline, verifies pinned hashes/sizes, and requires a new output directory. Parish sets, population denominators, normalized registration identities, conflict membership and original SOAP labels are validated. CSV files, figure and report are staged and published together; failures leave no partial bundle and existing destinations are preserved. Compare CSV hashes and numeric summaries with the committed audit. JSON paths/code provenance reflect the replay environment, and figure bytes can differ with rendering libraries or fonts.

Verification and parsing use the same captured bytes for analysis inputs, including coordinates, boundaries and Census denominators. Pinned files used only as provenance references are checked by hash and size without parsing their contents. SOAP records are parsed once and reused for cohort selection and aggregation; the configuration fingerprint describes the exact configuration used. A later on-disk change cannot silently alter the current run, though it may prevent future replay against the pinned hashes. The report contains both the scenario `summary` and its separate `coordinate_summary`. The original committed evidence bundle is preserved; replays with the corrected reader retain its numeric results and CSV hashes while recording the new code fingerprints.

## Implication for the study

The observed rankings are relatively stable under these two parish-label scenarios, while some parish counts and capacity differences change direction. This informs a future geographic assignment policy; it does not select a preferred scenario or validate establishment addresses. The study pipeline and original snapshots retain their existing assignments.

The [historical completeness discrepancy](rnal-coverage.md) remains unresolved. Stable rankings within surviving records cannot recover missing records, establish historical capacity, or demonstrate robustness of the longitudinal housing models. No housing associations or model coefficients are estimated here. The definitive v1.1 run still requires historical evidence, documented date/geography semantics and durable input archiving. Raw snapshots and record-level coordinates remain in the ignored local workspace; only aggregates are committed.
