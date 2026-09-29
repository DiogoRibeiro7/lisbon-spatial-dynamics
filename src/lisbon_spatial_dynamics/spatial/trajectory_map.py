"""Map-ready GeoJSON export for baseline-to-latest freguesia trajectories."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lisbon_spatial_dynamics.analysis.trajectories import FreguesiaTrajectory
from lisbon_spatial_dynamics.spatial.annual_maps import ReferenceFeature


class TrajectoryMapError(ValueError):
    """Raised when trajectories cannot be joined to canonical geometry."""


def load_trajectory_csv(path: Path) -> tuple[FreguesiaTrajectory, ...]:
    """Load the stable freguesia trajectory CSV contract."""
    rows: list[FreguesiaTrajectory] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
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
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise TrajectoryMapError(
                "trajectory CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for index, raw in enumerate(reader, start=2):
            rows.append(
                FreguesiaTrajectory(
                    freguesia_id=_required(raw.get("freguesia_id"), index, "freguesia_id"),
                    freguesia_name=_required(
                        raw.get("freguesia_name"), index, "freguesia_name"
                    ),
                    baseline_year=_required_int(
                        raw.get("baseline_year"), index, "baseline_year"
                    ),
                    latest_year=_required_int(
                        raw.get("latest_year"), index, "latest_year"
                    ),
                    years_elapsed=_required_int(
                        raw.get("years_elapsed"), index, "years_elapsed"
                    ),
                    observed_q4_years=_required_int(
                        raw.get("observed_q4_years"), index, "observed_q4_years"
                    ),
                    housing_baseline_eur_m2=_optional_decimal(
                        raw.get("housing_baseline_eur_m2"),
                        index,
                        "housing_baseline_eur_m2",
                    ),
                    housing_latest_eur_m2=_optional_decimal(
                        raw.get("housing_latest_eur_m2"),
                        index,
                        "housing_latest_eur_m2",
                    ),
                    housing_change_abs_eur_m2=_optional_decimal(
                        raw.get("housing_change_abs_eur_m2"),
                        index,
                        "housing_change_abs_eur_m2",
                    ),
                    housing_change_pct=_optional_decimal(
                        raw.get("housing_change_pct"), index, "housing_change_pct"
                    ),
                    housing_latest_yoy_pct=_optional_decimal(
                        raw.get("housing_latest_yoy_pct"),
                        index,
                        "housing_latest_yoy_pct",
                    ),
                    rnal_active_baseline=_required_int(
                        raw.get("rnal_active_baseline"),
                        index,
                        "rnal_active_baseline",
                    ),
                    rnal_active_latest=_required_int(
                        raw.get("rnal_active_latest"), index, "rnal_active_latest"
                    ),
                    rnal_active_change_abs=_required_int(
                        raw.get("rnal_active_change_abs"),
                        index,
                        "rnal_active_change_abs",
                    ),
                    rnal_active_change_pct=_optional_decimal(
                        raw.get("rnal_active_change_pct"),
                        index,
                        "rnal_active_change_pct",
                    ),
                    rnal_beds_known_baseline=_required_int(
                        raw.get("rnal_beds_known_baseline"),
                        index,
                        "rnal_beds_known_baseline",
                    ),
                    rnal_beds_known_latest=_required_int(
                        raw.get("rnal_beds_known_latest"),
                        index,
                        "rnal_beds_known_latest",
                    ),
                    rnal_beds_missing_latest=_required_int(
                        raw.get("rnal_beds_missing_latest"),
                        index,
                        "rnal_beds_missing_latest",
                    ),
                    rnal_users_known_baseline=_required_int(
                        raw.get("rnal_users_known_baseline"),
                        index,
                        "rnal_users_known_baseline",
                    ),
                    rnal_users_known_latest=_required_int(
                        raw.get("rnal_users_known_latest"),
                        index,
                        "rnal_users_known_latest",
                    ),
                    rnal_users_missing_latest=_required_int(
                        raw.get("rnal_users_missing_latest"),
                        index,
                        "rnal_users_missing_latest",
                    ),
                    latest_flow_quarters_observed=_required_int(
                        raw.get("latest_flow_quarters_observed"),
                        index,
                        "latest_flow_quarters_observed",
                    ),
                    latest_registrations_year=_optional_int(
                        raw.get("latest_registrations_year"),
                        index,
                        "latest_registrations_year",
                    ),
                    latest_cessations_year=_optional_int(
                        raw.get("latest_cessations_year"),
                        index,
                        "latest_cessations_year",
                    ),
                    latest_net_registrations_year=_optional_int(
                        raw.get("latest_net_registrations_year"),
                        index,
                        "latest_net_registrations_year",
                    ),
                )
            )

    if not rows:
        raise TrajectoryMapError("trajectory CSV cannot be empty")

    return tuple(rows)


def build_trajectory_geojson(
    rows: Sequence[FreguesiaTrajectory],
    reference: Sequence[ReferenceFeature],
) -> dict[str, object]:
    """Join trajectory attributes to the exact canonical freguesia geometry."""
    if not rows:
        raise TrajectoryMapError("trajectory rows cannot be empty")
    if not reference:
        raise TrajectoryMapError("reference geometry cannot be empty")

    row_by_id = _unique_trajectory_mapping(rows)
    reference_by_id = _unique_reference_mapping(reference)

    if set(row_by_id) != set(reference_by_id):
        missing = sorted(set(reference_by_id) - set(row_by_id))
        extra = sorted(set(row_by_id) - set(reference_by_id))
        raise TrajectoryMapError(
            f"trajectory/reference key mismatch; missing={missing}, extra={extra}"
        )

    windows = {(row.baseline_year, row.latest_year) for row in rows}
    if len(windows) != 1:
        raise TrajectoryMapError("trajectory rows do not share one comparison window")

    baseline_year, latest_year = next(iter(windows))
    features: list[dict[str, object]] = []

    for freguesia_id in sorted(reference_by_id):
        row = row_by_id[freguesia_id]
        feature = reference_by_id[freguesia_id]

        if row.freguesia_name != feature.name:
            raise TrajectoryMapError(
                f"name mismatch for {freguesia_id}: "
                f"{row.freguesia_name!r} != {feature.name!r}"
            )

        properties = dict(feature.properties)
        properties.update(_trajectory_properties(row))

        features.append(
            {
                "type": "Feature",
                "id": freguesia_id,
                "properties": properties,
                "geometry": dict(feature.geometry),
            }
        )

    return {
        "type": "FeatureCollection",
        "name": f"lisbon_freguesia_trajectories_{baseline_year}_{latest_year}",
        "baseline_year": baseline_year,
        "latest_year": latest_year,
        "feature_count": len(features),
        "features": features,
    }


def write_trajectory_geojson(document: Mapping[str, object], path: Path) -> None:
    """Write one immutable trajectory GeoJSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def _trajectory_properties(row: FreguesiaTrajectory) -> dict[str, object]:
    """Convert one trajectory row to interoperable GeoJSON properties."""
    return {
        "baseline_year": row.baseline_year,
        "latest_year": row.latest_year,
        "years_elapsed": row.years_elapsed,
        "observed_q4_years": row.observed_q4_years,
        "housing_baseline_eur_m2": _decimal_number(row.housing_baseline_eur_m2),
        "housing_latest_eur_m2": _decimal_number(row.housing_latest_eur_m2),
        "housing_change_abs_eur_m2": _decimal_number(
            row.housing_change_abs_eur_m2
        ),
        "housing_change_pct": _decimal_number(row.housing_change_pct),
        "housing_latest_yoy_pct": _decimal_number(row.housing_latest_yoy_pct),
        "rnal_active_baseline": row.rnal_active_baseline,
        "rnal_active_latest": row.rnal_active_latest,
        "rnal_active_change_abs": row.rnal_active_change_abs,
        "rnal_active_change_pct": _decimal_number(row.rnal_active_change_pct),
        "rnal_beds_known_baseline": row.rnal_beds_known_baseline,
        "rnal_beds_known_latest": row.rnal_beds_known_latest,
        "rnal_beds_missing_latest": row.rnal_beds_missing_latest,
        "rnal_users_known_baseline": row.rnal_users_known_baseline,
        "rnal_users_known_latest": row.rnal_users_known_latest,
        "rnal_users_missing_latest": row.rnal_users_missing_latest,
        "latest_flow_quarters_observed": row.latest_flow_quarters_observed,
        "latest_registrations_year": row.latest_registrations_year,
        "latest_cessations_year": row.latest_cessations_year,
        "latest_net_registrations_year": row.latest_net_registrations_year,
    }


