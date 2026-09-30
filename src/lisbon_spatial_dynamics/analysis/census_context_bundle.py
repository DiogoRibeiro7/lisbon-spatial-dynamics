"""One-shot Censos 2021 neighbourhood-context milestone."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lisbon_spatial_dynamics.analysis.pressure_associations import (
    load_annual_housing_pressure_csv,
)
from lisbon_spatial_dynamics.panels.annual_context import (
    build_annual_context_panel,
    write_annual_context_csv,
)
from lisbon_spatial_dynamics.spatial.annual_maps import load_reference_geojson
from lisbon_spatial_dynamics.transformations.census_context import (
    build_census2021_context,
    build_census2021_context_geojson,
    write_census2021_context_csv,
    write_census2021_context_geojson,
)


@dataclass(frozen=True, slots=True)
class CensusContextBundleOutputs:
    """Files produced by the Censos 2021 context milestone."""

    context_csv: Path
    context_geojson: Path
    annual_context_csv: Path

    def paths(self) -> tuple[Path, ...]:
        """Return output paths in deterministic order."""
        return (
            self.context_csv,
            self.context_geojson,
            self.annual_context_csv,
        )


def build_census2021_context_bundle(
    archive_path: Path,
    reference_csv: Path,
    reference_geojson: Path,
    annual_panel: Path,
    output_directory: Path,
    *,
    expected_count: int = 24,
) -> CensusContextBundleOutputs:
    """Build static census context and enrich the annual research panel."""
    output_directory.mkdir(parents=True, exist_ok=True)

    outputs = CensusContextBundleOutputs(
        context_csv=output_directory / "lisbon_census2021_context.csv",
        context_geojson=output_directory / "lisbon_census2021_context.geojson",
        annual_context_csv=(output_directory / "lisbon_annual_housing_pressure_context.csv"),
    )

    for path in outputs.paths():
        if path.exists():
            raise FileExistsError(path)

    context = build_census2021_context(
        archive_path,
        reference_csv,
        expected_count=expected_count,
    )
    reference = load_reference_geojson(
        reference_geojson,
        expected_count=expected_count,
    )
    context_geojson = build_census2021_context_geojson(context, reference)

    annual = load_annual_housing_pressure_csv(annual_panel)
    enriched = build_annual_context_panel(annual, context)

    written: list[Path] = []

    try:
        write_census2021_context_csv(context, outputs.context_csv)
        written.append(outputs.context_csv)

        write_census2021_context_geojson(
            context_geojson,
            outputs.context_geojson,
        )
        written.append(outputs.context_geojson)

        write_annual_context_csv(
            enriched,
            outputs.annual_context_csv,
        )
        written.append(outputs.annual_context_csv)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return outputs
