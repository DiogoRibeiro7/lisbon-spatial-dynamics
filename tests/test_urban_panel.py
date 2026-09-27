"""Tests for the combined Lisbon urban-change panel."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.rnal import RNALQuarterRow
from lisbon_spatial_dynamics.panels.temporal import HousingChangeRow
from lisbon_spatial_dynamics.panels.urban import (
    URBAN_PANEL_COLUMNS,
    UrbanPanelError,
    build_urban_change_panel,
    load_housing_change_csv,
    load_rnal_quarter_csv,
    write_urban_change_csv,
)


def _housing(
    freguesia_id: str = "110654",
    freguesia_name: str = "Alvalade",
) -> HousingChangeRow:
    return HousingChangeRow(
        period_code="1.º Trimestre de 2026",
        year=2026,
        quarter=1,
        period_end=date(2026, 3, 31),
        freguesia_id=freguesia_id,
        freguesia_name=freguesia_name,
        value_eur_m2=Decimal("5200"),
        qoq_abs_eur_m2=Decimal("100"),
        qoq_pct=Decimal("1.96078431372549"),
        yoy_abs_eur_m2=Decimal("500"),
        yoy_pct=Decimal("10.6382978723404"),
    )


def _rnal(
    freguesia_id: str = "110654",
    freguesia_name: str = "Alvalade",
) -> RNALQuarterRow:
    return RNALQuarterRow(
        period_code="1.º Trimestre de 2026",
        year=2026,
        quarter=1,
        period_end=date(2026, 3, 31),
        freguesia_id=freguesia_id,
        freguesia_name=freguesia_name,
        registrations=8,
        cessations=3,
        net_registrations=5,
        active_registrations=120,
        active_beds_known=250,
        active_beds_missing=2,
        active_users_known=410,
        active_users_missing=1,
    )


def test_strict_join_preserves_component_measures() -> None:
    """The combined row should preserve housing and RNAL variables unchanged."""
    rows = build_urban_change_panel((_housing(),), (_rnal(),))

    assert len(rows) == 1
    row = rows[0]
    assert row.freguesia_id == "110654"
    assert row.housing_value_eur_m2 == Decimal("5200")
    assert row.housing_yoy_pct == Decimal("10.6382978723404")
    assert row.rnal_active_registrations == 120
    assert row.rnal_net_registrations == 5


def test_missing_component_key_is_rejected() -> None:
    """The project should not silently perform a partial left/right join."""
    housing = (_housing(), _housing("110656", "Arroios"))

    with pytest.raises(UrbanPanelError, match="component panel keys differ"):
        build_urban_change_panel(housing, (_rnal(),))


def test_duplicate_component_key_is_rejected() -> None:
    """Each component must be one row per freguesia-quarter."""
    with pytest.raises(UrbanPanelError, match="duplicate housing key"):
        build_urban_change_panel((_housing(), _housing()), (_rnal(),))


def test_shared_dimension_mismatch_is_rejected() -> None:
    """Matching keys must also agree on canonical names and period metadata."""
    with pytest.raises(UrbanPanelError, match="freguesia_name mismatch"):
        build_urban_change_panel((_housing(),), (_rnal(freguesia_name="Wrong"),))


def test_csv_loaders_and_writer_use_stable_contract(tmp_path: Path) -> None:
    """CSV boundaries should round-trip into the combined contract."""
    housing_path = tmp_path / "housing.csv"
    housing_path.write_text(
        "period_code,year,quarter,period_end,freguesia_id,freguesia_name,"
        "value_eur_m2,qoq_abs_eur_m2,qoq_pct,yoy_abs_eur_m2,yoy_pct\n"
        "1.º Trimestre de 2026,2026,1,2026-03-31,110654,Alvalade,"
        "5200,100,1.96,500,10.64\n",
        encoding="utf-8",
    )

    rnal_path = tmp_path / "rnal.csv"
    rnal_path.write_text(
        "period_code,year,quarter,period_end,freguesia_id,freguesia_name,"
        "registrations,cessations,net_registrations,active_registrations,"
        "active_beds_known,active_beds_missing,active_users_known,"
        "active_users_missing\n"
        "1.º Trimestre de 2026,2026,1,2026-03-31,110654,Alvalade,"
        "8,3,5,120,250,2,410,1\n",
        encoding="utf-8",
    )

    housing = load_housing_change_csv(housing_path)
    rnal = load_rnal_quarter_csv(rnal_path)
    combined = build_urban_change_panel(housing, rnal)

    output = tmp_path / "urban.csv"
    write_urban_change_csv(combined, output)

    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert tuple(rows[0]) == URBAN_PANEL_COLUMNS
    assert rows[0]["housing_value_eur_m2"] == "5200"
    assert rows[0]["rnal_active_registrations"] == "120"

    with pytest.raises(FileExistsError):
        write_urban_change_csv(combined, output)
