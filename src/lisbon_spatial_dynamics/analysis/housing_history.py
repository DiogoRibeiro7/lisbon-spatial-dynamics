"""Descriptive Q4 housing evidence independent of historical RNAL availability."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Context, Decimal, localcontext
from pathlib import Path
from statistics import median
from typing import Any

from lisbon_spatial_dynamics.panels.housing import CURRENT_HOUSING_INDICATOR, HousingPanelRow
from lisbon_spatial_dynamics.panels.temporal import build_housing_change_panel, parse_ine_quarter


def analyse_housing_history(
    rows: Sequence[HousingPanelRow],
    reference: Mapping[str, str],
    *,
    baseline_year: int,
    latest_year: int,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Require a complete positive Q4 matrix; preserve the requested annual window.

    Medians weight each parish equally. They are not municipality transaction
    medians. Changes describe nominal rolling-12-month sale-value statistics.
    """
    if (
        not reference
        or type(baseline_year) is not int
        or type(latest_year) is not int
        or not 1 <= baseline_year < latest_year <= 9999
    ):
        raise ValueError("non-empty reference and increasing calendar years required")
    seen = set()
    selected = set()
    excluded_periods = set()
    for row in rows:
        period = parse_ine_quarter(row.period_code)
        key = (row.freguesia_id, period.ordinal)
        if key in seen:
            raise ValueError("duplicate parish-quarter observation")
        seen.add(key)
        if row.freguesia_id not in reference or reference[row.freguesia_id] != row.freguesia_name:
            raise ValueError("housing parish differs from canonical reference")
        if (
            row.indicator_code != CURRENT_HOUSING_INDICATOR
            or row.category_code != "H1"
            or row.category_name != "Total"
            or not row.source_geography_code.endswith(row.freguesia_id)
            or row.source_geography_name != row.freguesia_name
        ):
            raise ValueError("housing indicator, category or source geography differs")
        if row.value_eur_m2 is None or not row.value_eur_m2.is_finite() or row.value_eur_m2 <= 0:
            raise ValueError("housing values must be finite and strictly positive")
        if period.quarter == 4 and baseline_year <= period.year <= latest_year:
            selected.add((row.freguesia_id, period.year))
        else:
            excluded_periods.add((period.year, period.quarter))
    expected = {
        (code, year) for code in reference for year in range(baseline_year, latest_year + 1)
    }
    if selected != expected:
        raise ValueError("requested Q4 matrix is incomplete")

    # Use a fresh context so a caller's precision or rounding cannot change the evidence.
    with localcontext(Context(prec=28)):
        changes = build_housing_change_panel(rows)
        q4 = [
            row for row in changes if (row.freguesia_id, row.year) in selected and row.quarter == 4
        ]
        starts = {row.freguesia_id: row.value_eur_m2 for row in q4 if row.year == baseline_year}
        annual: list[dict[str, Any]] = []
        endpoints: list[dict[str, Any]] = []
        yearly: list[dict[str, Any]] = []
        for observation in q4:
            start, value = starts[observation.freguesia_id], observation.value_eur_m2
            assert start is not None and value is not None  # Validated before computation.
            absolute = value - start
            percentage = absolute / start * Decimal(100)
            annual.append(
                {
                    "year": observation.year,
                    "period_end": observation.period_end.isoformat(),
                    "freguesia_id": observation.freguesia_id,
                    "freguesia_name": observation.freguesia_name,
                    "value_eur_m2": value,
                    "baseline_change_eur_m2": absolute,
                    "baseline_change_pct": percentage,
                    "q4_yoy_pct": None
                    if observation.year == baseline_year
                    else observation.yoy_pct,
                }
            )
            if observation.year == latest_year:
                endpoints.append(
                    {
                        "freguesia_id": observation.freguesia_id,
                        "freguesia_name": observation.freguesia_name,
                        "baseline_year": baseline_year,
                        "latest_year": latest_year,
                        "baseline_eur_m2": start,
                        "latest_eur_m2": value,
                        "change_eur_m2": absolute,
                        "change_pct": percentage,
                    }
                )
        for year in range(baseline_year, latest_year + 1):
            observations = [row for row in annual if row["year"] == year]
            levels = [row["value_eur_m2"] for row in observations]
            yearly.append(
                {
                    "year": year,
                    "parishes": len(observations),
                    "median_parish_value_eur_m2": median(levels),
                    "minimum_parish_value_eur_m2": min(levels),
                    "maximum_parish_value_eur_m2": max(levels),
                    "median_parish_baseline_change_pct": median(
                        row["baseline_change_pct"] for row in observations
                    ),
                    "parishes_below_previous_q4": None
                    if year == baseline_year
                    else sum(row["q4_yoy_pct"] < 0 for row in observations),
                }
            )
        percentage_changes = [row["change_pct"] for row in endpoints]
        summary = {
            "baseline_year": baseline_year,
            "latest_year": latest_year,
            "reference_quarter": 4,
            "parishes": len(reference),
            "input_rows": len(rows),
            "annual_rows": len(annual),
            "excluded_rows": len(rows) - len(annual),
            "excluded_periods": [f"{year}Q{quarter}" for year, quarter in sorted(excluded_periods)],
            "parishes_increased": sum(value > 0 for value in percentage_changes),
            "parishes_unchanged": sum(value == 0 for value in percentage_changes),
            "parishes_decreased": sum(value < 0 for value in percentage_changes),
            "median_parish_change_pct": float(median(percentage_changes)),
            "minimum_parish_change_pct": float(min(percentage_changes)),
            "maximum_parish_change_pct": float(max(percentage_changes)),
        }
    return summary, {
        "annual_q4.csv": annual,
        "parish_changes.csv": endpoints,
        "yearly_summary.csv": yearly,
    }


