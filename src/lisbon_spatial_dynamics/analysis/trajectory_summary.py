"""Aggregate descriptive summary for common-window freguesia trajectories."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import median

from lisbon_spatial_dynamics.analysis.trajectories import FreguesiaTrajectory


class TrajectorySummaryError(ValueError):
    """Raised when trajectory rows cannot form one comparable summary."""


@dataclass(frozen=True, slots=True)
class TrajectorySummary:
    """City-wide descriptive coverage and aggregate trajectory statistics."""

    baseline_year: int
    latest_year: int
    years_elapsed: int
    freguesia_count: int
    housing_complete_count: int
    housing_missing_count: int
    housing_change_pct_median: Decimal | None
    rnal_pct_defined_count: int
    rnal_pct_undefined_count: int
    rnal_active_total_baseline: int
    rnal_active_total_latest: int
    rnal_active_total_change: int
    rnal_beds_known_total_baseline: int
    rnal_beds_known_total_latest: int
    rnal_users_known_total_baseline: int
    rnal_users_known_total_latest: int
    latest_full_flow_count: int
    latest_partial_flow_count: int


def build_trajectory_summary(
    rows: Sequence[FreguesiaTrajectory],
) -> TrajectorySummary:
    """Build a city-wide descriptive summary without ranking freguesias."""
    if not rows:
        raise TrajectorySummaryError("trajectory rows cannot be empty")

    windows = {(row.baseline_year, row.latest_year) for row in rows}
    if len(windows) != 1:
        raise TrajectorySummaryError("trajectory rows do not share one comparison window")

    baseline_year, latest_year = next(iter(windows))
    ids = [row.freguesia_id for row in rows]
    if len(ids) != len(set(ids)):
        raise TrajectorySummaryError("trajectory rows contain duplicate freguesia IDs")

    housing_changes = [row.housing_change_pct for row in rows if row.housing_change_pct is not None]
    housing_complete_count = len(housing_changes)
    housing_missing_count = len(rows) - housing_complete_count

    rnal_defined_count = sum(row.rnal_active_change_pct is not None for row in rows)
    full_flow_count = sum(
        row.latest_flow_quarters_observed == 4
        and row.latest_registrations_year is not None
        and row.latest_cessations_year is not None
        and row.latest_net_registrations_year is not None
        for row in rows
    )

    return TrajectorySummary(
        baseline_year=baseline_year,
        latest_year=latest_year,
        years_elapsed=latest_year - baseline_year,
        freguesia_count=len(rows),
        housing_complete_count=housing_complete_count,
        housing_missing_count=housing_missing_count,
        housing_change_pct_median=(median(housing_changes) if housing_changes else None),
        rnal_pct_defined_count=rnal_defined_count,
        rnal_pct_undefined_count=len(rows) - rnal_defined_count,
        rnal_active_total_baseline=sum(row.rnal_active_baseline for row in rows),
        rnal_active_total_latest=sum(row.rnal_active_latest for row in rows),
        rnal_active_total_change=sum(row.rnal_active_change_abs for row in rows),
        rnal_beds_known_total_baseline=sum(row.rnal_beds_known_baseline for row in rows),
        rnal_beds_known_total_latest=sum(row.rnal_beds_known_latest for row in rows),
        rnal_users_known_total_baseline=sum(row.rnal_users_known_baseline for row in rows),
        rnal_users_known_total_latest=sum(row.rnal_users_known_latest for row in rows),
        latest_full_flow_count=full_flow_count,
        latest_partial_flow_count=len(rows) - full_flow_count,
    )


def write_trajectory_summary_json(
    summary: TrajectorySummary,
    path: Path,
) -> None:
    """Write the aggregate trajectory summary without overwriting."""
    path.parent.mkdir(parents=True, exist_ok=True)

    document: dict[str, object] = {
        "schema_version": 1,
        "comparison_window": {
            "baseline_year": summary.baseline_year,
            "latest_year": summary.latest_year,
            "years_elapsed": summary.years_elapsed,
        },
        "coverage": {
            "freguesia_count": summary.freguesia_count,
            "housing_complete_count": summary.housing_complete_count,
            "housing_missing_count": summary.housing_missing_count,
            "rnal_pct_defined_count": summary.rnal_pct_defined_count,
            "rnal_pct_undefined_count": summary.rnal_pct_undefined_count,
            "latest_full_flow_count": summary.latest_full_flow_count,
            "latest_partial_flow_count": summary.latest_partial_flow_count,
        },
        "descriptive": {
            "housing_change_pct_median": _decimal_number(summary.housing_change_pct_median),
            "rnal_active_total_baseline": summary.rnal_active_total_baseline,
            "rnal_active_total_latest": summary.rnal_active_total_latest,
            "rnal_active_total_change": summary.rnal_active_total_change,
            "rnal_beds_known_total_baseline": (summary.rnal_beds_known_total_baseline),
            "rnal_beds_known_total_latest": summary.rnal_beds_known_total_latest,
            "rnal_users_known_total_baseline": (summary.rnal_users_known_total_baseline),
            "rnal_users_known_total_latest": (summary.rnal_users_known_total_latest),
        },
    }

    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def _decimal_number(value: Decimal | None) -> float | None:
    """Convert an exact Decimal to a JSON-compatible number."""
    return None if value is None else float(value)
