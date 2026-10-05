"""National CPI context for audited annual housing medians, in baseline-year euros."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Context, Decimal, localcontext
from pathlib import Path
from statistics import median
from typing import Any

from lisbon_spatial_dynamics.analysis.housing_history import analyse_housing_history
from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.transformations.cpi import parse_cpi_reference


def analyse_housing_inflation(
    housing: Sequence[HousingPanelRow],
    reference: Mapping[str, str],
    cpi_csv: str,
    *,
    baseline_year: int,
    latest_year: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Reproduce nominal evidence, then apply a common annual national deflator."""
    nominal_summary, nominal = analyse_housing_history(
        housing, reference, baseline_year=baseline_year, latest_year=latest_year
    )
    cpi = parse_cpi_reference(cpi_csv, list(range(baseline_year, latest_year + 1)))
    annual: list[dict[str, Any]] = []
    endpoints: list[dict[str, Any]] = []
    yearly: list[dict[str, Any]] = []
    with localcontext(Context(prec=28)):
        start = {
            row["freguesia_id"]: row["value_eur_m2"]
            for row in nominal["annual_q4.csv"]
            if row["year"] == baseline_year
        }
        previous: dict[str, Decimal] = {}
        for row in nominal["annual_q4.csv"]:
            year, code = row["year"], row["freguesia_id"]
            factor = cpi[baseline_year] / cpi[year]
            adjusted = row["value_eur_m2"] * cpi[baseline_year] / cpi[year]
            annual.append(
                {
                    "year": year,
                    "period_end": row["period_end"],
                    "freguesia_id": code,
                    "freguesia_name": reference[code],
                    "nominal_eur_m2": row["value_eur_m2"],
                    "cpi_index": cpi[year],
                    "cpi_conversion_to_baseline": factor,
                    "cpi_adjusted_eur_m2": adjusted,
                    "nominal_baseline_change_pct": row["baseline_change_pct"],
                    "cpi_adjusted_baseline_change_pct": (adjusted - start[code])
                    / start[code]
                    * 100,
                    "cpi_adjusted_q4_yoy_pct": None
                    if year == baseline_year
                    else (adjusted / previous[code] - 1) * 100,
                }
            )
            previous[code] = adjusted
        by_key = {(row["year"], row["freguesia_id"]): row for row in annual}
        for row in nominal["parish_changes.csv"]:
            adjusted_row = by_key[latest_year, row["freguesia_id"]]
            endpoints.append(
                {
                    "freguesia_id": row["freguesia_id"],
                    "freguesia_name": row["freguesia_name"],
                    "baseline_year": baseline_year,
                    "latest_year": latest_year,
                    "baseline_nominal_eur_m2": row["baseline_eur_m2"],
                    "latest_nominal_eur_m2": row["latest_eur_m2"],
                    "latest_cpi_adjusted_eur_m2": adjusted_row["cpi_adjusted_eur_m2"],
                    "nominal_change_pct": row["change_pct"],
                    "cpi_adjusted_change_pct": adjusted_row["cpi_adjusted_baseline_change_pct"],
                }
            )
        for year in range(baseline_year, latest_year + 1):
            rows = [row for row in annual if row["year"] == year]
            yearly.append(
                {
                    "year": year,
                    "parishes": len(rows),
                    "cpi_index": cpi[year],
                    "cpi_change_since_baseline_pct": (cpi[year] / cpi[baseline_year] - 1) * 100,
                    "median_parish_nominal_eur_m2": median(row["nominal_eur_m2"] for row in rows),
                    "median_parish_cpi_adjusted_eur_m2": median(
                        row["cpi_adjusted_eur_m2"] for row in rows
                    ),
                    "median_parish_nominal_change_pct": median(
                        row["nominal_baseline_change_pct"] for row in rows
                    ),
                    "median_parish_cpi_adjusted_change_pct": median(
                        row["cpi_adjusted_baseline_change_pct"] for row in rows
                    ),
                    "parishes_below_cpi_adjusted_baseline": sum(
                        row["cpi_adjusted_baseline_change_pct"] < 0 for row in rows
                    ),
                    "parishes_below_previous_cpi_adjusted_q4": None
                    if year == baseline_year
                    else sum(row["cpi_adjusted_q4_yoy_pct"] < 0 for row in rows),
                }
            )
        changes = [row["cpi_adjusted_change_pct"] for row in endpoints]
        summary = {
            "baseline_year": baseline_year,
            "latest_year": latest_year,
            "currency_reference_year": baseline_year,
            "parishes": len(reference),
            "annual_rows": len(annual),
            "cpi_years": len(cpi),
            "cpi_change_pct": float((cpi[latest_year] / cpi[baseline_year] - 1) * 100),
            "latest_conversion_to_baseline": float(cpi[baseline_year] / cpi[latest_year]),
            "median_nominal_change_pct": nominal_summary["median_parish_change_pct"],
            "median_cpi_adjusted_change_pct": float(median(changes)),
            "minimum_cpi_adjusted_change_pct": float(min(changes)),
            "maximum_cpi_adjusted_change_pct": float(max(changes)),
            "parishes_increased_cpi_adjusted": sum(value > 0 for value in changes),
            "parishes_unchanged_cpi_adjusted": sum(value == 0 for value in changes),
            "parishes_decreased_cpi_adjusted": sum(value < 0 for value in changes),
            "decreased_parishes": [
                {
                    "freguesia_id": row["freguesia_id"],
                    "freguesia_name": row["freguesia_name"],
                    "change_pct": float(row["cpi_adjusted_change_pct"]),
                }
                for row in endpoints
                if row["cpi_adjusted_change_pct"] < 0
            ],
        }
    return (
        summary,
        {
            "annual_adjusted.csv": annual,
            "parish_changes.csv": endpoints,
            "yearly_summary.csv": yearly,
        },
        nominal_summary,
    )


