"""Pre-specified multivariable analysis for Lisbon housing change."""

from __future__ import annotations

import csv
import json
import math
import random
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import numpy as np
from numpy.typing import NDArray
from scipy import stats

from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    SpatialWeights,
    build_queen_weights,
)
from lisbon_spatial_dynamics.spatial.annual_maps import ReferenceFeature
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    TrajectoryMapFeature,
)

type FloatArray = NDArray[np.float64]

_OUTCOME = "housing_change_from_baseline_pct"
_PRIMARY_EXPOSURE = "rnal_pressure_change_per_1000"
_SUPPORTED_PREDICTORS: frozenset[str] = frozenset(
    {
        _PRIMARY_EXPOSURE,
        "log_baseline_housing_eur_m2",
        "log_population_density_per_km2",
        "census_rented_share_pct",
        "census_age_65_plus_pct",
        "census_vacant_or_secondary_family_share_pct",
        "census_pre1945_building_share_pct",
        "census_repair_needed_building_share_pct",
    }
)
_CONTEXT_SOURCE_FIELDS: tuple[str, ...] = (
    "population_reference_year",
    "population_resident",
    "population_density_per_km2",
    "census_rented_share_pct",
    "census_age_65_plus_pct",
    "census_vacant_or_secondary_family_share_pct",
    "census_pre1945_building_share_pct",
    "census_repair_needed_building_share_pct",
)


class MultivariableAnalysisError(ValueError):
    """Raised when the multivariable analysis cannot be built safely."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """One pre-specified regression model."""

    name: str
    label: str
    predictors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Validated multivariable-model configuration."""

    outcome: str
    primary_model: str
    standardize_predictors: bool
    models: tuple[ModelSpec, ...]


@dataclass(frozen=True, slots=True)
class ModelObservation:
    """One common-window freguesia observation for regression analysis."""

    freguesia_id: str
    freguesia_name: str
    baseline_year: int
    latest_year: int
    outcome: float | None
    values: Mapping[str, float | None]


@dataclass(frozen=True, slots=True)
class Standardization:
    """Mean and scale used for one predictor."""

    mean: float
    standard_deviation: float


@dataclass(frozen=True, slots=True)
class CoefficientResult:
    """One OLS coefficient with HC3 robust uncertainty."""

    term: str
    estimate: float
    hc3_se: float
    ci_95_low: float
    ci_95_high: float
    t_statistic: float
    p_value: float
    vif: float | None
    standardization_mean: float | None
    standardization_sd: float | None


@dataclass(frozen=True, slots=True)
class ResidualMoranResult:
    """Global Moran diagnostic for model residuals."""

    morans_i: float | None
    expected_i: float
    permutation_p_two_sided: float | None
    complete_cases: int
    edge_count: int
    islands: tuple[str, ...]
    permutations: int
    seed: int


@dataclass(frozen=True, slots=True)
class ModelDiagnostics:
    """Core regression and residual diagnostics."""

    n_observations: int
    n_parameters: int
    residual_degrees_of_freedom: int
    r_squared: float
    adjusted_r_squared: float
    rmse: float
    condition_number: float
    max_vif: float | None
    breusch_pagan_lm: float
    breusch_pagan_p_value: float
    residual_moran: ResidualMoranResult


@dataclass(frozen=True, slots=True)
class ResidualObservation:
    """One fitted/residual observation for audit and influence diagnostics."""

    freguesia_id: str
    freguesia_name: str
    observed: float
    fitted: float
    residual: float
    leverage: float
    cooks_distance: float


@dataclass(frozen=True, slots=True)
class ModelFit:
    """Complete fitted model result."""

    spec: ModelSpec
    coefficients: tuple[CoefficientResult, ...]
    diagnostics: ModelDiagnostics
    residuals: tuple[ResidualObservation, ...]
    excluded_freguesias: tuple[str, ...]
    standardization: Mapping[str, Standardization]


@dataclass(frozen=True, slots=True)
class LeaveOneOutRow:
    """Primary-exposure estimate after omitting one freguesia."""

    omitted_freguesia_id: str
    omitted_freguesia_name: str
    pressure_coefficient: float | None
    status: str


@dataclass(frozen=True, slots=True)
class LeaveOneOutSummary:
    """Summary of leave-one-freguesia-out pressure-coefficient stability."""

    full_sample_pressure_coefficient: float
    successful_refits: int
    failed_refits: int
    same_sign_fraction: float | None
    coefficient_min: float | None
    coefficient_median: float | None
    coefficient_max: float | None
    rows: tuple[LeaveOneOutRow, ...]


@dataclass(frozen=True, slots=True)
class MultivariableAnalysisResult:
    """All fitted pre-specified models and primary sensitivity diagnostics."""

    baseline_year: int
    latest_year: int
    outcome: str
    primary_model: str
    fits: tuple[ModelFit, ...]
    leave_one_out: LeaveOneOutSummary
    observations: tuple[ModelObservation, ...]


