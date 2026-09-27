"""Tests for housing temporal normalization and change metrics."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.panels.temporal import (
    CHANGE_COLUMNS,
    HousingTimeError,
    build_housing_change_panel,
    parse_ine_quarter,
    write_housing_change_csv,
)


def _row(period: str, value: str | None) -> HousingPanelRow:
    return HousingPanelRow(
        period_code=period,
        freguesia_id="110654",
        freguesia_name="Alvalade",
        indicator_code="0012234",
        source_geography_code="1A0110654",
        source_geography_name="Alvalade",
        category_code="H1",
        category_name="Total",
        value_eur_m2=None if value is None else Decimal(value),
    )


def test_parse_ine_quarter_is_strict() -> None:
    period = parse_ine_quarter("1.º Trimestre de 2026")

    assert period.year == 2026
    assert period.quarter == 1
    assert period.period_end.isoformat() == "2026-03-31"

    with pytest.raises(HousingTimeError):
        parse_ine_quarter("Q1 2026")


def test_change_panel_computes_qoq_and_yoy() -> None:
    rows = (
        _row("1.º Trimestre de 2025", "4000"),
        _row("4.º Trimestre de 2025", "4400"),
        _row("1.º Trimestre de 2026", "4600"),
    )

    result = build_housing_change_panel(rows)
    latest = result[-1]

    assert latest.qoq_abs_eur_m2 == Decimal("200")
    assert latest.qoq_pct == Decimal("200") / Decimal("4400") * Decimal("100")
    assert latest.yoy_abs_eur_m2 == Decimal("600")
    assert latest.yoy_pct == Decimal("15")


def test_missing_value_propagates_to_change_metrics() -> None:
    rows = (
        _row("4.º Trimestre de 2025", "4400"),
        _row("1.º Trimestre de 2026", None),
    )

    latest = build_housing_change_panel(rows)[-1]

    assert latest.value_eur_m2 is None
    assert latest.qoq_abs_eur_m2 is None
    assert latest.qoq_pct is None


def test_duplicate_quarter_for_freguesia_is_rejected() -> None:
    rows = (
        _row("1.º Trimestre de 2026", "4500"),
        _row("1.º Trimestre de 2026", "4600"),
    )

    with pytest.raises(HousingTimeError, match="duplicate quarter"):
        build_housing_change_panel(rows)


def test_write_change_panel_csv(tmp_path: Path) -> None:
    rows = build_housing_change_panel(
        (
            _row("1.º Trimestre de 2025", "4000"),
            _row("1.º Trimestre de 2026", "4600"),
        )
    )
    path = tmp_path / "changes.csv"

    write_housing_change_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == CHANGE_COLUMNS
    assert table[-1]["year"] == "2026"
    assert table[-1]["quarter"] == "1"
    assert table[-1]["period_end"] == "2026-03-31"
    assert table[-1]["yoy_pct"] == "15"
