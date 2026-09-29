"""Tests for aggregate trajectory summary output."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.trajectory_summary import (
    TrajectorySummaryError,
    build_trajectory_summary,
    write_trajectory_summary_json,
)
from lisbon_spatial_dynamics.analysis.trajectories import FreguesiaTrajectory


def _row(
    freguesia_id: str,
    housing_change: Decimal | None,
    *,
    rnal_baseline: int = 100,
    rnal_latest: int = 130,
    full_flow: bool = True,
) -> FreguesiaTrajectory:
    return FreguesiaTrajectory(
        freguesia_id=freguesia_id,
        freguesia_name=f"Name {freguesia_id}",
        baseline_year=2019,
        latest_year=2025,
        years_elapsed=6,
        observed_q4_years=7,
        housing_baseline_eur_m2=Decimal("4000"),
        housing_latest_eur_m2=Decimal("6000"),
        housing_change_abs_eur_m2=Decimal("2000"),
        housing_change_pct=housing_change,
        housing_latest_yoy_pct=Decimal("4"),
        rnal_active_baseline=rnal_baseline,
        rnal_active_latest=rnal_latest,
        rnal_active_change_abs=rnal_latest - rnal_baseline,
        rnal_active_change_pct=(
            None
            if rnal_baseline == 0
            else Decimal(rnal_latest - rnal_baseline)
            / Decimal(rnal_baseline)
            * Decimal("100")
        ),
        rnal_beds_known_baseline=200,
        rnal_beds_known_latest=260,
        rnal_beds_missing_latest=1,
        rnal_users_known_baseline=300,
        rnal_users_known_latest=390,
        rnal_users_missing_latest=2,
        latest_flow_quarters_observed=4 if full_flow else 2,
        latest_registrations_year=10 if full_flow else None,
        latest_cessations_year=3 if full_flow else None,
        latest_net_registrations_year=7 if full_flow else None,
    )


def test_summary_reports_coverage_and_aggregate_totals() -> None:
    rows = (
        _row("110654", Decimal("50")),
        _row("110656", Decimal("25"), rnal_baseline=0, rnal_latest=20),
        _row("110657", None, full_flow=False),
    )

    summary = build_trajectory_summary(rows)

    assert summary.baseline_year == 2019
    assert summary.latest_year == 2025
    assert summary.freguesia_count == 3
    assert summary.housing_complete_count == 2
    assert summary.housing_missing_count == 1
    assert summary.housing_change_pct_median == Decimal("37.5")
    assert summary.rnal_pct_defined_count == 2
    assert summary.rnal_pct_undefined_count == 1
    assert summary.latest_full_flow_count == 2
    assert summary.latest_partial_flow_count == 1
    assert summary.rnal_active_total_baseline == 200
    assert summary.rnal_active_total_latest == 280
    assert summary.rnal_active_total_change == 80


def test_summary_rejects_mixed_windows() -> None:
    first = _row("110654", Decimal("50"))
    second = _row("110656", Decimal("25"))
    second = FreguesiaTrajectory(
        **{
            **second.__dict__,
            "baseline_year": 2020,
        }
    )

    with pytest.raises(TrajectorySummaryError, match="one comparison window"):
        build_trajectory_summary((first, second))


def test_summary_json_is_immutable(tmp_path: Path) -> None:
    summary = build_trajectory_summary((_row("110654", Decimal("50")),))
    path = tmp_path / "summary.json"

    write_trajectory_summary_json(summary, path)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["comparison_window"]["baseline_year"] == 2019
    assert document["descriptive"]["housing_change_pct_median"] == 50.0

    with pytest.raises(FileExistsError):
        write_trajectory_summary_json(summary, path)
