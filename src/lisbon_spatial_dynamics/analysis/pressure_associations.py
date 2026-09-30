"""Descriptive association between housing change and normalized RNAL pressure."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import fmean

from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    AnnualHousingPressureRow,
)


class PressureAssociationError(ValueError):
    """Raised when annual housing-pressure rows cannot support the analysis."""


@dataclass(frozen=True, slots=True)
class PressureAssociationPoint:
    """One freguesia observation in the normalized association analysis."""

    freguesia_id: str
    freguesia_name: str
    baseline_year: int
    latest_year: int
    population_reference_year: int
    population_resident: int
    housing_change_pct: float
    rnal_pressure_change_per_1000: float


@dataclass(frozen=True, slots=True)
class PressureAssociationResult:
    """Descriptive association for one common baseline-to-latest window."""

    baseline_year: int
    latest_year: int
    total_freguesias: int
    complete_cases: int
    excluded_missing_housing: int
    pearson_r: float | None
    spearman_rho: float | None
    points: tuple[PressureAssociationPoint, ...]


def load_annual_housing_pressure_csv(
    path: Path,
) -> tuple[AnnualHousingPressureRow, ...]:
    """Load the stable annual housing-pressure research CSV."""
    rows: list[AnnualHousingPressureRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "year",
            "baseline_year",
            "period_code",
            "period_end",
            "freguesia_id",
            "freguesia_name",
            "population_reference_year",
            "population_resident",
            "population_density_per_km2",
            "flow_quarters_observed",
            "housing_value_eur_m2",
            "housing_yoy_abs_eur_m2",
            "housing_yoy_pct",
            "housing_change_from_baseline_abs_eur_m2",
            "housing_change_from_baseline_pct",
            "rnal_registrations_year",
            "rnal_cessations_year",
            "rnal_net_registrations_year",
            "rnal_registrations_year_per_1000",
            "rnal_cessations_year_per_1000",
            "rnal_net_registrations_year_per_1000",
            "rnal_active_registrations_year_end",
            "rnal_active_registrations_per_1000_year_end",
            "rnal_active_registrations_per_1000_change_from_baseline",
            "rnal_active_beds_known_year_end",
            "rnal_active_beds_missing_year_end",
            "rnal_active_beds_known_per_1000_year_end",
            "rnal_active_beds_known_per_1000_change_from_baseline",
            "rnal_active_users_known_year_end",
            "rnal_active_users_missing_year_end",
            "rnal_active_users_known_per_1000_year_end",
            "rnal_active_users_known_per_1000_change_from_baseline",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise PressureAssociationError(
                "annual housing-pressure CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for row_index, raw in enumerate(reader, start=2):
            rows.append(
                AnnualHousingPressureRow(
                    year=_required_int(raw.get("year"), row_index, "year"),
                    baseline_year=_required_int(
                        raw.get("baseline_year"), row_index, "baseline_year"
                    ),
                    period_code=_required(raw.get("period_code"), row_index, "period_code"),
                    period_end=_required_date(raw.get("period_end"), row_index, "period_end"),
                    freguesia_id=_required(raw.get("freguesia_id"), row_index, "freguesia_id"),
                    freguesia_name=_required(
                        raw.get("freguesia_name"), row_index, "freguesia_name"
                    ),
                    population_reference_year=_required_int(
                        raw.get("population_reference_year"),
                        row_index,
                        "population_reference_year",
                    ),
                    population_resident=_required_positive_int(
                        raw.get("population_resident"),
                        row_index,
                        "population_resident",
                    ),
                    population_density_per_km2=_required_positive_decimal(
                        raw.get("population_density_per_km2"),
                        row_index,
                        "population_density_per_km2",
                    ),
                    flow_quarters_observed=_required_int(
                        raw.get("flow_quarters_observed"),
                        row_index,
                        "flow_quarters_observed",
                    ),
                    housing_value_eur_m2=_optional_decimal(
                        raw.get("housing_value_eur_m2"),
                        row_index,
                        "housing_value_eur_m2",
                    ),
                    housing_yoy_abs_eur_m2=_optional_decimal(
                        raw.get("housing_yoy_abs_eur_m2"),
                        row_index,
                        "housing_yoy_abs_eur_m2",
                    ),
                    housing_yoy_pct=_optional_decimal(
                        raw.get("housing_yoy_pct"),
                        row_index,
                        "housing_yoy_pct",
                    ),
                    housing_change_from_baseline_abs_eur_m2=_optional_decimal(
                        raw.get("housing_change_from_baseline_abs_eur_m2"),
                        row_index,
                        "housing_change_from_baseline_abs_eur_m2",
                    ),
                    housing_change_from_baseline_pct=_optional_decimal(
                        raw.get("housing_change_from_baseline_pct"),
                        row_index,
                        "housing_change_from_baseline_pct",
                    ),
                    rnal_registrations_year=_optional_int(
                        raw.get("rnal_registrations_year"),
                        row_index,
                        "rnal_registrations_year",
                    ),
                    rnal_cessations_year=_optional_int(
                        raw.get("rnal_cessations_year"),
                        row_index,
                        "rnal_cessations_year",
                    ),
                    rnal_net_registrations_year=_optional_int(
                        raw.get("rnal_net_registrations_year"),
                        row_index,
                        "rnal_net_registrations_year",
                    ),
                    rnal_registrations_year_per_1000=_optional_decimal(
                        raw.get("rnal_registrations_year_per_1000"),
                        row_index,
                        "rnal_registrations_year_per_1000",
                    ),
                    rnal_cessations_year_per_1000=_optional_decimal(
                        raw.get("rnal_cessations_year_per_1000"),
                        row_index,
                        "rnal_cessations_year_per_1000",
                    ),
                    rnal_net_registrations_year_per_1000=_optional_decimal(
                        raw.get("rnal_net_registrations_year_per_1000"),
                        row_index,
                        "rnal_net_registrations_year_per_1000",
                    ),
                    rnal_active_registrations_year_end=_required_non_negative_int(
                        raw.get("rnal_active_registrations_year_end"),
                        row_index,
                        "rnal_active_registrations_year_end",
                    ),
                    rnal_active_registrations_per_1000_year_end=_required_decimal(
                        raw.get("rnal_active_registrations_per_1000_year_end"),
                        row_index,
                        "rnal_active_registrations_per_1000_year_end",
                    ),
                    rnal_active_registrations_per_1000_change_from_baseline=_required_decimal(
                        raw.get("rnal_active_registrations_per_1000_change_from_baseline"),
                        row_index,
                        "rnal_active_registrations_per_1000_change_from_baseline",
                    ),
                    rnal_active_beds_known_year_end=_required_non_negative_int(
                        raw.get("rnal_active_beds_known_year_end"),
                        row_index,
                        "rnal_active_beds_known_year_end",
                    ),
                    rnal_active_beds_missing_year_end=_required_non_negative_int(
                        raw.get("rnal_active_beds_missing_year_end"),
                        row_index,
                        "rnal_active_beds_missing_year_end",
                    ),
                    rnal_active_beds_known_per_1000_year_end=_required_decimal(
                        raw.get("rnal_active_beds_known_per_1000_year_end"),
                        row_index,
                        "rnal_active_beds_known_per_1000_year_end",
                    ),
                    rnal_active_beds_known_per_1000_change_from_baseline=_required_decimal(
                        raw.get("rnal_active_beds_known_per_1000_change_from_baseline"),
                        row_index,
                        "rnal_active_beds_known_per_1000_change_from_baseline",
                    ),
                    rnal_active_users_known_year_end=_required_non_negative_int(
                        raw.get("rnal_active_users_known_year_end"),
                        row_index,
                        "rnal_active_users_known_year_end",
                    ),
                    rnal_active_users_missing_year_end=_required_non_negative_int(
                        raw.get("rnal_active_users_missing_year_end"),
                        row_index,
                        "rnal_active_users_missing_year_end",
                    ),
                    rnal_active_users_known_per_1000_year_end=_required_decimal(
                        raw.get("rnal_active_users_known_per_1000_year_end"),
                        row_index,
                        "rnal_active_users_known_per_1000_year_end",
                    ),
                    rnal_active_users_known_per_1000_change_from_baseline=_required_decimal(
                        raw.get("rnal_active_users_known_per_1000_change_from_baseline"),
                        row_index,
                        "rnal_active_users_known_per_1000_change_from_baseline",
                    ),
                )
            )

    if not rows:
        raise PressureAssociationError("annual housing-pressure CSV cannot be empty")

    return tuple(rows)


def build_pressure_association(
    rows: Sequence[AnnualHousingPressureRow],
) -> PressureAssociationResult:
    """Compare housing change with RNAL pressure-point change.

    The latest year must be common to every freguesia. The baseline year must
    also agree across freguesias.
    """
    if not rows:
        raise PressureAssociationError("annual housing-pressure rows cannot be empty")

    by_id: dict[str, dict[int, AnnualHousingPressureRow]] = {}
    for row in rows:
        years = by_id.setdefault(row.freguesia_id, {})
        if row.year in years:
            raise PressureAssociationError(
                f"duplicate annual key: ({row.year}, {row.freguesia_id})"
            )
        years[row.year] = row

    baseline_years = {row.baseline_year for row in rows}
    if len(baseline_years) != 1:
        raise PressureAssociationError("freguesias do not share one baseline year")
    baseline_year = next(iter(baseline_years))

    common_years = set.intersection(*(set(years) for years in by_id.values()))
    if not common_years:
        raise PressureAssociationError("freguesias do not share any common annual observation year")

    latest_year = max(common_years)
    points: list[PressureAssociationPoint] = []
    missing_housing = 0

    for freguesia_id in sorted(by_id):
        row = by_id[freguesia_id][latest_year]

        if row.baseline_year != baseline_year:
            raise PressureAssociationError(f"{freguesia_id} baseline year changed unexpectedly")

        if row.housing_change_from_baseline_pct is None:
            missing_housing += 1
            continue

        points.append(
            PressureAssociationPoint(
                freguesia_id=freguesia_id,
                freguesia_name=row.freguesia_name,
                baseline_year=baseline_year,
                latest_year=latest_year,
                population_reference_year=row.population_reference_year,
                population_resident=row.population_resident,
                housing_change_pct=float(row.housing_change_from_baseline_pct),
                rnal_pressure_change_per_1000=float(
                    row.rnal_active_registrations_per_1000_change_from_baseline
                ),
            )
        )

    if len(points) < 2:
        raise PressureAssociationError("at least two complete freguesia observations are required")

    housing = [point.housing_change_pct for point in points]
    pressure = [point.rnal_pressure_change_per_1000 for point in points]

    return PressureAssociationResult(
        baseline_year=baseline_year,
        latest_year=latest_year,
        total_freguesias=len(by_id),
        complete_cases=len(points),
        excluded_missing_housing=missing_housing,
        pearson_r=_pearson(housing, pressure),
        spearman_rho=_pearson(
            _average_ranks(housing),
            _average_ranks(pressure),
        ),
        points=tuple(points),
    )


def write_pressure_association_json(
    result: PressureAssociationResult,
    path: Path,
) -> None:
    """Write the normalized association report without overwriting."""
    path.parent.mkdir(parents=True, exist_ok=True)

    document: dict[str, object] = {
        "schema_version": 1,
        "analysis": "housing_vs_rnal_pressure_change",
        "comparison_window": {
            "baseline_year": result.baseline_year,
            "latest_common_year": result.latest_year,
        },
        "variables": {
            "x": "rnal_active_registrations_per_1000_change_from_baseline",
            "y": "housing_change_from_baseline_pct",
        },
        "coverage": {
            "total_freguesias": result.total_freguesias,
            "complete_cases": result.complete_cases,
            "excluded_missing_housing": result.excluded_missing_housing,
        },
        "correlations": {
            "pearson_r": result.pearson_r,
            "spearman_rho": result.spearman_rho,
        },
        "interpretation": (
            "Descriptive cross-sectional association between cumulative housing "
            "change and change in RNAL pressure per 1,000 Census-2021 residents. "
            "The population denominator is static and the correlation is not causal."
        ),
        "points": [
            {
                "freguesia_id": point.freguesia_id,
                "freguesia_name": point.freguesia_name,
                "baseline_year": point.baseline_year,
                "latest_year": point.latest_year,
                "population_reference_year": point.population_reference_year,
                "population_resident": point.population_resident,
                "housing_change_pct": point.housing_change_pct,
                "rnal_pressure_change_per_1000": (point.rnal_pressure_change_per_1000),
            }
            for point in result.points
        ],
    }

    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def write_pressure_association_scatter(
    result: PressureAssociationResult,
    path: Path,
    *,
    label_points: bool = True,
) -> None:
    """Write a scatter plot for housing change versus RNAL pressure change."""
    if path.exists():
        raise FileExistsError(path)

    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)

    x = [point.rnal_pressure_change_per_1000 for point in result.points]
    y = [point.housing_change_pct for point in result.points]

    figure, axis = plt.subplots()
    axis.scatter(x, y)
    axis.axhline(0, linewidth=0.8)
    axis.axvline(0, linewidth=0.8)

    if label_points:
        for point in result.points:
            axis.annotate(
                point.freguesia_name,
                (
                    point.rnal_pressure_change_per_1000,
                    point.housing_change_pct,
                ),
                xytext=(4, 4),
                textcoords="offset points",
                fontsize=7,
            )

    axis.set_xlabel("Change in active RNAL registrations per 1,000 residents")
    axis.set_ylabel("Housing value change from baseline (%)")
    axis.set_title(
        f"Lisbon freguesia pressure trajectories: {result.baseline_year}–{result.latest_year}"
    )
    axis.grid(True, alpha=0.25)
    figure.tight_layout()

    try:
        figure.savefig(path, dpi=180, bbox_inches="tight")
    finally:
        plt.close(figure)


def _pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Return Pearson correlation, or None for a constant variable."""
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
        value_x * value_y for value_x, value_y in zip(centered_x, centered_y, strict=True)
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


