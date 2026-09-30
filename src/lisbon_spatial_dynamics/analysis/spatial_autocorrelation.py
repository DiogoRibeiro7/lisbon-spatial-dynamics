"""Global spatial autocorrelation for trajectory change metrics."""

from __future__ import annotations

import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean
from typing import Literal

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    TrajectoryMapFeature,
    load_trajectory_map,
)

MetricName = Literal["housing_change_pct", "rnal_active_change_pct"]


class SpatialAutocorrelationError(ValueError):
    """Raised when spatial autocorrelation cannot be computed safely."""


@dataclass(frozen=True, slots=True)
class SpatialWeights:
    """Symmetric queen-contiguity neighbours for canonical freguesias."""

    neighbors: Mapping[str, tuple[str, ...]]

    @property
    def edge_count(self) -> int:
        """Return the number of undirected neighbour pairs."""
        return sum(len(values) for values in self.neighbors.values()) // 2


@dataclass(frozen=True, slots=True)
class MoranResult:
    """Global Moran's I result for one trajectory metric."""

    metric: MetricName
    baseline_year: int
    latest_year: int
    total_freguesias: int
    complete_cases: int
    excluded_missing: int
    islands: tuple[str, ...]
    edge_count: int
    morans_i: float | None
    expected_i: float
    permutation_p_two_sided: float | None
    permutations: int
    seed: int


def build_queen_weights(data: TrajectoryMapData) -> SpatialWeights:
    """Build symmetric queen-contiguity weights from canonical polygons.

    Two freguesias are neighbours when their polygon boundaries touch at any
    point. Overlapping polygon interiors are rejected because the canonical
    administrative partition should not contain overlaps.
    """
    geometries: dict[str, BaseGeometry] = {}

    for feature in data.features:
        geometry = shape(dict(feature.geometry))
        if geometry.is_empty:
            raise SpatialAutocorrelationError(f"{feature.freguesia_id} has empty geometry")
        if not geometry.is_valid:
            raise SpatialAutocorrelationError(f"{feature.freguesia_id} has invalid geometry")
        geometries[feature.freguesia_id] = geometry

    neighbors: dict[str, set[str]] = {feature.freguesia_id: set() for feature in data.features}
    ids = sorted(geometries)

    for index, left_id in enumerate(ids):
        left = geometries[left_id]
        for right_id in ids[index + 1 :]:
            right = geometries[right_id]

            if left.overlaps(right):
                raise SpatialAutocorrelationError(
                    f"canonical geometries overlap: {left_id}, {right_id}"
                )

            if left.touches(right):
                neighbors[left_id].add(right_id)
                neighbors[right_id].add(left_id)

    return SpatialWeights(
        neighbors={
            freguesia_id: tuple(sorted(values))
            for freguesia_id, values in sorted(neighbors.items())
        }
    )


def analyse_global_morans_i(
    data: TrajectoryMapData,
    *,
    permutations: int = 999,
    seed: int = 42,
) -> tuple[MoranResult, MoranResult]:
    """Calculate Global Moran's I for housing and RNAL trajectory changes."""
    if permutations < 0:
        raise ValueError("permutations must be non-negative")

    weights = build_queen_weights(data)

    return (
        _analyse_metric(
            data,
            weights,
            metric="housing_change_pct",
            permutations=permutations,
            seed=seed,
        ),
        _analyse_metric(
            data,
            weights,
            metric="rnal_active_change_pct",
            permutations=permutations,
            seed=seed,
        ),
    )