@dataclass(frozen=True, slots=True)
class MultivariableOutputs:
    """Artifacts produced by the multivariable-analysis milestone."""

    model_input_csv: Path
    coefficients_csv: Path
    residuals_csv: Path
    leave_one_out_csv: Path
    report_json: Path
    pressure_coefficients_plot: Path
    primary_residuals_plot: Path

    def paths(self) -> tuple[Path, ...]:
        """Return output paths in deterministic order."""
        return (
            self.model_input_csv,
            self.coefficients_csv,
            self.residuals_csv,
            self.leave_one_out_csv,
            self.report_json,
            self.pressure_coefficients_plot,
            self.primary_residuals_plot,
        )


def load_model_config(path: Path) -> ModelConfig:
    """Load and validate the pre-specified model configuration."""
    with path.open("rb") as stream:
        raw = tomllib.load(stream)

    analysis = _require_mapping(raw.get("analysis"), "analysis")
    models_raw = _require_mapping(raw.get("models"), "models")

    outcome = _require_string(analysis, "outcome", "analysis")
    if outcome != _OUTCOME:
        raise MultivariableAnalysisError(f"unsupported outcome: {outcome!r}; expected {_OUTCOME!r}")

    primary_model = _require_string(
        analysis,
        "primary_model",
        "analysis",
    )
    standardize = analysis.get("standardize_predictors")
    if not isinstance(standardize, bool):
        raise MultivariableAnalysisError("analysis.standardize_predictors must be boolean")
    if not standardize:
        raise MultivariableAnalysisError(
            "predictor standardization must remain enabled for this analysis"
        )

    specs: list[ModelSpec] = []
    for name, value in models_raw.items():
        if not isinstance(name, str):
            raise MultivariableAnalysisError("model names must be strings")
        table = _require_mapping(value, f"models.{name}")
        label = _require_string(table, "label", f"models.{name}")
        predictors_raw = table.get("predictors")
        if not isinstance(predictors_raw, list) or not predictors_raw:
            raise MultivariableAnalysisError(f"models.{name}.predictors must be a non-empty list")
        if not all(isinstance(item, str) for item in predictors_raw):
            raise MultivariableAnalysisError(f"models.{name}.predictors must contain only strings")
        predictors = tuple(predictors_raw)
        if len(set(predictors)) != len(predictors):
            raise MultivariableAnalysisError(f"models.{name} contains duplicate predictors")
        unsupported = set(predictors) - _SUPPORTED_PREDICTORS
        if unsupported:
            raise MultivariableAnalysisError(
                f"models.{name} contains unsupported predictors: " + ", ".join(sorted(unsupported))
            )
        if _PRIMARY_EXPOSURE not in predictors:
            raise MultivariableAnalysisError(f"models.{name} must include {_PRIMARY_EXPOSURE}")
        specs.append(ModelSpec(name=name, label=label, predictors=predictors))

    if primary_model not in {spec.name for spec in specs}:
        raise MultivariableAnalysisError(f"primary model {primary_model!r} is not defined")

    return ModelConfig(
        outcome=outcome,
        primary_model=primary_model,
        standardize_predictors=standardize,
        models=tuple(specs),
    )


