"""Command-line entry points for reproducible project workflows."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.analysis.associations import (
    build_descriptive_association,
    write_association_json,
    write_association_scatter,
)
from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    analyse_local_morans_i,
    write_local_morans_i_json,
)
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    analyse_global_morans_i,
    write_morans_i_json,
)
from lisbon_spatial_dynamics.analysis.trajectory_summary import (
    build_trajectory_summary,
    write_trajectory_summary_json,
)
from lisbon_spatial_dynamics.analysis.trajectories import (
    build_freguesia_trajectories,
    write_freguesia_trajectory_csv,
)
from lisbon_spatial_dynamics.panels.annual import (
    build_annual_urban_panel,
    load_urban_change_csv,
    write_annual_urban_csv,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    build_annual_housing_pressure_panel,
    load_annual_rnal_pressure_csv,
    write_annual_housing_pressure_csv,
)
from lisbon_spatial_dynamics.panels.housing import (
    build_current_housing_freguesia_panel,
    load_freguesia_index,
    write_housing_panel_csv,
)
from lisbon_spatial_dynamics.panels.rnal import (
    build_rnal_quarter_panel,
    load_analysis_quarters,
    load_rnal_snapshot,
    write_rnal_quarter_csv,
)
from lisbon_spatial_dynamics.panels.rnal_pressure import (
    build_rnal_population_pressure,
    load_population_reference,
    write_rnal_population_pressure_csv,
)
from lisbon_spatial_dynamics.panels.rnal_pressure_annual import (
    build_annual_rnal_pressure,
    load_rnal_population_pressure_csv,
    write_annual_rnal_pressure_csv,
)
from lisbon_spatial_dynamics.panels.temporal import (
    build_housing_change_panel,
    load_housing_panel_csv,
    write_housing_change_csv,
)
from lisbon_spatial_dynamics.panels.urban import (
    build_urban_change_panel,
    load_housing_change_csv,
    load_rnal_quarter_csv,
    write_urban_change_csv,
)
from lisbon_spatial_dynamics.sources.caop import CAOPConfig, fetch_caop_snapshot
from lisbon_spatial_dynamics.sources.census2021 import (
    Census2021Config,
    fetch_census2021_snapshot,
)
from lisbon_spatial_dynamics.sources.ine import INEIndicatorConfig, fetch_ine_snapshot
from lisbon_spatial_dynamics.sources.rnal import RNALConfig, fetch_rnal_snapshot
from lisbon_spatial_dynamics.spatial.annual_maps import (
    build_annual_geojson_layers,
    load_annual_urban_csv,
    load_reference_geojson,
    write_annual_geojson_layers,
)
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    load_trajectory_map,
    write_trajectory_choropleths,
)
from lisbon_spatial_dynamics.spatial.lisa_cluster_maps import (
    load_local_morans_json,
    write_lisa_cluster_maps,
)
from lisbon_spatial_dynamics.spatial.trajectory_map import (
    build_trajectory_geojson,
    load_trajectory_csv,
    write_trajectory_geojson,
)
from lisbon_spatial_dynamics.transformations.geography import (
    parse_caop_reference,
    write_reference_geography,
)
from lisbon_spatial_dynamics.transformations.population import (
    build_census_population_reference,
    write_census_population_csv,
)
from lisbon_spatial_dynamics.transformations.housing import (
    parse_ine_housing_payload,
    select_housing_observations,
    write_housing_csv,
)


def fetch_ine_housing() -> None:
    """Fetch a configured INE housing indicator as a raw snapshot."""
    parser = ArgumentParser(description="Fetch INE housing data and metadata.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/ine_housing_current.toml"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    config = INEIndicatorConfig.from_toml(cast(Path, args.config))
    snapshot = fetch_ine_snapshot(
        config,
        root=cast(Path, args.root),
        timeout=cast(float, args.timeout),
    )

    print(f"INE indicator {config.indicator_code} snapshot captured:")
    print(f"  data:     {snapshot.data.relative_path}")
    print(f"  metadata: {snapshot.metadata.relative_path}")
    print(f"  manifest: {snapshot.manifest.relative_path}")


def transform_ine_housing() -> None:
    """Transform one raw INE housing payload into a stable geography CSV."""
    parser = ArgumentParser(description="Transform raw INE housing JSON.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--geography", default="Lisboa")
    parser.add_argument("--category", default="Total")
    args = parser.parse_args()

    input_path = cast(Path, args.input)
    output_path = cast(Path, args.output)

    observations = parse_ine_housing_payload(input_path.read_bytes())
    selected = select_housing_observations(
        observations,
        geography_name=cast(str, args.geography),
        category_name=cast(str, args.category),
    )
    write_housing_csv(selected, output_path)
    print(f"Wrote {len(selected)} observations to {output_path}")


def fetch_caop_lisbon() -> None:
    """Fetch the canonical CAOP2025 Lisbon freguesia boundaries."""
    parser = ArgumentParser(description="Fetch official CAOP2025 Lisbon freguesias.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/caop_lisbon.toml"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    config = CAOPConfig.from_toml(cast(Path, args.config))
    snapshot = fetch_caop_snapshot(
        config,
        root=cast(Path, args.root),
        timeout=cast(float, args.timeout),
    )

    print("CAOP2025 Lisbon reference geography captured:")
    print(f"  geojson:  {snapshot.geojson_path}")
    print(f"  metadata: {snapshot.metadata_path}")
    print(f"  manifest: {snapshot.manifest_path}")


def build_reference_geography() -> None:
    """Build canonical freguesia CSV and GeoJSON from a raw CAOP snapshot."""
    parser = ArgumentParser(description="Build canonical Lisbon freguesia artifacts.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    input_path = cast(Path, args.input)
    output_directory = cast(Path, args.output_directory)
    references = parse_caop_reference(input_path.read_bytes())

    csv_path = output_directory / "lisbon_freguesias.csv"
    geojson_path = output_directory / "lisbon_freguesias.geojson"
    write_reference_geography(
        references,
        csv_path=csv_path,
        geojson_path=geojson_path,
    )

    print(f"Wrote {len(references)} canonical freguesias:")
    print(f"  table:    {csv_path}")
    print(f"  geometry: {geojson_path}")


def build_housing_freguesia_panel() -> None:
    """Join current INE housing data to the canonical freguesia reference."""
    parser = ArgumentParser(description="Build the Lisbon freguesia housing panel.")
    parser.add_argument("input", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--category", default="Total")
    args = parser.parse_args()

    observations = parse_ine_housing_payload(cast(Path, args.input).read_bytes())
    reference = load_freguesia_index(cast(Path, args.reference))
    rows = build_current_housing_freguesia_panel(
        observations,
        reference,
        category_name=cast(str, args.category),
    )
    output = cast(Path, args.output)
    write_housing_panel_csv(rows, output)

    period_count = len({row.period_code for row in rows})
    print(
        f"Wrote {len(rows)} rows across {period_count} periods "
        f"and {len(reference)} freguesias to {output}"
    )


def build_housing_changes() -> None:
    """Normalize periods and compute quarter-on-quarter and year-on-year changes."""
    parser = ArgumentParser(description="Build housing temporal change metrics.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    panel = load_housing_panel_csv(cast(Path, args.input))
    changes = build_housing_change_panel(panel)
    output = cast(Path, args.output)
    write_housing_change_csv(changes, output)

    print(f"Wrote {len(changes)} temporally normalized rows to {output}")


def fetch_rnal_lisboa() -> None:
    """Fetch privacy-minimised RNAL records for Lisboa."""
    parser = ArgumentParser(
        description="Fetch Turismo de Portugal RNAL records for Lisboa."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/rnal_lisboa.toml"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    config = RNALConfig.from_toml(cast(Path, args.config))
    snapshot = fetch_rnal_snapshot(
        config,
        root=cast(Path, args.root),
        timeout=cast(float, args.timeout),
    )

    print(f"RNAL Lisboa snapshot captured with {snapshot.record_count} records:")
    print(f"  records:  {snapshot.records_path}")
    print(f"  manifest: {snapshot.manifest_path}")


def build_rnal_quarter_panel_cli() -> None:
    """Build quarterly RNAL flows and active stock aligned to housing periods."""
    parser = ArgumentParser(
        description="Build the Lisboa RNAL quarter panel on the housing time grid."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("housing_changes", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    records = load_rnal_snapshot(cast(Path, args.input))
    reference = load_freguesia_index(cast(Path, args.reference))
    periods = load_analysis_quarters(cast(Path, args.housing_changes))
    rows = build_rnal_quarter_panel(records, reference, periods)

    output = cast(Path, args.output)
    write_rnal_quarter_csv(rows, output)

    print(
        f"Wrote {len(rows)} RNAL freguesia-quarter rows across "
        f"{len(periods)} periods to {output}"
    )


def build_urban_change_panel_cli() -> None:
    """Join housing and RNAL panels on the exact freguesia-quarter key set."""
    parser = ArgumentParser(description="Build the combined Lisbon urban-change panel.")
    parser.add_argument("housing", type=Path)
    parser.add_argument("rnal", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    housing = load_housing_change_csv(cast(Path, args.housing))
    rnal = load_rnal_quarter_csv(cast(Path, args.rnal))
    rows = build_urban_change_panel(housing, rnal)

    output = cast(Path, args.output)
    write_urban_change_csv(rows, output)

    quarters = {(row.year, row.quarter) for row in rows}
    freguesias = {row.freguesia_id for row in rows}
    print(
        f"Wrote {len(rows)} urban-change rows across "
        f"{len(quarters)} quarters and {len(freguesias)} freguesias to {output}"
    )


def build_annual_urban_panel_cli() -> None:
    """Build the Q4-anchored annual Lisbon urban-change panel."""
    parser = ArgumentParser(
        description="Build year-end urban-change comparisons by freguesia."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    quarterly = load_urban_change_csv(cast(Path, args.input))
    annual = build_annual_urban_panel(quarterly)

    output = cast(Path, args.output)
    write_annual_urban_csv(annual, output)

    years = {row.year for row in annual}
    freguesias = {row.freguesia_id for row in annual}
    print(
        f"Wrote {len(annual)} annual rows across "
        f"{len(years)} years and {len(freguesias)} freguesias to {output}"
    )


def build_annual_map_layers_cli() -> None:
    """Build one map-ready annual GeoJSON layer per available year."""
    parser = ArgumentParser(
        description="Build annual Lisbon urban-change GeoJSON layers."
    )
    parser.add_argument("annual", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    annual = load_annual_urban_csv(cast(Path, args.annual))
    reference = load_reference_geojson(cast(Path, args.reference))
    layers = build_annual_geojson_layers(annual, reference)
    paths = write_annual_geojson_layers(
        layers,
        cast(Path, args.output_directory),
    )

    print(
        f"Wrote {len(paths)} annual GeoJSON layers "
        f"for {len(reference)} freguesias."
    )


def build_freguesia_trajectories_cli() -> None:
    """Build common-window baseline-to-latest trajectories by freguesia."""
    parser = ArgumentParser(
        description="Build baseline-to-latest Lisbon freguesia trajectories."
    )
    parser.add_argument("annual", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    annual = load_annual_urban_csv(cast(Path, args.annual))
    trajectories = build_freguesia_trajectories(annual)

    output = cast(Path, args.output)
    write_freguesia_trajectory_csv(trajectories, output)

    baseline_years = {row.baseline_year for row in trajectories}
    latest_years = {row.latest_year for row in trajectories}
    print(
        f"Wrote {len(trajectories)} freguesia trajectories "
        f"for window {min(baseline_years)}-{max(latest_years)} to {output}"
    )


def build_trajectory_map_cli() -> None:
    """Build the baseline-to-latest trajectory GeoJSON."""
    parser = ArgumentParser(
        description="Build map-ready Lisbon freguesia trajectory GeoJSON."
    )
    parser.add_argument("trajectories", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    trajectories = load_trajectory_csv(cast(Path, args.trajectories))
    reference = load_reference_geojson(cast(Path, args.reference))
    document = build_trajectory_geojson(trajectories, reference)

    output = cast(Path, args.output)
    write_trajectory_geojson(document, output)

    print(
        f"Wrote trajectory GeoJSON for {len(trajectories)} freguesias to {output}"
    )


def build_trajectory_summary_cli() -> None:
    """Build the aggregate common-window trajectory summary JSON."""
    parser = ArgumentParser(
        description="Build aggregate descriptive Lisbon trajectory summary."
    )
    parser.add_argument("trajectories", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    trajectories = load_trajectory_csv(cast(Path, args.trajectories))
    summary = build_trajectory_summary(trajectories)

    output = cast(Path, args.output)
    write_trajectory_summary_json(summary, output)

    print(
        f"Wrote {summary.baseline_year}-{summary.latest_year} trajectory summary "
        f"for {summary.freguesia_count} freguesias to {output}"
    )


def build_descriptive_association_cli() -> None:
    """Build descriptive housing/RNAL correlations and a scatter plot."""
    parser = ArgumentParser(
        description="Build descriptive housing-versus-RNAL association outputs."
    )
    parser.add_argument("trajectories", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("output_plot", type=Path)
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Do not annotate freguesia names on the scatter plot.",
    )
    args = parser.parse_args()

    trajectories = load_trajectory_csv(cast(Path, args.trajectories))
    result = build_descriptive_association(trajectories)

    output_json = cast(Path, args.output_json)
    output_plot = cast(Path, args.output_plot)

    write_association_json(result, output_json)
    write_association_scatter(
        result,
        output_plot,
        label_points=not cast(bool, args.no_labels),
    )

    print(
        f"Wrote descriptive association for {result.complete_cases}/"
        f"{result.total_freguesias} complete freguesias: "
        f"Pearson={result.pearson_r}, Spearman={result.spearman_rho}"
    )


def build_trajectory_choropleths_cli() -> None:
    """Build static housing and RNAL trajectory choropleths."""
    parser = ArgumentParser(
        description="Build static trajectory choropleths for Lisbon freguesias."
    )
    parser.add_argument("trajectory_geojson", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument(
        "--labels",
        action="store_true",
        help="Annotate freguesia names on the choropleths.",
    )
    args = parser.parse_args()

    data = load_trajectory_map(cast(Path, args.trajectory_geojson))
    housing, rnal = write_trajectory_choropleths(
        data,
        cast(Path, args.output_directory),
        label_freguesias=cast(bool, args.labels),
    )

    print(f"Wrote housing choropleth: {housing}")
    print(f"Wrote RNAL choropleth: {rnal}")


def build_global_morans_i_cli() -> None:
    """Calculate Global Moran's I for housing and RNAL trajectory changes."""
    parser = ArgumentParser(
        description="Build Global Moran's I spatial autocorrelation outputs."
    )
    parser.add_argument("trajectory_geojson", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--permutations",
        type=int,
        default=999,
        help="Number of random permutations for the two-sided test.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic permutation results.",
    )
    args = parser.parse_args()

    data = load_trajectory_map(cast(Path, args.trajectory_geojson))
    results = analyse_global_morans_i(
        data,
        permutations=cast(int, args.permutations),
        seed=cast(int, args.seed),
    )

    output = cast(Path, args.output)
    write_morans_i_json(results, output)

    for result in results:
        print(
            f"{result.metric}: I={result.morans_i}, "
            f"expected={result.expected_i}, "
            f"p={result.permutation_p_two_sided}, "
            f"n={result.complete_cases}"
        )


