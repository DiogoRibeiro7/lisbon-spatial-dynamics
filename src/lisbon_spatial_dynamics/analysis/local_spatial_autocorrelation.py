"""Local Moran's I (LISA) for Lisbon trajectory change metrics."""

from __future__ import annotations

import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import fmean
from typing import Literal

from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    MetricName,
    SpatialAutocorrelationError,
    SpatialWeights,
    build_queen_weights,
)
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    TrajectoryMapFeature,
    load_trajectory_map,
)

Quadrant = Literal["HH", "LL", "HL", "LH"]
LocalStatus = Literal["ok", "missing", "island", "constant"]
ClusterClass = Literal[
    "HH",
    "LL",
    "HL",
    "LH",
    "not_significant",
    "not_evaluated",
    "missing",
    "island",
    "constant",
]


@dataclass(frozen=True, slots=True)
class LocalMoranObservation:
    """One freguesia-level Local Moran result."""

    metric: MetricName
    freguesia_id: str
    freguesia_name: str
    value: float | None
    standardized_value: float | None
    spatial_lag_standardized: float | None
    local_i: float | None
    neighbor_count: int
    permutation_p_two_sided: float | None
    fdr_q: float | None
    significant_fdr: bool | None
    quadrant: Quadrant | None
    cluster_class: ClusterClass
    status: LocalStatus


@dataclass(frozen=True, slots=True)
class LocalMoranResult:
    """Local Moran results for one trajectory metric."""

    metric: MetricName
    baseline_year: int
    latest_year: int
    alpha: float
    permutations: int
    seed: int
    total_freguesias: int
    complete_cases: int
    observations: tuple[LocalMoranObservation, ...]


