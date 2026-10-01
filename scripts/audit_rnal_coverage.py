"""Acquire a minimal GIS snapshot or replay a pinned, offline RNAL coverage audit."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import tomllib
from datetime import date
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.rnal_coverage import compare_snapshots
from lisbon_spatial_dynamics.panels.housing import load_freguesia_index
from lisbon_spatial_dynamics.panels.rnal import load_rnal_snapshot
from lisbon_spatial_dynamics.sources.rnal_geodata import ITEM_URL, LAYER_URL, fetch_snapshot


def fingerprint(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def verify(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    actual = fingerprint(path)
    if any(actual[key] != expected[key] for key in ("sha256", "size_bytes")):
        raise ValueError(f"input integrity mismatch: {path}")
    return actual


def audit(config_path: Path, output: Path) -> None:
    """Check exact acquisition bytes before comparing records; emit aggregates only."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"audit output already exists: {output}")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    inputs = {name: verify(Path(value["path"]), value) for name, value in config["inputs"].items()}
    paths = {name: Path(value["path"]) for name, value in inputs.items()}
    soap_manifest = json.loads(paths["soap_manifest"].read_bytes())
    soap_path = Path(soap_manifest["sanitised_snapshot"]["path"])
    inputs["soap_records"] = verify(soap_path, soap_manifest["sanitised_snapshot"])
    gis_manifest = json.loads(paths["gis_manifest"].read_bytes())
    resources = gis_manifest["resources"]
    if {value["file"] for value in resources} != {"records.json", "layer.json", "item.json"}:
        raise ValueError("unexpected GIS resource set")
    for resource in resources:
        inputs["gis_" + resource["file"]] = verify(
            paths["gis_manifest"].parent / resource["file"], resource
        )
    gis = json.loads((paths["gis_manifest"].parent / "records.json").read_bytes())["records"]
    layer = json.loads((paths["gis_manifest"].parent / "layer.json").read_bytes())
    item = json.loads((paths["gis_manifest"].parent / "item.json").read_bytes())
    soap = load_rnal_snapshot(soap_path)
    if (
        len(soap) != soap_manifest["written_record_count"]
        or len(gis) != gis_manifest["record_count"]
    ):
        raise ValueError("snapshot counts differ from manifests")
    reference = load_freguesia_index(paths["reference"])
    benchmark = config["benchmark"]
    summary, parishes, early = compare_snapshots(
        soap,
        gis,
        reference,
        benchmark_date=date.fromisoformat(benchmark["date"]),
        benchmark_count=benchmark["registrations"],
    )
    code_paths = [
        Path("scripts/audit_rnal_coverage.py"),
        Path("src/lisbon_spatial_dynamics/analysis/rnal_coverage.py"),
        Path("src/lisbon_spatial_dynamics/sources/rnal_geodata.py"),
        Path("src/lisbon_spatial_dynamics/panels/rnal.py"),
        Path("src/lisbon_spatial_dynamics/panels/housing.py"),
        Path("pyproject.toml"),
        Path("poetry.lock"),
        config_path,
    ]
    report = {
        "schema_version": 1,
        "audit_date": config["audit_date"],
        "scope": "RNAL source coverage; no definitive historical study",
        "inputs": inputs,
        "code_and_configuration": [fingerprint(path) for path in code_paths],
        "python_version": platform.python_version(),
        "summary": summary,
        "acquisition": {
            "soap_captured_at": soap_manifest["fetched_at"],
            "soap_endpoint": soap_manifest["endpoint_url"],
            "gis_started_at": gis_manifest["started_at"],
            "gis_completed_at": gis_manifest["completed_at"],
            "gis_layer_url": LAYER_URL,
            "gis_item_url": ITEM_URL,
            "gis_item_description": item.get("description"),
            "gis_item_licence_info": item.get("licenseInfo"),
            "gis_schema_fields": [
                {"name": field["name"], "type": field["type"]} for field in layer["fields"]
            ],
            "gis_time_info": layer.get("timeInfo"),
            "gis_date_fields_time_reference": layer.get("dateFieldsTimeReference"),
            "date_conversion": "epoch milliseconds interpreted in UTC; no date corrections",
            "gis_membership_stable_during_capture": gis_manifest[
                "membership_stable_during_capture"
            ],
            "gis_transactional_snapshot": gis_manifest["transactional_snapshot"],
            "captures_simultaneous": False,
        },
        "published_benchmark_provenance": benchmark,
        "archive_status": "exact raw inputs retained locally; not deposited in a public archive",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # A sibling staging directory keeps the final rename on the same filesystem.
    # TemporaryDirectory removes only this run's unpublished files on failure.
    with TemporaryDirectory(prefix=".rnal-audit-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        outputs = []
        for name, rows, columns in (
            ("parish_comparison.csv", parishes, list(parishes[0])),
            (
                "early_registration_years.csv",
                early,
                [
                    "registration_year",
                    "soap_records",
                    "gis_records",
                    "shared_with_same_registration_date",
                    "gis_opening_before_screen",
                    "gis_opening_missing",
                ],
            ),
        ):
            path = staging / name
            with path.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            artifact = fingerprint(path)
            artifact["path"] = (output / name).as_posix()
            outputs.append(artifact)
        report["outputs"] = outputs
        with (staging / "audit.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"audit output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser(
        "fetch", help="Make live GIS requests; output must be a new directory"
    )
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--timeout", type=float, default=60)
    replay = commands.add_parser(
        "audit", help="Replay the pinned comparison without network access"
    )
    replay.add_argument(
        "--config", type=Path, default=Path("configs/rnal_coverage_2026-10-01.toml")
    )
    replay.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        print(fetch_snapshot(args.output, timeout=args.timeout))
    else:
        audit(args.config, args.output)


if __name__ == "__main__":
    main()