def load_model_observations(path: Path) -> tuple[ModelObservation, ...]:
    """Load annual context rows and derive one common-window model row per freguesia."""
    required = {
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
    }

    grouped: dict[str, dict[int, dict[str, str]]] = {}

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise MultivariableAnalysisError(
                "annual context CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for row_index, raw in enumerate(reader, start=2):
            freguesia_id = _required_csv(
                raw.get("freguesia_id"),
                f"row {row_index}.freguesia_id",
            )
            year = _required_int_csv(
                raw.get("year"),
                f"row {row_index}.year",
            )
            years = grouped.setdefault(freguesia_id, {})
            if year in years:
                raise MultivariableAnalysisError(f"duplicate annual key: ({year}, {freguesia_id})")
            years[year] = dict(raw)

    if not grouped:
        raise MultivariableAnalysisError("annual context CSV cannot be empty")

    baseline_years = {
        _required_int_csv(row.get("baseline_year"), "baseline_year")
        for years in grouped.values()
        for row in years.values()
    }
    if len(baseline_years) != 1:
        raise MultivariableAnalysisError("freguesias do not share one baseline year")
    baseline_year = next(iter(baseline_years))

    common_years = set.intersection(*(set(years) for years in grouped.values()))
    if baseline_year not in common_years:
        raise MultivariableAnalysisError(
            "common annual coverage does not include the baseline year"
        )
    latest_year = max(common_years)

    output: list[ModelObservation] = []

    for freguesia_id in sorted(grouped):
        years = grouped[freguesia_id]
        _validate_static_context(freguesia_id, years)

        baseline = years[baseline_year]
        latest = years[latest_year]
        name = _required_csv(
            latest.get("freguesia_name"),
            f"{freguesia_id}.freguesia_name",
        )

        baseline_housing = _optional_float_csv(
            baseline.get("housing_value_eur_m2"),
            f"{freguesia_id}.baseline_housing",
        )
        density = _positive_float_csv(
            latest.get("population_density_per_km2"),
            f"{freguesia_id}.population_density_per_km2",
        )

        values: dict[str, float | None] = {
            _PRIMARY_EXPOSURE: _required_float_csv(
                latest.get("rnal_active_registrations_per_1000_change_from_baseline"),
                f"{freguesia_id}.rnal_pressure_change",
            ),
            "log_baseline_housing_eur_m2": (
                None
                if baseline_housing is None or baseline_housing <= 0
                else math.log(baseline_housing)
            ),
            "log_population_density_per_km2": math.log(density),
            "census_rented_share_pct": _required_float_csv(
                latest.get("census_rented_share_pct"),
                f"{freguesia_id}.census_rented_share_pct",
            ),
            "census_age_65_plus_pct": _required_float_csv(
                latest.get("census_age_65_plus_pct"),
                f"{freguesia_id}.census_age_65_plus_pct",
            ),
            "census_vacant_or_secondary_family_share_pct": _required_float_csv(
                latest.get("census_vacant_or_secondary_family_share_pct"),
                f"{freguesia_id}.census_vacant_or_secondary_family_share_pct",
            ),
            "census_pre1945_building_share_pct": _required_float_csv(
                latest.get("census_pre1945_building_share_pct"),
                f"{freguesia_id}.census_pre1945_building_share_pct",
            ),
            "census_repair_needed_building_share_pct": _required_float_csv(
                latest.get("census_repair_needed_building_share_pct"),
                f"{freguesia_id}.census_repair_needed_building_share_pct",
            ),
        }

        output.append(
            ModelObservation(
                freguesia_id=freguesia_id,
                freguesia_name=name,
                baseline_year=baseline_year,
                latest_year=latest_year,
                outcome=_optional_float_csv(
                    latest.get("housing_change_from_baseline_pct"),
                    f"{freguesia_id}.housing_change_from_baseline_pct",
                ),
                values=values,
            )
        )

    return tuple(output)


def fit_multivariable_models(
    observations: Sequence[ModelObservation],
    config: ModelConfig,
    reference: Sequence[ReferenceFeature],
    *,
    permutations: int = 999,
    seed: int = 42,
) -> MultivariableAnalysisResult:
    """Fit every pre-specified model and primary leave-one-out sensitivity analysis."""
    if not observations:
        raise MultivariableAnalysisError("model observations cannot be empty")
    if permutations < 0:
        raise ValueError("permutations must be non-negative")

    baseline_years = {row.baseline_year for row in observations}
    latest_years = {row.latest_year for row in observations}
    if len(baseline_years) != 1 or len(latest_years) != 1:
        raise MultivariableAnalysisError("model observations must share one comparison window")

    weights = _build_reference_weights(observations, reference)
    fits: list[ModelFit] = []

    for model_index, spec in enumerate(config.models):
        fits.append(
            _fit_spec(
                observations,
                spec,
                weights,
                permutations=permutations,
                seed=seed + model_index * 10_000,
            )
        )

    primary_fit = next(fit for fit in fits if fit.spec.name == config.primary_model)
    primary_spec = next(spec for spec in config.models if spec.name == config.primary_model)
    leave_one_out = _leave_one_out(
        observations,
        primary_spec,
        primary_fit,
    )

    return MultivariableAnalysisResult(
        baseline_year=next(iter(baseline_years)),
        latest_year=next(iter(latest_years)),
        outcome=config.outcome,
        primary_model=config.primary_model,
        fits=tuple(fits),
        leave_one_out=leave_one_out,
        observations=tuple(observations),
    )


def build_multivariable_analysis(
    annual_context_csv: Path,
    reference_geojson: Path,
    config_path: Path,
    output_directory: Path,
    *,
    permutations: int = 999,
    seed: int = 42,
    expected_freguesias: int = 24,
) -> MultivariableOutputs:
    """Load inputs, fit models, and write the complete modelling milestone."""
    from lisbon_spatial_dynamics.spatial.annual_maps import load_reference_geojson

    observations = load_model_observations(annual_context_csv)
    config = load_model_config(config_path)
    reference = load_reference_geojson(reference_geojson, expected_count=expected_freguesias)
    result = fit_multivariable_models(
        observations,
        config,
        reference,
        permutations=permutations,
        seed=seed,
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = MultivariableOutputs(
        model_input_csv=output_directory / "model_input.csv",
        coefficients_csv=output_directory / "coefficients.csv",
        residuals_csv=output_directory / "residuals.csv",
        leave_one_out_csv=output_directory / "leave_one_out.csv",
        report_json=output_directory / "model_report.json",
        pressure_coefficients_plot=output_directory / "pressure_coefficients.png",
        primary_residuals_plot=output_directory / "primary_residuals.png",
    )

    for path in outputs.paths():
        if path.exists():
            raise FileExistsError(path)

    written: list[Path] = []
    try:
        _write_model_input(result, outputs.model_input_csv)
        written.append(outputs.model_input_csv)
        _write_coefficients(result, outputs.coefficients_csv)
        written.append(outputs.coefficients_csv)
        _write_residuals(result, outputs.residuals_csv)
        written.append(outputs.residuals_csv)
        _write_leave_one_out(result, outputs.leave_one_out_csv)
        written.append(outputs.leave_one_out_csv)
        _write_report(result, outputs.report_json)
        written.append(outputs.report_json)
        _write_pressure_coefficients_plot(
            result,
            outputs.pressure_coefficients_plot,
        )
        written.append(outputs.pressure_coefficients_plot)
        _write_primary_residuals_plot(
            result,
            outputs.primary_residuals_plot,
        )
        written.append(outputs.primary_residuals_plot)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return outputs


def _fit_spec(
    observations: Sequence[ModelObservation],
    spec: ModelSpec,
    weights: SpatialWeights,
    *,
    permutations: int,
    seed: int,
    fixed_standardization: Mapping[str, Standardization] | None = None,
) -> ModelFit:
    """Fit one model on complete cases using HC3 robust covariance."""
    complete = [
        row
        for row in observations
        if row.outcome is not None
        and all(row.values[predictor] is not None for predictor in spec.predictors)
    ]
    complete_ids = {row.freguesia_id for row in complete}
    excluded = tuple(
        row.freguesia_id for row in observations if row.freguesia_id not in complete_ids
    )

    n = len(complete)
    p = len(spec.predictors)
    if n <= p + 2:
        raise MultivariableAnalysisError(
            f"model {spec.name} has too few complete observations: n={n}, p={p}"
        )

    raw_predictors = np.asarray(
        [[cast_value(row.values[predictor]) for predictor in spec.predictors] for row in complete],
        dtype=np.float64,
    )
    outcome = np.asarray(
        [cast_value(row.outcome) for row in complete],
        dtype=np.float64,
    )

    standardization = (
        dict(fixed_standardization)
        if fixed_standardization is not None
        else _standardization(raw_predictors, spec.predictors)
    )
    standardized = _apply_standardization(
        raw_predictors,
        spec.predictors,
        standardization,
    )
    design = np.column_stack((np.ones(n, dtype=np.float64), standardized))

    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise MultivariableAnalysisError(f"model {spec.name} design matrix is rank deficient")

    beta, _, _, _ = np.linalg.lstsq(design, outcome, rcond=None)
    fitted = design @ beta
    residual = outcome - fitted
    k = design.shape[1]
    df_residual = n - k

    xtx_inv = np.linalg.inv(design.T @ design)
    leverage = np.einsum("ij,jk,ik->i", design, xtx_inv, design)
    if np.any(1.0 - leverage <= 1e-10):
        raise MultivariableAnalysisError(
            f"model {spec.name} contains leverage values too close to one"
        )

    hc3_weights = (residual / (1.0 - leverage)) ** 2
    meat = design.T @ (design * hc3_weights[:, None])
    covariance = xtx_inv @ meat @ xtx_inv
    robust_se = np.sqrt(np.maximum(np.diag(covariance), 0.0))

    t_critical = float(stats.t.ppf(0.975, df_residual))
    terms = ("intercept", *spec.predictors)
    vifs = _vif_map(standardized, spec.predictors)
    coefficients: list[CoefficientResult] = []

    for index, term in enumerate(terms):
        estimate = float(beta[index])
        se = float(robust_se[index])
        t_stat = 0.0 if math.isclose(se, 0.0) else estimate / se
        p_value = (
            1.0
            if math.isclose(se, 0.0) and math.isclose(estimate, 0.0)
            else 0.0
            if math.isclose(se, 0.0)
            else float(2.0 * stats.t.sf(abs(t_stat), df_residual))
        )
        scaling = standardization.get(term)
        coefficients.append(
            CoefficientResult(
                term=term,
                estimate=estimate,
                hc3_se=se,
                ci_95_low=estimate - t_critical * se,
                ci_95_high=estimate + t_critical * se,
                t_statistic=t_stat,
                p_value=p_value,
                vif=None if term == "intercept" else vifs[term],
                standardization_mean=(None if scaling is None else scaling.mean),
                standardization_sd=(None if scaling is None else scaling.standard_deviation),
            )
        )

    rss = float(residual @ residual)
    centered_outcome = outcome - float(np.mean(outcome))
    tss = float(centered_outcome @ centered_outcome)
    r_squared = 1.0 if math.isclose(tss, 0.0) else 1.0 - rss / tss
    adjusted_r_squared = 1.0 - (1.0 - r_squared) * (n - 1) / df_residual
    rmse = math.sqrt(rss / n)
    condition_number = float(np.linalg.cond(design))
    if not math.isfinite(condition_number):
        raise MultivariableAnalysisError(f"model {spec.name} has a non-finite condition number")
    finite_vifs = [value for value in vifs.values() if value is not None]
    max_vif = None if len(finite_vifs) != len(vifs) else max(finite_vifs)

    bp_lm, bp_p = _breusch_pagan(residual, design)
    residual_moran = _residual_moran(
        complete,
        residual,
        weights,
        permutations=permutations,
        seed=seed,
    )

    mse_classic = rss / df_residual
    cooks = (
        np.zeros_like(residual)
        if math.isclose(mse_classic, 0.0)
        else ((residual**2 / (k * mse_classic)) * leverage / ((1.0 - leverage) ** 2))
    )
    residual_rows = tuple(
        ResidualObservation(
            freguesia_id=row.freguesia_id,
            freguesia_name=row.freguesia_name,
            observed=float(outcome[index]),
            fitted=float(fitted[index]),
            residual=float(residual[index]),
            leverage=float(leverage[index]),
            cooks_distance=float(cooks[index]),
        )
        for index, row in enumerate(complete)
    )

    return ModelFit(
        spec=spec,
        coefficients=tuple(coefficients),
        diagnostics=ModelDiagnostics(
            n_observations=n,
            n_parameters=k,
            residual_degrees_of_freedom=df_residual,
            r_squared=r_squared,
            adjusted_r_squared=adjusted_r_squared,
            rmse=rmse,
            condition_number=condition_number,
            max_vif=max_vif,
            breusch_pagan_lm=bp_lm,
            breusch_pagan_p_value=bp_p,
            residual_moran=residual_moran,
        ),
        residuals=residual_rows,
        excluded_freguesias=excluded,
        standardization=standardization,
    )


def _standardization(
    raw: FloatArray,
    predictors: Sequence[str],
) -> dict[str, Standardization]:
    """Calculate deterministic population-standardization parameters."""
    means = np.mean(raw, axis=0)
    standard_deviations = np.std(raw, axis=0, ddof=0)

    mapping: dict[str, Standardization] = {}
    for index, predictor in enumerate(predictors):
        sd = float(standard_deviations[index])
        if math.isclose(sd, 0.0):
            raise MultivariableAnalysisError(
                f"predictor {predictor} is constant in the model sample"
            )
        mapping[predictor] = Standardization(
            mean=float(means[index]),
            standard_deviation=sd,
        )
    return mapping


def _apply_standardization(
    raw: FloatArray,
    predictors: Sequence[str],
    standardization: Mapping[str, Standardization],
) -> FloatArray:
    """Apply named standardization parameters to a predictor matrix."""
    result = np.empty_like(raw, dtype=np.float64)
    for index, predictor in enumerate(predictors):
        scaling = standardization[predictor]
        result[:, index] = (raw[:, index] - scaling.mean) / scaling.standard_deviation
    return result


def _vif_map(
    standardized: FloatArray,
    predictors: Sequence[str],
) -> dict[str, float | None]:
    """Calculate variance-inflation factors for standardized predictors."""
    p = standardized.shape[1]
    if p == 1:
        return {predictors[0]: 1.0}

    output: dict[str, float | None] = {}
    for target_index, predictor in enumerate(predictors):
        target = standardized[:, target_index]
        others = np.delete(standardized, target_index, axis=1)
        design = np.column_stack((np.ones(others.shape[0], dtype=np.float64), others))
        beta, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
        residual = target - design @ beta
        rss = float(residual @ residual)
        centered = target - float(np.mean(target))
        tss = float(centered @ centered)
        r_squared = 1.0 if math.isclose(tss, 0.0) else 1.0 - rss / tss
        denominator = 1.0 - r_squared
        output[predictor] = None if denominator <= 1e-12 else 1.0 / denominator
    return output


def _breusch_pagan(
    residual: FloatArray,
    design: FloatArray,
) -> tuple[float, float]:
    """Calculate the Breusch-Pagan LM diagnostic using squared residuals."""
    squared = residual**2
    beta, _, _, _ = np.linalg.lstsq(design, squared, rcond=None)
    fitted = design @ beta
    centered = squared - float(np.mean(squared))
    tss = float(centered @ centered)
    if math.isclose(tss, 0.0):
        return 0.0, 1.0
    residual_aux = squared - fitted
    rss = float(residual_aux @ residual_aux)
    r_squared = max(0.0, min(1.0, 1.0 - rss / tss))
    lm = len(residual) * r_squared
    df = design.shape[1] - 1
    p_value = float(stats.chi2.sf(lm, df))
    return lm, p_value


def _build_reference_weights(
    observations: Sequence[ModelObservation],
    reference: Sequence[ReferenceFeature],
) -> SpatialWeights:
    """Build queen weights after exact canonical-key and name validation."""
    observation_by_id = {row.freguesia_id: row for row in observations}
    reference_by_id = {feature.freguesia_id: feature for feature in reference}
    if len(observation_by_id) != len(observations):
        raise MultivariableAnalysisError("duplicate model freguesia IDs")
    if set(observation_by_id) != set(reference_by_id):
        missing = sorted(set(observation_by_id) - set(reference_by_id))
        extra = sorted(set(reference_by_id) - set(observation_by_id))
        raise MultivariableAnalysisError(
            f"model/reference key mismatch; missing_geometry={missing}, geometry_only={extra}"
        )

    features: list[TrajectoryMapFeature] = []
    for freguesia_id in sorted(reference_by_id):
        observation = observation_by_id[freguesia_id]
        feature = reference_by_id[freguesia_id]
        if observation.freguesia_name != feature.name:
            raise MultivariableAnalysisError(
                f"{freguesia_id} name mismatch: {observation.freguesia_name!r} != {feature.name!r}"
            )
        features.append(
            TrajectoryMapFeature(
                freguesia_id=freguesia_id,
                name=feature.name,
                housing_change_pct=0.0,
                rnal_active_change_pct=0.0,
                geometry=feature.geometry,
            )
        )

    first = observations[0]
    data = TrajectoryMapData(
        baseline_year=first.baseline_year,
        latest_year=first.latest_year,
        features=tuple(features),
    )
    return build_queen_weights(data)


def _residual_moran(
    complete: Sequence[ModelObservation],
    residual: FloatArray,
    weights: SpatialWeights,
    *,
    permutations: int,
    seed: int,
) -> ResidualMoranResult:
    """Calculate Global Moran's I for model residuals."""
    ids = [row.freguesia_id for row in complete]
    residual_by_id = {
        freguesia_id: float(value) for freguesia_id, value in zip(ids, residual, strict=True)
    }
    induced = {
        freguesia_id: tuple(
            neighbor for neighbor in weights.neighbors[freguesia_id] if neighbor in residual_by_id
        )
        for freguesia_id in ids
    }
    islands = tuple(
        sorted(freguesia_id for freguesia_id, neighbors in induced.items() if not neighbors)
    )
    values = [residual_by_id[freguesia_id] for freguesia_id in ids]
    observed = _morans_i(values, ids, induced)
    expected = -1.0 / (len(values) - 1)

    p_value: float | None
    if observed is None or permutations == 0:
        p_value = None
    else:
        rng = random.Random(seed)
        extreme = 0
        observed_distance = abs(observed - expected)
        permuted = list(values)
        for _ in range(permutations):
            rng.shuffle(permuted)
            simulated = _morans_i(permuted, ids, induced)
            if simulated is not None and (abs(simulated - expected) >= observed_distance - 1e-15):
                extreme += 1
        p_value = (extreme + 1) / (permutations + 1)

    return ResidualMoranResult(
        morans_i=observed,
        expected_i=expected,
        permutation_p_two_sided=p_value,
        complete_cases=len(values),
        edge_count=sum(len(neighbors) for neighbors in induced.values()) // 2,
        islands=islands,
        permutations=permutations,
        seed=seed,
    )


def _morans_i(
    values: Sequence[float],
    ids: Sequence[str],
    neighbors: Mapping[str, Sequence[str]],
) -> float | None:
    """Return row-standardized Moran's I for arbitrary numeric values."""
    mean_value = float(np.mean(np.asarray(values, dtype=np.float64)))
    centered = {
        freguesia_id: value - mean_value for freguesia_id, value in zip(ids, values, strict=True)
    }
    denominator = sum(value * value for value in centered.values())
    if math.isclose(denominator, 0.0):
        return None

    cross = 0.0
    weight_sum = 0.0
    for freguesia_id in ids:
        row_neighbors = neighbors[freguesia_id]
        if not row_neighbors:
            continue
        weight = 1.0 / len(row_neighbors)
        for neighbor in row_neighbors:
            cross += weight * centered[freguesia_id] * centered[neighbor]
            weight_sum += weight

    if math.isclose(weight_sum, 0.0):
        return None
    return len(values) / weight_sum * cross / denominator


def _leave_one_out(
    observations: Sequence[ModelObservation],
    spec: ModelSpec,
    full_fit: ModelFit,
) -> LeaveOneOutSummary:
    """Refit the primary model after omitting each complete-case freguesia."""
    full_pressure = _coefficient(full_fit, _PRIMARY_EXPOSURE).estimate
    full_complete_ids = {row.freguesia_id for row in full_fit.residuals}
    complete = [row for row in observations if row.freguesia_id in full_complete_ids]

    rows: list[LeaveOneOutRow] = []
    estimates: list[float] = []
    same_sign = 0

    dummy_weights = SpatialWeights(neighbors={row.freguesia_id: tuple() for row in complete})

    for omitted in complete:
        reduced = [row for row in complete if row.freguesia_id != omitted.freguesia_id]
        try:
            fit = _fit_spec(
                reduced,
                spec,
                dummy_weights,
                permutations=0,
                seed=0,
                fixed_standardization=full_fit.standardization,
            )
            estimate = _coefficient(fit, _PRIMARY_EXPOSURE).estimate
            estimates.append(estimate)
            if _same_sign(estimate, full_pressure):
                same_sign += 1
            rows.append(
                LeaveOneOutRow(
                    omitted_freguesia_id=omitted.freguesia_id,
                    omitted_freguesia_name=omitted.freguesia_name,
                    pressure_coefficient=estimate,
                    status="ok",
                )
            )
        except (MultivariableAnalysisError, np.linalg.LinAlgError) as exc:
            rows.append(
                LeaveOneOutRow(
                    omitted_freguesia_id=omitted.freguesia_id,
                    omitted_freguesia_name=omitted.freguesia_name,
                    pressure_coefficient=None,
                    status=f"failed: {exc}",
                )
            )

    return LeaveOneOutSummary(
        full_sample_pressure_coefficient=full_pressure,
        successful_refits=len(estimates),
        failed_refits=len(rows) - len(estimates),
        same_sign_fraction=(None if not estimates else same_sign / len(estimates)),
        coefficient_min=None if not estimates else min(estimates),
        coefficient_median=None if not estimates else median(estimates),
        coefficient_max=None if not estimates else max(estimates),
        rows=tuple(rows),
    )


def _same_sign(left: float, right: float) -> bool:
    """Return whether two nonzero estimates have the same sign."""
    if math.isclose(left, 0.0) or math.isclose(right, 0.0):
        return math.isclose(left, right)
    return (left > 0) == (right > 0)


def _coefficient(fit: ModelFit, term: str) -> CoefficientResult:
    """Return one named coefficient from a fitted model."""
    for coefficient in fit.coefficients:
        if coefficient.term == term:
            return coefficient
    raise MultivariableAnalysisError(f"model {fit.spec.name} is missing coefficient {term}")


def _write_model_input(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Write the derived common-window model input table."""
    predictors = sorted(_SUPPORTED_PREDICTORS)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "freguesia_id",
                "freguesia_name",
                "baseline_year",
                "latest_year",
                result.outcome,
                *predictors,
            )
        )
        for row in result.observations:
            writer.writerow(
                (
                    row.freguesia_id,
                    row.freguesia_name,
                    row.baseline_year,
                    row.latest_year,
                    _optional_number(row.outcome),
                    *(_optional_number(row.values[predictor]) for predictor in predictors),
                )
            )


def _write_coefficients(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Write coefficient and robust-uncertainty table."""
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "model",
                "model_label",
                "term",
                "estimate",
                "hc3_se",
                "ci_95_low",
                "ci_95_high",
                "t_statistic",
                "p_value",
                "vif",
                "standardization_mean",
                "standardization_sd",
            )
        )
        for fit in result.fits:
            for coefficient in fit.coefficients:
                writer.writerow(
                    (
                        fit.spec.name,
                        fit.spec.label,
                        coefficient.term,
                        coefficient.estimate,
                        coefficient.hc3_se,
                        coefficient.ci_95_low,
                        coefficient.ci_95_high,
                        coefficient.t_statistic,
                        coefficient.p_value,
                        _optional_number(coefficient.vif),
                        _optional_number(coefficient.standardization_mean),
                        _optional_number(coefficient.standardization_sd),
                    )
                )


def _write_residuals(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Write fitted, residual, leverage, and Cook's-distance diagnostics."""
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "model",
                "freguesia_id",
                "freguesia_name",
                "observed",
                "fitted",
                "residual",
                "leverage",
                "cooks_distance",
            )
        )
        for fit in result.fits:
            for row in fit.residuals:
                writer.writerow(
                    (
                        fit.spec.name,
                        row.freguesia_id,
                        row.freguesia_name,
                        row.observed,
                        row.fitted,
                        row.residual,
                        row.leverage,
                        row.cooks_distance,
                    )
                )


