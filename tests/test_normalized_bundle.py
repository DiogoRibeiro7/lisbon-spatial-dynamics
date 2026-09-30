"""Tests for the normalized analysis milestone bundle."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from lisbon_spatial_dynamics.analysis.normalized_bundle import (
    build_normalized_analysis_bundle,
    build_normalized_trajectory,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    AnnualHousingPressureRow,
)
from lisbon_spatial_dynamics.spatial.annual_maps import ReferenceFeature


def _row(
    freguesia_id: str,
    name: str,
    year: int,
    housing_change: str,
    pressure_change: str,
) -> AnnualHousingPressureRow:
    return AnnualHousingPressureRow(
        year=year,
        baseline_year=2019,
        period_code=f"4.º Trimestre de {year}",
        period_end=date(year, 12, 31),
        freguesia_id=freguesia_id,
        freguesia_name=name,
        population_reference_year=2021,
        population_resident=10_000,
        population_density_per_km2=Decimal("5000"),
        flow_quarters_observed=4 if year > 2019 else 1,
        housing_value_eur_m2=Decimal("5000"),
        housing_yoy_abs_eur_m2=Decimal("100") if year > 2019 else None,
        housing_yoy_pct=Decimal("2") if year > 2019 else None,
        housing_change_from_baseline_abs_eur_m2=Decimal("1000"),
        housing_change_from_baseline_pct=Decimal(housing_change),
        rnal_registrations_year=10 if year > 2019 else None,
        rnal_cessations_year=3 if year > 2019 else None,
        rnal_net_registrations_year=7 if year > 2019 else None,
        rnal_registrations_year_per_1000=Decimal("1") if year > 2019 else None,
        rnal_cessations_year_per_1000=Decimal("0.3") if year > 2019 else None,
        rnal_net_registrations_year_per_1000=Decimal("0.7") if year > 2019 else None,
        rnal_active_registrations_year_end=100,
        rnal_active_registrations_per_1000_year_end=Decimal("10"),
        rnal_active_registrations_per_1000_change_from_baseline=Decimal(pressure_change),
        rnal_active_beds_known_year_end=200,
        rnal_active_beds_missing_year_end=0,
        rnal_active_beds_known_per_1000_year_end=Decimal("20"),
        rnal_active_beds_known_per_1000_change_from_baseline=Decimal("2"),
        rnal_active_users_known_year_end=300,
        rnal_active_users_missing_year_end=0,
        rnal_active_users_known_per_1000_year_end=Decimal("30"),
        rnal_active_users_known_per_1000_change_from_baseline=Decimal("3"),
    )


def _square(index: int) -> dict[str, object]:
    x0 = float(index)
    x1 = float(index + 1)
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [x0, 0.0],
                [x1, 0.0],
                [x1, 1.0],
                [x0, 1.0],
                [x0, 0.0],
            ]
        ],
    }


def _reference() -> tuple[ReferenceFeature, ...]:
    return tuple(
        ReferenceFeature(
            freguesia_id=str(index),
            name=f"F{index}",
            properties={
                "freguesia_id": str(index),
                "name": f"F{index}",
            },
            geometry=_square(index),
        )
        for index in range(4)
    )


def _annual_rows() -> tuple[AnnualHousingPressureRow, ...]:
    rows = []
    for index in range(4):
        rows.append(_row(str(index), f"F{index}", 2019, "0", "0"))
        rows.append(
            _row(
                str(index),
                f"F{index}",
                2025,
                str((index + 1) * 10),
                str(index + 1),
            )
        )
    return tuple(rows)


def test_normalized_trajectory_uses_latest_common_year() -> None:
    rows = _annual_rows() + (_row("0", "F0", 2026, "60", "6"),)

    trajectory = build_normalized_trajectory(rows)

    assert {row.latest_year for row in trajectory} == {2025}
    assert trajectory[0].rnal_pressure_change_per_1000 == Decimal("1")


def test_bundle_writes_complete_analysis_milestone(tmp_path: Path) -> None:
    output = tmp_path / "bundle"

    result = build_normalized_analysis_bundle(
        _annual_rows(),
        _reference(),
        output,
        permutations=9,
        seed=7,
        alpha=0.10,
        label_maps=False,
        label_scatter=False,
    )

    for path in result.paths():
        assert path.exists()
        assert path.stat().st_size > 0

    summary = json.loads(result.summary_json.read_text(encoding="utf-8"))
    assert summary["comparison_window"]["baseline_year"] == 2019
    assert summary["comparison_window"]["latest_common_year"] == 2025
    assert summary["coverage"]["freguesia_count"] == 4

    global_moran = json.loads(result.global_morans_json.read_text(encoding="utf-8"))
    metrics = {item["metric"] for item in global_moran["results"]}
    assert metrics == {
        "housing_change_pct",
        "rnal_pressure_change_per_1000",
    }

    local_moran = json.loads(result.local_morans_json.read_text(encoding="utf-8"))
    assert len(local_moran["results"]) == 2
