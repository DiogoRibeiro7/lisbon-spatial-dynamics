"""Final research-results synthesis from completed analysis artifacts."""

from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class FinalResultsError(ValueError):
    """Raised when final research artifacts cannot be synthesized safely."""


@dataclass(frozen=True, slots=True)
class FinalResultsOutputs:
    """Publication-style result artifacts."""

    descriptive_table_csv: Path
    spatial_table_csv: Path
    model_table_csv: Path
    diagnostics_table_csv: Path
    findings_json: Path
    findings_markdown: Path
    figure_pressure_association: Path
    figure_pressure_coefficients: Path
    figure_primary_residuals: Path

    def paths(self) -> tuple[Path, ...]:
        """Return every output path in deterministic order."""
        return (
            self.descriptive_table_csv,
            self.spatial_table_csv,
            self.model_table_csv,
            self.diagnostics_table_csv,
            self.findings_json,
            self.findings_markdown,
            self.figure_pressure_association,
            self.figure_pressure_coefficients,
            self.figure_primary_residuals,
        )


def build_final_results_package(
    normalized_directory: Path,
    multivariable_directory: Path,
    output_directory: Path,
) -> FinalResultsOutputs:
    """Synthesize existing analysis outputs into final research artifacts."""
    normalized_summary = _read_json(
        normalized_directory / "normalized_summary.json"
    )
    association = _read_json(
        normalized_directory / "normalized_association.json"
    )
    global_moran = _read_json(
        normalized_directory / "global_morans_i.json"
    )
    local_moran = _read_json(
        normalized_directory / "local_morans_i.json"
    )
    model_report = _read_json(
        multivariable_directory / "model_report.json"
    )

    _validate_cross_artifact_window(
        normalized_summary,
        association,
        global_moran,
        local_moran,
        model_report,
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = FinalResultsOutputs(
        descriptive_table_csv=output_directory / "table_1_descriptive.csv",
        spatial_table_csv=output_directory / "table_2_spatial.csv",
        model_table_csv=output_directory / "table_3_models.csv",
        diagnostics_table_csv=output_directory / "table_4_diagnostics.csv",
        findings_json=output_directory / "findings.json",
        findings_markdown=output_directory / "findings.md",
        figure_pressure_association=(
            output_directory / "figure_1_pressure_association.png"
        ),
        figure_pressure_coefficients=(
            output_directory / "figure_2_pressure_coefficients.png"
        ),
        figure_primary_residuals=(
            output_directory / "figure_3_primary_residuals.png"
        ),
    )

    for path in outputs.paths():
        if path.exists():
            raise FileExistsError(path)

    descriptive_rows = _descriptive_rows(normalized_summary, association)
    spatial_rows = _spatial_rows(global_moran, local_moran)
    model_rows = _model_rows(model_report)
    diagnostic_rows = _diagnostic_rows(model_report)
    findings = _findings_document(
        normalized_summary,
        association,
        global_moran,
        local_moran,
        model_report,
    )

    written: list[Path] = []
    try:
        _write_rows(
            outputs.descriptive_table_csv,
            ("section", "metric", "value"),
            descriptive_rows,
        )
        written.append(outputs.descriptive_table_csv)

        _write_rows(
            outputs.spatial_table_csv,
            (
                "metric",
                "global_morans_i",
                "global_expected_i",
                "global_permutation_p",
                "local_significant_fdr_count",
                "local_hh",
                "local_ll",
                "local_hl",
                "local_lh",
            ),
            spatial_rows,
        )
        written.append(outputs.spatial_table_csv)

        _write_rows(
            outputs.model_table_csv,
            (
                "model",
                "model_label",
                "pressure_estimate",
                "pressure_hc3_se",
                "pressure_ci_95_low",
                "pressure_ci_95_high",
                "pressure_p_value",
                "n_observations",
                "adjusted_r_squared",
            ),
            model_rows,
        )
        written.append(outputs.model_table_csv)

        _write_rows(
            outputs.diagnostics_table_csv,
            (
                "model",
                "max_vif",
                "condition_number",
                "breusch_pagan_p_value",
                "residual_morans_i",
                "residual_moran_p_value",
            ),
            diagnostic_rows,
        )
        written.append(outputs.diagnostics_table_csv)

        _write_json(outputs.findings_json, findings)
        written.append(outputs.findings_json)

        outputs.findings_markdown.write_text(
            _findings_markdown(findings),
            encoding="utf-8",
        )
        written.append(outputs.findings_markdown)

        _copy_figure(
            normalized_directory / "normalized_association.png",
            outputs.figure_pressure_association,
        )
        written.append(outputs.figure_pressure_association)

        _copy_figure(
            multivariable_directory / "pressure_coefficients.png",
            outputs.figure_pressure_coefficients,
        )
        written.append(outputs.figure_pressure_coefficients)

        _copy_figure(
            multivariable_directory / "primary_residuals.png",
            outputs.figure_primary_residuals,
        )
        written.append(outputs.figure_primary_residuals)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return outputs


def _descriptive_rows(
    summary: Mapping[str, object],
    association: Mapping[str, object],
) -> list[dict[str, object]]:
    """Build compact publication-style descriptive rows."""
    comparison = _mapping(summary, "comparison_window")
    coverage = _mapping(summary, "coverage")
    descriptive = _mapping(summary, "descriptive")
    assoc = _mapping(summary, "association")
    assoc_corr = _mapping(association, "correlations")

    return [
        {"section": "study", "metric": "baseline_year", "value": comparison["baseline_year"]},
        {"section": "study", "metric": "latest_common_year", "value": comparison["latest_common_year"]},
        {"section": "coverage", "metric": "freguesia_count", "value": coverage["freguesia_count"]},
        {"section": "descriptive", "metric": "median_housing_change_pct", "value": descriptive["housing_change_pct_median"]},
        {"section": "descriptive", "metric": "median_rnal_pressure_change_per_1000", "value": descriptive["rnal_pressure_change_per_1000_median"]},
        {"section": "association", "metric": "pearson_r", "value": assoc_corr["pearson_r"]},
        {"section": "association", "metric": "spearman_rho", "value": assoc_corr["spearman_rho"]},
        {"section": "association", "metric": "complete_cases", "value": assoc["complete_cases"]},
    ]


def _spatial_rows(
    global_moran: Mapping[str, object],
    local_moran: Mapping[str, object],
) -> list[dict[str, object]]:
    """Combine global and local Moran diagnostics by metric."""
    global_results = _result_mapping(global_moran, "results", "metric")
    local_results = _result_mapping(local_moran, "results", "metric")

    if set(global_results) != set(local_results):
        raise FinalResultsError("global/local Moran metric sets do not match")

    rows: list[dict[str, object]] = []
    for metric in sorted(global_results):
        global_result = global_results[metric]
        local_result = local_results[metric]
        observations = _sequence(local_result, "observations")

        cluster_counts = {"HH": 0, "LL": 0, "HL": 0, "LH": 0}
        significant = 0
        for raw in observations:
            observation = _as_mapping(raw, f"{metric}.observation")
            if observation.get("significant_fdr") is True:
                significant += 1
            cluster = observation.get("cluster_class")
            if cluster in cluster_counts:
                cluster_counts[cast(str, cluster)] += 1

        rows.append(
            {
                "metric": metric,
                "global_morans_i": global_result.get("morans_i"),
                "global_expected_i": global_result.get("expected_i"),
                "global_permutation_p": global_result.get("permutation_p_two_sided"),
                "local_significant_fdr_count": significant,
                "local_hh": cluster_counts["HH"],
                "local_ll": cluster_counts["LL"],
                "local_hl": cluster_counts["HL"],
                "local_lh": cluster_counts["LH"],
            }
        )

    return rows


def _model_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    """Build one RNAL-pressure coefficient row per pre-specified model."""
    rows: list[dict[str, object]] = []

    for raw_model in _sequence(report, "models"):
        model = _as_mapping(raw_model, "model")
        coefficient = _find_coefficient(model, "rnal_pressure_change_per_1000")
        diagnostics = _mapping(model, "diagnostics")

        rows.append(
            {
                "model": model["name"],
                "model_label": model["label"],
                "pressure_estimate": coefficient["estimate"],
                "pressure_hc3_se": coefficient["hc3_se"],
                "pressure_ci_95_low": coefficient["ci_95_low"],
                "pressure_ci_95_high": coefficient["ci_95_high"],
                "pressure_p_value": coefficient["p_value"],
                "n_observations": diagnostics["n_observations"],
                "adjusted_r_squared": diagnostics["adjusted_r_squared"],
            }
        )

    return rows


def _diagnostic_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    """Build one model-diagnostic row per specification."""
    rows: list[dict[str, object]] = []

    for raw_model in _sequence(report, "models"):
        model = _as_mapping(raw_model, "model")
        diagnostics = _mapping(model, "diagnostics")
        residual_moran = _mapping(diagnostics, "residual_moran")

        rows.append(
            {
                "model": model["name"],
                "max_vif": diagnostics.get("max_vif"),
                "condition_number": diagnostics["condition_number"],
                "breusch_pagan_p_value": diagnostics["breusch_pagan_p_value"],
                "residual_morans_i": residual_moran.get("morans_i"),
                "residual_moran_p_value": residual_moran.get("permutation_p_two_sided"),
            }
        )

    return rows


def _findings_document(
    summary: Mapping[str, object],
    association: Mapping[str, object],
    global_moran: Mapping[str, object],
    local_moran: Mapping[str, object],
    report: Mapping[str, object],
) -> dict[str, object]:
    """Build concise findings grounded only in generated analysis outputs."""
    comparison = _mapping(summary, "comparison_window")
    descriptive = _mapping(summary, "descriptive")
    assoc_corr = _mapping(association, "correlations")
    primary_name = _string(report.get("primary_model"), "primary_model")

    models = {
        _string(model["name"], "model.name"): model
        for model in (
            _as_mapping(raw, "model")
            for raw in _sequence(report, "models")
        )
    }
    if primary_name not in models:
        raise FinalResultsError(f"primary model {primary_name!r} is absent from report")

    primary = models[primary_name]
    pressure = _find_coefficient(primary, "rnal_pressure_change_per_1000")
    primary_diagnostics = _mapping(primary, "diagnostics")
    residual_moran = _mapping(primary_diagnostics, "residual_moran")
    leave_one_out = _mapping(report, "leave_one_freguesia_out")

    global_results = _result_mapping(global_moran, "results", "metric")
    local_results = _result_mapping(local_moran, "results", "metric")

    spatial_summary: dict[str, object] = {}
    for metric in sorted(global_results):
        local_observations = _sequence(local_results[metric], "observations")
        significant = sum(
            _as_mapping(item, "observation").get("significant_fdr") is True
            for item in local_observations
        )
        spatial_summary[metric] = {
            "global_morans_i": global_results[metric].get("morans_i"),
            "global_permutation_p": global_results[metric].get("permutation_p_two_sided"),
            "local_fdr_significant_count": significant,
        }

    return {
        "schema_version": 1,
        "study_window": {
            "baseline_year": comparison["baseline_year"],
            "latest_common_year": comparison["latest_common_year"],
        },
        "descriptive": {
            "median_housing_change_pct": descriptive["housing_change_pct_median"],
            "median_rnal_pressure_change_per_1000": descriptive[
                "rnal_pressure_change_per_1000_median"
            ],
            "pearson_r": assoc_corr["pearson_r"],
            "spearman_rho": assoc_corr["spearman_rho"],
        },
        "spatial": spatial_summary,
        "primary_model": {
            "name": primary_name,
            "label": primary["label"],
            "pressure_estimate": pressure["estimate"],
            "pressure_hc3_se": pressure["hc3_se"],
            "pressure_ci_95_low": pressure["ci_95_low"],
            "pressure_ci_95_high": pressure["ci_95_high"],
            "pressure_p_value": pressure["p_value"],
            "adjusted_r_squared": primary_diagnostics["adjusted_r_squared"],
            "max_vif": primary_diagnostics.get("max_vif"),
            "condition_number": primary_diagnostics["condition_number"],
            "breusch_pagan_p_value": primary_diagnostics["breusch_pagan_p_value"],
            "residual_morans_i": residual_moran.get("morans_i"),
            "residual_moran_p_value": residual_moran.get("permutation_p_two_sided"),
        },
        "leave_one_freguesia_out": {
            "same_sign_fraction": leave_one_out.get("same_sign_fraction"),
            "coefficient_min": leave_one_out.get("coefficient_min"),
            "coefficient_median": leave_one_out.get("coefficient_median"),
            "coefficient_max": leave_one_out.get("coefficient_max"),
            "failed_refits": leave_one_out["failed_refits"],
        },
        "interpretation_contract": (
            "All reported relationships are descriptive associations over a "
            "common baseline-to-latest window. Static Censos-2021 context is used "
            "for adjustment. No causal effect is identified."
        ),
    }


def _findings_markdown(findings: Mapping[str, object]) -> str:
    """Render concise, publication-style findings from the synthesis document."""
    window = _mapping(findings, "study_window")
    descriptive = _mapping(findings, "descriptive")
    spatial = _mapping(findings, "spatial")
    primary = _mapping(findings, "primary_model")
    loo = _mapping(findings, "leave_one_freguesia_out")

    lines = [
        "# Final research findings",
        "",
        f"The common comparison window runs from {window['baseline_year']} to {window['latest_common_year']}.",
        "",
        "## Descriptive pattern",
        "",
        (
            "Across the canonical Lisboa freguesias, the median cumulative "
            f"housing-value change was {_fmt(descriptive['median_housing_change_pct'])}% "
            "and the median change in active RNAL pressure was "
            f"{_fmt(descriptive['median_rnal_pressure_change_per_1000'])} "
            "registrations per 1,000 Censos-2021 residents."
        ),
        (
            "The bivariate association between housing change and RNAL-pressure "
            f"change was Pearson r = {_fmt(descriptive['pearson_r'])} and "
            f"Spearman rho = {_fmt(descriptive['spearman_rho'])}."
        ),
        "",
        "## Spatial pattern",
        "",
    ]

    for metric in sorted(spatial):
        values = _as_mapping(spatial[metric], f"spatial.{metric}")
        lines.append(
            f"- {metric}: Global Moran's I = {_fmt(values['global_morans_i'])}, "
            f"permutation p = {_fmt(values['global_permutation_p'])}; "
            f"{values['local_fdr_significant_count']} local associations remained "
            "significant after FDR correction."
        )

    lines.extend(
        [
            "",
            "## Adjusted descriptive model",
            "",
            (
                f"The primary model ({primary['label']}) estimated a "
                f"{_fmt(primary['pressure_estimate'])}-percentage-point difference "
                "in cumulative housing change for a one-standard-deviation larger "
                "increase in RNAL pressure, conditional on the pre-specified "
                "baseline and Census context variables."
            ),
            (
                "The HC3 robust 95% confidence interval was "
                f"[{_fmt(primary['pressure_ci_95_low'])}, "
                f"{_fmt(primary['pressure_ci_95_high'])}] with p = "
                f"{_fmt(primary['pressure_p_value'])}."
            ),
            (
                f"Adjusted R-squared was {_fmt(primary['adjusted_r_squared'])}; "
                f"maximum VIF was {_fmt(primary['max_vif'])}; "
                f"the Breusch-Pagan p-value was {_fmt(primary['breusch_pagan_p_value'])}; "
                f"and residual Moran's I was {_fmt(primary['residual_morans_i'])} "
                f"(permutation p = {_fmt(primary['residual_moran_p_value'])})."
            ),
            "",
            "## Sensitivity",
            "",
            (
                "In the leave-one-freguesia-out analysis, the RNAL-pressure "
                f"coefficient retained the full-sample sign in "
                f"{_fmt_fraction(loo['same_sign_fraction'])} of successful refits."
            ),
            (
                "The case-deletion coefficient range was "
                f"[{_fmt(loo['coefficient_min'])}, {_fmt(loo['coefficient_max'])}], "
                f"with median {_fmt(loo['coefficient_median'])}; "
                f"{loo['failed_refits']} refits failed."
            ),
            "",
            "## Interpretation",
            "",
            cast(str, findings["interpretation_contract"]),
            "",
        ]
    )

    return "\n".join(lines)


def _validate_cross_artifact_window(
    summary: Mapping[str, object],
    association: Mapping[str, object],
    global_moran: Mapping[str, object],
    local_moran: Mapping[str, object],
    report: Mapping[str, object],
) -> None:
    """Require all synthesized artifacts to describe the same study window."""
    summary_window = _mapping(summary, "comparison_window")
    association_window = _mapping(association, "comparison_window")
    report_window = _mapping(report, "comparison_window")

    baseline = summary_window["baseline_year"]
    latest = summary_window["latest_common_year"]

    if association_window["baseline_year"] != baseline:
        raise FinalResultsError("association baseline year mismatch")
    if association_window["latest_common_year"] != latest:
        raise FinalResultsError("association latest year mismatch")
    if report_window["baseline_year"] != baseline:
        raise FinalResultsError("model baseline year mismatch")
    if report_window["latest_year"] != latest:
        raise FinalResultsError("model latest year mismatch")

    for document, label in (
        (global_moran, "global Moran"),
        (local_moran, "local Moran"),
    ):
        for raw in _sequence(document, "results"):
            result = _as_mapping(raw, label)
            if result["baseline_year"] != baseline:
                raise FinalResultsError(f"{label} baseline year mismatch")
            if result["latest_year"] != latest:
                raise FinalResultsError(f"{label} latest year mismatch")


def _copy_figure(source: Path, target: Path) -> None:
    """Copy one generated figure without modifying its bytes."""
    if not source.exists():
        raise FinalResultsError(f"required figure is missing: {source}")
    shutil.copyfile(source, target)


def _write_rows(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, object]],
) -> None:
    """Write a stable CSV table."""
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, document: Mapping[str, object]) -> None:
    """Write deterministic JSON."""
    payload = json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> Mapping[str, object]:
    """Load one required JSON artifact."""
    if not path.exists():
        raise FinalResultsError(f"required artifact is missing: {path}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FinalResultsError(f"invalid JSON: {path}") from exc
    return _as_mapping(raw, str(path))


def _find_coefficient(
    model: Mapping[str, object],
    term: str,
) -> Mapping[str, object]:
    """Find one named coefficient in a model report entry."""
    for raw in _sequence(model, "coefficients"):
        coefficient = _as_mapping(raw, "coefficient")
        if coefficient.get("term") == term:
            return coefficient
    raise FinalResultsError(
        f"model {model.get('name')!r} is missing coefficient {term!r}"
    )


def _result_mapping(
    document: Mapping[str, object],
    field: str,
    key: str,
) -> dict[str, Mapping[str, object]]:
    """Index a sequence of result mappings by one required string field."""
    output: dict[str, Mapping[str, object]] = {}
    for raw in _sequence(document, field):
        item = _as_mapping(raw, field)
        value = _string(item.get(key), f"{field}.{key}")
        if value in output:
            raise FinalResultsError(f"duplicate {field} key: {value}")
        output[value] = item
    return output


def _mapping(
    raw: Mapping[str, object],
    field: str,
) -> Mapping[str, object]:
    """Return a required nested mapping."""
    return _as_mapping(raw.get(field), field)


def _sequence(
    raw: Mapping[str, object],
    field: str,
) -> Sequence[object]:
    """Return a required list field."""
    value = raw.get(field)
    if not isinstance(value, list):
        raise FinalResultsError(f"{field} must be a list")
    return value


def _as_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required mapping."""
    if not isinstance(value, Mapping):
        raise FinalResultsError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


def _string(value: object, context: str) -> str:
    """Return a required non-empty string."""
    if not isinstance(value, str) or not value:
        raise FinalResultsError(f"{context} must be a non-empty string")
    return value


def _fmt(value: object) -> str:
    """Format numeric values compactly for generated prose."""
    if value is None:
        return "NA"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return f"{float(value):.3f}"


def _fmt_fraction(value: object) -> str:
    """Format a fraction as a percentage when available."""
    if value is None:
        return "NA"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    return f"{100.0 * float(value):.1f}%"
