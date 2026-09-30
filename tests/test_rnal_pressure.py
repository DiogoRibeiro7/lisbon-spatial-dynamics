"""Tests for population-normalized RNAL pressure metrics."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.rnal import RNALQuarterRow
from lisbon_spatial_dynamics.panels.rnal_pressure import (
    RNAL_PRESSURE_COLUMNS,
    PopulationReferenceRow,
    RNALPressureError,
    build_rnal_population_pressure,
    load_population_reference,
    write_rnal_population_pressure_csv,
)


def _rnal(
    freguesia_id: str,
    name: str,
    *,
    registrations: int,
    cessations: int,
    active: int,
    beds: int,
    users: int,
) -> RNALQuarterRow:
    return RNALQuarterRow(
        period_code="1.º Trimestre de 2025",
        year=2025,
        quarter=1,
        period_end=date(2025, 3, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        registrations=registrations,
        cessations=cessations,
        net_registrations=registrations - cessations,
        active_registrations=active,
        active_beds_known=beds,
        active_beds_missing=1,
        active_users_known=users,
        active_users_missing=2,
    )


def _population() -> tuple[PopulationReferenceRow, ...]:
    return (
        PopulationReferenceRow(
            freguesia_id="110654",
            freguesia_name="Alvalade",
            census_year=2021,
            population_resident=10_000,
            population_density_per_km2=Decimal("5000"),
        ),
        PopulationReferenceRow(
            freguesia_id="110656",
            freguesia_name="Arroios",
            census_year=2021,
            population_resident=20_000,
            population_density_per_km2=Decimal("10000"),
        ),
    )


def test_build_pressure_metrics_per_1000() -> None:
    rows = build_rnal_population_pressure(
        (
            _rnal(
                "110654",
                "Alvalade",
                registrations=10,
                cessations=2,
                active=100,
                beds=200,
                users=300,
            ),
            _rnal(
                "110656",
                "Arroios",
                registrations=20,
                cessations=5,
                active=400,
                beds=600,
                users=800,
            ),
        ),
        _population(),
    )

    alvalade = rows[0]
    arroios = rows[1]

    assert alvalade.population_reference_year == 2021
    assert alvalade.registrations_per_1000 == Decimal("1")
    assert alvalade.cessations_per_1000 == Decimal("0.2")
    assert alvalade.active_registrations_per_1000 == Decimal("10")
    assert alvalade.active_beds_known_per_1000 == Decimal("20")
    assert alvalade.active_users_known_per_1000 == Decimal("30")

    assert arroios.registrations_per_1000 == Decimal("1")
    assert arroios.active_registrations_per_1000 == Decimal("20")


def test_population_key_mismatch_is_rejected() -> None:
    rnal_rows = (
        _rnal(
            "110654",
            "Alvalade",
            registrations=1,
            cessations=0,
            active=10,
            beds=20,
            users=30,
        ),
    )

    with pytest.raises(RNALPressureError, match="key mismatch"):
        build_rnal_population_pressure(rnal_rows, _population())


def test_population_name_mismatch_is_rejected() -> None:
    population = (
        PopulationReferenceRow(
            freguesia_id="110654",
            freguesia_name="Wrong",
            census_year=2021,
            population_resident=10_000,
            population_density_per_km2=Decimal("5000"),
        ),
    )
    rnal_rows = (
        _rnal(
            "110654",
            "Alvalade",
            registrations=1,
            cessations=0,
            active=10,
            beds=20,
            users=30,
        ),
    )

    with pytest.raises(RNALPressureError, match="name mismatch"):
        build_rnal_population_pressure(rnal_rows, population)


def test_loader_requires_2021_reference(tmp_path: Path) -> None:
    path = tmp_path / "population.csv"
    path.write_text(
        "freguesia_id,freguesia_name,census_year,population_resident,"
        "population_density_per_km2\n"
        "110654,Alvalade,2020,10000,5000\n",
        encoding="utf-8",
    )

    with pytest.raises(RNALPressureError, match="unexpected census year"):
        load_population_reference(path)


def test_writer_uses_stable_contract_and_is_immutable(tmp_path: Path) -> None:
    rows = build_rnal_population_pressure(
        (
            _rnal(
                "110654",
                "Alvalade",
                registrations=10,
                cessations=2,
                active=100,
                beds=200,
                users=300,
            ),
            _rnal(
                "110656",
                "Arroios",
                registrations=20,
                cessations=5,
                active=400,
                beds=600,
                users=800,
            ),
        ),
        _population(),
    )
    path = tmp_path / "pressure.csv"

    write_rnal_population_pressure_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == RNAL_PRESSURE_COLUMNS
    assert table[0]["active_registrations_per_1000"] == "10"

    with pytest.raises(FileExistsError):
        write_rnal_population_pressure_csv(rows, path)
