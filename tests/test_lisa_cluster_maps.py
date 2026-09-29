"""Tests for Local Moran cluster maps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    ClusterClass,
    LocalMoranObservation,
    LocalMoranResult,
    MetricName,
)
from lisbon_spatial_dynamics.spatial.lisa_cluster_maps import (
    LISAClusterMapError,
    LISAMapBundle,
    load_local_morans_json,
    write_lisa_cluster_maps,
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


def _trajectory() -> TrajectoryMapData:
    return TrajectoryMapData(
        baseline_year=2019,
        latest_year=2025,
        features=(
            TrajectoryMapFeature("a", "A", 10.0, 20.0, _square(0.0, 1.0)),
            TrajectoryMapFeature("b", "B", 15.0, 25.0, _square(1.0, 2.0)),
        ),
    )


def _observation(
    metric: MetricName,
    freguesia_id: str,
    name: str,
    cluster_class: ClusterClass,
) -> LocalMoranObservation:
    return LocalMoranObservation(
        metric=metric,
        freguesia_id=freguesia_id,
        freguesia_name=name,
        value=10.0,
        standardized_value=1.0,
        spatial_lag_standardized=1.0,
        local_i=1.0,
        neighbor_count=1,
        permutation_p_two_sided=0.01,
        fdr_q=0.02,
        significant_fdr=cluster_class in {"HH", "LL", "HL", "LH"},
        quadrant="HH",
        cluster_class=cluster_class,
        status="ok",
    )


def _result(metric: MetricName) -> LocalMoranResult:
    return LocalMoranResult(
        metric=metric,
        baseline_year=2019,
        latest_year=2025,
        alpha=0.05,
        permutations=999,
        seed=42,
        total_freguesias=2,
        complete_cases=2,
        observations=(
            _observation(metric, "a", "A", "HH"),
            _observation(metric, "b", "B", "not_significant"),
        ),
    )


def test_renderer_writes_two_cluster_maps(tmp_path: Path) -> None:
    bundle = LISAMapBundle(
        housing=_result("housing_change_pct"),
        rnal=_result("rnal_active_change_pct"),
    )

    housing, rnal = write_lisa_cluster_maps(
        _trajectory(),
        bundle,
        tmp_path,
    )

    assert housing.name == "housing_lisa_clusters.png"
    assert rnal.name == "rnal_lisa_clusters.png"
    assert housing.stat().st_size > 0
    assert rnal.stat().st_size > 0

    with pytest.raises(FileExistsError):
        write_lisa_cluster_maps(_trajectory(), bundle, tmp_path)


def test_window_mismatch_is_rejected(tmp_path: Path) -> None:
    result = _result("housing_change_pct")
    mismatched = LocalMoranResult(
        metric=result.metric,
        baseline_year=2020,
        latest_year=result.latest_year,
        alpha=result.alpha,
        permutations=result.permutations,
        seed=result.seed,
        total_freguesias=result.total_freguesias,
        complete_cases=result.complete_cases,
        observations=result.observations,
    )

    bundle = LISAMapBundle(
        housing=mismatched,
        rnal=_result("rnal_active_change_pct"),
    )

    with pytest.raises(LISAClusterMapError, match="comparison window"):
        write_lisa_cluster_maps(_trajectory(), bundle, tmp_path)


def test_name_mismatch_is_rejected(tmp_path: Path) -> None:
    result = _result("housing_change_pct")
    first = result.observations[0]
    bad_observation = LocalMoranObservation(
        metric=first.metric,
        freguesia_id=first.freguesia_id,
        freguesia_name="Wrong",
        value=first.value,
        standardized_value=first.standardized_value,
        spatial_lag_standardized=first.spatial_lag_standardized,
        local_i=first.local_i,
        neighbor_count=first.neighbor_count,
        permutation_p_two_sided=first.permutation_p_two_sided,
        fdr_q=first.fdr_q,
        significant_fdr=first.significant_fdr,
        quadrant=first.quadrant,
        cluster_class=first.cluster_class,
        status=first.status,
    )
    bad_result = LocalMoranResult(
        metric=result.metric,
        baseline_year=result.baseline_year,
        latest_year=result.latest_year,
        alpha=result.alpha,
        permutations=result.permutations,
        seed=result.seed,
        total_freguesias=result.total_freguesias,
        complete_cases=result.complete_cases,
        observations=(bad_observation, result.observations[1]),
    )

    bundle = LISAMapBundle(
        housing=bad_result,
        rnal=_result("rnal_active_change_pct"),
    )

    with pytest.raises(LISAClusterMapError, match="name mismatch"):
        write_lisa_cluster_maps(_trajectory(), bundle, tmp_path)


def test_loader_requires_both_metrics(tmp_path: Path) -> None:
    path = tmp_path / "local.json"
    path.write_text(
        json.dumps(
            {
                "analysis": "local_morans_i",
                "results": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(LISAClusterMapError, match="metric set mismatch"):
        load_local_morans_json(path)


def test_metric_type_helper_is_literal_safe() -> None:
    metric = cast(MetricName, "housing_change_pct")
    assert _result(metric).metric == "housing_change_pct"
