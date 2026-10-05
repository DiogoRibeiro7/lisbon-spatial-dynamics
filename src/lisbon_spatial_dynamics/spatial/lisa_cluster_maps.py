"""Static cluster maps for FDR-controlled Local Moran (LISA) results."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    ClusterClass,
    LocalMoranObservation,
    LocalMoranResult,
    LocalStatus,
    Quadrant,
)
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import MetricName
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    _exterior_rings,
    _label_point,
)


class LISAClusterMapError(ValueError):
    """Raised when Local Moran results cannot be mapped safely."""


@dataclass(frozen=True, slots=True)
class LISAMapBundle:
    """Validated Local Moran results for the supported trajectory metrics."""

    housing: LocalMoranResult
    rnal: LocalMoranResult


_SUPPORTED_METRICS: tuple[MetricName, ...] = (
    "housing_change_pct",
    "rnal_active_change_pct",
)


def load_local_morans_json(path: Path) -> LISAMapBundle:
    """Load and validate the machine-readable Local Moran output."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LISAClusterMapError("Local Moran JSON is not valid JSON") from exc

    document = _require_mapping(raw, "root")
    if document.get("analysis") != "local_morans_i":
        raise LISAClusterMapError("Local Moran JSON has an unexpected analysis identifier")

    results_raw = document.get("results")
    if not isinstance(results_raw, list):
        raise LISAClusterMapError("Local Moran results must be a list")

    results: dict[MetricName, LocalMoranResult] = {}

    for index, raw_result in enumerate(results_raw):
        context = f"results[{index}]"
        result = _parse_result(raw_result, context)

        if result.metric in results:
            raise LISAClusterMapError(f"duplicate Local Moran metric: {result.metric}")
        results[result.metric] = result

    missing = set(_SUPPORTED_METRICS) - set(results)
    extra = set(results) - set(_SUPPORTED_METRICS)
    if missing or extra:
        raise LISAClusterMapError(
            f"Local Moran metric set mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )

    return LISAMapBundle(
        housing=results["housing_change_pct"],
        rnal=results["rnal_active_change_pct"],
    )


def write_lisa_cluster_maps(
    trajectory: TrajectoryMapData,
    bundle: LISAMapBundle,
    output_directory: Path,
    *,
    label_freguesias: bool = False,
) -> tuple[Path, Path]:
    """Write housing and RNAL Local Moran cluster maps.

    The plotting layer consumes the final FDR-controlled cluster class from the
    analysis output. It does not recalculate significance.
    """
    _validate_result_against_trajectory(trajectory, bundle.housing)
    _validate_result_against_trajectory(trajectory, bundle.rnal)

    housing_path = output_directory / "housing_lisa_clusters.png"
    rnal_path = output_directory / "rnal_lisa_clusters.png"

    for path in (housing_path, rnal_path):
        if path.exists():
            raise FileExistsError(path)

    output_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    try:
        _write_cluster_map(
            trajectory,
            bundle.housing,
            output_path=housing_path,
            title="Housing value change — Local Moran clusters",
            label_freguesias=label_freguesias,
        )
        written.append(housing_path)

        _write_cluster_map(
            trajectory,
            bundle.rnal,
            output_path=rnal_path,
            title="Active local-accommodation change — Local Moran clusters",
            label_freguesias=label_freguesias,
        )
        written.append(rnal_path)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return housing_path, rnal_path


def _write_cluster_map(
    trajectory: TrajectoryMapData,
    result: LocalMoranResult,
    *,
    output_path: Path,
    title: str,
    label_freguesias: bool,
) -> None:
    """Render one categorical Local Moran cluster map."""
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch, Polygon

    observation_by_id = {
        observation.freguesia_id: observation for observation in result.observations
    }

    class_styles: dict[ClusterClass, tuple[str, str]] = {
        "HH": ("#b2182b", "HH — high/high"),
        "LL": ("#2166ac", "LL — low/low"),
        "HL": ("#ef8a62", "HL — high/low"),
        "LH": ("#67a9cf", "LH — low/high"),
        "not_significant": ("#f0f0f0", "Not significant"),
        "not_evaluated": ("#d9d9d9", "Not evaluated"),
        "missing": ("#bdbdbd", "Missing"),
        "island": ("#969696", "Island"),
        "constant": ("#737373", "Constant metric"),
    }

    figure = Figure(figsize=(8, 8))
    axis = figure.subplots()
    used_classes: set[ClusterClass] = set()

    for feature in trajectory.features:
        observation = observation_by_id[feature.freguesia_id]
        cluster_class = observation.cluster_class
        used_classes.add(cluster_class)
        facecolor = class_styles[cluster_class][0]

        for ring in _exterior_rings(feature.geometry):
            axis.add_patch(
                Polygon(
                    ring,
                    closed=True,
                    facecolor=facecolor,
                    edgecolor="0.25",
                    linewidth=0.6,
                )
            )

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
        f"{title}\n{trajectory.baseline_year}–{trajectory.latest_year}, FDR α={result.alpha:g}",
        pad=12,
    )

    legend_order: tuple[ClusterClass, ...] = (
        "HH",
        "LL",
        "HL",
        "LH",
        "not_significant",
        "not_evaluated",
        "missing",
        "island",
        "constant",
    )
    handles = [
        Patch(
            facecolor=class_styles[cluster_class][0],
            edgecolor="0.25",
            label=class_styles[cluster_class][1],
        )
        for cluster_class in legend_order
        if cluster_class in used_classes
    ]

    if handles:
        axis.legend(
            handles=handles,
            loc="lower left",
            frameon=True,
            fontsize=8,
        )

    figure.tight_layout()

    figure.savefig(output_path, dpi=180, bbox_inches="tight")


