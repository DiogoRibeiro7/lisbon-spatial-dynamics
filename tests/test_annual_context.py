"""Tests for annual research panel enrichment with census context."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.annual_context import (
    ANNUAL_CONTEXT_COLUMNS,
    AnnualContextError,
    build_annual_context_panel,
    write_annual_context_csv,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    AnnualHousingPressureRow,
)
from lisbon_spatial_dynamics.transformations.census_context import (
    CensusContextRow,
)


def _annual(
    freguesia_id: str,
    name: str,
) -> AnnualHousingPressureRow:
    return AnnualHousingPressureRow(
        year=2025,
        baseline_year=2019,
        period_code="4.º Trimestre de 2025",
        period_end=date(2025, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        population_reference_year=2021,
        population_resident=100,
        population_density_per_km2=Decimal("5000"),
        flow_quarters_observed=4,
        housing_value_eur_m2=Decimal("5000"),
        housing_yoy_abs_eur_m2=Decimal("100"),
        housing_yoy_pct=Decimal("2"),
        housing_change_from_baseline_abs_eur_m2=Decimal("1000"),
        housing_change_from_baseline_pct=Decimal("25"),
        rnal_registrations_year=10,
        rnal_cessations_year=3,
        rnal_net_registrations_year=7,
        rnal_registrations_year_per_1000=Decimal("100"),
        rnal_cessations_year_per_1000=Decimal("30"),
        rnal_net_registrations_year_per_1000=Decimal("70"),
        rnal_active_registrations_year_end=20,
        rnal_active_registrations_per_1000_year_end=Decimal("200"),
        rnal_active_registrations_per_1000_change_from_baseline=Decimal("50"),
        rnal_active_beds_known_year_end=40,
        rnal_active_beds_missing_year_end=0,
        rnal_active_beds_known_per_1000_year_end=Decimal("400"),
        rnal_active_beds_known_per_1000_change_from_baseline=Decimal("100"),
        rnal_active_users_known_year_end=60,
        rnal_active_users_missing_year_end=0,
        rnal_active_users_known_per_1000_year_end=Decimal("600"),
        rnal_active_users_known_per_1000_change_from_baseline=Decimal("150"),
    )


def _context(
    freguesia_id: str,
    name: str,
) -> CensusContextRow:
    return CensusContextRow(
        freguesia_id=freguesia_id,
        freguesia_name=name,
        census_year=2021,
        population_resident=100,
        classic_buildings=10,
        pre1945_buildings=2,
        repair_needed_buildings=1,
        total_dwellings=30,
        family_dwellings=28,
        usual_residence_dwellings=20,
        vacant_or_secondary_dwellings=8,
        owner_occupied_dwellings=10,
        rented_dwellings=8,
        private_households=40,
        age_0_14=10,
        age_15_24=10,
        age_25_64=60,
        age_65_plus=20,
        age_0_14_pct=Decimal("10"),
        age_15_24_pct=Decimal("10"),
        age_25_64_pct=Decimal("60"),
        age_65_plus_pct=Decimal("20"),
        owner_occupied_share_pct=Decimal("50"),
        rented_share_pct=Decimal("40"),
        vacant_or_secondary_family_share_pct=Decimal("28.5714285714"),
        pre1945_building_share_pct=Decimal("20"),
        repair_needed_building_share_pct=Decimal("10"),
        dwellings_per_classic_building=Decimal("3"),
    )


def test_enrichment_repeats_static_context_across_annual_rows() -> None:
    annual = (
        _annual("110654", "Alvalade"),
        _annual("110656", "Arroios"),
    )
    context = (
        _context("110654", "Alvalade"),
        _context("110656", "Arroios"),
    )

    rows = build_annual_context_panel(annual, context)

    assert len(rows) == 2
    assert rows[0].census.rented_share_pct == Decimal("40")


def test_population_mismatch_is_rejected() -> None:
    census = _context("110654", "Alvalade")
    bad = replace(census, population_resident=101)

    with pytest.raises(AnnualContextError, match="population mismatch"):
        build_annual_context_panel(
            (_annual("110654", "Alvalade"),),
            (bad,),
        )


def test_writer_appends_context_columns(tmp_path: Path) -> None:
    rows = build_annual_context_panel(
        (_annual("110654", "Alvalade"),),
        (_context("110654", "Alvalade"),),
    )
    path = tmp_path / "annual_context.csv"

    write_annual_context_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == ANNUAL_CONTEXT_COLUMNS
    assert table[0]["census_rented_share_pct"] == "40"

    with pytest.raises(FileExistsError):
        write_annual_context_csv(rows, path)
