"""Static choropleths for baseline-to-latest freguesia trajectories."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class ChoroplethError(ValueError):
    """Raised when trajectory GeoJSON cannot be rendered safely."""


@dataclass(frozen=True, slots=True)
class TrajectoryMapFeature:
    """One validated trajectory feature for plotting."""

    freguesia_id: str
    name: str
    housing_change_pct: float | None
    rnal_active_change_pct: float | None
    geometry: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TrajectoryMapData:
    """Validated common-window trajectory map data."""

    baseline_year: int
    latest_year: int
    features: tuple[TrajectoryMapFeature, ...]


def load_trajectory_map(path: Path) -> TrajectoryMapData:
    """Load and validate a trajectory GeoJSON document."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ChoroplethError("trajectory GeoJSON is not valid JSON") from exc

    document = _require_mapping(raw, "root")
    if document.get("type") != "FeatureCollection":
        raise ChoroplethError("trajectory GeoJSON must be a FeatureCollection")

    baseline_year = _require_int(document.get("baseline_year"), "baseline_year")
    latest_year = _require_int(document.get("latest_year"), "latest_year")
    if latest_year <= baseline_year:
        raise ChoroplethError("latest_year must be greater than baseline_year")

    features_raw = document.get("features")
    if not isinstance(features_raw, list) or not features_raw:
        raise ChoroplethError("trajectory GeoJSON features must be a non-empty list")

    features: list[TrajectoryMapFeature] = []
    seen_ids: set[str] = set()

    for index, raw_feature in enumerate(features_raw):
        context = f"features[{index}]"
        feature = _require_mapping(raw_feature, context)
        properties = _require_mapping(
            feature.get("properties"),
            f"{context}.properties",
        )
        geometry = _require_mapping(feature.get("geometry"), f"{context}.geometry")

        freguesia_id = _require_string(
            properties,
            "freguesia_id",
            f"{context}.properties",
        )
        feature_id = feature.get("id")
        if feature_id != freguesia_id:
            raise ChoroplethError(
                f"{context}.id must equal properties.freguesia_id"
            )
        if freguesia_id in seen_ids:
            raise ChoroplethError(
                f"duplicate trajectory freguesia_id: {freguesia_id}"
            )
        seen_ids.add(freguesia_id)

        geometry_type = geometry.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise ChoroplethError(
                f"{context}.geometry has unsupported type: {geometry_type!r}"
            )
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            raise ChoroplethError(f"{context}.geometry has no coordinates")

        features.append(
            TrajectoryMapFeature(
                freguesia_id=freguesia_id,
                name=_require_string(
                    properties,
                    "name",
                    f"{context}.properties",
                ),
                housing_change_pct=_optional_number(
                    properties.get("housing_change_pct"),
                    f"{context}.properties.housing_change_pct",
                ),
                rnal_active_change_pct=_optional_number(
                    properties.get("rnal_active_change_pct"),
                    f"{context}.properties.rnal_active_change_pct",
                ),
                geometry=geometry,
            )
        )

    return TrajectoryMapData(
        baseline_year=baseline_year,
        latest_year=latest_year,
        features=tuple(sorted(features, key=lambda feature: feature.freguesia_id)),
    )


def write_trajectory_choropleths(
    data: TrajectoryMapData,
    output_directory: Path,
    *,
    label_freguesias: bool = False,
) -> tuple[Path, Path]:
    """Write housing-change and RNAL-change choropleths.

    Existing outputs are never overwritten.
    """
    housing_path = output_directory / "housing_change_pct.png"
    rnal_path = output_directory / "rnal_active_change_pct.png"

    for path in (housing_path, rnal_path):
        if path.exists():
            raise FileExistsError(path)

    output_directory.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    try:
        _write_choropleth(
            data,
            value_name="housing_change_pct",
            title="Housing value change",
            legend_label="Housing change (%)",
            output_path=housing_path,
            label_freguesias=label_freguesias,
        )
        written.append(housing_path)

        _write_choropleth(
            data,
            value_name="rnal_active_change_pct",
            title="Active local-accommodation change",
            legend_label="Active RNAL change (%)",
            output_path=rnal_path,
            label_freguesias=label_freguesias,
        )
        written.append(rnal_path)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return housing_path, rnal_path


