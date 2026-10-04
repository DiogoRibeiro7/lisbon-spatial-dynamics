"""Metric, contiguity and parish-influence diagnostics for housing changes."""

from __future__ import annotations

import csv
import math
import random
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from shapely.geometry import shape

from lisbon_spatial_dynamics.analysis.housing_spatial import build_housing_map
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import build_queen_weights

METRICS = ("percentage_change", "log_change", "absolute_change")
CONTIGUITIES = ("queen", "rook")
FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


def row_weights(adjacency: BoolArray) -> FloatArray:
    """Normalize a symmetric binary graph; retain islands with zero-weight rows."""
    if (
        adjacency.ndim != 2
        or adjacency.shape[0] != adjacency.shape[1]
        or adjacency.dtype != np.dtype(bool)
        or np.any(np.diag(adjacency))
        or not np.array_equal(adjacency, adjacency.T)
    ):
        raise ValueError("a square symmetric boolean graph without self-links is required")
    degree = adjacency.sum(axis=1)
    if not np.any(degree):
        raise ValueError("graph has no neighbour links")
    return np.divide(
        adjacency,
        degree[:, None],
        out=np.zeros(adjacency.shape, dtype=float),
        where=degree[:, None] != 0,
    )


def moran_statistic(values: FloatArray, adjacency: BoolArray) -> float:
    """Calculate n/S0 * z'Wz/z'z after centring, including any island observations."""
    weights = row_weights(adjacency)
    if values.ndim != 1 or len(values) < 3 or len(values) != len(weights):
        raise ValueError("at least three values matching the graph are required")
    if not np.all(np.isfinite(values)):
        raise ValueError("values must be finite")
    centered = values - values.mean()
    denominator = float(centered @ centered)
    if denominator == 0 or not math.isfinite(denominator):
        raise ValueError("finite non-constant variation is required")
    return float(len(values) / weights.sum() * (centered @ weights @ centered) / denominator)


