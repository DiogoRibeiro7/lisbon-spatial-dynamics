"""Tests for the pre-specified multivariable-analysis milestone."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.multivariable import (
    build_multivariable_analysis,
    fit_multivariable_models,
    load_model_config,
    load_model_observations,
)
from lisbon_spatial_dynamics.spatial.annual_maps import load_reference_geojson


def _write_context_csv(path: Path, *, n_freguesias: int = 12) -> None:
    fieldnames = (
        "year",
        "baseline_year",
        "freguesia_id",
        "freguesia_name",
        "housing_value_eur_m2",
        "housing_change_from_baseline_pct",
        "rnal_active_registrations_per_1000_change_from_baseline",
        "population_reference_year",
        "population_resident",
        "population_density_per_km2",
        "census_rented_share_pct",
        "census_age_65_plus_pct",
        "census_vacant_or_secondary_family_share_pct",
        "census_pre1945_building_share_pct",
        "census_repair_needed_building_share_pct",
    )

    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()

        for index in range(n_freguesias):
            freguesia_id = f"{index:06d}"
            name = f"F{index}"
            baseline_housing = 2500.0 + index * 120.0
            density = 3500.0 + index * 300.0
            rented = 25.0 + index * 1.1
            age_65 = 12.0 + index * 0.8
            vacant = 8.0 + index * 0.7
            pre1945 = 10.0 + index * 1.2
            repair = 4.0 + index * 0.45

            writer.writerow(
                {
                    "year": 2019,
                    "baseline_year": 2019,
                    "freguesia_id": freguesia_id,
                    "freguesia_name": name,
                    "housing_value_eur_m2": f"{baseline_housing:.6f}",
                    "housing_change_from_baseline_pct": "0",
                    "rnal_active_registrations_per_1000_change_from_baseline": "0",
                    "population_reference_year": 2021,
                    "population_resident": 10000 + index * 250,
                    "population_density_per_km2": f"{density:.6f}",
                    "census_rented_share_pct": f"{rented:.6f}",
                    "census_age_65_plus_pct": f"{age_65:.6f}",
                    "census_vacant_or_secondary_family_share_pct": f"{vacant:.6f}",
                    "census_pre1945_building_share_pct": f"{pre1945:.6f}",
                    "census_repair_needed_building_share_pct": f"{repair:.6f}",
                }
            )

            pressure_change = -1.5 + index * 0.65
            outcome = (
                18.0
                + 3.2 * pressure_change
                - 0.002 * (baseline_housing - 3000.0)
                + 0.11 * rented
                - 0.08 * age_65
                + ((index % 3) - 1) * 0.7
            )
            writer.writerow(
                {
                    "year": 2025,
                    "baseline_year": 2019,
                    "freguesia_id": freguesia_id,
                    "freguesia_name": name,
                    "housing_value_eur_m2": f"{baseline_housing * (1 + outcome / 100):.6f}",
                    "housing_change_from_baseline_pct": f"{outcome:.6f}",
                    "rnal_active_registrations_per_1000_change_from_baseline": (
                        f"{pressure_change:.6f}"
                    ),
                    "population_reference_year": 2021,
                    "population_resident": 10000 + index * 250,
                    "population_density_per_km2": f"{density:.6f}",
                    "census_rented_share_pct": f"{rented:.6f}",
                    "census_age_65_plus_pct": f"{age_65:.6f}",
                    "census_vacant_or_secondary_family_share_pct": f"{vacant:.6f}",
                    "census_pre1945_building_share_pct": f"{pre1945:.6f}",
                    "census_repair_needed_building_share_pct": f"{repair:.6f}",
                }
            )


def _write_reference(path: Path, *, n_freguesias: int = 12) -> None:
    features = []
    for index in range(n_freguesias):
        x0 = float(index)
        x1 = float(index + 1)
        freguesia_id = f"{index:06d}"
        features.append(
            {
                "type": "Feature",
                "id": freguesia_id,
                "properties": {
                    "freguesia_id": freguesia_id,
                    "name": f"F{index}",
                },
                "geometry": {
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
                },
            }
        )

    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": features,
            }
        ),
        encoding="utf-8",
    )


def _write_config(path: Path) -> None:
    path.write_text(
        """[analysis]
outcome = "housing_change_from_baseline_pct"
primary_model = "context_adjusted"
standardize_predictors = true

