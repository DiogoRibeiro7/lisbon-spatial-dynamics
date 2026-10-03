"""Locate temporary gaps in registration-month cohorts across adjacent archive captures."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date
from typing import Any

from lisbon_spatial_dynamics.analysis.rnal_archive import ArchiveSnapshot

TIME_COLUMNS = ("earlier_timestamp", "middle_timestamp", "later_timestamp")
WINDOW_COLUMNS = (
    *TIME_COLUMNS,
    "earlier_to_middle_days",
    "middle_to_later_days",
    "common_bracket_records",
    "bracket_date_disagreements_excluded",
    "same_date_bracket_records",
    "same_date_bracket_records_missing_middle",
    "affected_registration_months",
    "empty_middle_registration_months",
)
COHORT_COLUMNS = (
    *TIME_COLUMNS,
    "registration_month",
    "earlier_records_in_month",
    "middle_records_in_month",
    "later_records_in_month",
    "same_date_bracket_records",
    "same_date_bracket_records_present_middle",
    "same_date_bracket_records_missing_middle",
    "present_records_with_changed_middle_date",
    "empty_middle_registration_month",
)
DATASET_COLUMNS = {"capture_windows.csv": WINDOW_COLUMNS, "affected_cohorts.csv": COHORT_COLUMNS}
COLUMN_DEFINITIONS = {
    "registration_month": "YYYY-MM of the identical registration date in both bracketing captures.",
    "common_bracket_records": "Registry numbers present in both the earlier and later captures.",
    "bracket_date_disagreements_excluded": (
        "Common registry numbers with different registration dates at the brackets; "
        "excluded from cohort comparisons."
    ),
    "same_date_bracket_records": (
        "Common registry numbers with identical registration dates at the brackets. "
        "Restricted to the registration month in affected_cohorts.csv."
    ),
    "same_date_bracket_records_missing_middle": (
        "Eligible bracket registry numbers absent from the middle capture. "
        "An observed gap, not a closure or a reconstructed stock value."
    ),
    "same_date_bracket_records_present_middle": (
        "Eligible bracket registry numbers also present in the middle capture, "
        "regardless of that capture's registration-date value."
    ),
    "present_records_with_changed_middle_date": (
        "Eligible bracket registry numbers present in the middle capture "
        "with a registration date different from the bracket date."
    ),
    "empty_middle_registration_month": (
        "True only when eligible bracket records exist, every one is absent in the middle, "
        "and no middle-capture record reports that registration month."
    ),
    "earlier_records_in_month / middle_records_in_month / later_records_in_month": (
        "Unique registry numbers reporting this registration month in that capture; "
        "not limited to shared records."
    ),
    "timestamps": "Publisher-supplied capture labels; timezone unspecified.",
    "day_intervals": "Differences between publisher calendar dates, not precise elapsed UTC time.",
    "record_units": "Unique registry numbers within each comparison, not people or capacity.",
}


def analyse_capture_gaps(
    snapshots: Sequence[ArchiveSnapshot],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Check every consecutive triple; leave source records and observations unchanged."""
    if len(snapshots) < 3:
        raise ValueError("capture-gap analysis requires at least three snapshots")
    ordered = sorted(snapshots, key=lambda snapshot: snapshot.timestamp)
    if len({snapshot.timestamp for snapshot in ordered}) != len(ordered):
        raise ValueError("duplicate archive timestamps")
    month_counts = [
        Counter(row.registered_on.isoformat()[:7] for row in snapshot.records.values())
        for snapshot in ordered
    ]
    windows: list[dict[str, Any]] = []
    cohorts: list[dict[str, Any]] = []
    distinct_missing: set[int] = set()
    for index in range(1, len(ordered) - 1):
        earlier, middle, later = ordered[index - 1 : index + 2]
        shared = earlier.records.keys() & later.records.keys()
        eligible = {
            key
            for key in shared
            if earlier.records[key].registered_on == later.records[key].registered_on
        }
        missing = eligible - middle.records.keys()
        distinct_missing.update(missing)
        months = sorted({earlier.records[key].registered_on.isoformat()[:7] for key in missing})
        empty_months = 0
        times = dict(
            zip(TIME_COLUMNS, (earlier.timestamp, middle.timestamp, later.timestamp), strict=True)
        )
        for month in months:
            cohort = {
                key
                for key in eligible
                if earlier.records[key].registered_on.isoformat()[:7] == month
            }
            present = cohort & middle.records.keys()
            absent = cohort - middle.records.keys()
            empty = not present and month_counts[index][month] == 0
            empty_months += empty
            cohorts.append(
                {
                    **times,
                    "registration_month": month,
                    "earlier_records_in_month": month_counts[index - 1][month],
                    "middle_records_in_month": month_counts[index][month],
                    "later_records_in_month": month_counts[index + 1][month],
                    "same_date_bracket_records": len(cohort),
                    "same_date_bracket_records_present_middle": len(present),
                    "same_date_bracket_records_missing_middle": len(absent),
                    "present_records_with_changed_middle_date": sum(
                        middle.records[key].registered_on != earlier.records[key].registered_on
                        for key in present
                    ),
                    "empty_middle_registration_month": empty,
                }
            )
        windows.append(
            {
                **times,
                "earlier_to_middle_days": (
                    date.fromisoformat(middle.timestamp[:10])
                    - date.fromisoformat(earlier.timestamp[:10])
                ).days,
                "middle_to_later_days": (
                    date.fromisoformat(later.timestamp[:10])
                    - date.fromisoformat(middle.timestamp[:10])
                ).days,
                "common_bracket_records": len(shared),
                "bracket_date_disagreements_excluded": len(shared - eligible),
                "same_date_bracket_records": len(eligible),
                "same_date_bracket_records_missing_middle": len(missing),
                "affected_registration_months": len(months),
                "empty_middle_registration_months": empty_months,
            }
        )
    summary = {
        "snapshots": len(ordered),
        "consecutive_triples_assessed": len(windows),
        "unassessed_endpoint_timestamps": [ordered[0].timestamp, ordered[-1].timestamp],
        "windows_with_gaps": sum(
            row["same_date_bracket_records_missing_middle"] > 0 for row in windows
        ),
        "missing_middle_record_observations": sum(
            row["same_date_bracket_records_missing_middle"] for row in windows
        ),
        "distinct_registry_numbers_missing_middle": len(distinct_missing),
        "bracket_date_disagreement_observations_excluded": sum(
            row["bracket_date_disagreements_excluded"] for row in windows
        ),
        "affected_cohort_rows": len(cohorts),
        "empty_middle_registration_months": [
            row for row in cohorts if row["empty_middle_registration_month"]
        ],
        "capture_cause_established": False,
        "records_imputed": 0,
        "historical_completeness_established": False,
    }
    return summary, {"capture_windows.csv": windows, "affected_cohorts.csv": cohorts}
