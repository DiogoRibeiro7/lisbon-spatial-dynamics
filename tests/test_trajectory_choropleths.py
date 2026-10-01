"""Tests for trajectory choropleth rendering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    ChoroplethError,
    load_trajectory_map,
    write_trajectory_choropleths,
)


def _document() -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "baseline_year": 2019,
        "latest_year": 2025,
        "features": [
            {
                "type": "Feature",
                "id": "110654",
                "properties": {
                    "freguesia_id": "110654",
                    "name": "Alvalade",
                    "housing_change_pct": 50.0,
                    "rnal_active_change_pct": 30.0,
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
                    "housing_change_pct": None,
                    "rnal_active_change_pct": -10.0,
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[2, 0], [3, 0], [3, 1], [2, 0]]]],
                },
            },
        ],
    }


def test_loader_validates_common_window_and_metrics(tmp_path: Path) -> None:
    path = tmp_path / "trajectory.geojson"
    path.write_text(json.dumps(_document()), encoding="utf-8")

    data = load_trajectory_map(path)

    assert data.baseline_year == 2019
    assert data.latest_year == 2025
    assert len(data.features) == 2
    assert data.features[0].housing_change_pct == 50.0
    assert data.features[1].rnal_active_change_pct == -10.0


def test_loader_rejects_bad_feature_id(tmp_path: Path) -> None:
    document = _document()
    features = document["features"]
    assert isinstance(features, list)
    first = features[0]
    assert isinstance(first, dict)
    first["id"] = "wrong"

    path = tmp_path / "trajectory.geojson"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ChoroplethError, match="must equal"):
        load_trajectory_map(path)


def test_renderer_writes_two_immutable_maps(tmp_path: Path) -> None:
    path = tmp_path / "trajectory.geojson"
    path.write_text(json.dumps(_document()), encoding="utf-8")
    data = load_trajectory_map(path)

    output_directory = tmp_path / "plots"
    housing, rnal = write_trajectory_choropleths(data, output_directory)

    assert housing.name == "housing_change_pct.png"
    assert rnal.name == "rnal_active_change_pct.png"
    assert housing.stat().st_size > 0
    assert rnal.stat().st_size > 0

    with pytest.raises(FileExistsError):
        write_trajectory_choropleths(data, output_directory)


def test_renderer_rejects_metric_with_no_values(tmp_path: Path) -> None:
    document = _document()
    features = document["features"]
    assert isinstance(features, list)

    for feature in features:
        assert isinstance(feature, dict)
        properties = feature["properties"]
        assert isinstance(properties, dict)
        properties["housing_change_pct"] = None

    path = tmp_path / "trajectory.geojson"
    path.write_text(json.dumps(document), encoding="utf-8")
    data = load_trajectory_map(path)

    with pytest.raises(ChoroplethError, match="no non-missing values"):
        write_trajectory_choropleths(data, tmp_path / "plots")