def _write_choropleth(
    data: TrajectoryMapData,
    *,
    value_name: str,
    title: str,
    legend_label: str,
    output_path: Path,
    label_freguesias: bool,
) -> None:
    """Render one trajectory metric as a static choropleth."""
    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize, TwoSlopeNorm
    from matplotlib.patches import Polygon

    values = [
        _metric_value(feature, value_name)
        for feature in data.features
        if _metric_value(feature, value_name) is not None
    ]
    if not values:
        raise ChoroplethError(f"{value_name} has no non-missing values")

    minimum = min(values)
    maximum = max(values)

    if math.isclose(minimum, maximum):
        padding = 1.0 if math.isclose(minimum, 0.0) else abs(minimum) * 0.05
        if math.isclose(padding, 0.0):
            padding = 1.0
        norm: Normalize = Normalize(vmin=minimum - padding, vmax=maximum + padding)
    elif minimum < 0 < maximum:
        norm = TwoSlopeNorm(vmin=minimum, vcenter=0.0, vmax=maximum)
    else:
        norm = Normalize(vmin=minimum, vmax=maximum)

    cmap = plt.get_cmap("coolwarm")
    figure, axis = plt.subplots(figsize=(8, 8))

    for feature in data.features:
        value = _metric_value(feature, value_name)
        facecolor = "0.85" if value is None else cmap(norm(value))

        for ring in _exterior_rings(feature.geometry):
            patch = Polygon(
                ring,
                closed=True,
                facecolor=facecolor,
                edgecolor="0.25",
                linewidth=0.6,
            )
            axis.add_patch(patch)

        if label_freguesias:
            x, y = _label_point(feature.geometry)
            axis.annotate(
                feature.name,
                (x, y),
                ha="center",
                va="center",
                fontsize=6,
            )

    axis.autoscale_view()
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        f"{title}, {data.baseline_year}–{data.latest_year}",
        pad=12,
    )

    mappable = ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    figure.colorbar(
        mappable,
        ax=axis,
        shrink=0.72,
        label=legend_label,
    )
    figure.tight_layout()

    try:
        figure.savefig(output_path, dpi=180, bbox_inches="tight")
    finally:
        plt.close(figure)


def _metric_value(
    feature: TrajectoryMapFeature,
    value_name: str,
) -> float | None:
    """Return one supported trajectory metric."""
    if value_name == "housing_change_pct":
        return feature.housing_change_pct
    if value_name == "rnal_active_change_pct":
        return feature.rnal_active_change_pct
    raise ChoroplethError(f"unsupported choropleth metric: {value_name}")


def _exterior_rings(
    geometry: Mapping[str, object],
) -> tuple[list[tuple[float, float]], ...]:
    """Extract exterior polygon rings from GeoJSON geometry."""
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, list):
        raise ChoroplethError("geometry.coordinates must be a list")

    polygon_rings: list[object]
    if geometry_type == "Polygon":
        polygon_rings = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygon_rings = coordinates
    else:
        raise ChoroplethError(f"unsupported geometry type: {geometry_type!r}")

    exteriors: list[list[tuple[float, float]]] = []

    for polygon_index, polygon_raw in enumerate(polygon_rings):
        if not isinstance(polygon_raw, list) or not polygon_raw:
            raise ChoroplethError(
                f"polygon {polygon_index} must contain at least one ring"
            )

        exterior_raw = polygon_raw[0]
        if not isinstance(exterior_raw, list) or len(exterior_raw) < 4:
            raise ChoroplethError(
                f"polygon {polygon_index} exterior ring is invalid"
            )

        exterior: list[tuple[float, float]] = []
        for point_index, point_raw in enumerate(exterior_raw):
            if (
                not isinstance(point_raw, list)
                or len(point_raw) < 2
                or isinstance(point_raw[0], bool)
                or isinstance(point_raw[1], bool)
                or not isinstance(point_raw[0], (int, float))
                or not isinstance(point_raw[1], (int, float))
            ):
                raise ChoroplethError(
                    f"polygon {polygon_index} point {point_index} is invalid"
                )
            exterior.append((float(point_raw[0]), float(point_raw[1])))

        exteriors.append(exterior)

    return tuple(exteriors)


def _label_point(geometry: Mapping[str, object]) -> tuple[float, float]:
    """Return a simple exterior-ring centroid for optional labels."""
    rings = _exterior_rings(geometry)
    largest = max(rings, key=lambda ring: abs(_signed_area(ring)))
    points = largest[:-1] if largest[0] == largest[-1] else largest

    x = sum(point[0] for point in points) / len(points)
    y = sum(point[1] for point in points) / len(points)
    return x, y


def _signed_area(ring: Sequence[tuple[float, float]]) -> float:
    """Return polygon signed area for selecting the dominant exterior."""
    area = 0.0
    for current, following in zip(ring, ring[1:] + ring[:1], strict=True):
        area += current[0] * following[1] - following[0] * current[1]
    return area / 2.0


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required JSON object."""
    if not isinstance(value, Mapping):
        raise ChoroplethError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ChoroplethError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _require_int(value: object, context: str) -> int:
    """Return a required integer value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChoroplethError(f"{context} must be an integer")
    return value


def _optional_number(value: object, context: str) -> float | None:
    """Return an optional finite JSON number."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ChoroplethError(f"{context} must be numeric or null")

    number = float(value)
    if not math.isfinite(number):
        raise ChoroplethError(f"{context} must be finite")
    return number
