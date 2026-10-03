"""Fetch a pinned conflict cohort's coordinates or replay its aggregate boundary audit."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import tomllib
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NamedTuple

import pyproj
import shapely

from lisbon_spatial_dynamics.analysis.rnal_geography import (
    conflict_cohort,
    coordinate_evidence,
    project_boundaries,
    reconcile,
)
from lisbon_spatial_dynamics.analysis.rnal_parish_sensitivity import (
    compare_assignments,
    parse_population,
    plot_sensitivity,
)
from lisbon_spatial_dynamics.panels.rnal import RNALRecord, parse_rnal_snapshot
from lisbon_spatial_dynamics.sources.rnal_locations import fetch_locations


class VerifiedFile(NamedTuple):
    payload: bytes
    provenance: dict[str, Any]


class Baseline(NamedTuple):
    cohort: dict[int, tuple[str, str]]
    soap: tuple[RNALRecord, ...]
    files: dict[str, VerifiedFile]


def fingerprint_bytes(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def fingerprint(path: Path) -> dict[str, Any]:
    return fingerprint_bytes(path, path.read_bytes())


def read_verified(path: Path, expected: dict[str, Any]) -> VerifiedFile:
    """Return the exact bytes hashed, so parsing never reopens a verified path."""
    payload = path.read_bytes()
    actual = fingerprint_bytes(path, payload)
    if any(actual[key] != expected[key] for key in ("sha256", "size_bytes")):
        raise ValueError(f"input integrity mismatch: {path}")
    return VerifiedFile(payload, actual)


def verify(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    return read_verified(path, expected).provenance


def load_baseline(config: dict[str, Any]) -> Baseline:
    files = {
        name: read_verified(Path(value["path"]), value)
        for name, value in config["inputs"].items()
        if name != "locations_manifest"
    }
    soap = parse_rnal_snapshot(files["soap"].payload.decode("utf-8"))
    gis = json.loads(files["gis"].payload)["records"]
    cohort = conflict_cohort(soap, gis)
    if len(cohort) != config["expectations"]["conflicts"]:
        raise ValueError("conflict count differs from the pinned baseline audit")
    return Baseline(cohort, soap, files)


def audit(config_path: Path, output: Path) -> None:
    """Validate provenance, compare projected coordinates and publish aggregates atomically."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"geography audit output already exists: {output}")
    config_payload = config_path.read_bytes()
    config = tomllib.loads(config_payload.decode("utf-8"))
    kind = config["analysis"].get("kind", "coordinate_support")
    if kind not in {"coordinate_support", "parish_sensitivity"}:
        raise ValueError("unknown geography audit kind")
    baseline = load_baseline(config)
    cohort, soap, files = baseline
    inputs = {name: file.provenance for name, file in files.items()}
    pinned = config["inputs"]["locations_manifest"]
    manifest_path = Path(pinned["path"])
    manifest_file = read_verified(manifest_path, pinned)
    inputs["locations_manifest"] = manifest_file.provenance
    manifest = json.loads(manifest_file.payload)
    if manifest["crs"] != "EPSG:4326" or manifest["record_count"] != len(cohort):
        raise ValueError("location acquisition CRS or cohort count mismatch")
    if {resource["file"] for resource in manifest["resources"]} != {"locations.json", "layer.json"}:
        raise ValueError("unexpected location resource set")
    for resource in manifest["resources"]:
        file = read_verified(manifest_path.parent / resource["file"], resource)
        files["locations_" + resource["file"]] = file
        inputs["locations_" + resource["file"]] = file.provenance
    locations = json.loads(files["locations_locations.json"].payload)["records"]
    layer = json.loads(files["locations_layer.json"].payload)
    reference = json.loads(files["reference"].payload)
    polygons, names, projector = project_boundaries(
        reference, expected_count=config["expectations"]["parishes"]
    )
    summary, rows = reconcile(
        cohort,
        locations,
        polygons,
        names,
        projector,
        thresholds_m=config["analysis"]["boundary_margins_m"],
    )
    coordinate_summary = summary
    datasets = {"coordinate_support_by_parish.csv": rows}
    if kind == "parish_sensitivity":
        population = parse_population(files["population"].payload.decode("utf-8"))
        if (
            len(soap) != config["expectations"]["snapshot_records"]
            or sum(population.values()) != config["expectations"]["population_2021"]
        ):
            raise ValueError("snapshot count or Census population differs from pinned expectation")
        summary, scenario_rows = compare_assignments(
            soap,
            cohort,
            coordinate_evidence(cohort, locations, polygons, projector),
            names,
            population,
            margin_m=config["analysis"]["reassignment_margin_m"],
        )
        datasets["parish_scenarios.csv"] = scenario_rows
    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_date": config["audit_date"],
        "summary": summary,
        "inputs": inputs,
        "analysis": config["analysis"],
        "coordinate_capture": {
            key: manifest[key] for key in ("started_at", "completed_at", "record_count", "crs")
        },
        "provider_reliability_domain": next(
            field["domain"] for field in layer["fields"] if field["name"] == "FiabilidadeGeo"
        ),
        "projection": {
            "source_crs": "EPSG:4326",
            "target_crs": "EPSG:3763",
            "always_xy": True,
            "description": projector.description,
            "definition": projector.definition,
            "reported_accuracy_m": projector.accuracy,
            "network_enabled": projector.is_network_enabled,
        },
        "software": {
            "python": platform.python_version(),
            "pyproj": pyproj.__version__,
            "proj": pyproj.proj_version_str,
            "shapely": shapely.__version__,
            "geos": shapely.geos_version_string,
        },
        "code_and_configuration": [
            fingerprint_bytes(config_path, config_payload),
            *(
                fingerprint(path)
                for path in (
                    Path(__file__).relative_to(Path.cwd()),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                    Path("src/lisbon_spatial_dynamics/analysis/rnal_geography.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/rnal_parish_sensitivity.py"),
                    Path("src/lisbon_spatial_dynamics/sources/rnal_locations.py"),
                    Path("src/lisbon_spatial_dynamics/sources/rnal_geodata.py"),
                    Path("src/lisbon_spatial_dynamics/panels/rnal.py"),
                )
            ),
        ],
        "interpretation": (
            "Only the pinned SOAP/GIS parish conflicts are inspected. The GIS coordinates and "
            "labels share a provider. Any reassignment is a sensitivity scenario within the "
            "unchanged SOAP cohort. No establishment locations or registry assignments are "
            "independently verified or corrected; no historical completeness is established."
        ),
        "archive_status": "Local ignored inputs; only aggregates committed.",
    }
    if kind == "parish_sensitivity":
        report["coordinate_summary"] = coordinate_summary
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".rnal-geography-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        artifacts = []
        for filename, data_rows in datasets.items():
            csv_path = staging / filename
            with csv_path.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(data_rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(data_rows)
            artifact = fingerprint(csv_path)
            artifact["path"] = (output / csv_path.name).as_posix()
            artifacts.append(artifact)
        if kind == "parish_sensitivity":
            figure = staging / "parish_sensitivity.png"
            plot_sensitivity(
                datasets["parish_scenarios.csv"],
                figure,
                margin_m=config["analysis"]["reassignment_margin_m"],
            )
            artifact = fingerprint(figure)
            artifact["path"] = (output / figure.name).as_posix()
            artifacts.append(artifact)
        report["outputs"] = artifacts
        (staging / "audit.json").write_bytes(
            (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"geography audit output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "audit"))
    parser.add_argument(
        "--config", type=Path, default=Path("configs/rnal_geography_2026-10-01.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        config = tomllib.loads(args.config.read_text(encoding="utf-8"))
        baseline = load_baseline(config)
        print(
            fetch_locations({key: value[1] for key, value in baseline.cohort.items()}, args.output)
        )
    else:
        audit(args.config, args.output)


if __name__ == "__main__":
    main()
