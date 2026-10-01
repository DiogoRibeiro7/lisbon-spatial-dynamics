"""End-to-end reproducible build for the v1 Lisbon study release."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from lisbon_spatial_dynamics.analysis.final_results import (
    build_final_results_package,
)
from lisbon_spatial_dynamics.analysis.multivariable import (
    build_multivariable_analysis,
)
from lisbon_spatial_dynamics.analysis.normalized_bundle import (
    build_normalized_analysis_bundle,
)
from lisbon_spatial_dynamics.panels.annual import (
    build_annual_urban_panel,
    write_annual_urban_csv,
)
from lisbon_spatial_dynamics.panels.annual_context import (
    build_annual_context_panel,
    write_annual_context_csv,
)
from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    build_annual_housing_pressure_panel,
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
    write_annual_rnal_pressure_csv,
)
from lisbon_spatial_dynamics.panels.temporal import (
    build_housing_change_panel,
    write_housing_change_csv,
)
from lisbon_spatial_dynamics.panels.urban import (
    build_urban_change_panel,
    write_urban_change_csv,
)
from lisbon_spatial_dynamics.spatial.annual_maps import load_reference_geojson
from lisbon_spatial_dynamics.transformations.census_context import (
    build_census2021_context,
    build_census2021_context_geojson,
    write_census2021_context_csv,
    write_census2021_context_geojson,
)
from lisbon_spatial_dynamics.transformations.housing import (
    parse_ine_housing_payload,
)
from lisbon_spatial_dynamics.transformations.population import (
    build_census_population_reference,
    write_census_population_csv,
)

STUDY_V1_VERSION = "1.0.1"


class StudyV1BuildError(ValueError):
    """Raised when the v1 study build cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class StudyV1Inputs:
    """Immutable input snapshots/configuration for one v1 study build."""

    housing_snapshot: Path
    rnal_snapshot: Path
    census_archive: Path
    reference_csv: Path
    reference_geojson: Path
    model_config: Path

    def paths(self) -> tuple[Path, ...]:
        """Return every input path."""
        return (
            self.housing_snapshot,
            self.rnal_snapshot,
            self.census_archive,
            self.reference_csv,
            self.reference_geojson,
            self.model_config,
        )


@dataclass(frozen=True, slots=True)
class StudyV1Outputs:
    """Top-level output locations for one completed v1 study build."""

    output_root: Path
    normalized_directory: Path
    multivariable_directory: Path
    final_results_directory: Path
    manifest_path: Path

    def paths(self) -> tuple[Path, ...]:
        """Return the principal release output locations."""
        return (
            self.normalized_directory,
            self.multivariable_directory,
            self.final_results_directory,
            self.manifest_path,
        )


