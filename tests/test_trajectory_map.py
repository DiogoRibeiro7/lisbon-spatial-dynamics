"""Tests for trajectory GeoJSON export."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.trajectories import FreguesiaTrajectory
from lisbon_spatial_dynamics.spatial.annual_maps import ReferenceFeature
from lisbon_spatial_dynamics.spatial.trajectory_map import (
    TrajectoryMapError,
    build_trajectory_geojson,
    write_trajectory_geojson,
)


def _trajectory(
    freguesia_id: str,
    name: str,
    housing_change: str = "50",
) -> FreguesiaTrajectory:
    return FreguesiaTrajectory(
        freguesia_id=freguesia_id,
        freguesia_name=name,
        baseline_year=2019,
        latest_year=2025,
        years_elapsed=6,
        observed_q4_years=7,
        housing_baseline_eur_m2=Decimal("4000"),
        housing_latest_eur_m2=Decimal("6000"),
        housing_change_abs_eur_m2=Decimal("2000"),
        housing_change_pct=Decimal(housing_change),
        housing_latest_yoy_pct=Decimal("4"),
        rnal_active_baseline=100,
        rnal_active_latest=130,
        rnal_active_change_abs=30,
        rnal_active_change_pct=Decimal("30"),
        rnal_beds_known_baseline=200,
        rnal_beds_known_latest=260,
        rnal_beds_missing_latest=1,
        rnal_users_known_baseline=300,
        rnal_users_known_latest=390,
        rnal_users_missing_latest=2,
        latest_flow_quarters_observed=4,
        latest_registrations_year=10,
        latest_cessations_year=3,
        latest_net_registrations_year=7,
    )


def _reference(freguesia_id: str, name: str) -> ReferenceFeature:
    return ReferenceFeature(
        freguesia_id=freguesia_id,
        name=name,
        properties={"freguesia_id": freguesia_id, "name": name},
        geometry={
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [0, 0]]],
        },
    )


def test_trajectory_geojson_joins_exact_reference_keys() -> None:
    rows = (
        _trajectory("110654", "Alvalade"),
        _trajectory("110656", "Arroios", "25"),
    )
    reference = (
        _reference("110654", "Alvalade"),
        _reference("110656", "Arroios"),
    )

    document = build_trajectory_geojson(rows, reference)

    assert document["baseline_year"] == 2019
    assert document["latest_year"] == 2025
    assert document["feature_count"] == 2

    features = document["features"]
    assert isinstance(features, list)
    assert features[0]["properties"]["housing_change_pct"] == 50.0
    assert features[1]["properties"]["rnal_active_change_abs"] == 30


def test_trajectory_reference_key_mismatch_is_rejected() -> None:
    rows = (_trajectory("110654", "Alvalade"),)
    reference = (
        _reference("110654", "Alvalade"),
        _reference("110656", "Arroios"),
    )

    with pytest.raises(TrajectoryMapError, match="key mismatch"):
        build_trajectory_geojson(rows, reference)


def test_trajectory_name_mismatch_is_rejected() -> None:
    rows = (_trajectory("110654", "Wrong"),)
    reference = (_reference("110654", "Alvalade"),)

    with pytest.raises(TrajectoryMapError, match="name mismatch"):
        build_trajectory_geojson(rows, reference)


def test_writer_is_immutable(tmp_path: Path) -> None:
    document = build_trajectory_geojson(
        (_trajectory("110654", "Alvalade"),),
        (_reference("110654", "Alvalade"),),
    )
    path = tmp_path / "trajectory.geojson"

    write_trajectory_geojson(document, path)

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["feature_count"] == 1

    with pytest.raises(FileExistsError):
        write_trajectory_geojson(document, path)
