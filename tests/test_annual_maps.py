"""Tests for annual map-ready GeoJSON layers."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.panels.annual import AnnualUrbanRow
from lisbon_spatial_dynamics.spatial.annual_maps import (
    AnnualMapError,
    ReferenceFeature,
    build_annual_geojson_layers,
    load_reference_geojson,
    write_annual_geojson_layers,
)


def _reference() -> tuple[ReferenceFeature, ...]:
    geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [1, 0], [0, 0]]],
    }
    return (
        ReferenceFeature(
            freguesia_id="110654",
            name="Alvalade",
            properties={"freguesia_id": "110654", "name": "Alvalade"},
            geometry=geometry,
        ),
        ReferenceFeature(
            freguesia_id="110656",
            name="Arroios",
            properties={"freguesia_id": "110656", "name": "Arroios"},
            geometry=geometry,
        ),
    )


def _row(
    year: int,
    freguesia_id: str,
    name: str,
    value: str | None,
) -> AnnualUrbanRow:
    return AnnualUrbanRow(
        year=year,
        baseline_year=2019,
        period_code=f"4.º Trimestre de {year}",
        period_end=date(year, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        flow_quarters_observed=4 if year > 2019 else 1,
        housing_value_eur_m2=None if value is None else Decimal(value),
        housing_yoy_abs_eur_m2=None,
        housing_yoy_pct=None,
        housing_change_from_baseline_abs_eur_m2=Decimal("0"),
        housing_change_from_baseline_pct=Decimal("0"),
        rnal_registrations_year=None if year == 2019 else 10,
        rnal_cessations_year=None if year == 2019 else 2,
        rnal_net_registrations_year=None if year == 2019 else 8,
        rnal_active_registrations_year_end=100,
        rnal_active_change_from_baseline_abs=0,
        rnal_active_change_from_baseline_pct=Decimal("0"),
        rnal_active_beds_known_year_end=200,
        rnal_active_beds_missing_year_end=1,
        rnal_active_users_known_year_end=300,
        rnal_active_users_missing_year_end=2,
    )


def test_layers_join_every_year_to_exact_reference() -> None:
    rows = (
        _row(2019, "110654", "Alvalade", "4000"),
        _row(2019, "110656", "Arroios", None),
        _row(2020, "110654", "Alvalade", "4500"),
        _row(2020, "110656", "Arroios", "4200"),
    )

    layers = build_annual_geojson_layers(rows, _reference())

    assert sorted(layers) == [2019, 2020]
    assert layers[2019]["feature_count"] == 2

    features = layers[2020]["features"]
    assert isinstance(features, list)
    assert [feature["id"] for feature in features] == ["110654", "110656"]

    properties = features[0]["properties"]
    assert properties["housing_value_eur_m2"] == 4500.0
    assert properties["rnal_registrations_year"] == 10


def test_missing_freguesia_in_year_is_rejected() -> None:
    rows = (_row(2019, "110654", "Alvalade", "4000"),)

    with pytest.raises(AnnualMapError, match="key mismatch"):
        build_annual_geojson_layers(rows, _reference())


def test_name_mismatch_is_rejected() -> None:
    rows = (
        _row(2019, "110654", "Wrong", "4000"),
        _row(2019, "110656", "Arroios", "4100"),
    )

    with pytest.raises(AnnualMapError, match="name mismatch"):
        build_annual_geojson_layers(rows, _reference())


def test_reference_loader_validates_feature_ids(tmp_path: Path) -> None:
    path = tmp_path / "reference.geojson"
    document = {
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
                    "coordinates": [[[0, 0], [1, 0], [0, 0]]],
                },
            }
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")

    features = load_reference_geojson(path, expected_count=1)

    assert features[0].freguesia_id == "110654"

    document["features"][0]["id"] = "wrong"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(AnnualMapError, match="must equal"):
        load_reference_geojson(path, expected_count=1)


def test_writer_creates_one_immutable_file_per_year(tmp_path: Path) -> None:
    rows = (
        _row(2019, "110654", "Alvalade", "4000"),
        _row(2019, "110656", "Arroios", "4100"),
        _row(2020, "110654", "Alvalade", "4500"),
        _row(2020, "110656", "Arroios", "4200"),
    )
    layers = build_annual_geojson_layers(rows, _reference())

    paths = write_annual_geojson_layers(layers, tmp_path)

    assert [path.name for path in paths] == [
        "lisbon_urban_change_2019.geojson",
        "lisbon_urban_change_2020.geojson",
    ]

    document = json.loads(paths[0].read_text(encoding="utf-8"))
    assert document["year"] == 2019
    assert document["feature_count"] == 2

    with pytest.raises(FileExistsError):
        write_annual_geojson_layers(layers, tmp_path)
