"""Canonical Lisbon reference-geography transformation."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class ReferenceGeographyError(ValueError):
    """Raised when a CAOP GeoJSON payload cannot form the canonical geography."""


@dataclass(frozen=True, slots=True)
class FreguesiaReference:
    """One canonical Lisbon freguesia and its source geometry."""

    freguesia_id: str
    name: str
    simplified_name: str
    municipality: str
    district: str
    nuts3_code: str
    nuts3_name: str
    nuts2_name: str
    nuts1_name: str
    area_ha: float
    geometry: Mapping[str, object]


REFERENCE_COLUMNS: tuple[str, ...] = (
    "freguesia_id",
    "name",
    "simplified_name",
    "municipality",
    "district",
    "nuts3_code",
    "nuts3_name",
    "nuts2_name",
    "nuts1_name",
    "area_ha",
)


def parse_caop_reference(
    payload: bytes,
    *,
    expected_count: int = 24,
) -> tuple[FreguesiaReference, ...]:
    """Parse raw CAOP GeoJSON into the stable Lisbon reference contract.

    Args:
        payload: Raw CAOP GeoJSON bytes.
        expected_count: Required number of Lisbon freguesias.

    Returns:
        Freguesias sorted by canonical `DTMNFR` identifier.

    Raises:
        ReferenceGeographyError: If source structure or required fields are invalid.
    """
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    try:
        raw: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceGeographyError("CAOP payload is not valid JSON") from exc

    collection = _require_mapping(raw, "root")
    if collection.get("type") != "FeatureCollection":
        raise ReferenceGeographyError("CAOP payload must be a FeatureCollection")

    features = collection.get("features")
    if not isinstance(features, list):
        raise ReferenceGeographyError("FeatureCollection.features must be a list")
    if len(features) != expected_count:
        raise ReferenceGeographyError(
            f"unexpected freguesia count: {len(features)} != {expected_count}"
        )

    references: list[FreguesiaReference] = []
    seen_ids: set[str] = set()

    for index, feature_raw in enumerate(features):
        context = f"features[{index}]"
        feature = _require_mapping(feature_raw, context)
        properties = _require_mapping(feature.get("properties"), f"{context}.properties")
        geometry = _require_mapping(feature.get("geometry"), f"{context}.geometry")

        freguesia_id = _require_string(properties, "dtmnfr", f"{context}.properties")
        if freguesia_id in seen_ids:
            raise ReferenceGeographyError(
                f"duplicate freguesia identifier: {freguesia_id}"
            )
        seen_ids.add(freguesia_id)

        geometry_type = geometry.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ReferenceGeographyError(
                f"{context}.geometry has unsupported type: {geometry_type!r}"
            )

        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            raise ReferenceGeographyError(f"{context}.geometry has no coordinates")

        municipality = _require_string(
            properties, "municipio", f"{context}.properties"
        )
        if municipality.casefold() != "lisboa":
            raise ReferenceGeographyError(
                f"{context} belongs to municipality {municipality!r}, not Lisboa"
            )

        references.append(
            FreguesiaReference(
                freguesia_id=freguesia_id,
                name=_require_string(properties, "freguesia", f"{context}.properties"),
                simplified_name=_optional_string(
                    properties, "designacao_simplificada", f"{context}.properties"
                ),
                municipality=municipality,
                district=_require_string(
                    properties, "distrito_ilha", f"{context}.properties"
                ),
                nuts3_code=_require_string(
                    properties, "nuts3_cod", f"{context}.properties"
                ),
                nuts3_name=_require_string(
                    properties, "nuts3", f"{context}.properties"
                ),
                nuts2_name=_require_string(
                    properties, "nuts2", f"{context}.properties"
                ),
                nuts1_name=_require_string(
                    properties, "nuts1", f"{context}.properties"
                ),
                area_ha=_require_positive_number(
                    properties, "area_ha", f"{context}.properties"
                ),
                geometry=geometry,
            )
        )

    return tuple(sorted(references, key=lambda row: row.freguesia_id))


def write_reference_geography(
    references: Sequence[FreguesiaReference],
    *,
    csv_path: Path,
    geojson_path: Path,
) -> None:
    """Write deterministic canonical CSV and GeoJSON reference artifacts."""
    if not references:
        raise ReferenceGeographyError("reference geography cannot be empty")
    if len({row.freguesia_id for row in references}) != len(references):
        raise ReferenceGeographyError("reference geography contains duplicate identifiers")
    if csv_path.exists():
        raise FileExistsError(csv_path)
    if geojson_path.exists():
        raise FileExistsError(geojson_path)

    ordered = tuple(sorted(references, key=lambda row: row.freguesia_id))
    csv_payload = _build_csv_payload(ordered)
    geojson_payload = _build_geojson_payload(ordered)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    geojson_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(csv_payload)

    try:
        with geojson_path.open("x", encoding="utf-8") as stream:
            stream.write(geojson_payload)
    except FileExistsError:
        csv_path.unlink(missing_ok=True)
        raise


def _build_csv_payload(references: Sequence[FreguesiaReference]) -> str:
    """Build the stable tabular freguesia index."""
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(REFERENCE_COLUMNS)

    for row in references:
        writer.writerow(
            (
                row.freguesia_id,
                row.name,
                row.simplified_name,
                row.municipality,
                row.district,
                row.nuts3_code,
                row.nuts3_name,
                row.nuts2_name,
                row.nuts1_name,
                format(row.area_ha, ".12g"),
            )
        )

    return stream.getvalue()


def _build_geojson_payload(references: Sequence[FreguesiaReference]) -> str:
    """Build canonical GeoJSON with project-owned property names."""
    features: list[dict[str, object]] = []

    for row in references:
        features.append(
            {
                "type": "Feature",
                "id": row.freguesia_id,
                "properties": {
                    "freguesia_id": row.freguesia_id,
                    "name": row.name,
                    "simplified_name": row.simplified_name,
                    "municipality": row.municipality,
                    "district": row.district,
                    "nuts3_code": row.nuts3_code,
                    "nuts3_name": row.nuts3_name,
                    "nuts2_name": row.nuts2_name,
                    "nuts1_name": row.nuts1_name,
                    "area_ha": row.area_ha,
                    "source": "DGT CAOP2025",
                },
                "geometry": dict(row.geometry),
            }
        )

    document: dict[str, object] = {
        "type": "FeatureCollection",
        "name": "lisbon_freguesias_caop2025",
        "features": features,
    }
    return json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required JSON object."""
    if not isinstance(value, Mapping):
        raise ReferenceGeographyError(f"{context} must be a JSON object")
    return cast(Mapping[str, object], value)


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReferenceGeographyError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _optional_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return an optional string, preserving missingness as an empty value."""
    value = raw.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ReferenceGeographyError(f"{context}.{key} must be a string")
    return value.strip()


def _require_positive_number(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> float:
    """Return a required positive numeric source field."""
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceGeographyError(f"{context}.{key} must be numeric")

    number = float(value)
    if number <= 0:
        raise ReferenceGeographyError(f"{context}.{key} must be positive")
    return number
