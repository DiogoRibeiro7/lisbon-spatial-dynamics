"""Parish-label sensitivity within one retained RNAL snapshot cohort."""

from __future__ import annotations

import csv
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from io import StringIO
from pathlib import Path
from typing import Any

from lisbon_spatial_dynamics.analysis.rnal_geography import validate_conflict_parishes
from lisbon_spatial_dynamics.panels.rnal import RNALRecord


def load_population(path: Path) -> dict[str, int]:
    """Read the previously audited Census 2021 denominators without collapsing duplicates."""
    return parse_population(path.read_text(encoding="utf-8"))


def parse_population(payload: str) -> dict[str, int]:
    """Validate captured Census CSV text without reopening its source file."""
    population: dict[str, int] = {}
    with StringIO(payload, newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"freguesia_id", "census_year", "population_resident"} <= set(
            reader.fieldnames or []
        ):
            raise ValueError("Census population columns missing")
        for row in reader:
            code = row["freguesia_id"]
            if code in population or row["census_year"] != "2021":
                raise ValueError("duplicate parish or non-2021 Census denominator")
            value = int(row["population_resident"])
            if value <= 0:
                raise ValueError("Census denominators must be positive")
            population[code] = value
    return population


@dataclass
class Totals:
    records: int = 0
    users_known: int = 0
    users_missing: int = 0
    incoming_records: int = 0
    outgoing_records: int = 0


def _ranks(values: Mapping[str, Fraction]) -> dict[str, int]:
    # Descending competition ranks: ties share a rank and leave a gap (1, 1, 3).
    return {
        code: 1 + sum(other > value for other in values.values()) for code, value in values.items()
    }


