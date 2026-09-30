"""Tests for the annual housing + RNAL pressure research panel."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.annual import AnnualUrbanRow
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    ANNUAL_HOUSING_PRESSURE_COLUMNS,
    AnnualHousingPressureError,
    build_annual_housing_pressure_panel,
    write_annual_housing_pressure_csv,
)
from lisbon_spatial_dynamics.panels.rnal_pressure_annual import (
    AnnualRNALPressureRow,
)


def _housing(
    freguesia_id: str = "110654",
    name: str = "Alvalade",
) -> AnnualUrbanRow:
    return AnnualUrbanRow(
        year=2025,
        baseline_year=2019,
        period_code="4.º Trimestre de 2025",
        period_end=date(2025, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        flow_quarters_observed=4,
        housing_value_eur_m2=Decimal("6000"),
        housing_yoy_abs_eur_m2=Decimal("200"),
        housing_yoy_pct=Decimal("3.45"),
        housing_change_from_baseline_abs_eur_m2=Decimal("2000"),
        housing_change_from_baseline_pct=Decimal("50"),
        rnal_registrations_year=10,
        rnal_cessations_year=3,
        rnal_net_registrations_year=7,
        rnal_active_registrations_year_end=130,
        rnal_active_change_from_baseline_abs=30,
        rnal_active_change_from_baseline_pct=Decimal("30"),
        rnal_active_beds_known_year_end=260,
        rnal_active_beds_missing_year_end=1,
        rnal_active_users_known_year_end=390,
        rnal_active_users_missing_year_end=2,
    )


def _pressure(
    freguesia_id: str = "110654",
    name: str = "Alvalade",
) -> AnnualRNALPressureRow:
    return AnnualRNALPressureRow(
        year=2025,
        baseline_year=2019,
        period_code="4.º Trimestre de 2025",
        period_end=date(2025, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        population_reference_year=2021,
        population_resident=10_000,
        population_density_per_km2=Decimal("5000"),
        flow_quarters_observed=4,
        registrations_year=10,
        cessations_year=3,
        net_registrations_year=7,
        registrations_year_per_1000=Decimal("1"),
        cessations_year_per_1000=Decimal("0.3"),
        net_registrations_year_per_1000=Decimal("0.7"),
        active_registrations_year_end=130,
        active_registrations_per_1000_year_end=Decimal("13"),
        active_registrations_per_1000_change_from_baseline=Decimal("3"),
        active_beds_known_year_end=260,
        active_beds_missing_year_end=1,
        active_beds_known_per_1000_year_end=Decimal("26"),
        active_beds_known_per_1000_change_from_baseline=Decimal("6"),
        active_users_known_year_end=390,
        active_users_missing_year_end=2,
        active_users_known_per_1000_year_end=Decimal("39"),
        active_users_known_per_1000_change_from_baseline=Decimal("9"),
    )


def test_join_preserves_housing_and_normalized_pressure() -> None:
    rows = build_annual_housing_pressure_panel(
        (_housing(),),
        (_pressure(),),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.housing_value_eur_m2 == Decimal("6000")
    assert row.housing_change_from_baseline_pct == Decimal("50")
    assert row.rnal_active_registrations_per_1000_year_end == Decimal("13")
    assert row.rnal_active_registrations_per_1000_change_from_baseline == Decimal("3")
    assert row.population_reference_year == 2021


def test_key_set_mismatch_is_rejected() -> None:
    housing = (_housing(), _housing("110656", "Arroios"))

    with pytest.raises(AnnualHousingPressureError, match="key sets differ"):
        build_annual_housing_pressure_panel(
            housing,
            (_pressure(),),
        )


def test_raw_rnal_disagreement_is_rejected() -> None:
    pressure = _pressure()
    bad_pressure = AnnualRNALPressureRow(
        year=pressure.year,
        baseline_year=pressure.baseline_year,
        period_code=pressure.period_code,
        period_end=pressure.period_end,
        freguesia_id=pressure.freguesia_id,
        freguesia_name=pressure.freguesia_name,
        population_reference_year=pressure.population_reference_year,
        population_resident=pressure.population_resident,
        population_density_per_km2=pressure.population_density_per_km2,
        flow_quarters_observed=pressure.flow_quarters_observed,
        registrations_year=pressure.registrations_year,
        cessations_year=pressure.cessations_year,
        net_registrations_year=pressure.net_registrations_year,
        registrations_year_per_1000=pressure.registrations_year_per_1000,
        cessations_year_per_1000=pressure.cessations_year_per_1000,
        net_registrations_year_per_1000=pressure.net_registrations_year_per_1000,
        active_registrations_year_end=999,
        active_registrations_per_1000_year_end=pressure.active_registrations_per_1000_year_end,
        active_registrations_per_1000_change_from_baseline=pressure.active_registrations_per_1000_change_from_baseline,
        active_beds_known_year_end=pressure.active_beds_known_year_end,
        active_beds_missing_year_end=pressure.active_beds_missing_year_end,
        active_beds_known_per_1000_year_end=pressure.active_beds_known_per_1000_year_end,
        active_beds_known_per_1000_change_from_baseline=pressure.active_beds_known_per_1000_change_from_baseline,
        active_users_known_year_end=pressure.active_users_known_year_end,
        active_users_missing_year_end=pressure.active_users_missing_year_end,
        active_users_known_per_1000_year_end=pressure.active_users_known_per_1000_year_end,
        active_users_known_per_1000_change_from_baseline=pressure.active_users_known_per_1000_change_from_baseline,
    )

    with pytest.raises(AnnualHousingPressureError, match="raw RNAL"):
        build_annual_housing_pressure_panel(
            (_housing(),),
            (bad_pressure,),
        )


def test_shared_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(AnnualHousingPressureError, match="freguesia_name mismatch"):
        build_annual_housing_pressure_panel(
            (_housing(),),
            (_pressure(name="Wrong"),),
        )


def test_writer_uses_stable_contract_and_is_immutable(tmp_path: Path) -> None:
    rows = build_annual_housing_pressure_panel(
        (_housing(),),
        (_pressure(),),
    )
    path = tmp_path / "annual_research.csv"

    write_annual_housing_pressure_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == ANNUAL_HOUSING_PRESSURE_COLUMNS
    assert table[0]["housing_change_from_baseline_pct"] == "50"
    assert table[0]["rnal_active_registrations_per_1000_year_end"] == "13"

    with pytest.raises(FileExistsError):
        write_annual_housing_pressure_csv(rows, path)