def build_local_morans_i_cli() -> None:
    """Calculate Local Moran's I for housing and RNAL trajectory changes."""
    parser = ArgumentParser(
        description="Build Local Moran's I (LISA) spatial association outputs."
    )
    parser.add_argument("trajectory_geojson", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--permutations",
        type=int,
        default=999,
        help="Conditional permutations per freguesia.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic local permutation tests.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="FDR-adjusted significance threshold.",
    )
    args = parser.parse_args()

    data = load_trajectory_map(cast(Path, args.trajectory_geojson))
    results = analyse_local_morans_i(
        data,
        permutations=cast(int, args.permutations),
        seed=cast(int, args.seed),
        alpha=cast(float, args.alpha),
    )

    output = cast(Path, args.output)
    write_local_morans_i_json(results, output)

    for result in results:
        significant = sum(
            observation.significant_fdr is True
            for observation in result.observations
        )
        print(
            f"{result.metric}: {significant} FDR-significant local associations "
            f"from {result.complete_cases} complete freguesias"
        )


def build_lisa_cluster_maps_cli() -> None:
    """Build FDR-controlled Local Moran cluster maps."""
    parser = ArgumentParser(
        description="Build Local Moran (LISA) cluster maps for Lisbon freguesias."
    )
    parser.add_argument("trajectory_geojson", type=Path)
    parser.add_argument("local_morans_json", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument(
        "--labels",
        action="store_true",
        help="Annotate freguesia names on the cluster maps.",
    )
    args = parser.parse_args()

    trajectory = load_trajectory_map(cast(Path, args.trajectory_geojson))
    bundle = load_local_morans_json(cast(Path, args.local_morans_json))
    housing, rnal = write_lisa_cluster_maps(
        trajectory,
        bundle,
        cast(Path, args.output_directory),
        label_freguesias=cast(bool, args.labels),
    )

    print(f"Wrote housing LISA map: {housing}")
    print(f"Wrote RNAL LISA map: {rnal}")


def fetch_census2021_population() -> None:
    """Fetch the official INE Censos 2021 subsection synthesis archive."""
    parser = ArgumentParser(
        description="Fetch the official Censos 2021 subsection synthesis ZIP."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/census2021_population.toml"),
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    config = Census2021Config.from_toml(cast(Path, args.config))
    snapshot = fetch_census2021_snapshot(
        config,
        root=cast(Path, args.root),
        timeout=cast(float, args.timeout),
    )

    print(
        f"Censos 2021 snapshot captured with {snapshot.member_count} files:"
    )
    print(f"  archive:  {snapshot.archive_path}")
    print(f"  manifest: {snapshot.manifest_path}")


def build_census2021_population_reference_cli() -> None:
    """Aggregate Censos 2021 subsection population to Lisboa freguesias."""
    parser = ArgumentParser(
        description="Build the static 2021 population reference by freguesia."
    )
    parser.add_argument("archive", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = build_census_population_reference(
        cast(Path, args.archive),
        cast(Path, args.reference),
    )
    output = cast(Path, args.output)
    write_census_population_csv(rows, output)

    total_population = sum(row.population_resident for row in rows)
    print(
        f"Wrote {len(rows)} freguesia population rows "
        f"for {total_population} Census 2021 residents to {output}"
    )


def build_rnal_population_pressure_cli() -> None:
    """Normalize the RNAL quarter panel using the static 2021 census population."""
    parser = ArgumentParser(
        description="Build population-normalized RNAL pressure metrics."
    )
    parser.add_argument("rnal", type=Path)
    parser.add_argument("population", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rnal = load_rnal_quarter_csv(cast(Path, args.rnal))
    population = load_population_reference(cast(Path, args.population))
    rows = build_rnal_population_pressure(rnal, population)

    output = cast(Path, args.output)
    write_rnal_population_pressure_csv(rows, output)

    print(
        f"Wrote {len(rows)} population-normalized RNAL rows "
        f"using Census {population[0].census_year} denominators to {output}"
    )


def build_annual_rnal_pressure_cli() -> None:
    """Build Q4-anchored annual RNAL pressure metrics."""
    parser = ArgumentParser(
        description="Build annual population-normalized RNAL pressure metrics."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    quarterly = load_rnal_population_pressure_csv(cast(Path, args.input))
    annual = build_annual_rnal_pressure(quarterly)

    output = cast(Path, args.output)
    write_annual_rnal_pressure_csv(annual, output)

    years = {row.year for row in annual}
    freguesias = {row.freguesia_id for row in annual}
    print(
        f"Wrote {len(annual)} annual RNAL pressure rows across "
        f"{len(years)} years and {len(freguesias)} freguesias to {output}"
    )


def build_annual_housing_pressure_panel_cli() -> None:
    """Join annual housing dynamics to population-normalized RNAL pressure."""
    parser = ArgumentParser(
        description="Build the annual housing + RNAL pressure research panel."
    )
    parser.add_argument("housing", type=Path)
    parser.add_argument("pressure", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    housing = load_annual_urban_csv(cast(Path, args.housing))
    pressure = load_annual_rnal_pressure_csv(cast(Path, args.pressure))
    rows = build_annual_housing_pressure_panel(housing, pressure)

    output = cast(Path, args.output)
    write_annual_housing_pressure_csv(rows, output)

    years = {row.year for row in rows}
    freguesias = {row.freguesia_id for row in rows}
    print(
        f"Wrote {len(rows)} annual housing-pressure rows across "
        f"{len(years)} years and {len(freguesias)} freguesias to {output}"
    )
