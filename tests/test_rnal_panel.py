"""Tests for the longitudinal RNAL freguesia panel."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.housing import FreguesiaIndexRow
from lisbon_spatial_dynamics.panels.rnal import (
    RNAL_PANEL_COLUMNS,
    RNALPanelError,
    RNALRecord,
    build_rnal_quarter_panel,
    load_analysis_quarters,
    load_rnal_snapshot,
    parse_rnal_date,
    write_rnal_quarter_csv,
)
from lisbon_spatial_dynamics.panels.temporal import QuarterPeriod


def _reference() -> tuple[FreguesiaIndexRow, ...]:
    return (
        FreguesiaIndexRow("110654", "Alvalade"),
        FreguesiaIndexRow("110656", "Arroios"),
    )


def _periods() -> tuple[QuarterPeriod, ...]:
    return (
        QuarterPeriod(2019, 4, "4.º Trimestre de 2019"),
        QuarterPeriod(2020, 1, "1.º Trimestre de 2020"),
    )


def test_parse_rnal_date_accepts_explicit_supported_forms() -> None:
    assert parse_rnal_date("2020-01-31") == date(2020, 1, 31)
    assert parse_rnal_date("2020-01-31T12:30:00") == date(2020, 1, 31)
    assert parse_rnal_date("31-01-2020") == date(2020, 1, 31)
    assert parse_rnal_date("31/01/2020") == date(2020, 1, 31)

    with pytest.raises(RNALPanelError, match="unsupported RNAL date"):
        parse_rnal_date("January 31, 2020")


def test_load_snapshot_parses_dates_capacity_and_cessation(tmp_path: Path) -> None:
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "NrRegisto": "1/AL",
                        "DataRegisto": "2019-10-15",
                        "CessadoEm": "2020-02-10",
                        "DTMNFR": "110654",
                        "Freguesia": "Alvalade",
                        "Modalidade": "Apartamento",
                        "NrCamas": "2",
                        "NrUtentes": "4",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    records = load_rnal_snapshot(path)

    assert records[0].registered_on == date(2019, 10, 15)
    assert records[0].ceased_on == date(2020, 2, 10)
    assert records[0].beds == 2
    assert records[0].users == 4


def test_quarter_panel_reconstructs_flows_and_stock() -> None:
    records = (
        RNALRecord(
            registration_id="1/AL",
            registered_on=date(2019, 10, 15),
            ceased_on=date(2020, 2, 10),
            freguesia_id="110654",
            freguesia_name="Alvalade",
            modality="Apartamento",
            beds=2,
            users=4,
        ),
        RNALRecord(
            registration_id="2/AL",
            registered_on=date(2020, 1, 10),
            ceased_on=None,
            freguesia_id="110654",
            freguesia_name="Alvalade",
            modality="Apartamento",
            beds=None,
            users=3,
        ),
        RNALRecord(
            registration_id="3/AL",
            registered_on=date(2018, 6, 1),
            ceased_on=None,
            freguesia_id="110656",
            freguesia_name="Arroios",
            modality="Quarto",
            beds=1,
            users=None,
        ),
    )

    rows = build_rnal_quarter_panel(records, _reference(), _periods())
    q4_alvalade = next(
        row
        for row in rows
        if row.period_code == "4.º Trimestre de 2019" and row.freguesia_id == "110654"
    )
    q1_alvalade = next(
        row
        for row in rows
        if row.period_code == "1.º Trimestre de 2020" and row.freguesia_id == "110654"
    )

    assert q4_alvalade.registrations == 1
    assert q4_alvalade.cessations == 0
    assert q4_alvalade.active_registrations == 1
    assert q4_alvalade.active_beds_known == 2

    assert q1_alvalade.registrations == 1
    assert q1_alvalade.cessations == 1
    assert q1_alvalade.net_registrations == 0
    assert q1_alvalade.active_registrations == 1
    assert q1_alvalade.active_beds_known == 0
    assert q1_alvalade.active_beds_missing == 1
    assert q1_alvalade.active_users_known == 3


def test_cessation_on_period_end_is_not_active() -> None:
    record = RNALRecord(
        registration_id="1/AL",
        registered_on=date(2019, 10, 1),
        ceased_on=date(2019, 12, 31),
        freguesia_id="110654",
        freguesia_name="Alvalade",
        modality="Apartamento",
        beds=2,
        users=4,
    )

    rows = build_rnal_quarter_panel((record,), _reference(), (_periods()[0],))
    alvalade = next(row for row in rows if row.freguesia_id == "110654")

    assert alvalade.cessations == 1
    assert alvalade.active_registrations == 0


def test_reference_name_mismatch_is_rejected() -> None:
    record = RNALRecord(
        registration_id="1/AL",
        registered_on=date(2019, 10, 1),
        ceased_on=None,
        freguesia_id="110654",
        freguesia_name="Wrong name",
        modality="Apartamento",
        beds=2,
        users=4,
    )

    with pytest.raises(RNALPanelError, match="name mismatch"):
        build_rnal_quarter_panel((record,), _reference(), _periods())


def test_load_analysis_quarters_deduplicates_housing_rows(tmp_path: Path) -> None:
    path = tmp_path / "housing_changes.csv"
    path.write_text(
        "period_code,year,quarter,period_end\n"
        "4.º Trimestre de 2019,2019,4,2019-12-31\n"
        "4.º Trimestre de 2019,2019,4,2019-12-31\n"
        "1.º Trimestre de 2020,2020,1,2020-03-31\n",
        encoding="utf-8",
    )

    periods = load_analysis_quarters(path)

    assert [(period.year, period.quarter) for period in periods] == [
        (2019, 4),
        (2020, 1),
    ]


def test_write_panel_csv_has_stable_contract(tmp_path: Path) -> None:
    rows = build_rnal_quarter_panel((), _reference(), _periods())
    path = tmp_path / "rnal.csv"

    write_rnal_quarter_csv(rows, path)

    with path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == RNAL_PANEL_COLUMNS
    assert len(table) == 4

    with pytest.raises(FileExistsError):
        write_rnal_quarter_csv(rows, path)