def _validate_result_against_trajectory(
    trajectory: TrajectoryMapData,
    result: LocalMoranResult,
) -> None:
    """Require exact window and freguesia correspondence."""
    if (
        result.baseline_year != trajectory.baseline_year
        or result.latest_year != trajectory.latest_year
    ):
        raise LISAClusterMapError(
            f"{result.metric} comparison window does not match trajectory GeoJSON"
        )

    trajectory_ids = {feature.freguesia_id for feature in trajectory.features}
    observation_ids = {observation.freguesia_id for observation in result.observations}

    if len(observation_ids) != len(result.observations):
        raise LISAClusterMapError(f"{result.metric} contains duplicate freguesia observations")

    if trajectory_ids != observation_ids:
        missing = sorted(trajectory_ids - observation_ids)
        extra = sorted(observation_ids - trajectory_ids)
        raise LISAClusterMapError(
            f"{result.metric} trajectory/LISA key mismatch; missing={missing}, extra={extra}"
        )

    names = {feature.freguesia_id: feature.name for feature in trajectory.features}
    for observation in result.observations:
        expected_name = names[observation.freguesia_id]
        if observation.freguesia_name != expected_name:
            raise LISAClusterMapError(
                f"{result.metric}/{observation.freguesia_id} name mismatch: "
                f"{observation.freguesia_name!r} != {expected_name!r}"
            )


def _parse_result(value: object, context: str) -> LocalMoranResult:
    """Parse one metric result from Local Moran JSON."""
    raw = _require_mapping(value, context)
    metric = _parse_metric(raw.get("metric"), f"{context}.metric")

    window = _require_mapping(
        raw.get("comparison_window"),
        f"{context}.comparison_window",
    )
    coverage = _require_mapping(
        raw.get("coverage"),
        f"{context}.coverage",
    )

    observations_raw = raw.get("observations")
    if not isinstance(observations_raw, list):
        raise LISAClusterMapError(f"{context}.observations must be a list")

    observations = tuple(
        _parse_observation(item, metric, f"{context}.observations[{index}]")
        for index, item in enumerate(observations_raw)
    )

    return LocalMoranResult(
        metric=metric,
        baseline_year=_require_int(
            window.get("baseline_year"),
            f"{context}.comparison_window.baseline_year",
        ),
        latest_year=_require_int(
            window.get("latest_year"),
            f"{context}.comparison_window.latest_year",
        ),
        alpha=_require_float(raw.get("alpha"), f"{context}.alpha"),
        permutations=_require_int(
            raw.get("permutations"),
            f"{context}.permutations",
        ),
        seed=_require_int(raw.get("seed"), f"{context}.seed"),
        total_freguesias=_require_int(
            coverage.get("total_freguesias"),
            f"{context}.coverage.total_freguesias",
        ),
        complete_cases=_require_int(
            coverage.get("complete_cases"),
            f"{context}.coverage.complete_cases",
        ),
        observations=observations,
    )


