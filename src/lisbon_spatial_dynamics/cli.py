"""Command-line entry points for reproducible project workflows."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.panels.housing import (
    build_current_housing_freguesia_panel,
    load_freguesia_index,
    write_housing_panel_csv,
)
from lisbon_spatial_dynamics.panels.temporal import (
    build_housing_change_panel,
    load_housing_panel_csv,
    write_housing_change_csv,
)
from lisbon_spatial_dynamics.sources.caop import CAOPConfig, fetch_caop_snapshot
from lisbon_spatial_dynamics.sources.ine import INEIndicatorConfig, fetch_ine_snapshot
from lisbon_spatial_dynamics.transformations.geography import (
    parse_caop_reference,
    write_reference_geography,
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
        "--config", type=Path, default=Path("configs/ine_housing_current.toml")
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
    parser.add_argument("--config", type=Path, default=Path("configs/caop_lisbon.toml"))
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
    parser.add_argument("input", type=Path, help="Canonical housing freguesia panel CSV.")
    parser.add_argument("output", type=Path, help="New housing change CSV path.")
    args = parser.parse_args()

    input_path = cast(Path, args.input)
    output_path = cast(Path, args.output)

    panel = load_housing_panel_csv(input_path)
    changes = build_housing_change_panel(panel)
    write_housing_change_csv(changes, output_path)

    print(f"Wrote {len(changes)} temporally normalized rows to {output_path}")


def fetch_rnal_lisboa() -> None:
    """Fetch privacy-minimised RNAL records for the municipality of Lisboa."""
    parser = ArgumentParser(description="Fetch Turismo de Portugal RNAL records for Lisboa.")
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