def permutation_test(
    values: FloatArray, adjacency: BoolArray, *, permutations: int, seed: int
) -> tuple[float, float]:
    """Use the primary analysis's shuffle sequence and distance-from-expectation tail."""
    if type(permutations) is not int or permutations < 1:
        raise ValueError("permutations must be a positive integer")
    observed = moran_statistic(values, adjacency)
    weights = row_weights(adjacency)
    scale = len(values) / weights.sum()
    expected = -1 / (len(values) - 1)
    threshold = abs(observed - expected)
    rng = random.Random(seed)
    permuted = list(values)
    extreme = 0
    for _ in range(permutations):
        rng.shuffle(permuted)
        centered = np.asarray(permuted) - values.mean()
        simulated = float(scale * (centered @ weights @ centered) / (centered @ centered))
        extreme += abs(simulated - expected) >= threshold - 1e-15
    return observed, (int(extreme) + 1) / (permutations + 1)


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Return Holm's step-down Bonferroni adjusted p-values in original order."""
    if not p_values or any(not math.isfinite(p) or not 0 <= p <= 1 for p in p_values):
        raise ValueError("a non-empty sequence of finite probabilities is required")
    adjusted = [1.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)), key=lambda i: p_values[i])):
        previous = max(previous, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = previous
    return adjusted


def analyse_housing_sensitivity(
    changes_csv: str,
    geometry_json: str,
    reference: Mapping[str, str],
    *,
    baseline_year: int,
    latest_year: int,
    permutations: int,
    seed: int,
    alpha: float,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Run all six declared comparisons and descriptive queen/percentage omissions."""
    if len(reference) < 4 or not 0 < alpha < 1:
        raise ValueError("at least four parishes and alpha between zero and one are required")
    data = build_housing_map(
        changes_csv,
        geometry_json,
        reference,
        baseline_year=baseline_year,
        latest_year=latest_year,
    )
    ids = [feature.freguesia_id for feature in data.features]
    weights = build_queen_weights(data)
    polygons = [shape(dict(feature.geometry)) for feature in data.features]
    queen = np.zeros((len(ids), len(ids)), dtype=bool)
    rook = np.zeros_like(queen)
    for i, left in enumerate(ids):
        for j in range(i + 1, len(ids)):
            if ids[j] in weights.neighbors[left]:
                queen[i, j] = queen[j, i] = True
                rook[i, j] = rook[j, i] = (
                    polygons[i].boundary.intersection(polygons[j].boundary).length > 0
                )
    source_rows = {row["freguesia_id"]: row for row in csv.DictReader(StringIO(changes_csv))}
    metric_rows: list[dict[str, Any]] = []
    for feature in data.features:
        row = source_rows[feature.freguesia_id]
        metric_rows.append(
            {
                "freguesia_id": feature.freguesia_id,
                "freguesia_name": feature.name,
                "baseline_eur_m2": row["baseline_eur_m2"],
                "latest_eur_m2": row["latest_eur_m2"],
                "percentage_change": feature.housing_change_pct,
                "log_change": math.log(float(row["latest_eur_m2"]))
                - math.log(float(row["baseline_eur_m2"])),
                "absolute_change": float(row["change_eur_m2"]),
            }
        )
    graphs = {"queen": queen, "rook": rook}
    scenarios: list[dict[str, Any]] = []
    for contiguity, graph in graphs.items():
        for metric in METRICS:
            values = np.array([row[metric] for row in metric_rows], dtype=float)
            observed, p = permutation_test(values, graph, permutations=permutations, seed=seed)
            scenarios.append(
                {
                    "contiguity": contiguity,
                    "metric": metric,
                    "parishes": len(ids),
                    "neighbor_pairs": int(graph.sum() // 2),
                    "islands": ";".join(
                        code
                        for code, degree in zip(ids, graph.sum(axis=1), strict=True)
                        if degree == 0
                    ),
                    "morans_i": observed,
                    "expected_i": -1 / (len(ids) - 1),
                    "permutation_p_two_sided": p,
                    "permutations": permutations,
                    "seed": seed,
                }
            )
    adjusted = holm_adjust([row["permutation_p_two_sided"] for row in scenarios])
    for row, p in zip(scenarios, adjusted, strict=True):
        row.update(holm_adjusted_p=p, significant_holm=p <= alpha)
    primary = scenarios[0]["morans_i"]
    values = np.array([row["percentage_change"] for row in metric_rows], dtype=float)
    omissions: list[dict[str, Any]] = []
    for i, code in enumerate(ids):
        keep = np.arange(len(ids)) != i
        graph = queen[np.ix_(keep, keep)]
        observed = moran_statistic(values[keep], graph)
        omissions.append(
            {
                "omitted_id": code,
                "omitted_name": reference[code],
                "retained_parishes": len(ids) - 1,
                "neighbor_pairs": int(graph.sum() // 2),
                "islands": ";".join(
                    c
                    for c, degree in zip(np.array(ids)[keep], graph.sum(axis=1), strict=True)
                    if degree == 0
                ),
                "morans_i": observed,
                "difference_from_full": observed - primary,
            }
        )
    normalized = {name: row_weights(graph) for name, graph in graphs.items()}
    pairs = [
        {
            "left_id": ids[i],
            "right_id": ids[j],
            "rook": bool(rook[i, j]),
            **{
                f"{name}_{direction}": float(matrix[left, right])
                for name, matrix in normalized.items()
                for direction, left, right in (("left_to_right", i, j), ("right_to_left", j, i))
            },
        }
        for i in range(len(ids))
        for j in range(i + 1, len(ids))
        if queen[i, j]
    ]
    lowest = min(omissions, key=lambda row: row["morans_i"])
    highest = max(omissions, key=lambda row: row["morans_i"])
    summary = {
        "baseline_year": baseline_year,
        "latest_year": latest_year,
        "parishes": len(ids),
        "scenarios": len(scenarios),
        "significant_holm": sum(row["significant_holm"] for row in scenarios),
        "queen_pairs": int(queen.sum() // 2),
        "rook_pairs": int(rook.sum() // 2),
        "identical_graphs": bool(np.array_equal(queen, rook)),
        "leave_one_out_minimum": lowest,
        "leave_one_out_maximum": highest,
        "leave_one_out_positive": sum(row["morans_i"] > 0 for row in omissions),
    }
    return summary, {
        "global_scenarios.csv": scenarios,
        "parish_metrics.csv": metric_rows,
        "neighbor_pairs.csv": pairs,
        "leave_one_out.csv": omissions,
    }


def plot_housing_sensitivity(
    datasets: Mapping[str, list[dict[str, Any]]],
    path: Path,
    *,
    baseline_year: int,
    latest_year: int,
) -> None:
    """Show every scenario and omission without treating influence values as intervals."""
    import matplotlib.pyplot as plt

    scenarios = datasets["global_scenarios.csv"]
    omissions = sorted(datasets["leave_one_out.csv"], key=lambda row: row["morans_i"])
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        figure, axes = plt.subplots(1, 2, figsize=(13, 9), gridspec_kw={"width_ratios": [1, 1.5]})
        try:
            labels = {
                "percentage_change": "Percentage",
                "log_change": "Log ratio",
                "absolute_change": "EUR/m²",
            }
            for i, row in enumerate(scenarios):
                axes[0].scatter(row["morans_i"], i, color="#256c92", s=45)
                axes[0].annotate(
                    f"Holm p = {row['holm_adjusted_p']:.4f}",
                    (row["morans_i"], i),
                    xytext=(7, 6),
                    textcoords="offset points",
                    fontsize=8,
                )
            axes[0].set_yticks(
                range(len(scenarios)),
                [f"{r['contiguity'].title()} · {labels[r['metric']]}" for r in scenarios],
            )
            axes[0].invert_yaxis()
            axes[0].set_ylim(len(scenarios) - 0.5, -0.7)
            axes[0].set_title("Six global comparisons")
            axes[1].scatter(
                [r["morans_i"] for r in omissions], range(len(omissions)), color="#256c92", s=24
            )
            axes[1].set_yticks(
                range(len(omissions)), [r["omitted_name"] for r in omissions], fontsize=8
            )
            axes[1].invert_yaxis()
            axes[1].axvline(
                scenarios[0]["morans_i"], color="#b26228", linestyle="--", label="All 24 parishes"
            )
            axes[1].set_title("Queen / percentage change: parish omitted")
            axes[1].legend(loc="lower right", fontsize=8)
            for axis in axes:
                axis.axvline(0, color="#888888", linewidth=0.7)
                axis.set_xlabel("Global Moran's I")
                axis.grid(axis="x", alpha=0.2)
                axis.spines[["top", "right"]].set_visible(False)
                displayed = [row["morans_i"] for row in scenarios + omissions]
                low, high = min(0.0, min(displayed)), max(0.0, max(displayed))
                span = max(high - low, 0.1)
                axis.set_xlim(low - 0.08 * span, high + 0.35 * span)
            figure.suptitle(
                "How sensitive is the housing spatial pattern?", fontsize=17, x=0.035, ha="left"
            )
            figure.subplots_adjust(left=0.15, right=0.98, top=0.90, bottom=0.14, wspace=0.95)
            figure.text(
                0.035,
                0.035,
                f"INE housing, {baseline_year} Q4 → {latest_year} Q4 · "
                "DGT CAOP2025 boundaries (CC BY 4.0).\n"
                "Left: all six tests adjusted together. Right: induced, row-normalized graphs; "
                "descriptive influence, no p-values or confidence intervals.",
                fontsize=8,
            )
            figure.savefig(path, dpi=180, facecolor="white", metadata={"Software": "Matplotlib"})
        finally:
            plt.close(figure)
