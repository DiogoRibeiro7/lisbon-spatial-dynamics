"""Baseline-to-latest freguesia trajectories from the annual urban panel."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero
from pathlib import Path

from lisbon_spatial_dynamics.panels.annual import AnnualUrbanRow


class TrajectoryError(ValueError):
    """Raised when annual rows cannot form comparable freguesia trajectories."""


@dataclass(frozen=True, slots=True)
class FreguesiaTrajectory:
    """One baseline-to-latest descriptive trajectory for a Lisbon freguesia."""

    freguesia_id: str
    freguesia_name: str
    baseline_year: int
    latest_year: int
    years_elapsed: int
    observed_q4_years: int
    housing_baseline_eur_m2: Decimal | None
    housing_latest_eur_m2: Decimal | None
    housing_change_abs_eur_m2: Decimal | None
    housing_change_pct: Decimal | None
    housing_latest_yoy_pct: Decimal | None
    rnal_active_baseline: int
    rnal_active_latest: int
    rnal_active_change_abs: int
    rnal_active_change_pct: Decimal | None
    rnal_beds_known_baseline: int
    rnal_beds_known_latest: int
    rnal_beds_missing_latest: int
    rnal_users_known_baseline: int
    rnal_users_known_latest: int
    rnal_users_missing_latest: int
    latest_flow_quarters_observed: int
    latest_registrations_year: int | None
    latest_cessations_year: int | None
    latest_net_registrations_year: int | None


TRAJECTORY_COLUMNS: tuple[str, ...] = (
    "freguesia_id",
    "freguesia_name",
    "baseline_year",
    "latest_year",
    "years_elapsed",
    "observed_q4_years",
    "housing_baseline_eur_m2",
    "housing_latest_eur_m2",
    "housing_change_abs_eur_m2",
    "housing_change_pct",
    "housing_latest_yoy_pct",
    "rnal_active_baseline",
    "rnal_active_latest",
    "rnal_active_change_abs",
    "rnal_active_change_pct",
    "rnal_beds_known_baseline",
    "rnal_beds_known_latest",
    "rnal_beds_missing_latest",
    "rnal_users_known_baseline",
    "rnal_users_known_latest",
    "rnal_users_missing_latest",
    "latest_flow_quarters_observed",
    "latest_registrations_year",
    "latest_cessations_year",
    "latest_net_registrations_year",
)


def build_freguesia_trajectories(
    rows: Sequence[AnnualUrbanRow],
    *,
    require_common_window: bool = True,
) -> tuple[FreguesiaTrajectory, ...]:
    """Build comparable baseline-to-latest trajectories.

    By default every freguesia must share the same baseline and latest year.
    This protects cross-freguesia comparisons from silently mixing windows of
    different lengths.
    """
    if not rows:
        raise TrajectoryError("annual urban panel cannot be empty")

    grouped: dict[str, dict[int, AnnualUrbanRow]] = {}
    names: dict[str, str] = {}

    for row in rows:
        years = grouped.setdefault(row.freguesia_id, {})
        if row.year in years:
            raise TrajectoryError(f"duplicate annual row for {row.freguesia_id}/{row.year}")

        known_name = names.get(row.freguesia_id)
        if known_name is not None and known_name != row.freguesia_name:
            raise TrajectoryError(f"inconsistent freguesia name for {row.freguesia_id}")
        names[row.freguesia_id] = row.freguesia_name
        years[row.year] = row

    windows: dict[str, tuple[int, int]] = {}
    for freguesia_id, years in grouped.items():
        ordered_years = sorted(years)
        if len(ordered_years) < 2:
            raise TrajectoryError(f"{freguesia_id} needs at least two annual observations")
        windows[freguesia_id] = (ordered_years[0], ordered_years[-1])

    if require_common_window:
        unique_windows = set(windows.values())
        if len(unique_windows) != 1:
            details = ", ".join(
                f"{freguesia_id}:{start}-{end}"
                for freguesia_id, (start, end) in sorted(windows.items())
            )
            raise TrajectoryError("freguesias do not share a common comparison window: " + details)

    output: list[FreguesiaTrajectory] = []

    for freguesia_id in sorted(grouped):
        years = grouped[freguesia_id]
        ordered_years = sorted(years)
        baseline = years[ordered_years[0]]
        latest = years[ordered_years[-1]]

        housing_abs, housing_pct = _decimal_change(
            latest.housing_value_eur_m2,
            baseline.housing_value_eur_m2,
        )
        rnal_active_abs = (
            latest.rnal_active_registrations_year_end - baseline.rnal_active_registrations_year_end
        )
        rnal_active_pct = _integer_pct_change(
            latest.rnal_active_registrations_year_end,
            baseline.rnal_active_registrations_year_end,
        )

        output.append(
            FreguesiaTrajectory(
                freguesia_id=freguesia_id,
                freguesia_name=latest.freguesia_name,
                baseline_year=baseline.year,
                latest_year=latest.year,
                years_elapsed=latest.year - baseline.year,
                observed_q4_years=len(ordered_years),
                housing_baseline_eur_m2=baseline.housing_value_eur_m2,
                housing_latest_eur_m2=latest.housing_value_eur_m2,
                housing_change_abs_eur_m2=housing_abs,
                housing_change_pct=housing_pct,
                housing_latest_yoy_pct=latest.housing_yoy_pct,
                rnal_active_baseline=baseline.rnal_active_registrations_year_end,
                rnal_active_latest=latest.rnal_active_registrations_year_end,
                rnal_active_change_abs=rnal_active_abs,
                rnal_active_change_pct=rnal_active_pct,
                rnal_beds_known_baseline=baseline.rnal_active_beds_known_year_end,
                rnal_beds_known_latest=latest.rnal_active_beds_known_year_end,
                rnal_beds_missing_latest=latest.rnal_active_beds_missing_year_end,
                rnal_users_known_baseline=baseline.rnal_active_users_known_year_end,
                rnal_users_known_latest=latest.rnal_active_users_known_year_end,
                rnal_users_missing_latest=latest.rnal_active_users_missing_year_end,
                latest_flow_quarters_observed=latest.flow_quarters_observed,
                latest_registrations_year=latest.rnal_registrations_year,
                latest_cessations_year=latest.rnal_cessations_year,
                latest_net_registrations_year=latest.rnal_net_registrations_year,
            )
        )

    return tuple(output)


def write_freguesia_trajectory_csv(
    rows: Sequence[FreguesiaTrajectory],
    path: Path,
) -> None:
    """Write the descriptive freguesia trajectory table without overwriting."""
    if not rows:
        raise TrajectoryError("trajectory table cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(TRAJECTORY_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.freguesia_id,
                    row.freguesia_name,
                    row.baseline_year,
                    row.latest_year,
                    row.years_elapsed,
                    row.observed_q4_years,
                    _decimal_text(row.housing_baseline_eur_m2),
                    _decimal_text(row.housing_latest_eur_m2),
                    _decimal_text(row.housing_change_abs_eur_m2),
                    _decimal_text(row.housing_change_pct),
                    _decimal_text(row.housing_latest_yoy_pct),
                    row.rnal_active_baseline,
                    row.rnal_active_latest,
                    row.rnal_active_change_abs,
                    _decimal_text(row.rnal_active_change_pct),
                    row.rnal_beds_known_baseline,
                    row.rnal_beds_known_latest,
                    row.rnal_beds_missing_latest,
                    row.rnal_users_known_baseline,
                    row.rnal_users_known_latest,
                    row.rnal_users_missing_latest,
                    row.latest_flow_quarters_observed,
                    _optional_int_text(row.latest_registrations_year),
                    _optional_int_text(row.latest_cessations_year),
                    _optional_int_text(row.latest_net_registrations_year),
                )
            )


def _decimal_change(
    current: Decimal | None,
    baseline: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Return absolute and percentage change from a Decimal baseline."""
    if current is None or baseline is None:
        return None, None

    absolute = current - baseline
    try:
        percentage = absolute / baseline * Decimal("100")
    except DivisionByZero:
        percentage = None

    return absolute, percentage


def _integer_pct_change(current: int, baseline: int) -> Decimal | None:
    """Return percentage change from an integer baseline."""
    if baseline == 0:
        return None

    return Decimal(current - baseline) / Decimal(baseline) * Decimal("100")


def _decimal_text(value: Decimal | None) -> str:
    """Serialize an optional Decimal without scientific notation."""
    return "" if value is None else format(value, "f")


def _optional_int_text(value: int | None) -> str:
    """Serialize an optional integer."""
    return "" if value is None else str(value)
