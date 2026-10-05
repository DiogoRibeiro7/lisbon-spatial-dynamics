"""Matched-parish category comparisons, without imputing unpublished INE medians."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Context, Decimal, localcontext
from pathlib import Path
from statistics import median
from typing import Any

from lisbon_spatial_dynamics.analysis.housing_history import analyse_housing_history
from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.transformations.housing_categories import (
    CATEGORIES,
    parse_category_reference,
)


def analyse_housing_categories(
    category_csv: str,
    housing: Sequence[HousingPanelRow],
    reference: Mapping[str, str],
    *,
    baseline_year: int,
    latest_year: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Reconcile all Total values, then compare only jointly observed endpoints."""
    nominal, nominal_tables = analyse_housing_history(
        housing, reference, baseline_year=baseline_year, latest_year=latest_year
    )
    years = list(range(baseline_year, latest_year + 1))
    rows = parse_category_reference(category_csv, reference, years)
    index = {(r.year, r.freguesia_id, r.category_code): r for r in rows}
    totals = {(r.year, r.freguesia_id): r.value_eur_m2 for r in rows if r.category_code == "H1"}
    audited = {
        (r["year"], r["freguesia_id"]): r["value_eur_m2"] for r in nominal_tables["annual_q4.csv"]
    }
    if totals != audited:
        raise ValueError("new Total medians differ from the pinned nominal evidence")
    endpoints: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    with localcontext(Context(prec=28)):
        changes: dict[tuple[str, str], Decimal | None] = {}
        for code in sorted(reference):
            for category in CATEGORIES:
                first, last = (
                    index[baseline_year, code, category],
                    index[latest_year, code, category],
                )
                a, b = first.value_eur_m2, last.value_eur_m2
                change = None if a is None or b is None else 100 * (b / a - 1)
                changes[code, category] = change
                total_change = changes[code, "H1"]
                endpoints.append(
                    {
                        "freguesia_id": code,
                        "freguesia_name": reference[code],
                        "category_code": category,
                        "category_name": CATEGORIES[category],
                        "baseline_year": baseline_year,
                        "latest_year": latest_year,
                        "baseline_eur_m2": a,
                        "latest_eur_m2": b,
                        "baseline_source_flag": first.source_flag,
                        "latest_source_flag": last.source_flag,
                        "complete_endpoints": change is not None,
                        "change_pct": change,
                        "total_change_pct": total_change,
                        "difference_from_total_pp": None
                        if change is None or total_change is None
                        else change - total_change,
                    }
                )
        for year in years:
            for category in CATEGORIES:
                selected = [r for r in rows if r.year == year and r.category_code == category]
                count = sum(r.value_eur_m2 is not None for r in selected)
                coverage.append(
                    {
                        "year": year,
                        "category_code": category,
                        "category_name": CATEGORIES[category],
                        "requested_parishes": len(reference),
                        "published_medians": count,
                        "unpublished_medians": len(reference) - count,
                    }
                )
        for category in CATEGORIES:
            paired = [
                r for r in endpoints if r["category_code"] == category and r["complete_endpoints"]
            ]
            complete_years = sum(
                all(index[y, code, category].value_eur_m2 is not None for y in years)
                for code in reference
            )
            comparisons.append(
                {
                    "category_code": category,
                    "category_name": CATEGORIES[category],
                    "matched_parishes": len(paired),
                    "excluded_parishes": len(reference) - len(paired),
                    "parishes_with_all_years": complete_years,
                    "published_observations": sum(
                        r.value_eur_m2 is not None for r in rows if r.category_code == category
                    ),
                    "unpublished_observations": sum(
                        r.value_eur_m2 is None for r in rows if r.category_code == category
                    ),
                    "median_category_change_pct": median(r["change_pct"] for r in paired)
                    if paired
                    else None,
                    "median_matched_total_change_pct": median(r["total_change_pct"] for r in paired)
                    if paired
                    else None,
                    "median_paired_difference_pp": median(
                        r["difference_from_total_pp"] for r in paired
                    )
                    if paired
                    else None,
                    "minimum_paired_difference_pp": min(
                        r["difference_from_total_pp"] for r in paired
                    )
                    if paired
                    else None,
                    "maximum_paired_difference_pp": max(
                        r["difference_from_total_pp"] for r in paired
                    )
                    if paired
                    else None,
                }
            )
    summary = {
        "baseline_year": baseline_year,
        "latest_year": latest_year,
        "parishes": len(reference),
        "category_rows": len(rows),
        "total_observations_verified": len(totals),
        "categories": [
            {
                key: float(value) if isinstance(value, Decimal) else value
                for key, value in item.items()
            }
            for item in comparisons
        ],
        "excluded_endpoints": [
            {
                key: item[key]
                for key in (
                    "freguesia_id",
                    "freguesia_name",
                    "category_code",
                    "baseline_source_flag",
                    "latest_source_flag",
                )
            }
            for item in endpoints
            if not item["complete_endpoints"]
        ],
    }
    return (
        summary,
        {
            "endpoint_changes.csv": endpoints,
            "annual_coverage.csv": coverage,
            "matched_comparisons.csv": comparisons,
        },
        nominal,
    )


