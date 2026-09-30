"""Tests for final research-results synthesis."""

from __future__ import annotations

import json
from pathlib import Path

from lisbon_spatial_dynamics.analysis.final_results import (
    build_final_results_package,
)


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    normalized = tmp_path / "normalized"
    models = tmp_path / "models"
    normalized.mkdir()
    models.mkdir()

    _write_json(
        normalized / "normalized_summary.json",
        {
            "comparison_window": {
                "baseline_year": 2019,
                "latest_common_year": 2025,
            },
            "coverage": {"freguesia_count": 24},
            "descriptive": {
                "housing_change_pct_median": 40.0,
                "rnal_pressure_change_per_1000_median": 2.5,
            },
            "association": {"complete_cases": 24},
        },
    )
    _write_json(
        normalized / "normalized_association.json",
        {
            "comparison_window": {
                "baseline_year": 2019,
                "latest_common_year": 2025,
            },
            "correlations": {
                "pearson_r": 0.4,
                "spearman_rho": 0.35,
            },
        },
    )

    spatial_results = [
        {
            "metric": "housing_change_pct",
            "baseline_year": 2019,
            "latest_year": 2025,
            "morans_i": 0.2,
            "expected_i": -0.043,
            "permutation_p_two_sided": 0.04,
        },
        {
            "metric": "rnal_pressure_change_per_1000",
            "baseline_year": 2019,
            "latest_year": 2025,
            "morans_i": 0.1,
            "expected_i": -0.043,
            "permutation_p_two_sided": 0.2,
        },
    ]
    _write_json(
        normalized / "global_morans_i.json",
        {"results": spatial_results},
    )
    _write_json(
        normalized / "local_morans_i.json",
        {
            "results": [
                {
                    "metric": item["metric"],
                    "baseline_year": 2019,
                    "latest_year": 2025,
                    "observations": [
                        {
                            "significant_fdr": True,
                            "cluster_class": "HH",
                        },
                        {
                            "significant_fdr": False,
                            "cluster_class": "not_significant",
                        },
                    ],
                }
                for item in spatial_results
            ]
        },
    )

    _write_json(
        models / "model_report.json",
        {
            "comparison_window": {
                "baseline_year": 2019,
                "latest_year": 2025,
            },
            "primary_model": "context_adjusted",
            "models": [
                {
                    "name": "unadjusted",
                    "label": "Unadjusted",
                    "coefficients": [
                        {
                            "term": "rnal_pressure_change_per_1000",
                            "estimate": 3.0,
                            "hc3_se": 1.0,
                            "ci_95_low": 0.8,
                            "ci_95_high": 5.2,
                            "p_value": 0.02,
                        }
                    ],
                    "diagnostics": {
                        "n_observations": 24,
                        "adjusted_r_squared": 0.2,
                        "max_vif": 1.0,
                        "condition_number": 1.1,
                        "breusch_pagan_p_value": 0.5,
                        "residual_moran": {
                            "morans_i": 0.1,
                            "permutation_p_two_sided": 0.3,
                        },
                    },
                },
                {
                    "name": "context_adjusted",
                    "label": "Context adjusted",
                    "coefficients": [
                        {
                            "term": "rnal_pressure_change_per_1000",
                            "estimate": 2.2,
                            "hc3_se": 0.9,
                            "ci_95_low": 0.2,
                            "ci_95_high": 4.2,
                            "p_value": 0.04,
                        }
                    ],
                    "diagnostics": {
                        "n_observations": 24,
                        "adjusted_r_squared": 0.5,
                        "max_vif": 2.5,
                        "condition_number": 4.0,
                        "breusch_pagan_p_value": 0.4,
                        "residual_moran": {
                            "morans_i": 0.02,
                            "permutation_p_two_sided": 0.7,
                        },
                    },
                },
            ],
            "leave_one_freguesia_out": {
                "full_sample_pressure_coefficient": 2.2,
                "successful_refits": 24,
                "failed_refits": 0,
                "same_sign_fraction": 1.0,
                "coefficient_min": 1.6,
                "coefficient_median": 2.1,
                "coefficient_max": 2.8,
            },
        },
    )

    for path in (
        normalized / "normalized_association.png",
        models / "pressure_coefficients.png",
        models / "primary_residuals.png",
    ):
        path.write_bytes(b"fake-png-content")

    return normalized, models


def test_final_results_package_writes_all_outputs(tmp_path: Path) -> None:
    normalized, models = _inputs(tmp_path)
    outputs = build_final_results_package(
        normalized,
        models,
        tmp_path / "final",
    )

    for path in outputs.paths():
        assert path.exists()
        assert path.stat().st_size > 0

    findings = json.loads(outputs.findings_json.read_text(encoding="utf-8"))
    assert findings["study_window"]["baseline_year"] == 2019
    assert findings["primary_model"]["name"] == "context_adjusted"
    assert findings["primary_model"]["pressure_estimate"] == 2.2

    markdown = outputs.findings_markdown.read_text(encoding="utf-8")
    assert "# Final research findings" in markdown
    assert "Context adjusted" in markdown


def test_final_results_rejects_window_mismatch(tmp_path: Path) -> None:
    normalized, models = _inputs(tmp_path)
    report_path = models / "model_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["comparison_window"]["latest_year"] = 2024
    report_path.write_text(json.dumps(report), encoding="utf-8")

    try:
        build_final_results_package(
            normalized,
            models,
            tmp_path / "final",
        )
    except ValueError as exc:
        assert "latest year mismatch" in str(exc)
    else:
        raise AssertionError("window mismatch should fail")
