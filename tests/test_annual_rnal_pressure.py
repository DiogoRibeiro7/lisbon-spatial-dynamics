"""Tests for annual population-normalized RNAL pressure."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.rnal_pressure import RNALPressureRow
from lisbon_spatial_dynamics.panels.rnal_pressure_annual import (
    ANNUAL_RNAL_PRESSURE_COLUMNS,
    AnnualRNALPressureError,
    build_annual_rnal_pressure,
    write_annual_rnal_pressure_csv,
)


def _row(
    year: int,
    quarter: int,
    *,
    active: int,
    registrations: int = 1,
    cessations: int = 0,
) -> RNALPressureRow:
    population = 10_000
    return RNALPressureRow(
        period_code=f"{quarter}.º Trimestre de {year}",
        year=year,
        quarter=quarter,
        period_end=(
            f"{year}-03-31"
            if quarter == 1
            else f"{year}-06-30"
            if quarter == 2
            else f"{year}-09-30"
            if quarter == 3
            else f"{year}-12-31"
        ),
        freguesia_id="110654",
        freguesia_name="Alvalade",
        population_reference_year=2021,
        population_resident=population,
        population_density_per_km2=Decimal("5000"),
        registrations=registrations,
        cessations=cessations,
        net_registrations=registrations - cessations,
        active_registrations=active,
        active_beds_known=active * 2,
        active_beds_missing=1,
        active_users_known=active * 3,
        active_users_missing=2,
        registrations_per_1000=Decimal(registrations) / Decimal("10"),
        cessations_per_1000=Decimal(cessations) / Decimal("10"),
        net_registrations_per_1000=(Decimal(registrations - cessations) / Decimal("10")),
        active_registrations_per_1000=Decimal(active) / Decimal("10"),
        active_beds_known_per_1000=Decimal(active * 2) / Decimal("10"),
        active_users_known_per_1000=Decimal(active * 3) / Decimal("10"),
    )


def test_annual_pressure_uses_q4_and_complete_year_flows() -> None:
    rows = (
        _row(2019, 4, active=100),
        _row(2020, 1, active=101, registrations=3),
        _row(2020, 2, active=103, registrations=4),
        _row(2020, 3, active=105, registrations=5),
        _row(2020, 4, active=108, registrations=6, cessations=1),
    )

    annual = build_annual_rnal_pressure(rows)

    baseline, year_2020 = annual

    assert baseline.year == 2019
    assert baseline.flow_quarters_observed == 1
    assert baseline.registrations_year is None
    assert baseline.active_registrations_per_1000_year_end == Decimal("10")
    assert baseline.active_registrations_per_1000_change_from_baseline == Decimal("0")

    assert year_2020.flow_quarters_observed == 4
    assert year_2020.registrations_year == 18
    assert year_2020.cessations_year == 1
    assert year_2020.net_registrations_year == 17
    assert year_2020.registrations_year_per_1000 == Decimal("1.8")
    assert year_2020.active_registrations_per_1000_year_end == Decimal("10.8")
    assert year_2020.active_registrations_per_1000_change_from_baseline == Decimal("0.8")
    assert year_2020.active_beds_known_per_1000_change_from_baseline == Decimal("1.6")


def test_partial_year_with_q4_keeps_level_but_nulls_flows() -> None:
    rows = (
        _row(2019, 4, active=100),
        _row(2020, 3, active=105),
        _row(2020, 4, active=108),
    )

    annual = build_annual_rnal_pressure(rows)
    year_2020 = annual[-1]

    assert year_2020.flow_quarters_observed == 2
    assert year_2020.registrations_year is None
    assert year_2020.registrations_year_per_1000 is None
    assert year_2020.active_registrations_per_1000_year_end == Decimal("10.8")


def test_year_without_q4_is_excluded() -> None:
    rows = (
        _row(2019, 4, active=100),
        _row(2020, 1, active=101),
        _row(2020, 2, active=102),
    )

    annual = build_annual_rnal_pressure(rows)

    assert [row.year for row in annual] == [2019]


def test_population_reference_change_is_rejected() -> None:
    first = _row(2019, 4, active=100)
    second = RNALPressureRow(
        period_code="4.º Trimestre de 2020",
        year=2020,
        quarter=4,
        period_end="2020-12-31",
        freguesia_id="110654",
        freguesia_name="Alvalade",
        population_reference_year=2021,
        population_resident=11_000,
        population_density_per_km2=Decimal("5500"),
        registrations=1,
        cessations=0,
        net_registrations=1,
        active_registrations=110,
        active_beds_known=220,
        active_beds_missing=1,
        active_users_known=330,
        active_users_missing=2,
        registrations_per_1000=Decimal("0.090909"),
        cessations_per_1000=Decimal("0"),
        net_registrations_per_1000=Decimal("0.090909"),
        active_registrations_per_1000=Decimal("10"),
        active_beds_known_per_1000=Decimal("20"),
        active_users_known_per_1000=Decimal("30"),
    )

    with pytest.raises(
        AnnualRNALPressureError,
        match="population reference changes",
    ):
        build_annual_rnal_pressure((first, second))


def test_writer_uses_stable_contract_and_is_immutable(tmp_path: Path) -> None:
    rows = build_annual_rnal_pressure(
        (
            _row(2019, 4, active=100),
            _row(2020, 4, active=108),
        )
    )
    path = tmp_path / "annual_pressure.csv"

    write_annual_rnal_pressure_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == ANNUAL_RNAL_PRESSURE_COLUMNS
    assert table[1]["active_registrations_per_1000_year_end"] == "10.8"
    assert table[1]["active_registrations_per_1000_change_from_baseline"] == "0.8"

    with pytest.raises(FileExistsError):
        write_annual_rnal_pressure_csv(rows, path)
