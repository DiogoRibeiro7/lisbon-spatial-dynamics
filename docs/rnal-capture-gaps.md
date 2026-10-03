# Missing registration-month cohorts in the RNAL archive

Two captures in the [community RNAL archive](rnal-archive-coverage.md) contain **empty registration-month groups whose records appear in the immediately preceding and following captures**. The October 2025 capture has no records registered in May 2018; the February 2026 capture has no records registered in September 2014. Identity matching confirms **349** and **34** missing records respectively. These are concrete capture-quality flags, not reconstructed closures or corrections to the source.

The [aggregate evidence bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/rnal-capture-gaps/2026-10-03) records all 11 consecutive three-capture comparisons from the same 13 archived exports. No new source acquisition or establishment-level publication is involved.

## Two empty groups

The columns below count unique registry numbers reporting the specified registration month in each capture. The final column counts the same identifiers observed on both sides and missing in the middle.

| Registration month | Earlier capture: count | Middle capture: count | Later capture: count | Matched IDs missing in the middle |
| --- | --- | --- | --- | ---: |
| May 2018 | 2025-09-01: **349** | 2025-10-01: **0** | 2025-11-08: **349** | **349** |
| September 2014 | 2026-01-03: **39** | 2026-02-01: **0** | 2026-03-07: **34** | **34** |

In the second row, five of January's 39 identifiers are absent in March too. They are outside this temporary-gap diagnostic; the matched missing count is **34**, not 39. Registration month is a property of the records, distinct from the date of the capture. For example, the first row concerns records registered in May 2018 that are missing from an October 2025 export.

The [publisher's retained collector](https://github.com/sztanko/al-pulse/blob/50322b0ae5680d24013fae4ee19d757350a8ba2c/scripts/fetch_al_list.py) queries successive registration-month intervals. Entire empty groups are consistent with a missing acquisition batch. This is an inference, not an established cause: the available files do not identify the precise collector code/arguments used for each run or distinguish collection failures from upstream revisions or reinstatements. Collector logs or provider record histories are needed to settle that question.

## All temporary gaps, not just empty months

Across all 11 comparisons, **392 distinct registry numbers** appear at both brackets with the same registration date but are missing in the middle. There are also 392 gap observations; a general replay reports these quantities separately because a number could be missing in more than one capture. No bracket registration-date disagreements occur in this retained input set.

| Middle capture | Missing matched IDs | Affected registration-month groups | Entirely empty groups |
| --- | ---: | ---: | ---: |
| 2025-10-01 | 349 | 1 | 1 |
| 2026-02-01 | 43 | 9 | 1 |
| Other nine assessed captures | 0 | 0 | 0 |

The two entirely empty groups account for **383 of the 392** missing identifiers. The other nine February gaps span eight registration months: October 2016, July 2017, January/March/June/October/November 2018, and November 2019. October 2018 contributes two identifiers; each other group contributes one.

Matching identifiers matters even when aggregate counts agree. The March-2018 group has 186 records in both the February and March 2026 captures, yet one identifier present in January and March is absent in February. Equal totals alone would miss that gap.

The earlier archive assessment reports **418 reappearance observations**. That diagnostic permits a returning number to have last appeared any number of captures earlier. This stricter comparison requires presence immediately before and after the missing capture. Its 392 observations therefore answer a different question; the original count is unchanged.

## Method and limits

For every consecutive triple, the earlier and later captures are the brackets. The audit selects registry numbers present in both with an identical full registration date, subtracts the middle capture's identifiers, and groups the missing numbers by registration month. Numbers whose dates disagree at the brackets are excluded and counted explicitly. The monthly earlier/middle/later totals use all records reporting that month, not only the selected shared identifiers.

An **empty middle registration month** requires eligible bracket records, all of them absent in the middle, and zero middle-capture records reporting that month. A record whose date changes in the middle remains present by identifier and cannot be silently reclassified as absent. Such date changes are counted separately in affected groups.

`capture_windows.csv` includes every assessed triple, including zero-gap comparisons and the calendar-day distances between captures. `affected_cohorts.csv` includes only registration months with at least one eligible missing identifier. A replay with no gaps still emits that CSV's header. The audit JSON records definitions, totals, exact input/code/configuration/output fingerprints and the selected analysis mode.

The first and last captures cannot be screened as middle observations and are listed as unassessed endpoints. Irregular intervals, including the existing 193-day gap, remain explicit; timestamps are publisher labels with unspecified timezone. The method detects only disappearance followed by reappearance across adjacent captures. It cannot establish completeness, identify all acquisition failures, date a cancellation, prove continuous registration between observations, or certify captures with zero detected gaps.

The previously reported duplicate rows are a separate diagnostic. Their coincidence with flagged captures does not prove that duplicated and omitted batches caused each other. This analysis neither restores missing records nor adjusts totals, capacity, dates or parish assignments. The 6,183-record January-to-February membership difference must not be converted into verified closures by subtracting the 43 temporary gaps.

## Reproduce the audit

Restore the same minimized archive files and provenance documents named in `configs/rnal_archive_2026-10-03.toml`. The shared loader also verifies the pinned SOAP snapshot/manifest; SOAP is not used in the three-capture comparison. From the repository root:

```bash
poetry sync --with docs
poetry run python scripts/audit_rnal_archive.py audit --analysis capture-gaps --output data/processed/rnal-capture-gaps-recheck
```

The output directory must be new. Replay makes no network requests, parses the verified analytical bytes, and publishes both CSVs and `audit.json` atomically. Compare the complete three-file artifact set, CSV hashes and numerical summary with the committed bundle. Paths and code/software provenance reflect the replay environment. Omitting `--analysis` retains the original coverage analysis and its three CSVs; the original evidence bundles are unchanged.

## Implication for source selection

October 2025 and February 2026 need targeted validation before their totals inform a longitudinal model. The precise queries are now whether the May-2018 and September-2014 registration groups were fully returned in those runs, and why the matched records disappear and return. These findings strengthen the historical-data request without supplying the missing 2019–2025 quarterly series or authorizing automatic repairs. No provider or archive-maintainer message has been sent.