[models.unadjusted]
label = "RNAL pressure only"
predictors = ["rnal_pressure_change_per_1000"]

[models.baseline_adjusted]
label = "RNAL pressure + baseline housing"
predictors = [
  "rnal_pressure_change_per_1000",
  "log_baseline_housing_eur_m2",
]

[models.context_adjusted]
label = "RNAL pressure + demographic context"
predictors = [
  "rnal_pressure_change_per_1000",
  "log_baseline_housing_eur_m2",
  "log_population_density_per_km2",
  "census_rented_share_pct",
  "census_age_65_plus_pct",
]

[models.built_environment_sensitivity]
label = "RNAL pressure + built environment"
predictors = [
  "rnal_pressure_change_per_1000",
  "log_baseline_housing_eur_m2",
  "census_vacant_or_secondary_family_share_pct",
  "census_pre1945_building_share_pct",
  "census_repair_needed_building_share_pct",
]
""",
        encoding="utf-8",
    )


def test_load_model_config_preserves_pre_specified_order(tmp_path: Path) -> None:
    config_path = tmp_path / "models.toml"
    _write_config(config_path)

    config = load_model_config(config_path)

    assert config.primary_model == "context_adjusted"
    assert [spec.name for spec in config.models] == [
        "unadjusted",
        "baseline_adjusted",
        "context_adjusted",
        "built_environment_sensitivity",
    ]


def test_model_observations_use_latest_common_year(tmp_path: Path) -> None:
    context_path = tmp_path / "context.csv"
    _write_context_csv(context_path, n_freguesias=8)

    # Add one non-common 2026 row for F0; common latest must remain 2025.
    with context_path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                2026,
                2019,
                "000000",
                "F0",
                4000,
                40,
                8,
                2021,
                10000,
                3500,
                25,
                12,
                8,
                10,
                4,
            )
        )

    observations = load_model_observations(context_path)

    assert {row.baseline_year for row in observations} == {2019}
    assert {row.latest_year for row in observations} == {2025}


def test_fit_models_produces_robust_diagnostics_and_sensitivity(
    tmp_path: Path,
) -> None:
    context_path = tmp_path / "context.csv"
    config_path = tmp_path / "models.toml"
    reference_path = tmp_path / "reference.geojson"
    _write_context_csv(context_path)
    _write_config(config_path)
    _write_reference(reference_path)

    observations = load_model_observations(context_path)
    config = load_model_config(config_path)
    reference = load_reference_geojson(reference_path, expected_count=12)

    result = fit_multivariable_models(
        observations,
        config,
        reference,
        permutations=19,
        seed=7,
    )

    assert len(result.fits) == 4
    primary = next(
        fit for fit in result.fits if fit.spec.name == result.primary_model
    )
    pressure = next(
        coefficient
        for coefficient in primary.coefficients
        if coefficient.term == "rnal_pressure_change_per_1000"
    )

    assert pressure.estimate > 0
    assert primary.diagnostics.n_observations == 12
    assert primary.diagnostics.residual_degrees_of_freedom == 6
    assert primary.diagnostics.residual_moran.complete_cases == 12
    assert primary.diagnostics.residual_moran.permutation_p_two_sided is not None
    assert result.leave_one_out.successful_refits == 12
    assert result.leave_one_out.same_sign_fraction is not None


def test_build_multivariable_analysis_writes_complete_milestone(
    tmp_path: Path,
) -> None:
    context_path = tmp_path / "context.csv"
    config_path = tmp_path / "models.toml"
    reference_path = tmp_path / "reference.geojson"
    _write_context_csv(context_path)
    _write_config(config_path)
    _write_reference(reference_path)

    outputs = build_multivariable_analysis(
        context_path,
        reference_path,
        config_path,
        tmp_path / "output",
        permutations=9,
        seed=3,
    )

    for path in outputs.paths():
        assert path.exists()
        assert path.stat().st_size > 0

    report = json.loads(outputs.report_json.read_text(encoding="utf-8"))
    assert report["analysis"] == "pre_specified_multivariable_ols"
    assert report["primary_model"] == "context_adjusted"
    assert len(report["models"]) == 4

    with outputs.coefficients_csv.open(
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))

    assert {
        row["model"] for row in rows
    } == {
        "unadjusted",
        "baseline_adjusted",
        "context_adjusted",
        "built_environment_sensitivity",
    }
