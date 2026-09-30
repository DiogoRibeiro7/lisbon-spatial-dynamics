"""Tests for the Censos 2021 neighbourhood-context bundle."""

from __future__ import annotations

import csv
import json
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from lisbon_spatial_dynamics.analysis.census_context_bundle import (
    build_census2021_context_bundle,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    ANNUAL_HOUSING_PRESSURE_COLUMNS,
    AnnualHousingPressureRow,
)


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    archive = tmp_path / "census.zip"
    header = ";".join(
        (
            "DTMNFR21",
            "N_INDIVIDUOS",
            "N_EDIFICIOS_CLASSICOS",
            "N_EDIFICIOS_CONSTR_ANTES 1945",
            "N_EDIFICIOS_COM NECESSIDADES REPARAÇAO",
            "N_ALOJAMENTOS_TOTAL",
            "N_ALOJAMENTOS_FAMILIARES",
            "N_ALOJAMENTOS_ FAM_CLASS_RHABITUAL",
            "N_ALOJAMENTOS_ FAM_CLASS_VAGOS OU RESID SECUNDARIA",
            "N_RHABITUAL_PROP_OCUP",
            "N_RHABITUAL_ARRENDADOS",
            "N_AGREGADOS DOMESTICOS PRIVADOS ",
            "N_INDIVIDUOS_0A14",
            "N_INDIVIDUOS_15A24",
            "N_INDIVIDUOS_25A64",
            "N_INDIVIDUOS_65_OU_MAIS",
        )
    )
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(
            "context.csv",
            header
            + "\n110654;100;10;2;1;30;28;20;8;10;8;40;10;10;60;20\n"
            + "110656;100;10;2;1;30;28;20;8;10;8;40;10;10;60;20\n",
        )

    reference_csv = tmp_path / "reference.csv"
    reference_csv.write_text(
        "freguesia_id,name\n110654,Alvalade\n110656,Arroios\n",
        encoding="utf-8",
    )

    reference_geojson = tmp_path / "reference.geojson"
    reference_geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "id": "110654",
                        "properties": {
                            "freguesia_id": "110654",
                            "name": "Alvalade",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "id": "110656",
                        "properties": {
                            "freguesia_id": "110656",
                            "name": "Arroios",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 0]]],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    annual_panel = tmp_path / "annual.csv"
    rows = [
        _annual("110654", "Alvalade"),
        _annual("110656", "Arroios"),
    ]
    with annual_panel.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(ANNUAL_HOUSING_PRESSURE_COLUMNS)
        for row in rows:
            writer.writerow(
                [
                    (
                        value.isoformat()
                        if isinstance(value, date)
                        else format(value, "f")
                        if isinstance(value, Decimal)
                        else ""
                        if value is None
                        else value
                    )
                    for value in (
                        getattr(row, field)
                        for field in ANNUAL_HOUSING_PRESSURE_COLUMNS
                    )
                ]
            )

    return archive, reference_csv, reference_geojson, annual_panel


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


def test_bundle_writes_all_context_outputs(tmp_path: Path) -> None:
    archive, reference_csv, reference_geojson, annual_panel = _write_inputs(tmp_path)

    outputs = build_census2021_context_bundle(
        archive,
        reference_csv,
        reference_geojson,
        annual_panel,
        tmp_path / "output",
        expected_count=2,
    )

    for path in outputs.paths():
        assert path.exists()
        assert path.stat().st_size > 0

    with outputs.annual_context_csv.open(
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 2
    assert rows[0]["census_age_65_plus_pct"] == "20"
