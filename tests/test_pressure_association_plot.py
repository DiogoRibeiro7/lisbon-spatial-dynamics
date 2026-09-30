"""Tests for normalized pressure association scatter plot."""

from __future__ import annotations

from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.pressure_associations import (
    PressureAssociationPoint,
    PressureAssociationResult,
    write_pressure_association_scatter,
)


def test_pressure_scatter_is_written_and_immutable(tmp_path: Path) -> None:
    result = PressureAssociationResult(
        baseline_year=2019,
        latest_year=2025,
        total_freguesias=2,
        complete_cases=2,
        excluded_missing_housing=0,
        pearson_r=1.0,
        spearman_rho=1.0,
        points=(
            PressureAssociationPoint(
                "a", "A", 2019, 2025, 2021, 10_000, 30.0, 3.0
            ),
            PressureAssociationPoint(
                "b", "B", 2019, 2025, 2021, 20_000, 50.0, 5.0
            ),
        ),
    )
    path = tmp_path / "pressure_scatter.png"

    write_pressure_association_scatter(result, path)

    assert path.exists()
    assert path.stat().st_size > 0

    with pytest.raises(FileExistsError):
        write_pressure_association_scatter(result, path)
