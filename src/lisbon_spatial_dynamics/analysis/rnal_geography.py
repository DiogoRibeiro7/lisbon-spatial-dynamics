"""Coordinate evidence for parish conflicts, without correcting registry records."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from lisbon_spatial_dynamics.panels.rnal import RNALRecord
from lisbon_spatial_dynamics.sources.rnal_geodata import validate_records
from lisbon_spatial_dynamics.sources.rnal_locations import validate_locations


def conflict_cohort(
    soap: Sequence[RNALRecord],
    gis: list[dict[str, Any]],
) -> dict[int, tuple[str, str]]:
    """Join by registry number; select disagreements among shared registrations."""
    validate_records(gis)
    indexed: dict[int, RNALRecord] = {}
    for row in soap:
        if not re.fullmatch(r"[0-9]+/AL", row.registration_id):
            raise ValueError("invalid SOAP registry number")
        number = int(row.registration_id[:-3])
        if number <= 0 or number in indexed:
            raise ValueError("invalid or duplicate normalized SOAP registry number")
        indexed[number] = row
    return {
        row["NrRNAL"]: (indexed[row["NrRNAL"]].freguesia_id, row["DTMNFR"])
        for row in gis
        if row["NrRNAL"] in indexed and indexed[row["NrRNAL"]].freguesia_id != row["DTMNFR"]
    }


def project_boundaries(
    document: dict[str, Any],
    *,
    expected_count: int,
) -> tuple[dict[str, BaseGeometry], dict[str, str], Transformer]:
    """Project canonical WGS84 GeoJSON to metre-based Portugal TM06 (EPSG:3763)."""
    if document.get("type") != "FeatureCollection" or "crs" in document:
        raise ValueError("canonical boundaries must be RFC 7946 WGS84 GeoJSON")
    projector = Transformer.from_crs(4326, 3763, always_xy=True, allow_ballpark=False)
    if projector.is_network_enabled:
        raise ValueError("PROJ network access must be disabled for offline replay")
    polygons: dict[str, BaseGeometry] = {}
    names: dict[str, str] = {}
    for feature in document["features"]:
        props = feature["properties"]
        code = props["freguesia_id"]
        if not isinstance(code, str) or not re.fullmatch(r"1106[0-9]{2}", code) or code in polygons:
            raise ValueError("invalid or duplicate canonical parish ID")
        geometry = shape(feature["geometry"])
        if (
            geometry.geom_type not in ("Polygon", "MultiPolygon")
            or geometry.is_empty
            or not geometry.is_valid
        ):
            raise ValueError("invalid canonical parish polygon")
        x0, y0, x1, y1 = geometry.bounds
        if not (-180 <= x0 <= x1 <= 180 and -90 <= y0 <= y1 <= 90):
            raise ValueError("canonical boundaries are not longitude/latitude coordinates")
        projected = transform(projector.transform, geometry)
        if not projected.is_valid or not all(math.isfinite(value) for value in projected.bounds):
            raise ValueError("invalid projected parish geometry")
        polygons[code] = projected
        names[code] = props["name"]
    if len(polygons) != expected_count or expected_count <= 0:
        raise ValueError("canonical parish count mismatch")
    # Boundary contacts are allowed; overlapping interiors invalidate a partition.
    ids = sorted(polygons)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if polygons[left].intersection(polygons[right]).area > 0:
                raise ValueError("canonical parish interiors overlap")
    return polygons, names, projector


def validate_conflict_parishes(
    conflicts: Mapping[int, tuple[str, str]], parish_ids: Collection[str]
) -> None:
    """Reject unknown parish codes before projecting or classifying any point."""
    for index, source in enumerate(("SOAP", "GIS")):
        unknown = sorted({pair[index] for pair in conflicts.values()} - set(parish_ids))
        if unknown:
            raise ValueError(
                f"{source} conflict parishes absent from canonical reference: {unknown}"
            )
    if any(soap == gis for soap, gis in conflicts.values()):
        raise ValueError("conflicts must have distinct SOAP and GIS parish assignments")


def classify_point(
    point: Point | None,
    polygons: Mapping[str, BaseGeometry],
    soap_parish: str,
    gis_parish: str,
) -> tuple[str, float | None]:
    """Classify metre-based coordinates; boundary points are never assigned by tie-break."""
    validate_conflict_parishes({0: (soap_parish, gis_parish)}, polygons)
    if point is None:
        return "missing_geometry", None
    if point.is_empty or not math.isfinite(point.x) or not math.isfinite(point.y):
        raise ValueError("invalid projected point")
    covered = [code for code, geometry in polygons.items() if geometry.covers(point)]
    distance = min(point.distance(geometry.boundary) for geometry in polygons.values())
    if not covered:
        return "outside_reference", distance
    if len(covered) != 1 or polygons[covered[0]].boundary.covers(point):
        return "boundary_ambiguous", distance
    return (
        "supports_soap"
        if covered[0] == soap_parish
        else "supports_gis"
        if covered[0] == gis_parish
        else "supports_other_parish"
    ), distance


def coordinate_evidence(
    conflicts: Mapping[int, tuple[str, str]],
    locations: list[dict[str, Any]],
    polygons: Mapping[str, BaseGeometry],
    projector: Transformer,
) -> dict[int, tuple[str, float | None]]:
    """Return in-memory evidence after validating the complete conflict cohort."""
    validate_conflict_parishes(conflicts, polygons)
    validate_locations(locations, {key: value[1] for key, value in conflicts.items()})
    evidence = {}
    for row in locations:
        geometry = row["geometry"]
        point = (
            None
            if geometry is None
            else Point(projector.transform(geometry["x"], geometry["y"], errcheck=True))
        )
        evidence[row["NrRNAL"]] = classify_point(point, polygons, *conflicts[row["NrRNAL"]])
    return evidence


def reconcile(
    conflicts: Mapping[int, tuple[str, str]],
    locations: list[dict[str, Any]],
    polygons: Mapping[str, BaseGeometry],
    names: Mapping[str, str],
    projector: Transformer,
    *,
    thresholds_m: Sequence[float],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Aggregate coordinate support and boundary-distance sensitivity only."""
    if (
        not thresholds_m
        or len(set(thresholds_m)) != len(thresholds_m)
        or any(not math.isfinite(value) or value < 0 for value in thresholds_m)
    ):
        raise ValueError("unique finite non-negative boundary thresholds required")
    evidence = coordinate_evidence(conflicts, locations, polygons, projector)
    categories = (
        "supports_soap",
        "supports_gis",
        "supports_other_parish",
        "boundary_ambiguous",
        "outside_reference",
        "missing_geometry",
    )
    counts: Counter[str] = Counter()
    by_parish = {code: Counter[str]() for code in polygons}
    sensitivity = {threshold: Counter[str]() for threshold in sorted(thresholds_m)}
    reliability: Counter[str] = Counter()
    for row in locations:
        soap_parish, _ = conflicts[row["NrRNAL"]]
        category, distance = evidence[row["NrRNAL"]]
        counts[category] += 1
        by_parish[soap_parish][category] += 1
        reliability[row["FiabilidadeGeo"] or "missing"] += 1
        for threshold, counter in sensitivity.items():
            if distance is not None and distance <= threshold:
                counter["within_boundary_margin"] += 1
            if category.startswith("supports_") and distance is not None and distance > threshold:
                counter[category] += 1
    rows = [
        {
            "soap_freguesia_id": code,
            "freguesia_name": names[code],
            "conflicting_records": sum(by_parish[code].values()),
            **{category: by_parish[code][category] for category in categories},
        }
        for code in sorted(polygons)
    ]
    summary: dict[str, object] = {
        "conflicting_records": len(conflicts),
        "categories": {key: counts[key] for key in categories},
        "provider_reliability_values": dict(sorted(reliability.items())),
        "boundary_sensitivity": [
            {
                "margin_m": threshold,
                **{
                    key: counter[key]
                    for key in (
                        "within_boundary_margin",
                        "supports_soap",
                        "supports_gis",
                        "supports_other_parish",
                    )
                },
            }
            for threshold, counter in sensitivity.items()
        ],
        "assignments_corrected": 0,
        "interpretation": (
            "Coordinate support among previously conflicting records, not verified "
            "establishment addresses or full-registry accuracy."
        ),
    }
    return summary, rows
