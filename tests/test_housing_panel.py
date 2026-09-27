"""Tests for the canonical Lisbon housing-freguesia panel."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.housing import (
    CURRENT_HOUSING_INDICATOR,
    PANEL_COLUMNS,
    FreguesiaIndexRow,
    HousingPanelCoverageError,
    HousingPanelError,
    build_current_housing_freguesia_panel,
    load_freguesia_index,
    write_housing_panel_csv,
)
from lisbon_spatial_dynamics.transformations.housing import HousingObservation


def _reference() -> tuple[FreguesiaIndexRow, ...]:
    return (
        FreguesiaIndexRow(freguesia_id="110654", name="Alvalade"),
        FreguesiaIndexRow(freguesia_id="110656", name="Arroios"),
    )


def _observations() -> tuple[HousingObservation, ...]:
    return (
        HousingObservation(
            indicator_code=CURRENT_HOUSING_INDICATOR,
            period_code="1.º Trimestre de 2026",
            geography_code="1A0110656",
            geography_name="Arroios",
            category_code="H1",
            category_name="Total",
            value_eur_m2=Decimal("4776"),
        ),
        HousingObservation(
            indicator_code=CURRENT_HOUSING_INDICATOR,
            period_code="1.º Trimestre de 2026",
            geography_code="1A0110654",
            geography_name="Alvalade",
            category_code="H1",
            category_name="Total",
            value_eur_m2=None,
        ),
        HousingObservation(
            indicator_code=CURRENT_HOUSING_INDICATOR,
            period_code="1.º Trimestre de 2026",
            geography_code="1A01106",
            geography_name="Lisboa",
            category_code="H1",
            category_name="Total",
            value_eur_m2=Decimal("5082"),
        ),
    )


def test_join_matches_suffix_but_validates_name() -> None:
    """INE geography codes should map through known DTMNFR suffixes only."""
    rows = build_current_housing_freguesia_panel(
        _observations(),
        _reference(),
    )

    assert [row.freguesia_id for row in rows] == ["110654", "110656"]
    assert rows[0].source_geography_code == "1A0110654"
    assert rows[0].value_eur_m2 is None
    assert rows[1].value_eur_m2 == Decimal("4776")


def test_name_mismatch_fails_join() -> None:
    """A suffix match must not override disagreement in official labels."""
    observations = list(_observations())
    observations[0] = HousingObservation(
        indicator_code=CURRENT_HOUSING_INDICATOR,
        period_code="1.º Trimestre de 2026",
        geography_code="1A0110656",
        geography_name="Not Arroios",
        category_code="H1",
        category_name="Total",
        value_eur_m2=Decimal("4776"),
    )

    with pytest.raises(HousingPanelError, match="name mismatch"):
        build_current_housing_freguesia_panel(observations, _reference())


def test_incomplete_period_fails_coverage() -> None:
    """A missing freguesia record is different from a published null value."""
    observations = (_observations()[0],)

    with pytest.raises(HousingPanelCoverageError, match="110654"):
        build_current_housing_freguesia_panel(observations, _reference())


def test_unrelated_geographies_are_ignored() -> None:
    """Municipality and non-Lisbon records must not enter the freguesia panel."""
    rows = build_current_housing_freguesia_panel(
        _observations(),
        _reference(),
    )

    assert {row.source_geography_name for row in rows} == {"Alvalade", "Arroios"}


def test_load_reference_index_validates_schema_and_count(tmp_path: Path) -> None:
    """The join should consume the stable canonical CSV contract."""
    path = tmp_path / "reference.csv"
    path.write_text(
        "freguesia_id,name\n110654,Alvalade\n110656,Arroios\n",
        encoding="utf-8",
    )

    rows = load_freguesia_index(path, expected_count=2)

    assert rows == _reference()


def test_write_panel_csv_is_stable_and_immutable(tmp_path: Path) -> None:
    """Panel output should use stable columns and preserve null values."""
    rows = build_current_housing_freguesia_panel(
        _observations(),
        _reference(),
    )
    path = tmp_path / "panel.csv"

    write_housing_panel_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == PANEL_COLUMNS
    assert table[0]["freguesia_id"] == "110654"
    assert table[0]["value_eur_m2"] == ""

    with pytest.raises(FileExistsError):
        write_housing_panel_csv(rows, path)