def _write_leave_one_out(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Write primary-model leave-one-freguesia-out pressure estimates."""
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "primary_model",
                "omitted_freguesia_id",
                "omitted_freguesia_name",
                "pressure_coefficient",
                "status",
            )
        )
        for row in result.leave_one_out.rows:
            writer.writerow(
                (
                    result.primary_model,
                    row.omitted_freguesia_id,
                    row.omitted_freguesia_name,
                    _optional_number(row.pressure_coefficient),
                    row.status,
                )
            )


def _write_report(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Write machine-readable model specifications and diagnostics."""
    document: dict[str, object] = {
        "schema_version": 1,
        "analysis": "pre_specified_multivariable_ols",
        "comparison_window": {
            "baseline_year": result.baseline_year,
            "latest_year": result.latest_year,
        },
        "outcome": result.outcome,
        "primary_model": result.primary_model,
        "estimation": {
            "method": "ordinary_least_squares",
            "predictor_scaling": "z_score_population_sd",
            "uncertainty": "HC3_robust_standard_errors",
            "confidence_interval": "95_percent_t",
        },
        "models": [
            {
                "name": fit.spec.name,
                "label": fit.spec.label,
                "predictors": list(fit.spec.predictors),
                "excluded_freguesias": list(fit.excluded_freguesias),
                "diagnostics": _diagnostic_document(fit.diagnostics),
                "coefficients": [
                    {
                        "term": coefficient.term,
                        "estimate": coefficient.estimate,
                        "hc3_se": coefficient.hc3_se,
                        "ci_95_low": coefficient.ci_95_low,
                        "ci_95_high": coefficient.ci_95_high,
                        "t_statistic": coefficient.t_statistic,
                        "p_value": coefficient.p_value,
                        "vif": coefficient.vif,
                        "standardization_mean": (coefficient.standardization_mean),
                        "standardization_sd": coefficient.standardization_sd,
                    }
                    for coefficient in fit.coefficients
                ],
            }
            for fit in result.fits
        ],
        "leave_one_freguesia_out": {
            "full_sample_pressure_coefficient": (
                result.leave_one_out.full_sample_pressure_coefficient
            ),
            "successful_refits": result.leave_one_out.successful_refits,
            "failed_refits": result.leave_one_out.failed_refits,
            "same_sign_fraction": result.leave_one_out.same_sign_fraction,
            "coefficient_min": result.leave_one_out.coefficient_min,
            "coefficient_median": result.leave_one_out.coefficient_median,
            "coefficient_max": result.leave_one_out.coefficient_max,
        },
        "interpretation": (
            "These are descriptive cross-sectional OLS specifications over one "
            "common baseline-to-latest window. Static Censos-2021 context is used "
            "for adjustment; coefficients are associations, not causal effects."
        ),
    }

    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def _diagnostic_document(diagnostics: ModelDiagnostics) -> dict[str, object]:
    """Convert diagnostics to a JSON-compatible mapping."""
    moran = diagnostics.residual_moran
    return {
        "n_observations": diagnostics.n_observations,
        "n_parameters": diagnostics.n_parameters,
        "residual_degrees_of_freedom": diagnostics.residual_degrees_of_freedom,
        "r_squared": diagnostics.r_squared,
        "adjusted_r_squared": diagnostics.adjusted_r_squared,
        "rmse": diagnostics.rmse,
        "condition_number": diagnostics.condition_number,
        "max_vif": diagnostics.max_vif,
        "breusch_pagan_lm": diagnostics.breusch_pagan_lm,
        "breusch_pagan_p_value": diagnostics.breusch_pagan_p_value,
        "residual_moran": {
            "morans_i": moran.morans_i,
            "expected_i": moran.expected_i,
            "permutation_p_two_sided": moran.permutation_p_two_sided,
            "complete_cases": moran.complete_cases,
            "edge_count": moran.edge_count,
            "islands": list(moran.islands),
            "permutations": moran.permutations,
            "seed": moran.seed,
        },
    }


def _write_pressure_coefficients_plot(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Plot the RNAL-pressure coefficient and robust 95% CI across model specs."""
    import matplotlib.pyplot as plt

    estimates: list[float] = []
    low_errors: list[float] = []
    high_errors: list[float] = []
    labels: list[str] = []

    for fit in result.fits:
        coefficient = _coefficient(fit, _PRIMARY_EXPOSURE)
        estimates.append(coefficient.estimate)
        low_errors.append(coefficient.estimate - coefficient.ci_95_low)
        high_errors.append(coefficient.ci_95_high - coefficient.estimate)
        labels.append(fit.spec.label)

    positions = np.arange(len(estimates), dtype=np.float64)
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.errorbar(
        estimates,
        positions,
        xerr=np.asarray([low_errors, high_errors]),
        fmt="o",
        capsize=4,
    )
    axis.axvline(0, linewidth=0.8)
    axis.set_yticks(positions, labels=labels)
    axis.set_xlabel("Housing-change percentage points per 1 SD RNAL-pressure increase")
    axis.set_title("RNAL pressure coefficient across pre-specified models")
    axis.grid(True, axis="x", alpha=0.25)
    figure.tight_layout()
    try:
        figure.savefig(path, dpi=180, bbox_inches="tight")
    finally:
        plt.close(figure)


def _write_primary_residuals_plot(
    result: MultivariableAnalysisResult,
    path: Path,
) -> None:
    """Write fitted-versus-residual diagnostic plot for the primary model."""
    import matplotlib.pyplot as plt

    fit = next(item for item in result.fits if item.spec.name == result.primary_model)

    figure, axis = plt.subplots(figsize=(7, 5))
    axis.scatter(
        [row.fitted for row in fit.residuals],
        [row.residual for row in fit.residuals],
    )
    axis.axhline(0, linewidth=0.8)
    for row in fit.residuals:
        axis.annotate(
            row.freguesia_name,
            (row.fitted, row.residual),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
        )
    axis.set_xlabel("Fitted housing change (%)")
    axis.set_ylabel("Residual (percentage points)")
    axis.set_title(f"Primary model residuals: {fit.spec.label}")
    axis.grid(True, alpha=0.25)
    figure.tight_layout()
    try:
        figure.savefig(path, dpi=180, bbox_inches="tight")
    finally:
        plt.close(figure)


def _validate_static_context(
    freguesia_id: str,
    years: Mapping[int, Mapping[str, str]],
) -> None:
    """Compare finite numeric context values independently of CSV formatting."""
    values: set[tuple[float, ...]] = set()
    for row in years.values():
        values.add(
            tuple(
                _required_float_csv(
                    row.get(field),
                    f"{freguesia_id}.{field}",
                )
                for field in _CONTEXT_SOURCE_FIELDS
            )
        )
    if len(values) != 1:
        raise MultivariableAnalysisError(
            f"static census context changes across years for {freguesia_id}"
        )


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required TOML table."""
    if not isinstance(value, Mapping):
        raise MultivariableAnalysisError(f"{context} must be a TOML table")
    return value


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty TOML string."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MultivariableAnalysisError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _required_csv(value: str | None, context: str) -> str:
    """Return a required non-empty CSV value."""
    if value is None or not value.strip():
        raise MultivariableAnalysisError(f"{context} must be non-empty")
    return value.strip()


def _required_int_csv(value: str | None, context: str) -> int:
    """Parse a required integer CSV value."""
    raw = _required_csv(value, context)
    try:
        return int(raw)
    except ValueError as exc:
        raise MultivariableAnalysisError(f"{context} must be an integer") from exc


def _required_float_csv(value: str | None, context: str) -> float:
    """Parse a required finite float CSV value."""
    parsed = _optional_float_csv(value, context)
    if parsed is None:
        raise MultivariableAnalysisError(f"{context} must be numeric")
    return parsed


def _positive_float_csv(value: str | None, context: str) -> float:
    """Parse a required positive finite float CSV value."""
    parsed = _required_float_csv(value, context)
    if parsed <= 0:
        raise MultivariableAnalysisError(f"{context} must be positive")
    return parsed


def _optional_float_csv(value: str | None, context: str) -> float | None:
    """Parse an optional finite float CSV value."""
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value.strip())
    except ValueError as exc:
        raise MultivariableAnalysisError(f"{context} must be numeric") from exc
    if not math.isfinite(parsed):
        raise MultivariableAnalysisError(f"{context} must be finite")
    return parsed


def cast_value(value: float | None) -> float:
    """Narrow an optional numeric value after complete-case validation."""
    if value is None:
        raise AssertionError("complete-case value unexpectedly missing")
    return value


def _optional_number(value: float | None) -> object:
    """Serialize optional numeric value to CSV primitive."""
    return "" if value is None else value
