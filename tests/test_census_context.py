"""Tests for Censos 2021 neighbourhood context aggregation."""

from __future__ import annotations

import csv
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.spatial.annual_maps import ReferenceFeature
from lisbon_spatial_dynamics.transformations.census_context import (
    CENSUS_CONTEXT_COLUMNS,
    CensusContextError,
    build_census2021_context,
    build_census2021_context_geojson,
    write_census2021_context_csv,
)

_HEADER = ";".join(
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


def _archive(path: Path) -> None:
    rows = [
        _HEADER,
        "110654;100;10;2;1;30;28;20;8;10;8;40;10;10;60;20",
        "110654;50;5;1;1;10;10;8;2;5;2;20;5;5;30;10",
        "110656;200;20;4;2;50;48;40;8;20;15;80;20;20;120;40",
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("FS2021SubSeccao.csv", "\n".join(rows) + "\n")


def _reference_csv(path: Path) -> None:
    path.write_text(
        "freguesia_id,name\n110654,Alvalade\n110656,Arroios\n",
        encoding="utf-8",
    )


def _reference_geojson() -> tuple[ReferenceFeature, ...]:
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
    }
    return (
        ReferenceFeature(
            "110654",
            "Alvalade",
            {"freguesia_id": "110654", "name": "Alvalade"},
            geometry,
        ),
        ReferenceFeature(
            "110656",
            "Arroios",
            {"freguesia_id": "110656", "name": "Arroios"},
            geometry,
        ),
    )


def test_context_aggregates_counts_and_derives_shares(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"
    _archive(archive)
    _reference_csv(reference)

    rows = build_census2021_context(
        archive,
        reference,
        expected_count=2,
    )

    alvalade = rows[0]
    assert alvalade.population_resident == 150
    assert alvalade.classic_buildings == 15
    assert alvalade.age_65_plus == 30
    assert alvalade.age_65_plus_pct == Decimal("20")
    assert alvalade.rented_share_pct == Decimal("10") / Decimal("28") * Decimal("100")
    assert alvalade.pre1945_building_share_pct == Decimal("20")
    assert alvalade.dwellings_per_classic_building == Decimal("40") / Decimal("15")


def test_age_bands_must_sum_to_population(tmp_path: Path) -> None:
    archive = tmp_path / "bad.zip"
    reference = tmp_path / "reference.csv"
    _reference_csv(reference)

    bad = [
        _HEADER,
        "110654;100;10;2;1;30;28;20;8;10;8;40;10;10;50;20",
        "110656;200;20;4;2;50;48;40;8;20;15;80;20;20;120;40",
    ]
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("bad.csv", "\n".join(bad) + "\n")

    with pytest.raises(CensusContextError, match="age bands"):
        build_census2021_context(
            archive,
            reference,
            expected_count=2,
        )


def test_context_csv_and_geojson_contracts(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"
    _archive(archive)
    _reference_csv(reference)

    rows = build_census2021_context(
        archive,
        reference,
        expected_count=2,
    )
    csv_path = tmp_path / "context.csv"
    write_census2021_context_csv(rows, csv_path)

    with csv_path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == CENSUS_CONTEXT_COLUMNS
    assert table[0]["freguesia_id"] == "110654"

    document = build_census2021_context_geojson(
        rows,
        _reference_geojson(),
    )
    assert document["feature_count"] == 2
    features = document["features"]
    assert isinstance(features, list)
    assert features[0]["properties"]["age_65_plus_pct"] == 20.0
