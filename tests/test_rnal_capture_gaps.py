"""Registration-month gap checks require matching identities at both brackets."""

from __future__ import annotations

from datetime import date

import pytest

from lisbon_spatial_dynamics.analysis.rnal_archive import (
    ArchiveRecord,
    ArchiveSnapshot,
    timestamp_from_filename,
)
from lisbon_spatial_dynamics.analysis.rnal_capture_gaps import analyse_capture_gaps

FILES = (
    "al_20250901_183120.csv.gz",
    "al_20251001_182443.csv.gz",
    "al_20251108_110211.csv.gz",
    "al_20251211_171247.csv.gz",
    "al_20260103_093105.csv.gz",
)


def snapshot(index: int, dates: dict[int, str]) -> ArchiveSnapshot:
    return ArchiveSnapshot(
        FILES[index],
        timestamp_from_filename(FILES[index]),
        len(dates),
        len(dates),
        {
            key: ArchiveRecord(date.fromisoformat(value), "110601", 4)
            for key, value in dates.items()
        },
    )


def test_empty_month_requires_common_ids_not_equal_aggregate_counts() -> None:
    earlier = snapshot(0, {1: "2018-05-01", 2: "2018-05-07", 3: "2018-06-01", 4: "2018-05-09"})
    middle = snapshot(1, {3: "2018-06-01", 5: "2018-07-01"})
    later = snapshot(2, {1: "2018-05-01", 2: "2018-05-07", 3: "2018-06-01"})
    summary, datasets = analyse_capture_gaps([later, earlier, middle])
    window = datasets["capture_windows.csv"][0]
    assert window["earlier_to_middle_days"] == 30
    assert window["middle_to_later_days"] == 38
    assert window["common_bracket_records"] == 3
    cohort = datasets["affected_cohorts.csv"][0]
    assert cohort["registration_month"] == "2018-05"
    assert [
        cohort[key]
        for key in ("earlier_records_in_month", "middle_records_in_month", "later_records_in_month")
    ] == [3, 0, 2]
    assert cohort["same_date_bracket_records_missing_middle"] == 2  # Record 4 never returns.
    assert cohort["empty_middle_registration_month"] is True
    assert summary["missing_middle_record_observations"] == 2
    assert summary["distinct_registry_numbers_missing_middle"] == 2
    assert summary["records_imputed"] == 0
    assert summary["capture_cause_established"] is False
    assert summary["unassessed_endpoint_timestamps"] == [earlier.timestamp, later.timestamp]
    assert middle.records.keys() == {3, 5}


@pytest.mark.parametrize(
    ("middle_dates", "present", "changed", "middle_month_count"),
    [
        ({1: "2018-05-01", 3: "2018-06-01"}, 1, 0, 1),
        ({1: "2018-06-02", 3: "2018-06-01"}, 1, 1, 0),
        ({99: "2018-05-01", 3: "2018-06-01"}, 0, 0, 1),
    ],
)
def test_partial_gaps_and_date_changes_do_not_imply_an_empty_month(
    middle_dates: dict[int, str], present: int, changed: int, middle_month_count: int
) -> None:
    dates = {1: "2018-05-01", 2: "2018-05-07", 3: "2018-06-01"}
    _, datasets = analyse_capture_gaps(
        [snapshot(0, dates), snapshot(1, middle_dates), snapshot(2, dates)]
    )
    cohort = datasets["affected_cohorts.csv"][0]
    assert cohort["same_date_bracket_records_present_middle"] == present
    assert cohort["present_records_with_changed_middle_date"] == changed
    assert cohort["middle_records_in_month"] == middle_month_count
    assert cohort["empty_middle_registration_month"] is False


def test_date_revisions_at_brackets_are_excluded_and_reported() -> None:
    summary, datasets = analyse_capture_gaps(
        [
            snapshot(0, {1: "2018-05-01", 2: "2018-06-01"}),
            snapshot(1, {2: "2018-06-01"}),
            snapshot(2, {1: "2018-05-02", 2: "2018-06-01"}),
        ]
    )
    assert summary["bracket_date_disagreement_observations_excluded"] == 1
    assert summary["missing_middle_record_observations"] == 0
    assert datasets["affected_cohorts.csv"] == []
    window = datasets["capture_windows.csv"][0]
    assert window["common_bracket_records"] == 2
    assert window["same_date_bracket_records"] == 1


def test_repeated_gap_observations_are_distinct_from_unique_registry_numbers() -> None:
    full = {1: "2018-05-01", 2: "2018-06-01"}
    partial = {2: "2018-06-01"}
    summary, datasets = analyse_capture_gaps(
        [snapshot(index, full if index % 2 == 0 else partial) for index in range(5)]
    )
    assert summary["consecutive_triples_assessed"] == 3
    assert summary["missing_middle_record_observations"] == 2
    assert summary["distinct_registry_numbers_missing_middle"] == 1
    assert len(datasets["capture_windows.csv"]) == 3
    assert len(datasets["affected_cohorts.csv"]) == 2


def test_persistent_absence_is_outside_this_diagnostic() -> None:
    summary, datasets = analyse_capture_gaps(
        [
            snapshot(0, {1: "2018-05-01", 2: "2018-06-01"}),
            snapshot(1, {2: "2018-06-01"}),
            snapshot(2, {2: "2018-06-01"}),
        ]
    )
    assert summary["missing_middle_record_observations"] == 0
    assert summary["historical_completeness_established"] is False
    assert datasets["affected_cohorts.csv"] == []


def test_rejects_insufficient_or_ambiguous_capture_sequences() -> None:
    first = snapshot(0, {1: "2018-05-01"})
    second = snapshot(1, {1: "2018-05-01"})
    with pytest.raises(ValueError, match="at least three"):
        analyse_capture_gaps([first, second])
    with pytest.raises(ValueError, match="duplicate archive timestamps"):
        analyse_capture_gaps([first, first, second])
