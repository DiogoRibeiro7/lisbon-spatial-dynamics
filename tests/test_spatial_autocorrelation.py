"""Tests for Global Moran's I trajectory analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    SpatialAutocorrelationError,
    analyse_global_morans_i,
    build_queen_weights,
    write_morans_i_json,
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
    return TrajectoryMapData(
        baseline_year=2019,
        latest_year=2025,
        features=tuple(
            TrajectoryMapFeature(
                freguesia_id=str(index),
                name=f"F{index}",
                housing_change_pct=float(index + 1),
                rnal_active_change_pct=float((index + 1) * 10),
                geometry=_square(float(index), float(index + 1)),
            )
            for index in range(4)
        ),
    )


def test_queen_weights_for_linear_adjacent_polygons() -> None:
    weights = build_queen_weights(_data())

    assert weights.neighbors == {
        "0": ("1",),
        "1": ("0", "2"),
        "2": ("1", "3"),
        "3": ("2",),
    }
    assert weights.edge_count == 3


def test_morans_i_matches_linear_example() -> None:
    housing, rnal = analyse_global_morans_i(
        _data(),
        permutations=99,
        seed=7,
    )

    assert housing.morans_i == pytest.approx(0.4)
    assert rnal.morans_i == pytest.approx(0.4)
    assert housing.expected_i == pytest.approx(-1.0 / 3.0)
    assert housing.permutation_p_two_sided is not None
    assert 0.0 < housing.permutation_p_two_sided <= 1.0


def test_permutation_test_is_deterministic() -> None:
    first = analyse_global_morans_i(_data(), permutations=99, seed=17)
    second = analyse_global_morans_i(_data(), permutations=99, seed=17)

    assert first == second


def test_missing_metric_values_are_reported() -> None:
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

    housing, rnal = analyse_global_morans_i(
        data,
        permutations=0,
    )

    assert housing.complete_cases == 3
    assert housing.excluded_missing == 1
    assert housing.islands == ("0",)
    assert housing.permutation_p_two_sided is None
    assert rnal.complete_cases == 4


def test_overlapping_polygons_are_rejected() -> None:
    data = TrajectoryMapData(
        baseline_year=2019,
        latest_year=2025,
        features=(
            TrajectoryMapFeature(
                "a",
                "A",
                1.0,
                1.0,
                _square(0.0, 2.0),
            ),
            TrajectoryMapFeature(
                "b",
                "B",
                2.0,
                2.0,
                _square(1.0, 3.0),
            ),
            TrajectoryMapFeature(
                "c",
                "C",
                3.0,
                3.0,
                _square(3.0, 4.0),
            ),
        ),
    )

    with pytest.raises(SpatialAutocorrelationError, match="overlap"):
        build_queen_weights(data)


def test_json_output_is_explicit_and_immutable(tmp_path: Path) -> None:
    results = analyse_global_morans_i(
        _data(),
        permutations=9,
        seed=3,
    )
    path = tmp_path / "morans_i.json"

    write_morans_i_json(results, path)

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["weights"]["contiguity"] == "queen"
    assert document["weights"]["standardization"] == "row"
    assert len(document["results"]) == 2

    with pytest.raises(FileExistsError):
        write_morans_i_json(results, path)
