"""Tests for the annual Lisbon urban-change panel."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.annual import (
    ANNUAL_PANEL_COLUMNS,
    AnnualPanelError,
    build_annual_urban_panel,
    write_annual_urban_csv,
)
from lisbon_spatial_dynamics.panels.urban import UrbanChangeRow


def _row(
    year: int,
    quarter: int,
    *,
    housing: str,
    active: int,
    registrations: int = 1,
    cessations: int = 0,
) -> UrbanChangeRow:
    month = quarter * 3
    day = 31 if month in {3, 12} else 30
    return UrbanChangeRow(
        period_code=f"{quarter}.º Trimestre de {year}",
        year=year,
        quarter=quarter,
        period_end=date(year, month, day),
        freguesia_id="110654",
        freguesia_name="Alvalade",
        housing_value_eur_m2=Decimal(housing),
        housing_qoq_abs_eur_m2=None,
        housing_qoq_pct=None,
        housing_yoy_abs_eur_m2=(
            Decimal("500") if year > 2019 and quarter == 4 else None
        ),
        housing_yoy_pct=(
            Decimal("10") if year > 2019 and quarter == 4 else None
        ),
        rnal_registrations=registrations,
        rnal_cessations=cessations,
        rnal_net_registrations=registrations - cessations,
        rnal_active_registrations=active,
        rnal_active_beds_known=active * 2,
        rnal_active_beds_missing=0,
        rnal_active_users_known=active * 3,
        rnal_active_users_missing=0,
    )


def test_annual_panel_uses_q4_and_complete_year_flows() -> None:
    rows = (
        _row(2019, 4, housing="4000", active=100),
        _row(2020, 1, housing="4100", active=101, registrations=3),
        _row(2020, 2, housing="4200", active=103, registrations=4),
        _row(2020, 3, housing="4300", active=105, registrations=5),
        _row(2020, 4, housing="4500", active=108, registrations=6, cessations=1),
        _row(2021, 1, housing="4600", active=110),
    )

    annual = build_annual_urban_panel(rows)

    assert [row.year for row in annual] == [2019, 2020]
    baseline, year_2020 = annual

    assert baseline.flow_quarters_observed == 1
    assert baseline.rnal_registrations_year is None
    assert baseline.housing_change_from_baseline_abs_eur_m2 == Decimal("0")

    assert year_2020.flow_quarters_observed == 4
    assert year_2020.rnal_registrations_year == 18
    assert year_2020.rnal_cessations_year == 1
    assert year_2020.rnal_net_registrations_year == 17
    assert year_2020.housing_change_from_baseline_abs_eur_m2 == Decimal("500")
    assert year_2020.housing_change_from_baseline_pct == Decimal("12.5")
    assert year_2020.rnal_active_change_from_baseline_abs == 8
    assert year_2020.rnal_active_change_from_baseline_pct == Decimal("8")


def test_year_without_q4_is_excluded() -> None:
    rows = (
        _row(2019, 4, housing="4000", active=100),
        _row(2020, 1, housing="4100", active=101),
        _row(2020, 2, housing="4200", active=102),
    )

    annual = build_annual_urban_panel(rows)

    assert [row.year for row in annual] == [2019]


def test_partial_year_with_q4_keeps_stock_but_nulls_flows() -> None:
    rows = (
        _row(2019, 4, housing="4000", active=100),
        _row(2020, 3, housing="4300", active=105),
        _row(2020, 4, housing="4500", active=108),
    )

    annual = build_annual_urban_panel(rows)
    year_2020 = annual[-1]

    assert year_2020.flow_quarters_observed == 2
    assert year_2020.rnal_registrations_year is None
    assert year_2020.rnal_cessations_year is None
    assert year_2020.rnal_active_registrations_year_end == 108


def test_duplicate_quarter_is_rejected() -> None:
    rows = (
        _row(2019, 4, housing="4000", active=100),
        _row(2019, 4, housing="4100", active=101),
    )

    with pytest.raises(AnnualPanelError, match="duplicate quarter"):
        build_annual_urban_panel(rows)


def test_zero_rnal_baseline_has_no_percentage_change() -> None:
    rows = (
        _row(2019, 4, housing="4000", active=0),
        _row(2020, 4, housing="4500", active=5),
    )

    annual = build_annual_urban_panel(rows)

    assert annual[-1].rnal_active_change_from_baseline_abs == 5
    assert annual[-1].rnal_active_change_from_baseline_pct is None


def test_writer_uses_stable_contract(tmp_path: Path) -> None:
    rows = build_annual_urban_panel(
        (
            _row(2019, 4, housing="4000", active=100),
            _row(2020, 4, housing="4500", active=108),
        )
    )
    path = tmp_path / "annual.csv"

    write_annual_urban_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == ANNUAL_PANEL_COLUMNS
    assert table[0]["year"] == "2019"
    assert table[1]["housing_change_from_baseline_pct"] == "12.5"

    with pytest.raises(FileExistsError):
        write_annual_urban_csv(rows, path)
