"""Build map-ready annual GeoJSON layers from the canonical annual panel."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.panels.annual import AnnualUrbanRow


class AnnualMapError(ValueError):
    """Raised when annual data and canonical geometry cannot be joined safely."""


@dataclass(frozen=True, slots=True)
class ReferenceFeature:
    """One canonical freguesia feature from the project GeoJSON."""

    freguesia_id: str
    name: str
    properties: Mapping[str, object]
    geometry: Mapping[str, object]


def load_annual_urban_csv(path: Path) -> tuple[AnnualUrbanRow, ...]:
    """Load the Q4-anchored annual urban-change panel."""
    rows: list[AnnualUrbanRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "year",
            "baseline_year",
            "period_code",
            "period_end",
            "freguesia_id",
            "freguesia_name",
            "flow_quarters_observed",
            "housing_value_eur_m2",
            "housing_yoy_abs_eur_m2",
            "housing_yoy_pct",
            "housing_change_from_baseline_abs_eur_m2",
            "housing_change_from_baseline_pct",
            "rnal_registrations_year",
            "rnal_cessations_year",
            "rnal_net_registrations_year",
            "rnal_active_registrations_year_end",
            "rnal_active_change_from_baseline_abs",
            "rnal_active_change_from_baseline_pct",
            "rnal_active_beds_known_year_end",
            "rnal_active_beds_missing_year_end",
            "rnal_active_users_known_year_end",
            "rnal_active_users_missing_year_end",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise AnnualMapError(
                "annual urban CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for index, raw in enumerate(reader, start=2):
            rows.append(
                AnnualUrbanRow(
                    year=_required_int(raw.get("year"), index, "year"),
                    baseline_year=_required_int(raw.get("baseline_year"), index, "baseline_year"),
                    period_code=_required(raw.get("period_code"), index, "period_code"),
                    period_end=_required_date(raw.get("period_end"), index, "period_end"),
                    freguesia_id=_required(raw.get("freguesia_id"), index, "freguesia_id"),
                    freguesia_name=_required(raw.get("freguesia_name"), index, "freguesia_name"),
                    flow_quarters_observed=_required_int(
                        raw.get("flow_quarters_observed"),
                        index,
                        "flow_quarters_observed",
                    ),
                    housing_value_eur_m2=_optional_decimal(
                        raw.get("housing_value_eur_m2"),
                        index,
                        "housing_value_eur_m2",
                    ),
                    housing_yoy_abs_eur_m2=_optional_decimal(
                        raw.get("housing_yoy_abs_eur_m2"),
                        index,
                        "housing_yoy_abs_eur_m2",
                    ),
                    housing_yoy_pct=_optional_decimal(
                        raw.get("housing_yoy_pct"),
                        index,
                        "housing_yoy_pct",
                    ),
                    housing_change_from_baseline_abs_eur_m2=_optional_decimal(
                        raw.get("housing_change_from_baseline_abs_eur_m2"),
                        index,
                        "housing_change_from_baseline_abs_eur_m2",
                    ),
                    housing_change_from_baseline_pct=_optional_decimal(
                        raw.get("housing_change_from_baseline_pct"),
                        index,
                        "housing_change_from_baseline_pct",
                    ),
                    rnal_registrations_year=_optional_int(
                        raw.get("rnal_registrations_year"),
                        index,
                        "rnal_registrations_year",
                    ),
                    rnal_cessations_year=_optional_int(
                        raw.get("rnal_cessations_year"),
                        index,
                        "rnal_cessations_year",
                    ),
                    rnal_net_registrations_year=_optional_int(
                        raw.get("rnal_net_registrations_year"),
                        index,
                        "rnal_net_registrations_year",
                    ),
                    rnal_active_registrations_year_end=_required_int(
                        raw.get("rnal_active_registrations_year_end"),
                        index,
                        "rnal_active_registrations_year_end",
                    ),
                    rnal_active_change_from_baseline_abs=_required_int(
                        raw.get("rnal_active_change_from_baseline_abs"),
                        index,
                        "rnal_active_change_from_baseline_abs",
                    ),
                    rnal_active_change_from_baseline_pct=_optional_decimal(
                        raw.get("rnal_active_change_from_baseline_pct"),
                        index,
                        "rnal_active_change_from_baseline_pct",
                    ),
                    rnal_active_beds_known_year_end=_required_int(
                        raw.get("rnal_active_beds_known_year_end"),
                        index,
                        "rnal_active_beds_known_year_end",
                    ),
                    rnal_active_beds_missing_year_end=_required_int(
                        raw.get("rnal_active_beds_missing_year_end"),
                        index,
                        "rnal_active_beds_missing_year_end",
                    ),
                    rnal_active_users_known_year_end=_required_int(
                        raw.get("rnal_active_users_known_year_end"),
                        index,
                        "rnal_active_users_known_year_end",
                    ),
                    rnal_active_users_missing_year_end=_required_int(
                        raw.get("rnal_active_users_missing_year_end"),
                        index,
                        "rnal_active_users_missing_year_end",
                    ),
                )
            )

    if not rows:
        raise AnnualMapError("annual urban CSV cannot be empty")

    return tuple(rows)


def load_reference_geojson(
    path: Path,
    *,
    expected_count: int = 24,
) -> tuple[ReferenceFeature, ...]:
    """Load the canonical project GeoJSON and validate its stable identifiers."""
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AnnualMapError("reference GeoJSON is not valid JSON") from exc

    document = _require_mapping(raw, "root")
    if document.get("type") != "FeatureCollection":
        raise AnnualMapError("reference GeoJSON must be a FeatureCollection")

    features_raw = document.get("features")
    if not isinstance(features_raw, list):
        raise AnnualMapError("reference GeoJSON features must be a list")
    if len(features_raw) != expected_count:
        raise AnnualMapError(
            f"unexpected reference feature count: {len(features_raw)} != {expected_count}"
        )

    features: list[ReferenceFeature] = []
    seen_ids: set[str] = set()

    for index, feature_raw in enumerate(features_raw):
        context = f"features[{index}]"
        feature = _require_mapping(feature_raw, context)
        properties = _require_mapping(feature.get("properties"), f"{context}.properties")
        geometry = _require_mapping(feature.get("geometry"), f"{context}.geometry")

        freguesia_id = _require_object_string(properties, "freguesia_id", f"{context}.properties")
        feature_id = feature.get("id")
        if feature_id != freguesia_id:
            raise AnnualMapError(f"{context}.id must equal properties.freguesia_id")
        if freguesia_id in seen_ids:
            raise AnnualMapError(f"duplicate reference freguesia_id: {freguesia_id}")
        seen_ids.add(freguesia_id)

        name = _require_object_string(properties, "name", f"{context}.properties")
        geometry_type = geometry.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise AnnualMapError(f"{context}.geometry has unsupported type: {geometry_type!r}")

        features.append(
            ReferenceFeature(
                freguesia_id=freguesia_id,
                name=name,
                properties=properties,
                geometry=geometry,
            )
        )

    return tuple(sorted(features, key=lambda feature: feature.freguesia_id))


def build_annual_geojson_layers(
    rows: Sequence[AnnualUrbanRow],
    reference: Sequence[ReferenceFeature],
) -> dict[int, dict[str, object]]:
    """Join each annual panel year to the exact canonical reference geometry."""
    if not rows:
        raise AnnualMapError("annual urban rows cannot be empty")
    if not reference:
        raise AnnualMapError("reference geometry cannot be empty")

    reference_by_id = _reference_mapping(reference)
    expected_ids = set(reference_by_id)
    by_year: dict[int, dict[str, AnnualUrbanRow]] = {}

    for row in rows:
        year_rows = by_year.setdefault(row.year, {})
        if row.freguesia_id in year_rows:
            raise AnnualMapError(f"duplicate annual key: ({row.year}, {row.freguesia_id})")
        year_rows[row.freguesia_id] = row

    layers: dict[int, dict[str, object]] = {}

    for year in sorted(by_year):
        year_rows = by_year[year]
        ids = set(year_rows)

        if ids != expected_ids:
            missing = sorted(expected_ids - ids)
            extra = sorted(ids - expected_ids)
            raise AnnualMapError(
                f"{year} annual/reference key mismatch; missing={missing}, extra={extra}"
            )

        features: list[dict[str, object]] = []

        for freguesia_id in sorted(expected_ids):
            reference_feature = reference_by_id[freguesia_id]
            row = year_rows[freguesia_id]

            if row.freguesia_name != reference_feature.name:
                raise AnnualMapError(
                    f"{year}/{freguesia_id} name mismatch: "
                    f"{row.freguesia_name!r} != {reference_feature.name!r}"
                )

            properties = dict(reference_feature.properties)
            properties.update(_annual_properties(row))

            features.append(
                {
                    "type": "Feature",
                    "id": freguesia_id,
                    "properties": properties,
                    "geometry": dict(reference_feature.geometry),
                }
            )

        layers[year] = {
            "type": "FeatureCollection",
            "name": f"lisbon_urban_change_{year}",
            "year": year,
            "feature_count": len(features),
            "features": features,
        }

    return layers


def write_annual_geojson_layers(
    layers: Mapping[int, Mapping[str, object]],
    output_directory: Path,
) -> tuple[Path, ...]:
    """Write one immutable map-ready GeoJSON layer per year."""
    if not layers:
        raise AnnualMapError("annual GeoJSON layers cannot be empty")

    targets = tuple(
        output_directory / f"lisbon_urban_change_{year}.geojson" for year in sorted(layers)
    )

    existing = [path for path in targets if path.exists()]
    if existing:
        raise FileExistsError(existing[0])

    payloads = {
        year: (
            json.dumps(
                layers[year],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        for year in sorted(layers)
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    try:
        for year, path in zip(sorted(layers), targets, strict=True):
            with path.open("x", encoding="utf-8") as stream:
                stream.write(payloads[year])
            written.append(path)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return targets


def _annual_properties(row: AnnualUrbanRow) -> dict[str, object]:
    """Convert one annual row to interoperable GeoJSON properties."""
    return {
        "year": row.year,
        "baseline_year": row.baseline_year,
        "period_code": row.period_code,
        "period_end": row.period_end.isoformat(),
        "flow_quarters_observed": row.flow_quarters_observed,
        "housing_value_eur_m2": _decimal_number(row.housing_value_eur_m2),
        "housing_yoy_abs_eur_m2": _decimal_number(row.housing_yoy_abs_eur_m2),
        "housing_yoy_pct": _decimal_number(row.housing_yoy_pct),
        "housing_change_from_baseline_abs_eur_m2": _decimal_number(
            row.housing_change_from_baseline_abs_eur_m2
        ),
        "housing_change_from_baseline_pct": _decimal_number(row.housing_change_from_baseline_pct),
        "rnal_registrations_year": row.rnal_registrations_year,
        "rnal_cessations_year": row.rnal_cessations_year,
        "rnal_net_registrations_year": row.rnal_net_registrations_year,
        "rnal_active_registrations_year_end": (row.rnal_active_registrations_year_end),
        "rnal_active_change_from_baseline_abs": (row.rnal_active_change_from_baseline_abs),
        "rnal_active_change_from_baseline_pct": _decimal_number(
            row.rnal_active_change_from_baseline_pct
        ),
        "rnal_active_beds_known_year_end": row.rnal_active_beds_known_year_end,
        "rnal_active_beds_missing_year_end": (row.rnal_active_beds_missing_year_end),
        "rnal_active_users_known_year_end": (row.rnal_active_users_known_year_end),
        "rnal_active_users_missing_year_end": (row.rnal_active_users_missing_year_end),
    }


def _reference_mapping(
    reference: Sequence[ReferenceFeature],
) -> dict[str, ReferenceFeature]:
    """Build a unique reference-feature mapping."""
    mapping: dict[str, ReferenceFeature] = {}

    for feature in reference:
        if feature.freguesia_id in mapping:
            raise AnnualMapError(f"duplicate reference freguesia_id: {feature.freguesia_id}")
        mapping[feature.freguesia_id] = feature

    return mapping


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required JSON object."""
    if not isinstance(value, Mapping):
        raise AnnualMapError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


def _require_object_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string from a JSON mapping."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AnnualMapError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _required(value: str | None, row: int, field: str) -> str:
    """Return a required CSV string."""
    if value is None or not value.strip():
        raise AnnualMapError(f"row {row}.{field} must be non-empty")
    return value.strip()


def _required_int(value: str | None, row: int, field: str) -> int:
    """Parse a required integer CSV field."""
    raw = _required(value, row, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise AnnualMapError(f"row {row}.{field} must be an integer") from exc


def _optional_int(value: str | None, row: int, field: str) -> int | None:
    """Parse an optional integer CSV field."""
    if value is None or not value.strip():
        return None

    try:
        return int(value.strip())
    except ValueError as exc:
        raise AnnualMapError(f"row {row}.{field} must be an integer") from exc


def _required_date(value: str | None, row: int, field: str) -> date:
    """Parse a required ISO date CSV field."""
    raw = _required(value, row, field)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise AnnualMapError(f"row {row}.{field} must be an ISO date") from exc


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
        raise AnnualMapError(f"row {row}.{field} must be numeric") from exc


def _decimal_number(value: Decimal | None) -> float | None:
    """Convert an exact table Decimal to a GeoJSON-compatible number."""
    return None if value is None else float(value)