def plot_housing_inflation(datasets: Mapping[str, list[dict[str, Any]]], path: Path) -> None:
    """Compare nominal and CPI-adjusted published medians with explicit units."""
    from matplotlib import rc_context
    from matplotlib.figure import Figure

    rows = sorted(
        datasets["parish_changes.csv"],
        key=lambda row: (-row["nominal_change_pct"], row["freguesia_id"]),
    )
    yearly = datasets["yearly_summary.csv"]
    with rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        figure = Figure(figsize=(13, 9))
        axes = figure.subplots(1, 2, gridspec_kw={"width_ratios": [1.5, 1]})
        for i, row in enumerate(rows):
            axes[0].plot(
                [float(row["cpi_adjusted_change_pct"]), float(row["nominal_change_pct"])],
                [i, i],
                color="#bbbbbb",
                linewidth=1,
            )
        axes[0].scatter(
            [float(row["nominal_change_pct"]) for row in rows],
            range(len(rows)),
            color="#c27031",
            s=27,
            label="Nominal",
        )
        axes[0].scatter(
            [float(row["cpi_adjusted_change_pct"]) for row in rows],
            range(len(rows)),
            color="#256c92",
            s=27,
            label="CPI adjusted",
        )
        axes[0].set_yticks(range(len(rows)), [row["freguesia_name"] for row in rows], fontsize=8)
        axes[0].invert_yaxis()
        axes[0].axvline(0, color="#777777", linewidth=0.8)
        axes[0].set_xlabel("Endpoint change (%)")
        axes[0].set_title(f"{rows[0]['baseline_year']} Q4 → {rows[0]['latest_year']} Q4")
        axes[0].legend(loc="lower right", fontsize=8)
        for key, color, label in (
            ("nominal", "#c27031", "Nominal"),
            ("cpi_adjusted", "#256c92", "CPI adjusted"),
        ):
            axes[1].plot(
                [row["year"] for row in yearly],
                [float(row[f"median_parish_{key}_change_pct"]) for row in yearly],
                marker="o",
                color=color,
                label=label,
            )
        axes[1].set_title("Median parish change from baseline")
        axes[1].set_xlabel("Q4 year")
        axes[1].set_ylabel("Median of parish-specific changes (%)")
        axes[1].set_xticks([row["year"] for row in yearly])
        axes[1].legend(fontsize=8)
        for axis in axes:
            axis.grid(alpha=0.2)
            axis.spines[["top", "right"]].set_visible(False)
        figure.suptitle(
            "Lisbon housing changes in national CPI context", fontsize=17, x=0.035, ha="left"
        )
        figure.subplots_adjust(left=0.2, right=0.98, top=0.90, bottom=0.15, wspace=0.32)
        figure.text(
            0.035,
            0.035,
            "Source: INE housing 0012234 and annual Portugal/Total CPI 0014642 (base 2025).\n"
            "Published rolling-year sale medians adjusted with national annual CPI averages; "
            "not a fixed-dwelling price index or an affordability measure.",
            fontsize=8,
        )
        figure.savefig(path, dpi=180, facecolor="white", metadata={"Software": "Matplotlib"})