def plot_housing_categories(tables: Mapping[str, list[dict[str, Any]]], path: Path) -> None:
    """Display Total and category changes only for matched endpoint observations."""
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 10), layout="constrained")
    for ax, category, label, color in zip(
        axes, ("H12", "H11"), ("Existing", "New"), ("#117864", "#b05b23"), strict=True
    ):
        selected = sorted(
            (
                r
                for r in tables["endpoint_changes.csv"]
                if r["category_code"] == category and r["complete_endpoints"]
            ),
            key=lambda r: (r["total_change_pct"], r["freguesia_id"]),
        )
        for y, row in enumerate(selected):
            ax.plot(
                [float(row["total_change_pct"]), float(row["change_pct"])],
                [y, y],
                color="#b7b7b7",
                linewidth=1.2,
                zorder=1,
            )
        ax.scatter(
            [float(r["total_change_pct"]) for r in selected],
            range(len(selected)),
            color="#475569",
            marker="o",
            label="Total",
            zorder=3,
        )
        ax.scatter(
            [float(r["change_pct"]) for r in selected],
            range(len(selected)),
            color=color,
            marker="D",
            label=label,
            zorder=3,
        )
        ax.set_yticks(range(len(selected)), [r["freguesia_name"] for r in selected], fontsize=9)
        ax.set_title(
            f"{label} dwellings vs Total\n{len(selected)} parishes with both endpoints", fontsize=12
        )
        ax.set_xlabel("Nominal change in rolling-year sale median (%)")
        ax.grid(axis="x", alpha=0.2)
        ax.legend(loc="lower right")
        ax.spines[["top", "right"]].set_visible(False)
    all_changes = [
        float(r[k])
        for r in tables["endpoint_changes.csv"]
        if r["complete_endpoints"]
        for k in ("change_pct", "total_change_pct")
    ]
    lower, upper = (
        min(0.0, min(all_changes, default=0.0)) - 5,
        max(0.0, max(all_changes, default=0.0)) + 10,
    )
    for ax in axes:
        ax.set_xlim(lower, upper)
    first = tables["endpoint_changes.csv"][0]
    fig.suptitle(
        f"Lisbon housing changes by dwelling category | "
        f"{first['baseline_year']} Q4–{first['latest_year']} Q4",
        fontsize=15,
    )
    fig.supxlabel(
        "INE 0012234 • Matched parish comparisons; missing endpoints excluded without imputation.\n"
        "Category medians do not identify a sales-mix contribution "
        "or constant-quality price change.",
        fontsize=10,
    )
    fig.savefig(path, dpi=180)
    plt.close(fig)
