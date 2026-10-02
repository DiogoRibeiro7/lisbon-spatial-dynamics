"""Assignment scenarios must isolate geography and preserve cohort/capacity totals."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.rnal_parish_sensitivity import (
    compare_assignments,
    load_population,
)
from lisbon_spatial_dynamics.panels.rnal import RNALRecord

A, B, C = "110601", "110602", "110603"
NAMES = {A: "A", B: "B", C: "C"}
POPULATION = {A: 100, B: 100, C: 200}


def records() -> list[RNALRecord]:
    return [
        RNALRecord(f"{number}/AL", date(1900, 1, 1), None, parish, NAMES[parish], "", None, users)
        for number, parish, users in [(1, A, 10), (2, A, None), (3, B, 0), (4, C, 30), (5, C, 20)]
    ]


def test_scenarios_preserve_membership_capacity_missingness_and_originals() -> None:
    source = records()
    # Cessation/date screening would change the estimand: retain this record too.
    source[0] = replace(source[0], ceased_on=date(2000, 1, 1))
    original = list(source)
    conflicts = {1: (A, B), 2: (A, C), 3: (B, A), 4: (C, A)}
    evidence = {
        1: ("supports_gis", 25.0),
        2: ("supports_gis", 40.0),
        3: ("supports_soap", 50.0),
        4: ("boundary_ambiguous", 0.0),
    }
    summary, rows = compare_assignments(source, conflicts, evidence, NAMES, POPULATION, margin_m=25)
    assert source == original
    assert summary["assignments_corrected"] == 0
    assert [scenario["reassigned_records"] for scenario in summary["scenarios"]] == [0, 4, 1]
    for scenario in summary["scenarios"]:
        assert scenario["municipality_records"] == 5
        assert scenario["municipality_users_known"] == 60
        assert scenario["municipality_users_missing"] == 1
        selected = [row for row in rows if row["scenario"] == scenario["scenario"]]
        assert sum(row["records_delta"] for row in selected) == 0
        assert sum(row["users_known_delta"] for row in selected) == 0
        assert sum(row["users_missing_delta"] for row in selected) == 0
        assert sum(row["incoming_records"] for row in selected) == scenario["reassigned_records"]
        for row in selected:
            assert row["records_delta"] == row["incoming_records"] - row["outgoing_records"]
            assert (
                row["records_per_1000"] == row["records"] * 1000 / POPULATION[row["freguesia_id"]]
            )
    indexed = {(row["scenario"], row["freguesia_id"]): row for row in rows}
    assert indexed["gis_all_conflicts", A]["records_delta"] == 0  # Gross moves cancel.
    assert indexed["gis_all_conflicts", A]["users_known_delta"] == 20
    assert indexed["gis_beyond_margin", A]["records_delta"] == -1
    assert indexed["gis_beyond_margin", C]["users_missing"] == 1
    assert indexed["gis_beyond_margin", C]["users_known"] == 50
    assert [indexed["soap", code]["record_pressure_rank"] for code in NAMES] == [1, 2, 2]
    assert [indexed["gis_beyond_margin", code]["record_pressure_rank"] for code in NAMES] == [
        2,
        2,
        1,
    ]


@pytest.mark.parametrize(
    "category,distance,expected",
    [
        ("supports_gis", 25.0001, 1),
        ("supports_gis", 25.0, 0),
        ("supports_gis", 24.9999, 0),
        ("supports_other_parish", 40.0, 0),
        ("outside_reference", 40.0, 0),
        ("missing_geometry", None, 0),
    ],
)
def test_only_gis_support_strictly_beyond_margin_is_selected(
    category: str, distance: float | None, expected: int
) -> None:
    summary, _ = compare_assignments(
        records(), {1: (A, B)}, {1: (category, distance)}, NAMES, POPULATION, margin_m=25
    )
    assert summary["scenarios"][1]["reassigned_records"] == 1
    assert summary["scenarios"][2]["reassigned_records"] == expected


def test_zero_baselines_and_exact_rational_ties() -> None:
    source = [replace(row, freguesia_id=A) for row in records()[:3]]
    _, rows = compare_assignments(
        source,
        {1: (A, C), 2: (A, C)},
        {1: ("supports_gis", 40.0), 2: ("supports_gis", 40.0)},
        NAMES,
        {A: 3, B: 1, C: 6},
        margin_m=25,
    )
    selected = {row["freguesia_id"]: row for row in rows if row["scenario"] == "gis_all_conflicts"}
    assert selected[A]["record_pressure_rank"] == selected[C]["record_pressure_rank"] == 1
    assert selected[B]["record_pressure_rank"] == 3
    assert selected[C]["records_delta_pct"] is None  # Never divide by zero or imply 0%.


@pytest.mark.parametrize(
    "failure",
    ["population", "zero", "duplicate", "unknown", "drift", "cohort", "margin", "evidence"],
)
def test_invalid_inputs_fail_before_scenario_aggregation(failure: str) -> None:
    source, population = records(), POPULATION.copy()
    conflicts = {1: (A, B)}
    evidence: dict[int, tuple[str, float | None]] = {1: ("supports_gis", 40.0)}
    margin = 25.0
    if failure == "population":
        population.pop(C)
    elif failure == "zero":
        population[A] = 0
    elif failure == "duplicate":
        source.append(replace(source[0], registration_id="01/AL"))
    elif failure == "unknown":
        conflicts[1] = (A, "110699")
    elif failure == "drift":
        conflicts[1] = (C, B)
    elif failure == "cohort":
        evidence = {}
    elif failure == "margin":
        margin = float("nan")
    else:
        evidence[1] = ("supports_gis", None)
    with pytest.raises(ValueError):
        compare_assignments(source, conflicts, evidence, NAMES, population, margin_m=margin)


@pytest.mark.parametrize("failure", ["duplicate", "year", "zero", "fractional", "columns"])
def test_population_loader_rejects_ambiguous_denominators(tmp_path: Path, failure: str) -> None:
    text = "freguesia_id,census_year,population_resident\n110601,2021,100\n"
    if failure == "duplicate":
        text += "110601,2021,100\n"
    elif failure == "year":
        text = text.replace("2021", "2020")
    elif failure == "zero":
        text = text.replace(",100", ",0")
    elif failure == "fractional":
        text = text.replace(",100", ",100.5")
    else:
        text = text.replace("population_resident", "other")
    path = tmp_path / "population.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_population(path)
