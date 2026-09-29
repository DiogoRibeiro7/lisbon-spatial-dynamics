"""Descriptive associations between housing and RNAL trajectory changes."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean

from lisbon_spatial_dynamics.analysis.trajectories import FreguesiaTrajectory


class AssociationError(ValueError):
    """Raised when trajectory rows cannot support descriptive association analysis."""


@dataclass(frozen=True, slots=True)
class AssociationPoint:
    """One complete-case freguesia observation."""

    freguesia_id: str
    freguesia_name: str
    housing_change_pct: float
    rnal_active_change_pct: float


@dataclass(frozen=True, slots=True)
class DescriptiveAssociation:
    """Descriptive correlation results for one common comparison window."""

    baseline_year: int
    latest_year: int
    total_freguesias: int
    complete_cases: int
    excluded_missing_housing: int
    excluded_undefined_rnal_pct: int
    pearson_r: float | None
    spearman_rho: float | None
    points: tuple[AssociationPoint, ...]


def build_descriptive_association(
    rows: Sequence[FreguesiaTrajectory],
) -> DescriptiveAssociation:
    """Compare housing-price percentage change with RNAL active-stock change."""
    if not rows:
        raise AssociationError("trajectory rows cannot be empty")

    windows = {(row.baseline_year, row.latest_year) for row in rows}
    if len(windows) != 1:
        raise AssociationError(
            "trajectory rows must share one baseline/latest comparison window"
        )

    baseline_year, latest_year = next(iter(windows))
    points: list[AssociationPoint] = []
    missing_housing = 0
    undefined_rnal = 0
    seen_ids: set[str] = set()

    for row in rows:
        if row.freguesia_id in seen_ids:
            raise AssociationError(f"duplicate freguesia_id: {row.freguesia_id}")
        seen_ids.add(row.freguesia_id)

        if row.housing_change_pct is None:
            missing_housing += 1
            continue
        if row.rnal_active_change_pct is None:
            undefined_rnal += 1
            continue

        points.append(
            AssociationPoint(
                freguesia_id=row.freguesia_id,
                freguesia_name=row.freguesia_name,
                housing_change_pct=float(row.housing_change_pct),
                rnal_active_change_pct=float(row.rnal_active_change_pct),
            )
        )

    if len(points) < 2:
        raise AssociationError(
            "at least two complete freguesia observations are required"
        )

    housing = [point.housing_change_pct for point in points]
    rnal = [point.rnal_active_change_pct for point in points]

    return DescriptiveAssociation(
        baseline_year=baseline_year,
        latest_year=latest_year,
        total_freguesias=len(rows),
        complete_cases=len(points),
        excluded_missing_housing=missing_housing,
        excluded_undefined_rnal_pct=undefined_rnal,
        pearson_r=_pearson(housing, rnal),
        spearman_rho=_pearson(_average_ranks(housing), _average_ranks(rnal)),
        points=tuple(points),
    )


def write_association_json(
    result: DescriptiveAssociation,
    path: Path,
) -> None:
    """Write a machine-readable association report without overwriting."""
    path.parent.mkdir(parents=True, exist_ok=True)

    document: dict[str, object] = {
        "schema_version": 1,
        "analysis": "descriptive_cross_sectional_association",
        "comparison_window": {
            "baseline_year": result.baseline_year,
            "latest_year": result.latest_year,
        },
        "variables": {
            "x": "rnal_active_change_pct",
            "y": "housing_change_pct",
        },
        "coverage": {
            "total_freguesias": result.total_freguesias,
            "complete_cases": result.complete_cases,
            "excluded_missing_housing": result.excluded_missing_housing,
            "excluded_undefined_rnal_pct": result.excluded_undefined_rnal_pct,
        },
        "correlations": {
            "pearson_r": result.pearson_r,
            "spearman_rho": result.spearman_rho,
        },
        "interpretation": (
            "Descriptive cross-sectional association only; correlation does not "
            "establish a causal effect of local accommodation on housing prices."
        ),
        "points": [
            {
                "freguesia_id": point.freguesia_id,
                "freguesia_name": point.freguesia_name,
                "housing_change_pct": point.housing_change_pct,
                "rnal_active_change_pct": point.rnal_active_change_pct,
            }
            for point in result.points
        ],
    }

    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    )

    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def write_association_scatter(
    result: DescriptiveAssociation,
    path: Path,
    *,
    label_points: bool = True,
) -> None:
    """Write one scatter plot for the complete-case association data."""
    if path.exists():
        raise FileExistsError(path)

    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)

    x = [point.rnal_active_change_pct for point in result.points]
    y = [point.housing_change_pct for point in result.points]

    figure, axis = plt.subplots()
    axis.scatter(x, y)
    axis.axhline(0, linewidth=0.8)
    axis.axvline(0, linewidth=0.8)

    if label_points:
        for point in result.points:
            axis.annotate(
                point.freguesia_name,
                (point.rnal_active_change_pct, point.housing_change_pct),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
            )

    axis.set_xlabel("Change in active RNAL registrations (%)")
    axis.set_ylabel("Change in housing value (€/m², %)")
    axis.set_title(
        f"Lisbon freguesia trajectories: "
        f"{result.baseline_year}–{result.latest_year}"
    )
    axis.grid(True, alpha=0.25)
    figure.tight_layout()

    try:
        figure.savefig(path, dpi=180, bbox_inches="tight")
    finally:
        plt.close(figure)


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Return Pearson correlation, or None when either variable is constant."""
    if len(x) != len(y):
        raise ValueError("x and y must have the same length")
    if len(x) < 2:
        raise ValueError("at least two observations are required")

    mean_x = fmean(x)
    mean_y = fmean(y)
    centered_x = [value - mean_x for value in x]
    centered_y = [value - mean_y for value in y]

    sum_sq_x = sum(value * value for value in centered_x)
    sum_sq_y = sum(value * value for value in centered_y)

    if math.isclose(sum_sq_x, 0.0) or math.isclose(sum_sq_y, 0.0):
        return None

    covariance_sum = sum(
        value_x * value_y
        for value_x, value_y in zip(centered_x, centered_y, strict=True)
    )
    return covariance_sum / math.sqrt(sum_sq_x * sum_sq_y)


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Return one-based average ranks with standard tie handling."""
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)

    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1

        average_rank = ((start + 1) + end) / 2.0
        for position in range(start, end):
            ranks[indexed[position][0]] = average_rank
        start = end

    return ranks
