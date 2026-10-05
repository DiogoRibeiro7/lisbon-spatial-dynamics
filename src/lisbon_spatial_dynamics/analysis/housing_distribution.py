"""Descriptive changes in published municipality quartiles and their dispersion."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Context, Decimal, localcontext
from pathlib import Path
from typing import Any

from lisbon_spatial_dynamics.transformations.housing_quartiles import parse_quartile_reference


def analyse_housing_distribution(
    quartile_csv: str,
    *,
    baseline_year: int,
    latest_year: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Keep absolute IQR, relative IQR and quantile changes as distinct statistics."""
    if (
        type(baseline_year) is not int
        or type(latest_year) is not int
        or not 1 <= baseline_year < latest_year <= 9999
    ):
        raise ValueError("increasing calendar years required")
    years = list(range(baseline_year, latest_year + 1))
    values = parse_quartile_reference(quartile_csv, years)
    annual: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []
    with localcontext(Context(prec=28)):
        for year in years:
            q1, q2, q3 = (values[year, q] for q in ("1", "2", "3"))
            annual.append(
                {
                    "year": year,
                    "geography_code": "1A01106",
                    "geography_name": "Lisboa",
                    "q1_eur_m2": q1,
                    "q2_eur_m2": q2,
                    "q3_eur_m2": q3,
                    "iqr_eur_m2": q3 - q1,
                    "iqr_as_pct_of_median": 100 * (q3 - q1) / q2,
                    "q1_index_baseline_100": 100 * q1 / values[baseline_year, "1"],
                    "q2_index_baseline_100": 100 * q2 / values[baseline_year, "2"],
                    "q3_index_baseline_100": 100 * q3 / values[baseline_year, "3"],
                }
            )
        first, last = annual[0], annual[-1]
        for metric in ("q1_eur_m2", "q2_eur_m2", "q3_eur_m2", "iqr_eur_m2"):
            a, b = first[metric], last[metric]
            endpoints.append(
                {
                    "metric": metric,
                    "baseline_year": baseline_year,
                    "latest_year": latest_year,
                    "baseline_eur_m2": a,
                    "latest_eur_m2": b,
                    "change_eur_m2": b - a,
                    "change_pct": 100 * (b - a) / a if a else None,
                }
            )
        summary = {
            "baseline_year": baseline_year,
            "latest_year": latest_year,
            "geography_code": "1A01106",
            "geography_name": "Lisboa",
            "geography_level": "municipality",
            "source_observations": len(values),
            "annual_observations": len(annual),
            "endpoint_changes": [
                {
                    key: float(value) if isinstance(value, Decimal) else value
                    for key, value in row.items()
                }
                for row in endpoints
            ],
            "baseline_iqr_as_pct_of_median": float(first["iqr_as_pct_of_median"]),
            "latest_iqr_as_pct_of_median": float(last["iqr_as_pct_of_median"]),
            "iqr_as_pct_of_median_change_pp": float(
                last["iqr_as_pct_of_median"] - first["iqr_as_pct_of_median"]
            ),
        }
    return summary, {"annual_distribution.csv": annual, "endpoint_changes.csv": endpoints}


def plot_housing_distribution(tables: Mapping[str, list[dict[str, Any]]], path: Path) -> None:
    """Label the quartile band as a distribution range, not statistical uncertainty."""
    from matplotlib.figure import Figure

    rows = tables["annual_distribution.csv"]
    years = [r["year"] for r in rows]
    fig = Figure(figsize=(12, 5.8), layout="constrained")
    axes = fig.subplots(1, 2)
    colors, labels = (
        ("#117864", "#334155", "#b05b23"),
        ("Lower quartile (Q1)", "Median (Q2)", "Upper quartile (Q3)"),
    )
    axes[0].fill_between(
        years,
        [float(r["q1_eur_m2"]) for r in rows],
        [float(r["q3_eur_m2"]) for r in rows],
        color="#94a3b8",
        alpha=0.18,
        label="Interquartile range (Q1–Q3)",
    )
    for quartile, color, label in zip(("q1", "q2", "q3"), colors, labels, strict=True):
        for ax, suffix in zip(axes, ("eur_m2", "index_baseline_100"), strict=True):
            ax.plot(
                years,
                [float(r[f"{quartile}_{suffix}"]) for r in rows],
                marker="o",
                color=color,
                label=label,
            )
    for ax in axes:
        ax.set_xticks(years)
        ax.set_xlabel("Calendar year of transactions")
        ax.grid(alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_title("Published municipal sale distribution")
    axes[0].set_ylabel("Nominal EUR/m²")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[1].set_title("Change relative to each quartile's baseline")
    axes[1].set_ylabel(f"Index ({years[0]} = 100)")
    axes[1].legend(fontsize=8, loc="upper left")
    fig.suptitle(
        f"Lisbon municipality | Housing sale quartiles, {years[0]}–{years[-1]}", fontsize=14
    )
    fig.supxlabel(
        "Source: INE 0013042 • The shaded band is the Q1–Q3 range, not a confidence interval.\n"
        "Annual transaction distributions; no tracking of the same dwellings or parish allocation.",
        fontsize=9,
    )
    fig.savefig(path, dpi=180)
