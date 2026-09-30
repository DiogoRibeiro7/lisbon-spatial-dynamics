"""Tests for housing versus normalized RNAL pressure association."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.pressure_associations import (
    PressureAssociationError,
    build_pressure_association,
    write_pressure_association_json,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    AnnualHousingPressureRow,
)


def _row(
    freguesia_id: str,
    year: int,
    housing_change: str | None,
    pressure_change: str,
) -> AnnualHousingPressureRow:
    return AnnualHousingPressureRow(
        year=year,
        baseline_year=2019,
        period_code=f"4.º Trimestre de {year}",
        period_end=date(year, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=f"Name {freguesia_id}",
        population_reference_year=2021,
        population_resident=10_000,
        population_density_per_km2=Decimal("5000"),
        flow_quarters_observed=4 if year > 2019 else 1,
        housing_value_eur_m2=Decimal("5000"),
        housing_yoy_abs_eur_m2=Decimal("100") if year > 2019 else None,
        housing_yoy_pct=Decimal("2") if year > 2019 else None,
        housing_change_from_baseline_abs_eur_m2=(
            None if housing_change is None else Decimal("1000")
        ),
        housing_change_from_baseline_pct=(
            None if housing_change is None else Decimal(housing_change)
        ),
        rnal_registrations_year=10 if year > 2019 else None,
        rnal_cessations_year=3 if year > 2019 else None,
        rnal_net_registrations_year=7 if year > 2019 else None,
        rnal_registrations_year_per_1000=(
            Decimal("1") if year > 2019 else None
        ),
        rnal_cessations_year_per_1000=(
            Decimal("0.3") if year > 2019 else None
        ),
        rnal_net_registrations_year_per_1000=(
            Decimal("0.7") if year > 2019 else None
        ),
        rnal_active_registrations_year_end=100,
        rnal_active_registrations_per_1000_year_end=Decimal("10"),
        rnal_active_registrations_per_1000_change_from_baseline=Decimal(
            pressure_change
        ),
        rnal_active_beds_known_year_end=200,
        rnal_active_beds_missing_year_end=0,
        rnal_active_beds_known_per_1000_year_end=Decimal("20"),
        rnal_active_beds_known_per_1000_change_from_baseline=Decimal("2"),
        rnal_active_users_known_year_end=300,
        rnal_active_users_missing_year_end=0,
        rnal_active_users_known_per_1000_year_end=Decimal("30"),
        rnal_active_users_known_per_1000_change_from_baseline=Decimal("3"),
    )


def test_association_uses_latest_common_year() -> None:
    rows = (
        _row("a", 2019, "0", "0"),
        _row("a", 2024, "20", "2"),
        _row("a", 2025, "30", "3"),
        _row("b", 2019, "0", "0"),
        _row("b", 2024, "40", "4"),
    )

    result = build_pressure_association(rows)

    assert result.baseline_year == 2019
    assert result.latest_year == 2024
    assert result.complete_cases == 2
    assert result.pearson_r == pytest.approx(1.0)
    assert result.spearman_rho == pytest.approx(1.0)


def test_missing_housing_is_complete_case_filtered() -> None:
    rows = (
        _row("a", 2019, "0", "0"),
        _row("a", 2025, "30", "3"),
        _row("b", 2019, "0", "0"),
        _row("b", 2025, None, "4"),
        _row("c", 2019, "0", "0"),
        _row("c", 2025, "50", "5"),
    )

    result = build_pressure_association(rows)

    assert result.total_freguesias == 3
    assert result.complete_cases == 2
    assert result.excluded_missing_housing == 1


def test_mixed_baseline_years_are_rejected() -> None:
    first = _row("a", 2019, "0", "0")
    second = _row("b", 2019, "0", "0")
    second = replace(second, baseline_year=2020)

    with pytest.raises(PressureAssociationError, match="baseline year"):
        build_pressure_association((first, second))


def test_json_output_is_explicit_and_immutable(tmp_path: Path) -> None:
    rows = (
        _row("a", 2019, "0", "0"),
        _row("a", 2025, "30", "3"),
        _row("b", 2019, "0", "0"),
        _row("b", 2025, "50", "5"),
    )
    result = build_pressure_association(rows)
    path = tmp_path / "pressure_association.json"

    write_pressure_association_json(result, path)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["comparison_window"]["latest_common_year"] == 2025
    assert document["variables"]["x"] == (
        "rnal_active_registrations_per_1000_change_from_baseline"
    )
    assert document["correlations"]["pearson_r"] == pytest.approx(1.0)

    with pytest.raises(FileExistsError):
        write_pressure_association_json(result, path)
