"""Historical reported capacity relative to a fixed Census population reference."""

from __future__ import annotations

import csv
from decimal import Context, Decimal, localcontext
from io import StringIO
from pathlib import Path
from statistics import median
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import audit_transcription, parse_reference


def analyse_historical_capacity(
    transcription: str, census: str, *, expected_parishes: int, baseline_top_n: int
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Reproduce the benchmark audit and normalize only its reconciled capacity table."""
    reader = csv.DictReader(StringIO(census, newline=""))
    columns = reader.fieldnames or []
    if len(columns) != len(set(columns)) or not {
        "freguesia_id",
        "freguesia_name",
        "census_year",
        "population_resident",
    } <= set(columns):
        raise ValueError("missing or duplicate population reference columns")
    populations = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed population reference row")
        value = row["population_resident"]
        if (
            row["census_year"] != "2021"
            or not value.isascii()
            or not value.isdigit()
            or int(value) <= 0
        ):
            raise ValueError("positive integer Census 2021 populations required")
        populations[row["freguesia_id"]] = int(value)
    reference = parse_reference(census, expected_count=expected_parishes)
    if type(baseline_top_n) is not int or not 0 < baseline_top_n < len(reference):
        raise ValueError("baseline_top_n must select a nonempty proper subset of parishes")
    benchmark, observations, _ = audit_transcription(transcription, reference)
    capacity_audit = {row["table_number"]: row for row in benchmark["tables"]}[19]
    if capacity_audit["row_change_discrepancies"] or any(
        row["parish_sum_minus_published_municipality"]
        for row in capacity_audit["column_sum_checks"]
    ):
        raise ValueError("capacity endpoints, changes and municipality totals must reconcile")
    capacity = {
        (row["geography_id"], row["reference_month"]): row["published_value"]
        for row in observations
        if row["table_number"] == 19 and row["scope"] == "freguesia"
    }
    start, end = "2019-11", "2022-11"
    total_a, total_b = (sum(capacity[code, month] for code in reference) for month in (start, end))
    if total_a <= 0 or total_b <= 0:
        raise ValueError("positive municipality capacity required for shares")
    cohort = sorted(reference, key=lambda code: (-capacity[code, start], code))[:baseline_top_n]
    population = sum(populations.values())
    parishes: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    with localcontext(Context(prec=28)):
        for code in sorted(reference):
            a, b, p = capacity[code, start], capacity[code, end], populations[code]
            parishes.append(
                {
                    "freguesia_id": code,
                    "freguesia_name": reference[code],
                    "baseline_month": start,
                    "latest_month": end,
                    "population_reference_year": 2021,
                    "population_resident_2021": p,
                    "baseline_capacity": a,
                    "latest_capacity": b,
                    "capacity_change": b - a,
                    "capacity_change_pct": Decimal(b - a) * 100 / a if a else None,
                    "baseline_capacity_per_1000_2021_residents": Decimal(a) * 1000 / p,
                    "latest_capacity_per_1000_2021_residents": Decimal(b) * 1000 / p,
                    "capacity_change_per_1000_2021_residents": Decimal(b - a) * 1000 / p,
                    "baseline_municipality_capacity_share_pct": Decimal(a) * 100 / total_a,
                    "latest_municipality_capacity_share_pct": Decimal(b) * 100 / total_b,
                    "capacity_share_change_pp": Decimal(b) * 100 / total_b
                    - Decimal(a) * 100 / total_a,
                    "in_baseline_largest_capacity_cohort": code in cohort,
                }
            )
        for group, codes in (
            ("baseline_largest_capacity", cohort),
            ("remaining_parishes", sorted(set(reference) - set(cohort))),
        ):
            a, b = (sum(capacity[code, month] for code in codes) for month in (start, end))
            groups.append(
                {
                    "group": group,
                    "parishes": len(codes),
                    "baseline_month": start,
                    "latest_month": end,
                    "baseline_capacity": a,
                    "latest_capacity": b,
                    "capacity_change": b - a,
                    "baseline_municipality_capacity_share_pct": Decimal(a) * 100 / total_a,
                    "latest_municipality_capacity_share_pct": Decimal(b) * 100 / total_b,
                    "capacity_share_change_pp": Decimal(b) * 100 / total_b
                    - Decimal(a) * 100 / total_a,
                }
            )
        municipality = {
            "municipality_id": "1106",
            "municipality_name": "Lisboa",
            "baseline_month": start,
            "latest_month": end,
            "population_reference_year": 2021,
            "population_resident_2021": population,
            "baseline_capacity": total_a,
            "latest_capacity": total_b,
            "capacity_change": total_b - total_a,
            "capacity_change_pct": Decimal(total_b - total_a) * 100 / total_a,
            "baseline_capacity_per_1000_2021_residents": Decimal(total_a) * 1000 / population,
            "latest_capacity_per_1000_2021_residents": Decimal(total_b) * 1000 / population,
            "capacity_change_per_1000_2021_residents": Decimal(total_b - total_a)
            * 1000
            / population,
        }
        median_change = median(row["capacity_change_per_1000_2021_residents"] for row in parishes)
    summary = {
        "parishes": len(reference),
        "population_reference_year": 2021,
        "baseline_month": start,
        "latest_month": end,
        "municipality": {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in municipality.items()
        },
        "parishes_increased": sum(row["capacity_change"] > 0 for row in parishes),
        "parishes_unchanged": sum(row["capacity_change"] == 0 for row in parishes),
        "parishes_decreased": sum(row["capacity_change"] < 0 for row in parishes),
        "median_parish_capacity_change_per_1000_2021_residents": float(median_change),
        "baseline_largest_capacity_cohort": [
            {"freguesia_id": code, "freguesia_name": reference[code]} for code in cohort
        ],
        "concentration": [
            {
                key: float(value) if isinstance(value, Decimal) else value
                for key, value in row.items()
            }
            for row in groups
        ],
    }
    return (
        summary,
        {
            "parish_capacity.csv": parishes,
            "municipality_capacity.csv": [municipality],
            "concentration.csv": groups,
        },
        benchmark,
    )


def plot_historical_capacity(parishes: list[dict[str, Any]], path: Path) -> None:
    """Show capacity levels and changes using the same fixed denominator convention."""
    from matplotlib.figure import Figure

    rows = sorted(
        parishes,
        key=lambda row: (row["baseline_capacity_per_1000_2021_residents"], row["freguesia_id"]),
    )
    fig = Figure(figsize=(14, 10), layout="constrained")
    axes = fig.subplots(1, 2, sharey=True)
    levels, changes = axes
    for index, row in enumerate(rows):
        levels.plot(
            [
                float(row["baseline_capacity_per_1000_2021_residents"]),
                float(row["latest_capacity_per_1000_2021_residents"]),
            ],
            [index, index],
            color="#a8afb8",
            zorder=1,
        )
    for key, label, color, marker in (
        ("baseline_capacity_per_1000_2021_residents", "November 2019", "#475569", "o"),
        ("latest_capacity_per_1000_2021_residents", "November 2022", "#117864", "D"),
    ):
        levels.scatter(
            [float(row[key]) for row in rows],
            range(len(rows)),
            color=color,
            marker=marker,
            label=label,
            zorder=3,
        )
    deltas = [float(row["capacity_change_per_1000_2021_residents"]) for row in rows]
    changes.barh(
        range(len(rows)),
        deltas,
        color=["#117864" if v >= 0 else "#a84459" for v in deltas],
        height=0.65,
    )
    changes.axvline(0, color="#475569", linewidth=0.8)
    levels.set_yticks(range(len(rows)), [row["freguesia_name"] for row in rows], fontsize=9)
    levels.set_title("Reported capacity at the two source months")
    changes.set_title("Change in reported capacity")
    levels.set_xlabel("Capacity places per 1,000 Census 2021 residents")
    changes.set_xlabel("Change in places per 1,000 Census 2021 residents")
    levels.legend(loc="lower right")
    for ax in axes:
        ax.grid(axis="x", alpha=0.2)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Lisbon accommodation capacity | November 2019–November 2022", fontsize=15)
    fig.supxlabel(
        "CML table 19 / Turismo de Portugal RNAL; INE Census 2021.\n"
        "Fixed population reference; reported capacity is not occupancy or a count of visitors.\n"
        "Exact observation days are unspecified.",
        fontsize=10,
    )
    fig.savefig(path, dpi=180)
