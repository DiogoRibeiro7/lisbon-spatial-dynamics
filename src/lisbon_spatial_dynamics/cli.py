"""Command-line entry points for reproducible project workflows."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.sources.ine import (
    INEIndicatorConfig,
    fetch_ine_snapshot,
)


def fetch_ine_housing() -> None:
    """Fetch the configured INE housing indicator as a raw snapshot."""
    parser = ArgumentParser(
        description="Fetch the configured INE housing indicator and metadata."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/ine_housing.toml"),
        help="Path to the INE housing TOML configuration.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository or working root for relative output paths.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds.",
    )
    args = parser.parse_args()

    config_path = cast(Path, args.config)
    root = cast(Path, args.root)
    timeout = cast(float, args.timeout)

    config = INEIndicatorConfig.from_toml(config_path)
    snapshot = fetch_ine_snapshot(
        config,
        root=root,
        timeout=timeout,
    )

    print(f"INE indicator {config.indicator_code} snapshot captured:")
    print(f"  data:     {snapshot.data.relative_path}")
    print(f"  metadata: {snapshot.metadata.relative_path}")
    print(f"  manifest: {snapshot.manifest.relative_path}")