def _parse_observation(
    value: object,
    metric: MetricName,
    context: str,
) -> LocalMoranObservation:
    """Parse one Local Moran observation."""
    raw = _require_mapping(value, context)

    return LocalMoranObservation(
        metric=metric,
        freguesia_id=_require_string(
            raw.get("freguesia_id"),
            f"{context}.freguesia_id",
        ),
        freguesia_name=_require_string(
            raw.get("freguesia_name"),
            f"{context}.freguesia_name",
        ),
        value=_optional_float(raw.get("value"), f"{context}.value"),
        standardized_value=_optional_float(
            raw.get("standardized_value"),
            f"{context}.standardized_value",
        ),
        spatial_lag_standardized=_optional_float(
            raw.get("spatial_lag_standardized"),
            f"{context}.spatial_lag_standardized",
        ),
        local_i=_optional_float(raw.get("local_i"), f"{context}.local_i"),
        neighbor_count=_require_int(
            raw.get("neighbor_count"),
            f"{context}.neighbor_count",
        ),
        permutation_p_two_sided=_optional_float(
            raw.get("permutation_p_two_sided"),
            f"{context}.permutation_p_two_sided",
        ),
        fdr_q=_optional_float(raw.get("fdr_q"), f"{context}.fdr_q"),
        significant_fdr=_optional_bool(
            raw.get("significant_fdr"),
            f"{context}.significant_fdr",
        ),
        quadrant=_optional_quadrant(
            raw.get("quadrant"),
            f"{context}.quadrant",
        ),
        cluster_class=_parse_cluster_class(
            raw.get("cluster_class"),
            f"{context}.cluster_class",
        ),
        status=_parse_status(raw.get("status"), f"{context}.status"),
    )


def _parse_metric(value: object, context: str) -> MetricName:
    """Parse a supported metric name."""
    if value not in _SUPPORTED_METRICS:
        raise LISAClusterMapError(f"{context} is not a supported metric")
    return value


def _optional_quadrant(value: object, context: str) -> Quadrant | None:
    """Parse an optional Moran quadrant."""
    if value is None:
        return None
    if value not in {"HH", "LL", "HL", "LH"}:
        raise LISAClusterMapError(f"{context} is not a valid quadrant")
    return cast(Quadrant, value)


def _parse_cluster_class(value: object, context: str) -> ClusterClass:
    """Parse a supported final cluster class."""
    allowed = {
        "HH",
        "LL",
        "HL",
        "LH",
        "not_significant",
        "not_evaluated",
        "missing",
        "island",
        "constant",
    }
    if value not in allowed:
        raise LISAClusterMapError(f"{context} is not a valid cluster class")
    return cast(ClusterClass, value)


def _parse_status(value: object, context: str) -> LocalStatus:
    """Parse a supported Local Moran status."""
    if value not in {"ok", "missing", "island", "constant"}:
        raise LISAClusterMapError(f"{context} is not a valid local status")
    return cast(LocalStatus, value)


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required JSON object."""
    if not isinstance(value, Mapping):
        raise LISAClusterMapError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


def _require_string(value: object, context: str) -> str:
    """Return a required non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise LISAClusterMapError(f"{context} must be a non-empty string")
    return value.strip()


def _require_int(value: object, context: str) -> int:
    """Return a required integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise LISAClusterMapError(f"{context} must be an integer")
    return value


def _require_float(value: object, context: str) -> float:
    """Return a required finite number."""
    parsed = _optional_float(value, context)
    if parsed is None:
        raise LISAClusterMapError(f"{context} must be numeric")
    return parsed


def _optional_float(value: object, context: str) -> float | None:
    """Return an optional finite number."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LISAClusterMapError(f"{context} must be numeric or null")

    number = float(value)
    if not math.isfinite(number):
        raise LISAClusterMapError(f"{context} must be finite")
    return number


def _optional_bool(value: object, context: str) -> bool | None:
    """Return an optional boolean."""
    if value is None:
        return None
    if not isinstance(value, bool):
        raise LISAClusterMapError(f"{context} must be boolean or null")
    return value
