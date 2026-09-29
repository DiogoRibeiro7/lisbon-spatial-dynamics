"""Tests for the descriptive association scatter plot."""

from __future__ import annotations

from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.associations import (
    AssociationPoint,
    DescriptiveAssociation,
    write_association_scatter,
)


def test_scatter_plot_is_written_and_immutable(tmp_path: Path) -> None:
    result = DescriptiveAssociation(
        baseline_year=2019,
        latest_year=2025,
        total_freguesias=2,
        complete_cases=2,
        excluded_missing_housing=0,
        excluded_undefined_rnal_pct=0,
        pearson_r=1.0,
        spearman_rho=1.0,
        points=(
            AssociationPoint("a", "A", 10.0, 5.0),
            AssociationPoint("b", "B", 20.0, 10.0),
        ),
    )
    path = tmp_path / "scatter.png"

    write_association_scatter(result, path)

    assert path.exists()
    assert path.stat().st_size > 0

    with pytest.raises(FileExistsError):
        write_association_scatter(result, path)
