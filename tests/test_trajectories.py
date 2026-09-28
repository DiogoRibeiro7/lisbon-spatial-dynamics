"""Tests for baseline-to-latest freguesia trajectories."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.trajectories import (
    TRAJECTORY_COLUMNS,
    TrajectoryError,
    build_freguesia_trajectories,
    write_freguesia_trajectory_csv,
)
from lisbon_spatial_dynamics.panels.annual import AnnualUrbanRow


def _row(
    freguesia_id: str,
    name: str,
    year: int,
    housing: str,
    active: int,
) -> AnnualUrbanRow:
    return AnnualUrbanRow(
        year=year,
        baseline_year=2019,
        period_code=f"4.º Trimestre de {year}",
        period_end=date(year, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        flow_quarters_observed=4 if year > 2019 else 1,
        housing_value_eur_m2=Decimal(housing),
        housing_yoy_abs_eur_m2=Decimal("100") if year > 2019 else None,
        housing_yoy_pct=Decimal("2.5") if year > 2019 else None,
        housing_change_from_baseline_abs_eur_m2=None,
        housing_change_from_baseline_pct=None,
        rnal_registrations_year=10 if year > 2019 else None,
        rnal_cessations_year=3 if year > 2019 else None,
        rnal_net_registrations_year=7 if year > 2019 else None,
        rnal_active_registrations_year_end=active,
        rnal_active_change_from_baseline_abs=0,
        rnal_active_change_from_baseline_pct=None,
        rnal_active_beds_known_year_end=active * 2,
        rnal_active_beds_missing_year_end=1,
        rnal_active_users_known_year_end=active * 3,
        rnal_active_users_missing_year_end=2,
    )


def test_build_trajectories_uses_common_baseline_and_latest_year() -> None:
    rows = (
        _row("110654", "Alvalade", 2019, "4000", 100),
        _row("110654", "Alvalade", 2020, "4500", 108),
        _row("110654", "Alvalade", 2025, "6000", 130),
        _row("110656", "Arroios", 2019, "3500", 200),
        _row("110656", "Arroios", 2025, "5250", 250),
    )

    trajectories = build_freguesia_trajectories(rows)

    assert [row.freguesia_id for row in trajectories] == ["110654", "110656"]

    alvalade = trajectories[0]
    assert alvalade.baseline_year == 2019
    assert alvalade.latest_year == 2025
    assert alvalade.years_elapsed == 6
    assert alvalade.observed_q4_years == 3
    assert alvalade.housing_change_abs_eur_m2 == Decimal("2000")
    assert alvalade.housing_change_pct == Decimal("50")
    assert alvalade.rnal_active_change_abs == 30
    assert alvalade.rnal_active_change_pct == Decimal("30")
    assert alvalade.latest_net_registrations_year == 7


def test_different_comparison_windows_are_rejected_by_default() -> None:
    rows = (
        _row("110654", "Alvalade", 2019, "4000", 100),
        _row("110654", "Alvalade", 2025, "6000", 130),
        _row("110656", "Arroios", 2020, "3800", 210),
        _row("110656", "Arroios", 2025, "5250", 250),
    )

    with pytest.raises(TrajectoryError, match="common comparison window"):
        build_freguesia_trajectories(rows)


def test_single_year_freguesia_is_rejected() -> None:
    with pytest.raises(TrajectoryError, match="at least two"):
        build_freguesia_trajectories(
            (_row("110654", "Alvalade", 2019, "4000", 100),)
        )


def test_zero_rnal_baseline_preserves_absolute_but_not_pct_change() -> None:
    rows = (
        _row("110654", "Alvalade", 2019, "4000", 0),
        _row("110654", "Alvalade", 2025, "6000", 30),
    )

    trajectory = build_freguesia_trajectories(rows)[0]

    assert trajectory.rnal_active_change_abs == 30
    assert trajectory.rnal_active_change_pct is None


def test_writer_uses_stable_contract_and_is_immutable(tmp_path: Path) -> None:
    rows = build_freguesia_trajectories(
        (
            _row("110654", "Alvalade", 2019, "4000", 100),
            _row("110654", "Alvalade", 2025, "6000", 130),
        )
    )
    path = tmp_path / "trajectories.csv"

    write_freguesia_trajectory_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == TRAJECTORY_COLUMNS
    assert table[0]["housing_change_pct"] == "50"
    assert table[0]["rnal_active_change_abs"] == "30"

    with pytest.raises(FileExistsError):
        write_freguesia_trajectory_csv(rows, path)