def _required(value: str | None, row: int, field: str) -> str:
    """Return a required CSV string."""
    if value is None or not value.strip():
        raise PressureAssociationError(f"row {row}.{field} must be non-empty")
    return value.strip()


def _required_int(value: str | None, row: int, field: str) -> int:
    """Parse a required integer."""
    raw = _required(value, row, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise PressureAssociationError(f"row {row}.{field} must be an integer") from exc


def _required_non_negative_int(
    value: str | None,
    row: int,
    field: str,
) -> int:
    """Parse a required non-negative integer."""
    number = _required_int(value, row, field)
    if number < 0:
        raise PressureAssociationError(f"row {row}.{field} must be non-negative")
    return number


def _required_positive_int(
    value: str | None,
    row: int,
    field: str,
) -> int:
    """Parse a required positive integer."""
    number = _required_int(value, row, field)
    if number <= 0:
        raise PressureAssociationError(f"row {row}.{field} must be positive")
    return number


def _optional_int(
    value: str | None,
    row: int,
    field: str,
) -> int | None:
    """Parse an optional integer."""
    if value is None or not value.strip():
        return None
    return _required_int(value, row, field)


def _required_date(
    value: str | None,
    row: int,
    field: str,
) -> date:
    """Parse a required ISO date."""
    raw = _required(value, row, field)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise PressureAssociationError(f"row {row}.{field} must be an ISO date") from exc


def _required_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal:
    """Parse a required Decimal."""
    raw = _required(value, row, field)
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise PressureAssociationError(f"row {row}.{field} must be numeric") from exc


def _required_positive_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal:
    """Parse a required positive Decimal."""
    number = _required_decimal(value, row, field)
    if number <= 0:
        raise PressureAssociationError(f"row {row}.{field} must be positive")
    return number


def _optional_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal | None:
    """Parse an optional Decimal."""
    if value is None or not value.strip():
        return None
    return _required_decimal(value, row, field)