def build_study_v1(
    inputs: StudyV1Inputs,
    output_root: Path,
    *,
    expected_freguesias: int = 24,
    permutations: int = 999,
    seed: int = 42,
    local_alpha: float = 0.05,
) -> StudyV1Outputs:
    """Build all processed panels, analyses, and final v1 research outputs."""
    if expected_freguesias <= 0:
        raise ValueError("expected_freguesias must be positive")
    if permutations < 0:
        raise ValueError("permutations must be non-negative")
    if not 0.0 < local_alpha < 1.0:
        raise ValueError("local_alpha must be between 0 and 1")
    if output_root.exists():
        raise FileExistsError(output_root)

    _validate_inputs(inputs)
    output_root.mkdir(parents=True)

    panels = output_root / "panels"
    reference_dir = output_root / "reference"
    context_dir = output_root / "context"
    analysis_dir = output_root / "analysis"
    normalized_dir = analysis_dir / "normalized"
    multivariable_dir = analysis_dir / "multivariable"
    final_dir = output_root / "results" / "final"

    housing_panel_path = panels / "housing_freguesia_panel.csv"
    housing_changes_path = panels / "housing_changes.csv"
    rnal_quarter_path = panels / "rnal_quarter_panel.csv"
    population_path = reference_dir / "population_2021.csv"
    rnal_pressure_path = panels / "rnal_population_pressure.csv"
    annual_rnal_pressure_path = panels / "annual_rnal_pressure.csv"
    urban_quarter_path = panels / "urban_change_quarterly.csv"
    annual_urban_path = panels / "annual_urban_change.csv"
    annual_housing_pressure_path = panels / "annual_housing_pressure.csv"
    census_context_path = context_dir / "census2021_context.csv"
    census_context_geojson_path = context_dir / "census2021_context.geojson"
    annual_context_path = context_dir / "annual_housing_pressure_context.csv"
    manifest_path = output_root / "study_manifest.json"

    try:
        reference_index = load_freguesia_index(
            inputs.reference_csv,
            expected_count=expected_freguesias,
        )
        reference_geometry = load_reference_geojson(
            inputs.reference_geojson,
            expected_count=expected_freguesias,
        )

        housing_observations = parse_ine_housing_payload(inputs.housing_snapshot.read_bytes())
        housing_panel = build_current_housing_freguesia_panel(
            housing_observations,
            reference_index,
        )
        write_housing_panel_csv(housing_panel, housing_panel_path)

        housing_changes = build_housing_change_panel(housing_panel)
        write_housing_change_csv(housing_changes, housing_changes_path)

        periods = load_analysis_quarters(housing_changes_path)
        rnal_records = load_rnal_snapshot(inputs.rnal_snapshot)
        rnal_quarter = build_rnal_quarter_panel(
            rnal_records,
            reference_index,
            periods,
        )
        write_rnal_quarter_csv(rnal_quarter, rnal_quarter_path)

        population = build_census_population_reference(
            inputs.census_archive,
            inputs.reference_csv,
            expected_count=expected_freguesias,
        )
        write_census_population_csv(population, population_path)
        population_reference = load_population_reference(population_path)

        rnal_pressure = build_rnal_population_pressure(
            rnal_quarter,
            population_reference,
        )
        write_rnal_population_pressure_csv(rnal_pressure, rnal_pressure_path)

        annual_rnal_pressure = build_annual_rnal_pressure(rnal_pressure)
        write_annual_rnal_pressure_csv(
            annual_rnal_pressure,
            annual_rnal_pressure_path,
        )

        urban_quarter = build_urban_change_panel(
            housing_changes,
            rnal_quarter,
        )
        write_urban_change_csv(urban_quarter, urban_quarter_path)

        annual_urban = build_annual_urban_panel(urban_quarter)
        write_annual_urban_csv(annual_urban, annual_urban_path)

        annual_housing_pressure = build_annual_housing_pressure_panel(
            annual_urban,
            annual_rnal_pressure,
        )
        write_annual_housing_pressure_csv(
            annual_housing_pressure,
            annual_housing_pressure_path,
        )

        census_context = build_census2021_context(
            inputs.census_archive,
            inputs.reference_csv,
            expected_count=expected_freguesias,
        )
        write_census2021_context_csv(census_context, census_context_path)
        census_context_geojson = build_census2021_context_geojson(
            census_context,
            reference_geometry,
        )
        write_census2021_context_geojson(
            census_context_geojson,
            census_context_geojson_path,
        )

        annual_context = build_annual_context_panel(
            annual_housing_pressure,
            census_context,
        )
        write_annual_context_csv(annual_context, annual_context_path)

        build_normalized_analysis_bundle(
            annual_housing_pressure,
            reference_geometry,
            normalized_dir,
            permutations=permutations,
            seed=seed,
            alpha=local_alpha,
        )

        build_multivariable_analysis(
            annual_context_path,
            inputs.reference_geojson,
            inputs.model_config,
            multivariable_dir,
            permutations=permutations,
            seed=seed,
            expected_freguesias=expected_freguesias,
        )

        build_final_results_package(
            normalized_dir,
            multivariable_dir,
            final_dir,
        )

        _write_manifest(
            inputs,
            output_root,
            manifest_path,
            expected_freguesias=expected_freguesias,
            permutations=permutations,
            seed=seed,
            local_alpha=local_alpha,
        )
    except Exception:
        shutil.rmtree(output_root, ignore_errors=True)
        raise

    return StudyV1Outputs(
        output_root=output_root,
        normalized_directory=normalized_dir,
        multivariable_directory=multivariable_dir,
        final_results_directory=final_dir,
        manifest_path=manifest_path,
    )


def _validate_inputs(inputs: StudyV1Inputs) -> None:
    """Require all release inputs to exist as regular files."""
    missing = [str(path) for path in inputs.paths() if not path.is_file()]
    if missing:
        raise StudyV1BuildError("missing v1 study input files: " + ", ".join(missing))


def _write_manifest(
    inputs: StudyV1Inputs,
    output_root: Path,
    manifest_path: Path,
    *,
    expected_freguesias: int,
    permutations: int,
    seed: int,
    local_alpha: float,
) -> None:
    """Write SHA-256 provenance for release inputs and every generated file."""
    input_records = [
        {
            "path": str(path),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in inputs.paths()
    ]
    output_records = [
        {
            "path": path.relative_to(output_root).as_posix(),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path != manifest_path
    ]

    document: dict[str, object] = {
        "schema_version": 1,
        "study_release": STUDY_V1_VERSION,
        "parameters": {
            "expected_freguesias": expected_freguesias,
            "spatial_permutations": permutations,
            "random_seed": seed,
            "local_moran_fdr_alpha": local_alpha,
        },
        "inputs": input_records,
        "outputs": output_records,
        "interpretation_contract": (
            "The v1 study reports descriptive and adjusted associations. "
            "No causal effect of local accommodation on housing prices is identified."
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
    manifest_path.write_text(payload, encoding="utf-8")


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