def analyse_local_morans_i(
    data: TrajectoryMapData,
    *,
    permutations: int = 999,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[LocalMoranResult, LocalMoranResult]:
    """Calculate Local Moran's I for housing and RNAL trajectory changes."""
    if permutations < 0:
        raise ValueError("permutations must be non-negative")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")

    weights = build_queen_weights(data)

    return (
        _analyse_metric(
            data,
            weights,
            metric="housing_change_pct",
            permutations=permutations,
            seed=seed,
            alpha=alpha,
        ),
        _analyse_metric(
            data,
            weights,
            metric="rnal_active_change_pct",
            permutations=permutations,
            seed=seed + 100_000,
            alpha=alpha,
        ),
    )


def load_and_analyse_local_morans_i(
    trajectory_geojson: Path,
    *,
    permutations: int = 999,
    seed: int = 42,
    alpha: float = 0.05,
) -> tuple[LocalMoranResult, LocalMoranResult]:
    """Load trajectory GeoJSON and calculate both Local Moran analyses."""
    data = load_trajectory_map(trajectory_geojson)
    return analyse_local_morans_i(
        data,
        permutations=permutations,
        seed=seed,
        alpha=alpha,
    )


def write_local_morans_i_json(
    results: Sequence[LocalMoranResult],
    path: Path,
) -> None:
    """Write Local Moran results without overwriting."""
    if not results:
        raise SpatialAutocorrelationError("Local Moran results cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    document: dict[str, object] = {
        "schema_version": 1,
        "analysis": "local_morans_i",
        "weights": {
            "contiguity": "queen",
            "standardization": "row",
        },
        "permutation_test": {
            "method": "conditional_randomization",
            "tail": "two-sided_absolute_local_i",
            "multiple_testing": "Benjamini-Hochberg FDR",
        },
        "results": [
            {
                "metric": result.metric,
                "comparison_window": {
                    "baseline_year": result.baseline_year,
                    "latest_year": result.latest_year,
                },
                "alpha": result.alpha,
                "permutations": result.permutations,
                "seed": result.seed,
                "coverage": {
                    "total_freguesias": result.total_freguesias,
                    "complete_cases": result.complete_cases,
                    "missing": sum(
                        observation.status == "missing" for observation in result.observations
                    ),
                    "islands": [
                        observation.freguesia_id
                        for observation in result.observations
                        if observation.status == "island"
                    ],
                },
                "cluster_counts": _cluster_counts(result.observations),
                "observations": [
                    {
                        "freguesia_id": observation.freguesia_id,
                        "freguesia_name": observation.freguesia_name,
                        "value": observation.value,
                        "standardized_value": observation.standardized_value,
                        "spatial_lag_standardized": (observation.spatial_lag_standardized),
                        "local_i": observation.local_i,
                        "neighbor_count": observation.neighbor_count,
                        "permutation_p_two_sided": (observation.permutation_p_two_sided),
                        "fdr_q": observation.fdr_q,
                        "significant_fdr": observation.significant_fdr,
                        "quadrant": observation.quadrant,
                        "cluster_class": observation.cluster_class,
                        "status": observation.status,
                    }
                    for observation in result.observations
                ],
            }
            for result in results
        ],
        "interpretation": (
            "Local Moran's I describes local spatial association under queen "
            "contiguity. HH/LL/HL/LH labels are promoted only when the "
            "FDR-adjusted local permutation result is significant. The analysis "
            "is descriptive and does not establish causality."
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


def _analyse_metric(
    data: TrajectoryMapData,
    weights: SpatialWeights,
    *,
    metric: MetricName,
    permutations: int,
    seed: int,
    alpha: float,
) -> LocalMoranResult:
    """Calculate metric-specific Local Moran statistics."""
    values_by_id = {
        feature.freguesia_id: value
        for feature in data.features
        if (value := _metric_value(feature, metric)) is not None
    }

    if len(values_by_id) < 3:
        raise SpatialAutocorrelationError(f"{metric} needs at least three complete observations")

    ordered_ids = sorted(values_by_id)
    values = [values_by_id[freguesia_id] for freguesia_id in ordered_ids]
    mean_value = fmean(values)
    variance = fmean((value - mean_value) ** 2 for value in values)

    if math.isclose(variance, 0.0):
        observations = tuple(
            _constant_or_missing_observation(
                feature,
                metric,
                values_by_id,
                weights,
            )
            for feature in sorted(data.features, key=lambda item: item.freguesia_id)
        )
        return LocalMoranResult(
            metric=metric,
            baseline_year=data.baseline_year,
            latest_year=data.latest_year,
            alpha=alpha,
            permutations=permutations,
            seed=seed,
            total_freguesias=len(data.features),
            complete_cases=len(values_by_id),
            observations=observations,
        )

    standard_deviation = math.sqrt(variance)
    z_by_id = {
        freguesia_id: (value - mean_value) / standard_deviation
        for freguesia_id, value in values_by_id.items()
    }
    induced_neighbors = {
        freguesia_id: tuple(
            neighbor for neighbor in weights.neighbors[freguesia_id] if neighbor in values_by_id
        )
        for freguesia_id in ordered_ids
    }

    raw_observations: list[LocalMoranObservation] = []
    tested_positions: list[int] = []
    p_values: list[float] = []

    for feature in sorted(data.features, key=lambda item: item.freguesia_id):
        freguesia_id = feature.freguesia_id
        value = values_by_id.get(freguesia_id)

        if value is None:
            raw_observations.append(
                LocalMoranObservation(
                    metric=metric,
                    freguesia_id=freguesia_id,
                    freguesia_name=feature.name,
                    value=None,
                    standardized_value=None,
                    spatial_lag_standardized=None,
                    local_i=None,
                    neighbor_count=0,
                    permutation_p_two_sided=None,
                    fdr_q=None,
                    significant_fdr=None,
                    quadrant=None,
                    cluster_class="missing",
                    status="missing",
                )
            )
            continue

        neighbors = induced_neighbors[freguesia_id]
        z_value = z_by_id[freguesia_id]

        if not neighbors:
            raw_observations.append(
                LocalMoranObservation(
                    metric=metric,
                    freguesia_id=freguesia_id,
                    freguesia_name=feature.name,
                    value=value,
                    standardized_value=z_value,
                    spatial_lag_standardized=None,
                    local_i=None,
                    neighbor_count=0,
                    permutation_p_two_sided=None,
                    fdr_q=None,
                    significant_fdr=None,
                    quadrant=None,
                    cluster_class="island",
                    status="island",
                )
            )
            continue

        lag = fmean(z_by_id[neighbor] for neighbor in neighbors)
        local_i = z_value * lag
        quadrant = _quadrant(z_value, lag)

        p_value = (
            None
            if permutations == 0
            else _conditional_permutation_p(
                focal_id=freguesia_id,
                z_value=z_value,
                neighbor_count=len(neighbors),
                z_by_id=z_by_id,
                observed_local_i=local_i,
                permutations=permutations,
                seed=seed + ordered_ids.index(freguesia_id),
            )
        )

        observation = LocalMoranObservation(
            metric=metric,
            freguesia_id=freguesia_id,
            freguesia_name=feature.name,
            value=value,
            standardized_value=z_value,
            spatial_lag_standardized=lag,
            local_i=local_i,
            neighbor_count=len(neighbors),
            permutation_p_two_sided=p_value,
            fdr_q=None,
            significant_fdr=None if p_value is None else False,
            quadrant=quadrant,
            cluster_class="not_evaluated" if p_value is None else "not_significant",
            status="ok",
        )
        raw_observations.append(observation)

        if p_value is not None:
            tested_positions.append(len(raw_observations) - 1)
            p_values.append(p_value)

    if p_values:
        q_values = _benjamini_hochberg(p_values)
        for position, q_value in zip(tested_positions, q_values, strict=True):
            observation = raw_observations[position]
            significant = q_value <= alpha
            cluster_class: ClusterClass = "not_significant"

            if significant and observation.quadrant is not None:
                cluster_class = observation.quadrant

            raw_observations[position] = replace(
                observation,
                fdr_q=q_value,
                significant_fdr=significant,
                cluster_class=cluster_class,
            )

    return LocalMoranResult(
        metric=metric,
        baseline_year=data.baseline_year,
        latest_year=data.latest_year,
        alpha=alpha,
        permutations=permutations,
        seed=seed,
        total_freguesias=len(data.features),
        complete_cases=len(values_by_id),
        observations=tuple(raw_observations),
    )


def _conditional_permutation_p(
    *,
    focal_id: str,
    z_value: float,
    neighbor_count: int,
    z_by_id: Mapping[str, float],
    observed_local_i: float,
    permutations: int,
    seed: int,
) -> float:
    """Return a conditional two-sided pseudo-p value for one focal unit."""
    candidates = [
        value for freguesia_id, value in sorted(z_by_id.items()) if freguesia_id != focal_id
    ]

    if neighbor_count > len(candidates):
        raise SpatialAutocorrelationError(
            "neighbor count exceeds conditional permutation candidate pool"
        )

    rng = random.Random(seed)
    extreme = 0
    threshold = abs(observed_local_i)

    for _ in range(permutations):
        sampled = rng.sample(candidates, neighbor_count)
        simulated = z_value * fmean(sampled)

        if abs(simulated) >= threshold - 1e-15:
            extreme += 1

    return (extreme + 1) / (permutations + 1)


def _benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Return Benjamini-Hochberg FDR-adjusted q-values."""
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * len(p_values)
    running_min = 1.0
    total = len(p_values)

    for reverse_index in range(total - 1, -1, -1):
        original_index, p_value = indexed[reverse_index]
        rank = reverse_index + 1
        candidate = min(1.0, p_value * total / rank)
        running_min = min(running_min, candidate)
        adjusted[original_index] = running_min

    return adjusted


def _quadrant(
    standardized_value: float,
    spatial_lag: float,
) -> Quadrant | None:
    """Return the Moran-scatterplot quadrant, excluding exact zero cases."""
    if math.isclose(standardized_value, 0.0) or math.isclose(spatial_lag, 0.0):
        return None
    if standardized_value > 0.0 and spatial_lag > 0.0:
        return "HH"
    if standardized_value < 0.0 and spatial_lag < 0.0:
        return "LL"
    if standardized_value > 0.0 and spatial_lag < 0.0:
        return "HL"
    return "LH"


def _constant_or_missing_observation(
    feature: TrajectoryMapFeature,
    metric: MetricName,
    values_by_id: Mapping[str, float],
    weights: SpatialWeights,
) -> LocalMoranObservation:
    """Return a result when all complete values are constant."""
    value = values_by_id.get(feature.freguesia_id)

    if value is None:
        return LocalMoranObservation(
            metric=metric,
            freguesia_id=feature.freguesia_id,
            freguesia_name=feature.name,
            value=None,
            standardized_value=None,
            spatial_lag_standardized=None,
            local_i=None,
            neighbor_count=0,
            permutation_p_two_sided=None,
            fdr_q=None,
            significant_fdr=None,
            quadrant=None,
            cluster_class="missing",
            status="missing",
        )

    neighbors = tuple(
        neighbor for neighbor in weights.neighbors[feature.freguesia_id] if neighbor in values_by_id
    )

    return LocalMoranObservation(
        metric=metric,
        freguesia_id=feature.freguesia_id,
        freguesia_name=feature.name,
        value=value,
        standardized_value=0.0,
        spatial_lag_standardized=0.0 if neighbors else None,
        local_i=None,
        neighbor_count=len(neighbors),
        permutation_p_two_sided=None,
        fdr_q=None,
        significant_fdr=None,
        quadrant=None,
        cluster_class="constant",
        status="constant",
    )


def _cluster_counts(
    observations: Sequence[LocalMoranObservation],
) -> dict[str, int]:
    """Count final local cluster classes."""
    counts: dict[str, int] = {}
    for observation in observations:
        counts[observation.cluster_class] = counts.get(observation.cluster_class, 0) + 1
    return dict(sorted(counts.items()))


def _metric_value(
    feature: TrajectoryMapFeature,
    metric: MetricName,
) -> float | None:
    """Return one supported trajectory metric."""
    if metric == "housing_change_pct":
        return feature.housing_change_pct
    if metric == "rnal_active_change_pct":
        return feature.rnal_active_change_pct
    raise AssertionError(f"unsupported metric: {metric}")
