"""Tests for Local Moran's I trajectory analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    _benjamini_hochberg,
    analyse_local_morans_i,
    write_local_morans_i_json,
)
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    TrajectoryMapFeature,
)


def _square(x0: float, x1: float) -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [x0, 0.0],
                [x1, 0.0],
                [x1, 1.0],
                [x0, 1.0],
                [x0, 0.0],
            ]
        ],
    }


def _data() -> TrajectoryMapData:
    values = (1.0, 2.0, 3.0, 4.0)
    return TrajectoryMapData(
        baseline_year=2019,
        latest_year=2025,
        features=tuple(
            TrajectoryMapFeature(
                freguesia_id=str(index),
                name=f"F{index}",
                housing_change_pct=value,
                rnal_active_change_pct=value * 10.0,
                geometry=_square(float(index), float(index + 1)),
            )
            for index, value in enumerate(values)
        ),
    )


def test_local_moran_values_for_linear_example() -> None:
    housing, rnal = analyse_local_morans_i(_data(), permutations=0)

    housing_i = [observation.local_i for observation in housing.observations]
    rnal_i = [observation.local_i for observation in rnal.observations]

    assert housing_i == pytest.approx([0.6, 0.2, 0.2, 0.6])
    assert rnal_i == pytest.approx([0.6, 0.2, 0.2, 0.6])
    assert [observation.quadrant for observation in housing.observations] == [
        "LL",
        "LL",
        "HH",
        "HH",
    ]
    assert all(
        observation.cluster_class == "not_evaluated"
        for observation in housing.observations
    )


def test_conditional_permutations_are_deterministic() -> None:
    first = analyse_local_morans_i(_data(), permutations=99, seed=13)
    second = analyse_local_morans_i(_data(), permutations=99, seed=13)
    assert first == second


def test_missing_values_can_create_islands() -> None:
    features = list(_data().features)
    features[1] = TrajectoryMapFeature(
        freguesia_id="1",
        name="F1",
        housing_change_pct=None,
        rnal_active_change_pct=20.0,
        geometry=_square(1.0, 2.0),
    )
    data = TrajectoryMapData(
        baseline_year=2019,
        latest_year=2025,
        features=tuple(features),
    )

    housing, _ = analyse_local_morans_i(data, permutations=0)
    by_id = {
        observation.freguesia_id: observation
        for observation in housing.observations
    }

    assert by_id["1"].status == "missing"
    assert by_id["0"].status == "island"
    assert by_id["0"].cluster_class == "island"


def test_benjamini_hochberg_expected_values() -> None:
    q_values = _benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
    assert q_values == pytest.approx([0.04, 0.0533333333, 0.0533333333, 0.2])


def test_json_output_contains_cluster_metadata(tmp_path: Path) -> None:
    results = analyse_local_morans_i(
        _data(),
        permutations=19,
        seed=5,
        alpha=0.10,
    )
    path = tmp_path / "local_morans_i.json"

    write_local_morans_i_json(results, path)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["weights"]["contiguity"] == "queen"
    assert document["permutation_test"]["multiple_testing"] == (
        "Benjamini-Hochberg FDR"
    )
    assert document["results"][0]["alpha"] == 0.10
    assert len(document["results"][0]["observations"]) == 4

    with pytest.raises(FileExistsError):
        write_local_morans_i_json(results, path)