def _unique_trajectory_mapping(
    rows: Sequence[FreguesiaTrajectory],
) -> dict[str, FreguesiaTrajectory]:
    """Build a unique trajectory mapping."""
    mapping: dict[str, FreguesiaTrajectory] = {}

    for row in rows:
        if row.freguesia_id in mapping:
            raise TrajectoryMapError(
                f"duplicate trajectory freguesia_id: {row.freguesia_id}"
            )
        mapping[row.freguesia_id] = row

    return mapping


def _unique_reference_mapping(
    reference: Sequence[ReferenceFeature],
) -> dict[str, ReferenceFeature]:
    """Build a unique reference-feature mapping."""
    mapping: dict[str, ReferenceFeature] = {}

    for feature in reference:
        if feature.freguesia_id in mapping:
            raise TrajectoryMapError(
                f"duplicate reference freguesia_id: {feature.freguesia_id}"
            )
        mapping[feature.freguesia_id] = feature

    return mapping


def _required(value: str | None, row: int, field: str) -> str:
    """Return a required CSV string."""
    if value is None or not value.strip():
        raise TrajectoryMapError(f"row {row}.{field} must be non-empty")
    return value.strip()


def _required_int(value: str | None, row: int, field: str) -> int:
    """Parse a required integer CSV field."""
    raw = _required(value, row, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise TrajectoryMapError(f"row {row}.{field} must be an integer") from exc


def _optional_int(value: str | None, row: int, field: str) -> int | None:
    """Parse an optional integer CSV field."""
    if value is None or not value.strip():
        return None
    try:
        return int(value.strip())
    except ValueError as exc:
        raise TrajectoryMapError(f"row {row}.{field} must be an integer") from exc


def _optional_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal | None:
    """Parse an optional Decimal CSV field."""
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise TrajectoryMapError(f"row {row}.{field} must be numeric") from exc


def _decimal_number(value: Decimal | None) -> float | None:
    """Convert an exact Decimal to a GeoJSON-compatible number."""
    return None if value is None else float(value)