def write_morans_i_json(
    results: Sequence[MoranResult],
    path: Path,
) -> None:
    """Write Global Moran's I results without overwriting."""
    if not results:
        raise SpatialAutocorrelationError("Moran results cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    document: dict[str, object] = {
        "schema_version": 1,
        "analysis": "global_morans_i",
        "weights": {
            "contiguity": "queen",
            "standardization": "row",
        },
        "permutation_test": {
            "tail": "two-sided",
            "reference": "distance from randomization expectation",
        },
        "results": [
            {
                "metric": result.metric,
                "comparison_window": {
                    "baseline_year": result.baseline_year,
                    "latest_year": result.latest_year,
                },
                "coverage": {
                    "total_freguesias": result.total_freguesias,
                    "complete_cases": result.complete_cases,
                    "excluded_missing": result.excluded_missing,
                    "islands": list(result.islands),
                    "edge_count": result.edge_count,
                },
                "morans_i": result.morans_i,
                "expected_i": result.expected_i,
                "permutation_p_two_sided": result.permutation_p_two_sided,
                "permutations": result.permutations,
                "seed": result.seed,
            }
            for result in results
        ],
        "interpretation": (
            "Global Moran's I tests spatial autocorrelation of the observed "
            "change metric under the chosen queen-contiguity weights. It does "
            "not identify local clusters and does not imply causality."
        ),
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


def load_and_analyse_global_morans_i(
    trajectory_geojson: Path,
    *,
    permutations: int = 999,
    seed: int = 42,
) -> tuple[MoranResult, MoranResult]:
    """Load trajectory GeoJSON and calculate both Global Moran statistics."""
    data = load_trajectory_map(trajectory_geojson)
    return analyse_global_morans_i(
        data,
        permutations=permutations,
        seed=seed,
    )


def _analyse_metric(
    data: TrajectoryMapData,
    weights: SpatialWeights,
    *,
    metric: MetricName,
    permutations: int,
    seed: int,
) -> MoranResult:
    """Calculate one metric-specific Moran statistic and permutation p-value."""
    values_by_id: dict[str, float] = {}
    for feature in data.features:
        value = _metric_value(feature, metric)
        if value is not None:
            values_by_id[feature.freguesia_id] = value

    if len(values_by_id) < 3:
        raise SpatialAutocorrelationError(f"{metric} needs at least three complete observations")

    ordered_ids = sorted(values_by_id)
    induced_neighbors = {
        freguesia_id: tuple(
            neighbor for neighbor in weights.neighbors[freguesia_id] if neighbor in values_by_id
        )
        for freguesia_id in ordered_ids
    }
    islands = tuple(
        freguesia_id for freguesia_id in ordered_ids if not induced_neighbors[freguesia_id]
    )

    values = [values_by_id[freguesia_id] for freguesia_id in ordered_ids]
    observed = _morans_i(values, ordered_ids, induced_neighbors)
    expected = -1.0 / (len(values) - 1)

    p_value: float | None
    if observed is None or permutations == 0:
        p_value = None
    else:
        rng = random.Random(seed)
        extreme = 0
        observed_distance = abs(observed - expected)
        permuted = list(values)

        for _ in range(permutations):
            rng.shuffle(permuted)
            simulated = _morans_i(
                permuted,
                ordered_ids,
                induced_neighbors,
            )
            if simulated is None:
                continue
            if abs(simulated - expected) >= observed_distance - 1e-15:
                extreme += 1

        p_value = (extreme + 1) / (permutations + 1)

    return MoranResult(
        metric=metric,
        baseline_year=data.baseline_year,
        latest_year=data.latest_year,
        total_freguesias=len(data.features),
        complete_cases=len(values_by_id),
        excluded_missing=len(data.features) - len(values_by_id),
        islands=islands,
        edge_count=_induced_edge_count(induced_neighbors),
        morans_i=observed,
        expected_i=expected,
        permutation_p_two_sided=p_value,
        permutations=permutations,
        seed=seed,
    )


def _morans_i(
    values: Sequence[float],
    ordered_ids: Sequence[str],
    neighbors: Mapping[str, Sequence[str]],
) -> float | None:
    """Return Moran's I using row-standardized neighbour weights."""
    if len(values) != len(ordered_ids):
        raise ValueError("values and ordered_ids must have the same length")

    mean_value = fmean(values)
    centered = {
        freguesia_id: value - mean_value
        for freguesia_id, value in zip(ordered_ids, values, strict=True)
    }

    denominator = sum(value * value for value in centered.values())
    if math.isclose(denominator, 0.0):
        return None

    weighted_cross_product = 0.0
    weight_sum = 0.0

    for freguesia_id in ordered_ids:
        row_neighbors = neighbors[freguesia_id]
        if not row_neighbors:
            continue

        weight = 1.0 / len(row_neighbors)
        for neighbor in row_neighbors:
            weighted_cross_product += weight * centered[freguesia_id] * centered[neighbor]
            weight_sum += weight

    if math.isclose(weight_sum, 0.0):
        raise SpatialAutocorrelationError("spatial weights contain no usable neighbour links")

    return len(values) / weight_sum * weighted_cross_product / denominator


def _induced_edge_count(
    neighbors: Mapping[str, Sequence[str]],
) -> int:
    """Return undirected edges in an induced neighbour mapping."""
    return sum(len(values) for values in neighbors.values()) // 2


def _metric_value(
    feature: TrajectoryMapFeature,
    metric: MetricName,
) -> float | None:
    """Return one supported trajectory change metric."""
    if metric == "housing_change_pct":
        return feature.housing_change_pct
    if metric == "rnal_active_change_pct":
        return feature.rnal_active_change_pct

    raise AssertionError(f"unsupported metric: {metric}")
