"""Descriptive sales-volume context for the audited housing medians."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Context, Decimal, localcontext
from pathlib import Path
from statistics import median
from typing import Any

from lisbon_spatial_dynamics.analysis.housing_history import analyse_housing_history
from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.transformations.housing_sales import (
    MUNICIPALITY,
    parse_sales_reference,
)


def analyse_housing_sales(
    sales_csv: str,
    housing: Sequence[HousingPanelRow],
    reference: Mapping[str, str],
    *,
    baseline_year: int,
    latest_year: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Pair annual sales and medians without deriving a pooled or weighted price."""
    nominal, nominal_tables = analyse_housing_history(
        housing, reference, baseline_year=baseline_year, latest_year=latest_year
    )
    years = list(range(baseline_year, latest_year + 1))
    rows = parse_sales_reference(sales_csv, reference, years)
    counts = {(r.year, r.geography_id): r.sales for r in rows}
    prices = {
        (r["year"], r["freguesia_id"]): r["value_eur_m2"] for r in nominal_tables["annual_q4.csv"]
    }
    price_changes = {
        r["freguesia_id"]: r["change_pct"] for r in nominal_tables["parish_changes.csv"]
    }
    annual, endpoints, municipality = [], [], []
    with localcontext(Context(prec=28)):
        for year in years:
            city = counts[year, MUNICIPALITY]
            previous = counts.get((year - 1, MUNICIPALITY))
            municipality.append(
                {
                    "year": year,
                    "published_sales": city,
                    "parish_sum": sum(counts[year, code] for code in reference),
                    "reconciliation_difference": 0,
                    "sales_index_baseline_100": Decimal(100 * city)
                    / counts[baseline_year, MUNICIPALITY],
                    "year_on_year_change_pct": None
                    if previous is None
                    else Decimal(100 * (city - previous)) / previous,
                }
            )
            for code in sorted(reference):
                annual.append(
                    {
                        "year": year,
                        "freguesia_id": code,
                        "freguesia_name": reference[code],
                        "sales": counts[year, code],
                        "municipality_sales": city,
                        "municipality_sales_share_pct": Decimal(100 * counts[year, code]) / city,
                        "sale_median_eur_m2": prices[year, code],
                    }
                )
        for code in sorted(reference):
            first, last = counts[baseline_year, code], counts[latest_year, code]
            first_share = Decimal(100 * first) / counts[baseline_year, MUNICIPALITY]
            last_share = Decimal(100 * last) / counts[latest_year, MUNICIPALITY]
            endpoints.append(
                {
                    "freguesia_id": code,
                    "freguesia_name": reference[code],
                    "baseline_year": baseline_year,
                    "latest_year": latest_year,
                    "baseline_sales": first,
                    "latest_sales": last,
                    "sales_change": last - first,
                    "sales_change_pct": Decimal(100 * (last - first)) / first if first else None,
                    "baseline_sales_share_pct": first_share,
                    "latest_sales_share_pct": last_share,
                    "sales_share_change_pp": last_share - first_share,
                    "baseline_sale_median_eur_m2": prices[baseline_year, code],
                    "latest_sale_median_eur_m2": prices[latest_year, code],
                    "sale_median_change_pct": price_changes[code],
                }
            )
        first_city, last_city = (
            counts[baseline_year, MUNICIPALITY],
            counts[latest_year, MUNICIPALITY],
        )
        changes = [r["sales_change_pct"] for r in endpoints if r["sales_change_pct"] is not None]
        summary = {
            "baseline_year": baseline_year,
            "latest_year": latest_year,
            "parishes": len(reference),
            "source_count_observations": len(rows),
            "paired_parish_observations": len(annual),
            "reconciled_years": years,
            "baseline_municipality_sales": first_city,
            "latest_municipality_sales": last_city,
            "municipality_sales_change": last_city - first_city,
            "municipality_sales_change_pct": float(
                Decimal(100 * (last_city - first_city)) / first_city
            ),
            "parishes_with_sales_growth": sum(r["sales_change"] > 0 for r in endpoints),
            "parishes_with_sales_decline": sum(r["sales_change"] < 0 for r in endpoints),
            "parishes_with_unchanged_sales": sum(r["sales_change"] == 0 for r in endpoints),
            "parishes_with_zero_baseline_sales": len(reference) - len(changes),
            "median_parish_sales_change_pct": float(median(changes)) if changes else None,
            "parishes_with_higher_median_and_fewer_sales": sum(
                r["sale_median_change_pct"] > 0 and r["sales_change"] < 0 for r in endpoints
            ),
        }
    return (
        summary,
        {
            "annual_parish.csv": annual,
            "endpoint_changes.csv": endpoints,
            "municipality_sales.csv": municipality,
        },
        nominal,
    )


def plot_housing_sales(tables: Mapping[str, list[dict[str, Any]]], path: Path) -> None:
    """Use separate panels for counts and medians over the same parish endpoints."""
    from matplotlib.figure import Figure

    selected = sorted(
        tables["endpoint_changes.csv"],
        key=lambda r: (
            r["sales_change_pct"] is not None,
            r["sales_change_pct"] or Decimal(0),
            r["freguesia_id"],
        ),
    )
    fig = Figure(figsize=(13, 10), layout="constrained")
    axes = fig.subplots(1, 2, sharey=True)
    for ax, metric, label in zip(
        axes,
        ("sales_change_pct", "sale_median_change_pct"),
        ("Change in number of sales (%)", "Change in nominal sale median (%)"),
        strict=True,
    ):
        for y, row in enumerate(selected):
            value = row[metric]
            if value is None:
                ax.text(0, y, "  undefined: zero baseline", fontsize=8, va="center")
            else:
                ax.barh(y, float(value), color="#117864" if value >= 0 else "#b05b23", height=0.65)
        ax.axvline(0, color="#475569", linewidth=0.8)
        ax.set_xlabel(label)
        ax.grid(axis="x", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_yticks(range(len(selected)), [r["freguesia_name"] for r in selected], fontsize=9)
    axes[0].set_title("Sales volume | INE 0014363")
    axes[1].set_title("Median EUR/m² | INE 0012234")
    first = selected[0]
    city = tables["municipality_sales.csv"]
    fig.suptitle(
        f"Lisbon housing sales and medians | {first['baseline_year']}–{first['latest_year']}",
        fontsize=15,
    )
    fig.supxlabel(
        f"Lisbon total: {city[0]['published_sales']:,} → {city[-1]['published_sales']:,} sales. "
        "Q4 observations each cover the preceding 12 months.\n"
        "Separate axis scales. Descriptive changes; no sales-mix decomposition or causal estimate.",
        fontsize=10,
    )
    fig.savefig(path, dpi=180)