def compare_assignments(
    records: Sequence[RNALRecord],
    conflicts: Mapping[int, tuple[str, str]],
    evidence: Mapping[int, tuple[str, float | None]],
    names: Mapping[str, str],
    population: Mapping[str, int],
    *,
    margin_m: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Hold cohort and capacity fixed; vary labels in three pre-specified scenarios.

    All snapshot members are included, regardless of registration/cessation dates.
    These are retained-record counts and captured capacity, not historical stocks.
    """
    if not names or set(population) != set(names):
        raise ValueError("Census and canonical parish sets must match exactly")
    if any(type(value) is not int or value <= 0 for value in population.values()):
        raise ValueError("Census denominators must be positive integers")
    if not math.isfinite(margin_m) or margin_m < 0:
        raise ValueError("boundary margin must be finite and non-negative")
    validate_conflict_parishes(conflicts, names)
    if set(evidence) != set(conflicts):
        raise ValueError("coordinate evidence must cover exactly the conflict cohort")
    supported: set[int] = set()
    categories = {
        "supports_soap",
        "supports_gis",
        "supports_other_parish",
        "boundary_ambiguous",
        "outside_reference",
        "missing_geometry",
    }
    for number, (category, distance) in evidence.items():
        if category not in categories or (
            (distance is None) != (category == "missing_geometry")
            or (distance is not None and (not math.isfinite(distance) or distance < 0))
        ):
            raise ValueError("invalid coordinate evidence")
        if category == "supports_gis" and distance is not None and distance > margin_m:
            supported.add(number)

    indexed: dict[int, RNALRecord] = {}
    for record in records:
        if not re.fullmatch(r"[0-9]+/AL", record.registration_id):
            raise ValueError("invalid SOAP registry number")
        number = int(record.registration_id[:-3])
        if number <= 0 or number in indexed:
            raise ValueError("invalid or duplicate normalized SOAP registry number")
        if record.freguesia_id not in names:
            raise ValueError("SOAP parish absent from canonical reference")
        if record.users is not None and (type(record.users) is not int or record.users < 0):
            raise ValueError("invalid SOAP user capacity")
        indexed[number] = record
    if not indexed or not set(conflicts) <= set(indexed):
        raise ValueError("conflict cohort must be contained in a non-empty SOAP snapshot")
    if any(indexed[key].freguesia_id != pair[0] for key, pair in conflicts.items()):
        raise ValueError("conflict SOAP assignment differs from the snapshot")

    selections = {
        "soap": set(),
        "gis_all_conflicts": set(conflicts),
        "gis_beyond_margin": supported,
    }
    rows: list[dict[str, Any]] = []
    baseline: dict[str, dict[str, Any]] = {}
    summaries: list[dict[str, Any]] = []
    for scenario, selected in selections.items():
        totals = {code: Totals() for code in names}
        for number, record in indexed.items():
            destination = conflicts[number][1] if number in selected else record.freguesia_id
            aggregate = totals[destination]
            aggregate.records += 1
            aggregate.users_known += record.users if record.users is not None else 0
            aggregate.users_missing += record.users is None
            if destination != record.freguesia_id:
                aggregate.incoming_records += 1
                totals[record.freguesia_id].outgoing_records += 1
        record_rates = {
            code: Fraction(value.records * 1000, population[code]) for code, value in totals.items()
        }
        capacity_rates = {
            code: Fraction(value.users_known * 1000, population[code])
            for code, value in totals.items()
        }
        record_ranks, capacity_ranks = _ranks(record_rates), _ranks(capacity_rates)
        scenario_rows = []
        for code in sorted(names):
            value = totals[code]
            row: dict[str, Any] = {
                "scenario": scenario,
                "freguesia_id": code,
                "freguesia_name": names[code],
                "population_2021": population[code],
                "records": value.records,
                "users_known": value.users_known,
                "users_missing": value.users_missing,
                "records_per_1000": float(record_rates[code]),
                "known_users_per_1000": float(capacity_rates[code]),
                "record_pressure_rank": record_ranks[code],
                "known_capacity_pressure_rank": capacity_ranks[code],
                "incoming_records": value.incoming_records,
                "outgoing_records": value.outgoing_records,
            }
            if scenario == "soap":
                baseline[code] = row.copy()
            base = baseline[code]
            for field in (
                "records",
                "users_known",
                "users_missing",
                "records_per_1000",
                "known_users_per_1000",
                "record_pressure_rank",
                "known_capacity_pressure_rank",
            ):
                row[field + "_delta"] = row[field] - base[field]
            row["records_delta_pct"] = (
                100 * row["records_delta"] / base["records"] if base["records"] else None
            )
            scenario_rows.append(row)
        rows.extend(scenario_rows)
        summaries.append(
            {
                "scenario": scenario,
                "reassigned_records": len(selected),
                "reassigned_known_users": sum(indexed[key].users or 0 for key in selected),
                "reassigned_records_missing_users": sum(
                    indexed[key].users is None for key in selected
                ),
                "municipality_records": sum(value.records for value in totals.values()),
                "municipality_users_known": sum(value.users_known for value in totals.values()),
                "municipality_users_missing": sum(value.users_missing for value in totals.values()),
                "parishes_with_net_record_change": sum(
                    row["records_delta"] != 0 for row in scenario_rows
                ),
                "parishes_with_record_rank_change": sum(
                    row["record_pressure_rank_delta"] != 0 for row in scenario_rows
                ),
                "parishes_with_capacity_rank_change": sum(
                    row["known_capacity_pressure_rank_delta"] != 0 for row in scenario_rows
                ),
                "max_absolute_record_change": max(
                    abs(row["records_delta"]) for row in scenario_rows
                ),
                "max_absolute_record_pressure_rank_change": max(
                    abs(row["record_pressure_rank_delta"]) for row in scenario_rows
                ),
                "max_absolute_capacity_pressure_rank_change": max(
                    abs(row["known_capacity_pressure_rank_delta"]) for row in scenario_rows
                ),
            }
        )
    return {
        "snapshot_records": len(indexed),
        "conflicting_records": len(conflicts),
        "population_2021": sum(population.values()),
        "boundary_margin_m": margin_m,
        "scenarios": summaries,
        "assignments_corrected": 0,
        "interpretation": (
            "Parish-label sensitivity among retained snapshot members, using captured capacity "
            "and fixed Census 2021 denominators. No historical stocks, operating businesses, "
            "contemporaneous resident counts or verified corrections are inferred."
        ),
    }, rows


def plot_sensitivity(rows: Sequence[Mapping[str, Any]], output: Path, *, margin_m: float) -> None:
    """Plot aggregate scenario-minus-SOAP changes, ordered by baseline record pressure."""
    import matplotlib.pyplot as plt

    baseline = sorted(
        (row for row in rows if row["scenario"] == "soap"),
        key=lambda row: (row["record_pressure_rank"], row["freguesia_id"]),
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, 9), sharey=True)
    try:
        for scenario, label, offset, color in (
            ("gis_all_conflicts", "All GIS conflict labels", -0.14, "#2368a2"),
            ("gis_beyond_margin", f"GIS support > {margin_m:g} m from boundaries", 0.14, "#b34619"),
        ):
            selected = {row["freguesia_id"]: row for row in rows if row["scenario"] == scenario}
            for axis, field in zip(
                axes, ("records_delta", "known_users_per_1000_delta"), strict=True
            ):
                axis.scatter(
                    [selected[row["freguesia_id"]][field] for row in baseline],
                    [position + offset for position in range(len(baseline))],
                    label=label,
                    color=color,
                    s=24,
                    zorder=3,
                )
        axes[0].set_yticks(range(len(baseline)), [row["freguesia_name"] for row in baseline])
        axes[0].invert_yaxis()
        for axis, label in zip(
            axes,
            (
                "Change in retained record count",
                "Change in known user capacity per 1,000 residents",
            ),
            strict=True,
        ):
            axis.axvline(0, color="#444444", linewidth=0.8)
            axis.grid(axis="y", alpha=0.15)
            axis.set_xlabel(label)
            axis.spines[["top", "right"]].set_visible(False)
        fig.suptitle("Sensitivity to RNAL parish labels", fontsize=17)
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.6, 0.04), ncol=2)
        fig.text(
            0.02,
            0.015,
            "Same retained SOAP cohort and captured capacity in each scenario; fixed Census 2021 "
            "denominators. No historical-stock inference.",
            fontsize=9,
        )
        fig.tight_layout(rect=(0, 0.09, 1, 0.96))
        fig.savefig(
            output, dpi=160, facecolor="white", metadata={"Software": "lisbon-spatial-dynamics"}
        )
    finally:
        plt.close(fig)
