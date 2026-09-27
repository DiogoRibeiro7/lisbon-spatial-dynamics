"""Command-line entry points for reproducible project workflows."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.sources.caop import CAOPConfig, fetch_caop_snapshot
from lisbon_spatial_dynamics.sources.ine import (
    INEIndicatorConfig,
    fetch_ine_snapshot,
)
from lisbon_spatial_dynamics.transformations.housing import (
    parse_ine_housing_payload,
    select_housing_observations,
    write_housing_csv,
)


def fetch_ine_housing() -> None:
    """Fetch a configured INE housing indicator as a raw snapshot."""
    parser = ArgumentParser(
        description="Fetch a configured INE housing indicator and metadata."
    )
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
    """Transform one raw INE housing payload into a stable Lisbon CSV."""
    parser = ArgumentParser(
        description="Transform raw INE housing JSON to the project CSV contract."
    )
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
    parser = ArgumentParser(
        description="Fetch and validate official CAOP2025 Lisbon freguesias."
    )
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
