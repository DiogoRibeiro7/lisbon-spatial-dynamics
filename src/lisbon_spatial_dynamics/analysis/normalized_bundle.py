"""One-shot normalized analysis bundle for Lisbon urban-change research."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import cast

from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    LocalMoranResult,
    analyse_local_morans_i,
)
from lisbon_spatial_dynamics.analysis.pressure_associations import (
    PressureAssociationResult,
    build_pressure_association,
    write_pressure_association_json,
    write_pressure_association_scatter,
)
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    MoranResult,
    analyse_global_morans_i,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    AnnualHousingPressureRow,
)
from lisbon_spatial_dynamics.spatial.annual_maps import (
    ReferenceFeature,
    load_reference_geojson,
)
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    TrajectoryMapFeature,
    _exterior_rings,
    _label_point,
)

_NORMALIZED_RNAL_METRIC = "rnal_pressure_change_per_1000"


class NormalizedBundleError(ValueError):
    """Raised when the normalized analysis bundle cannot be built safely."""


@dataclass(frozen=True, slots=True)
class NormalizedTrajectoryRow:
    """One common-window freguesia trajectory using normalized RNAL pressure."""

    freguesia_id: str
    freguesia_name: str
    baseline_year: int
    latest_year: int
    population_reference_year: int
    population_resident: int
    population_density_per_km2: Decimal
    housing_change_pct: Decimal | None
    housing_latest_eur_m2: Decimal | None
    rnal_pressure_latest_per_1000: Decimal
    rnal_pressure_change_per_1000: Decimal


NORMALIZED_TRAJECTORY_COLUMNS: tuple[str, ...] = (
    "freguesia_id",
    "freguesia_name",
    "baseline_year",
    "latest_year",
    "population_reference_year",
    "population_resident",
    "population_density_per_km2",
    "housing_change_pct",
    "housing_latest_eur_m2",
    "rnal_pressure_latest_per_1000",
    "rnal_pressure_change_per_1000",
)


@dataclass(frozen=True, slots=True)
class NormalizedBundleOutputs:
    """Files produced by the normalized analysis bundle."""

    trajectory_csv: Path
    trajectory_geojson: Path
    summary_json: Path
    association_json: Path
    association_plot: Path
    housing_choropleth: Path
    pressure_choropleth: Path
    global_morans_json: Path
    local_morans_json: Path


def build_normalized_trajectory(
    rows: Sequence[AnnualHousingPressureRow],
) -> tuple[NormalizedTrajectoryRow, ...]:
    """Reduce the annual research panel to one common-window row per freguesia."""
    if not rows:
        raise NormalizedBundleError("annual housing-pressure panel cannot be empty")

    by_id: dict[str, dict[int, AnnualHousingPressureRow]] = {}
    baseline_years = {row.baseline_year for row in rows}

    if len(baseline_years) != 1:
        raise NormalizedBundleError("freguesias do not share one baseline year")

    baseline_year = next(iter(baseline_years))

    for row in rows:
        years = by_id.setdefault(row.freguesia_id, {})
        if row.year in years:
            raise NormalizedBundleError(
                f"duplicate annual key: ({row.year}, {row.freguesia_id})"
            )
        years[row.year] = row

    common_years = set.intersection(*(set(years) for years in by_id.values()))
    if not common_years:
        raise NormalizedBundleError(
            "freguesias do not share any common annual observation year"
        )

    latest_year = max(common_years)
    output: list[NormalizedTrajectoryRow] = []

    for freguesia_id in sorted(by_id):
        row = by_id[freguesia_id][latest_year]

        if row.baseline_year != baseline_year:
            raise NormalizedBundleError(
                f"{freguesia_id} baseline year changed unexpectedly"
            )

        output.append(
            NormalizedTrajectoryRow(
                freguesia_id=freguesia_id,
                freguesia_name=row.freguesia_name,
                baseline_year=baseline_year,
                latest_year=latest_year,
                population_reference_year=row.population_reference_year,
                population_resident=row.population_resident,
                population_density_per_km2=row.population_density_per_km2,
                housing_change_pct=row.housing_change_from_baseline_pct,
                housing_latest_eur_m2=row.housing_value_eur_m2,
                rnal_pressure_latest_per_1000=(
                    row.rnal_active_registrations_per_1000_year_end
                ),
                rnal_pressure_change_per_1000=(
                    row.rnal_active_registrations_per_1000_change_from_baseline
                ),
            )
        )

    return tuple(output)


def build_normalized_analysis_bundle(
    annual_rows: Sequence[AnnualHousingPressureRow],
    reference: Sequence[ReferenceFeature],
    output_directory: Path,
    *,
    permutations: int = 999,
    seed: int = 42,
    alpha: float = 0.05,
    label_maps: bool = False,
    label_scatter: bool = True,
) -> NormalizedBundleOutputs:
    """Build the full normalized descriptive/spatial analysis milestone."""
    if permutations < 0:
        raise ValueError("permutations must be non-negative")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")

    trajectory = build_normalized_trajectory(annual_rows)
    _validate_reference(trajectory, reference)

    output_directory.mkdir(parents=True, exist_ok=True)

    outputs = NormalizedBundleOutputs(
        trajectory_csv=output_directory / "normalized_trajectories.csv",
        trajectory_geojson=output_directory / "normalized_trajectories.geojson",
        summary_json=output_directory / "normalized_summary.json",
        association_json=output_directory / "normalized_association.json",
        association_plot=output_directory / "normalized_association.png",
        housing_choropleth=output_directory / "housing_change_pct.png",
        pressure_choropleth=output_directory / "rnal_pressure_change_per_1000.png",
        global_morans_json=output_directory / "global_morans_i.json",
        local_morans_json=output_directory / "local_morans_i.json",
    )

    for path in outputs.__dict__.values():
        if cast(Path, path).exists():
            raise FileExistsError(path)

    association = build_pressure_association(annual_rows)
    spatial_data = _as_spatial_data(trajectory, reference)

    global_results = analyse_global_morans_i(
        spatial_data,
        permutations=permutations,
        seed=seed,
    )
    local_results = analyse_local_morans_i(
        spatial_data,
        permutations=permutations,
        seed=seed,
        alpha=alpha,
    )

    written: list[Path] = []

    try:
        _write_trajectory_csv(trajectory, outputs.trajectory_csv)
        written.append(outputs.trajectory_csv)

        _write_trajectory_geojson(
            trajectory,
            reference,
            outputs.trajectory_geojson,
        )
        written.append(outputs.trajectory_geojson)

        _write_summary_json(
            trajectory,
            association,
            outputs.summary_json,
        )
        written.append(outputs.summary_json)

        write_pressure_association_json(
            association,
            outputs.association_json,
        )
        written.append(outputs.association_json)

        write_pressure_association_scatter(
            association,
            outputs.association_plot,
            label_points=label_scatter,
        )
        written.append(outputs.association_plot)

        _write_normalized_choropleths(
            spatial_data,
            outputs.housing_choropleth,
            outputs.pressure_choropleth,
            label_freguesias=label_maps,
        )
        written.extend(
            (outputs.housing_choropleth, outputs.pressure_choropleth)
        )

        _write_global_morans_json(
            global_results,
            outputs.global_morans_json,
        )
        written.append(outputs.global_morans_json)

        _write_local_morans_json(
            local_results,
            outputs.local_morans_json,
        )
        written.append(outputs.local_morans_json)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return outputs


def load_and_build_normalized_analysis_bundle(
    annual_panel: Path,
    reference_geojson: Path,
    output_directory: Path,
    *,
    permutations: int = 999,
    seed: int = 42,
    alpha: float = 0.05,
    label_maps: bool = False,
    label_scatter: bool = True,
) -> NormalizedBundleOutputs:
    """Load canonical inputs and build the full normalized analysis bundle."""
    from lisbon_spatial_dynamics.analysis.pressure_associations import (
        load_annual_housing_pressure_csv,
    )

    annual_rows = load_annual_housing_pressure_csv(annual_panel)
    reference = load_reference_geojson(reference_geojson)

    return build_normalized_analysis_bundle(
        annual_rows,
        reference,
        output_directory,
        permutations=permutations,
        seed=seed,
        alpha=alpha,
        label_maps=label_maps,
        label_scatter=label_scatter,
    )


def _as_spatial_data(
    rows: Sequence[NormalizedTrajectoryRow],
    reference: Sequence[ReferenceFeature],
) -> TrajectoryMapData:
    """Adapt normalized pressure to the existing tested spatial-statistics engine."""
    reference_by_id = {feature.freguesia_id: feature for feature in reference}
    features: list[TrajectoryMapFeature] = []

    for row in rows:
        reference_feature = reference_by_id[row.freguesia_id]
        features.append(
            TrajectoryMapFeature(
                freguesia_id=row.freguesia_id,
                name=row.freguesia_name,
                housing_change_pct=(
                    None
                    if row.housing_change_pct is None
                    else float(row.housing_change_pct)
                ),
                # The spatial engine's second numeric slot is reused internally.
                # Bundle outputs relabel it as normalized RNAL pressure change.
                rnal_active_change_pct=float(
                    row.rnal_pressure_change_per_1000
                ),
                geometry=reference_feature.geometry,
            )
        )

    first = rows[0]
    return TrajectoryMapData(
        baseline_year=first.baseline_year,
        latest_year=first.latest_year,
        features=tuple(features),
    )


def _validate_reference(
    rows: Sequence[NormalizedTrajectoryRow],
    reference: Sequence[ReferenceFeature],
) -> None:
    """Require exact canonical geography coverage and names."""
    if not reference:
        raise NormalizedBundleError("reference geometry cannot be empty")

    row_by_id = {row.freguesia_id: row for row in rows}
    reference_by_id = {feature.freguesia_id: feature for feature in reference}

    if len(row_by_id) != len(rows):
        raise NormalizedBundleError("trajectory contains duplicate freguesia IDs")
    if len(reference_by_id) != len(reference):
        raise NormalizedBundleError("reference contains duplicate freguesia IDs")

    if set(row_by_id) != set(reference_by_id):
        missing = sorted(set(reference_by_id) - set(row_by_id))
        extra = sorted(set(row_by_id) - set(reference_by_id))
        raise NormalizedBundleError(
            f"trajectory/reference key mismatch; missing={missing}, extra={extra}"
        )

    for freguesia_id, row in row_by_id.items():
        expected = reference_by_id[freguesia_id].name
        if row.freguesia_name != expected:
            raise NormalizedBundleError(
                f"{freguesia_id} name mismatch: "
                f"{row.freguesia_name!r} != {expected!r}"
            )


def _write_trajectory_csv(
    rows: Sequence[NormalizedTrajectoryRow],
    path: Path,
) -> None:
    """Write common-window normalized trajectory CSV."""
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(NORMALIZED_TRAJECTORY_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.freguesia_id,
                    row.freguesia_name,
                    row.baseline_year,
                    row.latest_year,
                    row.population_reference_year,
                    row.population_resident,
                    _decimal_text(row.population_density_per_km2),
                    _optional_decimal_text(row.housing_change_pct),
                    _optional_decimal_text(row.housing_latest_eur_m2),
                    _decimal_text(row.rnal_pressure_latest_per_1000),
                    _decimal_text(row.rnal_pressure_change_per_1000),
                )
            )


def _write_trajectory_geojson(
    rows: Sequence[NormalizedTrajectoryRow],
    reference: Sequence[ReferenceFeature],
    path: Path,
) -> None:
    """Write map-ready normalized trajectory GeoJSON."""
    reference_by_id = {feature.freguesia_id: feature for feature in reference}
    features: list[dict[str, object]] = []

    for row in rows:
        reference_feature = reference_by_id[row.freguesia_id]
        properties = dict(reference_feature.properties)
        properties.update(
            {
                "baseline_year": row.baseline_year,
                "latest_year": row.latest_year,
                "population_reference_year": row.population_reference_year,
                "population_resident": row.population_resident,
                "population_density_per_km2": float(
                    row.population_density_per_km2
                ),
                "housing_change_pct": _decimal_number(
                    row.housing_change_pct
                ),
                "housing_latest_eur_m2": _decimal_number(
                    row.housing_latest_eur_m2
                ),
                "rnal_pressure_latest_per_1000": float(
                    row.rnal_pressure_latest_per_1000
                ),
                _NORMALIZED_RNAL_METRIC: float(
                    row.rnal_pressure_change_per_1000
                ),
            }
        )

        features.append(
            {
                "type": "Feature",
                "id": row.freguesia_id,
                "properties": properties,
                "geometry": dict(reference_feature.geometry),
            }
        )

    document: dict[str, object] = {
        "type": "FeatureCollection",
        "name": (
            f"lisbon_normalized_trajectories_"
            f"{rows[0].baseline_year}_{rows[0].latest_year}"
        ),
        "baseline_year": rows[0].baseline_year,
        "latest_year": rows[0].latest_year,
        "feature_count": len(features),
        "features": features,
    }

    _write_json(document, path)


def _write_summary_json(
    rows: Sequence[NormalizedTrajectoryRow],
    association: PressureAssociationResult,
    path: Path,
) -> None:
    """Write compact normalized-analysis summary metadata."""
    housing_values = [
        float(row.housing_change_pct)
        for row in rows
        if row.housing_change_pct is not None
    ]
    pressure_values = [
        float(row.rnal_pressure_change_per_1000)
        for row in rows
    ]

    document: dict[str, object] = {
        "schema_version": 1,
        "analysis": "normalized_urban_change_bundle",
        "comparison_window": {
            "baseline_year": rows[0].baseline_year,
            "latest_common_year": rows[0].latest_year,
        },
        "population_reference_year": rows[0].population_reference_year,
        "coverage": {
            "freguesia_count": len(rows),
            "housing_complete_count": len(housing_values),
            "housing_missing_count": len(rows) - len(housing_values),
        },
        "descriptive": {
            "housing_change_pct_median": (
                median(housing_values) if housing_values else None
            ),
            "rnal_pressure_change_per_1000_median": median(pressure_values),
            "population_total_2021": sum(
                row.population_resident for row in rows
            ),
        },
        "association": {
            "pearson_r": association.pearson_r,
            "spearman_rho": association.spearman_rho,
            "complete_cases": association.complete_cases,
        },
    }

    _write_json(document, path)


def _write_normalized_choropleths(
    data: TrajectoryMapData,
    housing_path: Path,
    pressure_path: Path,
    *,
    label_freguesias: bool,
) -> None:
    """Write housing-change and normalized RNAL-pressure choropleths."""
    _write_metric_choropleth(
        data,
        value_name="housing_change_pct",
        title="Housing value change",
        legend_label="Housing change (%)",
        output_path=housing_path,
        label_freguesias=label_freguesias,
    )
    _write_metric_choropleth(
        data,
        value_name="rnal_active_change_pct",
        title="RNAL pressure change",
        legend_label="Change in active RNAL per 1,000 residents",
        output_path=pressure_path,
        label_freguesias=label_freguesias,
    )


def _write_metric_choropleth(
    data: TrajectoryMapData,
    *,
    value_name: str,
    title: str,
    legend_label: str,
    output_path: Path,
    label_freguesias: bool,
) -> None:
    """Render one normalized bundle metric as a static choropleth."""
    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize, TwoSlopeNorm
    from matplotlib.patches import Polygon

    values = [
        value
        for feature in data.features
        if (value := _spatial_value(feature, value_name)) is not None
    ]
    if not values:
        raise NormalizedBundleError(f"{value_name} has no non-missing values")

    minimum = min(values)
    maximum = max(values)

    if math.isclose(minimum, maximum):
        padding = 1.0 if math.isclose(minimum, 0.0) else abs(minimum) * 0.05
        norm: Normalize = Normalize(
            vmin=minimum - padding,
            vmax=maximum + padding,
        )
    elif minimum < 0 < maximum:
        norm = TwoSlopeNorm(vmin=minimum, vcenter=0.0, vmax=maximum)
    else:
        norm = Normalize(vmin=minimum, vmax=maximum)

    cmap = plt.get_cmap("coolwarm")
    figure, axis = plt.subplots(figsize=(8, 8))

    for feature in data.features:
        value = _spatial_value(feature, value_name)
        facecolor = "0.85" if value is None else cmap(norm(value))

        for ring in _exterior_rings(feature.geometry):
            axis.add_patch(
                Polygon(
                    ring,
                    closed=True,
                    facecolor=facecolor,
                    edgecolor="0.25",
                    linewidth=0.6,
                )
            )

        if label_freguesias:
            x, y = _label_point(feature.geometry)
            axis.annotate(
                feature.name,
                (x, y),
                ha="center",
                va="center",
                fontsize=6,
            )

    axis.autoscale_view()
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")
    axis.set_title(
        f"{title}, {data.baseline_year}–{data.latest_year}",
        pad=12,
    )

    mappable = ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    figure.colorbar(mappable, ax=axis, shrink=0.72, label=legend_label)
    figure.tight_layout()

    try:
        figure.savefig(output_path, dpi=180, bbox_inches="tight")
    finally:
        plt.close(figure)


def _write_global_morans_json(
    results: Sequence[MoranResult],
    path: Path,
) -> None:
    """Write relabelled Global Moran diagnostics for normalized metrics."""
    document = {
        "schema_version": 1,
        "analysis": "global_morans_i_normalized_bundle",
        "weights": {
            "contiguity": "queen",
            "standardization": "row",
        },
        "results": [
            {
                "metric": _relabel_metric(result.metric),
                "baseline_year": result.baseline_year,
                "latest_year": result.latest_year,
                "complete_cases": result.complete_cases,
                "excluded_missing": result.excluded_missing,
                "islands": list(result.islands),
                "edge_count": result.edge_count,
                "morans_i": result.morans_i,
                "expected_i": result.expected_i,
                "permutation_p_two_sided": result.permutation_p_two_sided,
                "permutations": result.permutations,
                "seed": result.seed,
            }
            for result in results
        ],
    }
    _write_json(document, path)


def _write_local_morans_json(
    results: Sequence[LocalMoranResult],
    path: Path,
) -> None:
    """Write relabelled Local Moran diagnostics for normalized metrics."""
    document = {
        "schema_version": 1,
        "analysis": "local_morans_i_normalized_bundle",
        "weights": {
            "contiguity": "queen",
            "standardization": "row",
        },
        "results": [
            {
                "metric": _relabel_metric(result.metric),
                "baseline_year": result.baseline_year,
                "latest_year": result.latest_year,
                "alpha": result.alpha,
                "permutations": result.permutations,
                "seed": result.seed,
                "observations": [
                    {
                        "freguesia_id": observation.freguesia_id,
                        "freguesia_name": observation.freguesia_name,
                        "value": observation.value,
                        "local_i": observation.local_i,
                        "neighbor_count": observation.neighbor_count,
                        "permutation_p_two_sided": (
                            observation.permutation_p_two_sided
                        ),
                        "fdr_q": observation.fdr_q,
                        "significant_fdr": observation.significant_fdr,
                        "quadrant": observation.quadrant,
                        "cluster_class": observation.cluster_class,
                        "status": observation.status,
                    }
                    for observation in result.observations
                ],
            }
            for result in results
        ],
    }
    _write_json(document, path)


def _relabel_metric(metric: str) -> str:
    """Relabel the spatial engine's second slot to normalized RNAL pressure."""
    if metric == "rnal_active_change_pct":
        return _NORMALIZED_RNAL_METRIC
    return metric


def _spatial_value(
    feature: TrajectoryMapFeature,
    value_name: str,
) -> float | None:
    """Return one bundle spatial metric."""
    if value_name == "housing_change_pct":
        return feature.housing_change_pct
    if value_name == "rnal_active_change_pct":
        return feature.rnal_active_change_pct
    raise NormalizedBundleError(f"unsupported map metric: {value_name}")


def _write_json(document: Mapping[str, object], path: Path) -> None:
    """Write an immutable JSON document."""
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


def _decimal_text(value: Decimal) -> str:
    """Serialize Decimal without scientific notation."""
    return format(value, "f")


def _optional_decimal_text(value: Decimal | None) -> str:
    """Serialize optional Decimal."""
    return "" if value is None else _decimal_text(value)


def _decimal_number(value: Decimal | None) -> float | None:
    """Convert optional Decimal to JSON number."""
    return None if value is None else float(value)
