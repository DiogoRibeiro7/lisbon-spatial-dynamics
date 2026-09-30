"""Tests for the v1 study release build contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.study_v1 import (
    STUDY_V1_VERSION,
    StudyV1BuildError,
    StudyV1Inputs,
    build_study_v1,
)


def _inputs(tmp_path: Path) -> StudyV1Inputs:
    paths = {
        "housing_snapshot": tmp_path / "housing.json",
        "rnal_snapshot": tmp_path / "rnal.json",
        "census_archive": tmp_path / "census.zip",
        "reference_csv": tmp_path / "reference.csv",
        "reference_geojson": tmp_path / "reference.geojson",
        "model_config": tmp_path / "models.toml",
    }
    for path in paths.values():
        path.write_bytes(b"placeholder")

    return StudyV1Inputs(**paths)


def test_study_v1_version_is_stable_release() -> None:
    assert STUDY_V1_VERSION == "1.0.0"


def test_missing_input_fails_before_creating_output(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs.rnal_snapshot.unlink()
    output = tmp_path / "output"

    with pytest.raises(StudyV1BuildError, match="missing v1 study input files"):
        build_study_v1(inputs, output)

    assert not output.exists()


def test_existing_output_root_is_rejected(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    output = tmp_path / "output"
    output.mkdir()

    with pytest.raises(FileExistsError):
        build_study_v1(inputs, output)


def test_invalid_release_parameters_are_rejected(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)

    with pytest.raises(ValueError, match="expected_freguesias"):
        build_study_v1(inputs, tmp_path / "a", expected_freguesias=0)

    with pytest.raises(ValueError, match="permutations"):
        build_study_v1(inputs, tmp_path / "b", permutations=-1)

    with pytest.raises(ValueError, match="local_alpha"):
        build_study_v1(inputs, tmp_path / "c", local_alpha=1.0)