def plot_housing_changes(rows: Sequence[dict[str, Any]], path: Path) -> None:
    """Draw endpoint levels and nominal changes, ordered by unrounded percentage change."""
    from matplotlib import rc_context
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter

    ordered = sorted(rows, key=lambda row: (-row["change_pct"], row["freguesia_id"]))
    positions = list(range(len(ordered)))
    start = [float(row["baseline_eur_m2"]) for row in ordered]
    end = [float(row["latest_eur_m2"]) for row in ordered]
    change = [float(row["change_pct"]) for row in ordered]
    first, last = ordered[0]["baseline_year"], ordered[0]["latest_year"]
    with rc_context({"font.family": "DejaVu Sans", "font.size": 10}):
        figure = Figure(figsize=(13, 10))
        levels, growth = figure.subplots(1, 2, sharey=True, gridspec_kw={"width_ratios": [1.4, 1]})
        levels.hlines(positions, start, end, color="#bac4cb", linewidth=2)
        levels.scatter(start, positions, color="#246a91", label=f"{first} Q4", s=35, zorder=3)
        levels.scatter(end, positions, color="#ce7030", label=f"{last} Q4", s=35, zorder=3)
        levels.set_yticks(positions, [row["freguesia_name"] for row in ordered])
        levels.invert_yaxis()
        levels.set_xlim(left=0)
        levels.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        levels.set_xlabel("Published median sale value (EUR/m²)")
        levels.set_title("Levels at the two Q4 reference periods", loc="left", fontsize=11)
        levels.legend(loc="lower right", frameon=False)
        growth.barh(positions, change, color="#246a91", height=0.6)
        growth.axvline(0, color="#46545f", linewidth=0.7)
        growth.margins(x=0.18)
        for position, value in zip(positions, change, strict=True):
            growth.annotate(
                f"{value:+.1f}%",
                (value, position),
                xytext=(5 if value >= 0 else -5, 0),
                textcoords="offset points",
                ha="left" if value >= 0 else "right",
                va="center",
                fontsize=9,
            )
        growth.set_xlabel("Nominal change (%)")
        growth.set_title(f"{first} Q4 → {last} Q4", loc="left", fontsize=11)
        for axis in (levels, growth):
            axis.spines[["top", "right", "left"]].set_visible(False)
            axis.tick_params(axis="both", length=0)
            axis.grid(axis="x", color="#e5e9ec", linewidth=0.6)
            axis.set_axisbelow(True)
        figure.suptitle("Lisbon housing values across 24 parishes", x=0.03, ha="left", fontsize=19)
        figure.text(
            0.03,
            0.02,
            "INE 0012234 · Total dwellings · Q4 reference periods\n"
            "Each value covers sales in the preceding 12 months. "
            "Changes are not inflation-adjusted;\n"
            "transaction composition can change. "
            "These parish medians do not establish RNAL effects.",
            fontsize=9,
            color="#46545f",
        )
        figure.tight_layout(rect=(0.01, 0.09, 0.99, 0.95), w_pad=3)
        figure.savefig(path, dpi=180, facecolor="white", metadata={"Software": "Matplotlib"})
