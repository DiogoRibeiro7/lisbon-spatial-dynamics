"""Tests for descriptive trajectory associations."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.associations import (
    AssociationError,
    build_descriptive_association,
    write_association_json,
)
from lisbon_spatial_dynamics.analysis.trajectories import FreguesiaTrajectory


def _row(
    freguesia_id: str,
    housing_change: str | None,
    rnal_change: str | None,
) -> FreguesiaTrajectory:
    return FreguesiaTrajectory(
        freguesia_id=freguesia_id,
        freguesia_name=f"Name {freguesia_id}",
        baseline_year=2019,
        latest_year=2025,
        years_elapsed=6,
        observed_q4_years=7,
        housing_baseline_eur_m2=Decimal("4000"),
        housing_latest_eur_m2=Decimal("5000"),
        housing_change_abs_eur_m2=Decimal("1000"),
        housing_change_pct=None if housing_change is None else Decimal(housing_change),
        housing_latest_yoy_pct=Decimal("3"),
        rnal_active_baseline=100,
        rnal_active_latest=120,
        rnal_active_change_abs=20,
        rnal_active_change_pct=None if rnal_change is None else Decimal(rnal_change),
        rnal_beds_known_baseline=200,
        rnal_beds_known_latest=240,
        rnal_beds_missing_latest=0,
        rnal_users_known_baseline=300,
        rnal_users_known_latest=360,
        rnal_users_missing_latest=0,
        latest_flow_quarters_observed=4,
        latest_registrations_year=10,
        latest_cessations_year=3,
        latest_net_registrations_year=7,
    )


def test_perfect_positive_association() -> None:
    result = build_descriptive_association(
        (_row("a", "10", "1"), _row("b", "20", "2"), _row("c", "30", "3"))
    )

    assert result.complete_cases == 3
    assert result.pearson_r == pytest.approx(1.0)
    assert result.spearman_rho == pytest.approx(1.0)


def test_missing_values_are_complete_case_filtered() -> None:
    result = build_descriptive_association(
        (
            _row("a", "10", "1"),
            _row("b", None, "2"),
            _row("c", "30", None),
            _row("d", "40", "4"),
        )
    )

    assert result.total_freguesias == 4
    assert result.complete_cases == 2
    assert result.excluded_missing_housing == 1
    assert result.excluded_undefined_rnal_pct == 1


def test_constant_variable_returns_null_correlation() -> None:
    result = build_descriptive_association(
        (_row("a", "10", "5"), _row("b", "20", "5"), _row("c", "30", "5"))
    )

    assert result.pearson_r is None
    assert result.spearman_rho is None


def test_less_than_two_complete_cases_is_rejected() -> None:
    with pytest.raises(AssociationError, match="at least two"):
        build_descriptive_association((_row("a", "10", "1"), _row("b", None, "2")))


def test_json_output_is_explicit_and_immutable(tmp_path: Path) -> None:
    result = build_descriptive_association((_row("a", "10", "1"), _row("b", "20", "2")))
    path = tmp_path / "association.json"

    write_association_json(result, path)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["coverage"]["complete_cases"] == 2
    assert document["correlations"]["pearson_r"] == pytest.approx(1.0)
    assert "does not establish a causal effect" in document["interpretation"]

    with pytest.raises(FileExistsError):
        write_association_json(result, path)
