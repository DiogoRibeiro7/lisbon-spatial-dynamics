"""Audit retained primary snapshots without claiming a definitive historical study.

Run from the repository root with the locked Poetry environment. The config pins
local inputs; no network requests are made and no establishment rows are emitted.
"""

from __future__ import annotations

import argparse
import csv
import json
import tomllib
from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path

from lisbon_spatial_dynamics.panels.housing import (
    build_current_housing_freguesia_panel,
    load_freguesia_index,
    write_housing_panel_csv,
)
from lisbon_spatial_dynamics.panels.rnal import build_rnal_quarter_panel, load_rnal_snapshot
from lisbon_spatial_dynamics.panels.temporal import parse_ine_quarter
from lisbon_spatial_dynamics.transformations.census_context import (
    build_census2021_context,
    write_census2021_context_csv,
)
from lisbon_spatial_dynamics.transformations.housing import parse_ine_housing_payload


def fingerprint(path: Path) -> dict[str, object]:
    """Identify an exact local artifact using a portable relative path."""
    payload = path.read_bytes()
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def audit(config_path: Path, output: Path) -> None:
    """Validate source integrity, aggregate coverage, and retain compact evidence."""
    if output.exists():
        raise FileExistsError(f"audit output already exists: {output}")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    audit_date = date.fromisoformat(config["audit_date"])
    paths = {key: Path(value) for key, value in config["inputs"].items()}
    inputs = {key: fingerprint(path) for key, path in paths.items()}
    provenance = {}
    captured_paths = set()
    for name, filename in config["manifests"].items():
        manifest_path = Path(filename)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        resources = list(manifest.get("resources", {}).values())
        resources.extend(
            manifest[key] for key in ("resource", "sanitised_snapshot") if key in manifest
        )
        if not resources:
            raise ValueError(f"no resources in {manifest_path}")
        for resource in resources:
            actual = fingerprint(Path(resource["path"]))
            if any(actual[key] != resource[key] for key in ("sha256", "size_bytes")):
                raise ValueError(f"source hash/size mismatch: {resource['path']}")
            captured_paths.add(resource["path"])
        provenance[name] = {"file": fingerprint(manifest_path), "content": manifest}
    for key in ("housing", "rnal", "census"):
        if paths[key].as_posix() not in captured_paths:
            raise ValueError(f"{key} input is not covered by an acquisition manifest")

    reference = load_freguesia_index(paths["reference_csv"])
    housing = build_current_housing_freguesia_panel(
        parse_ine_housing_payload(paths["housing"].read_bytes()),
        reference,
    )
    periods = sorted(
        {parse_ine_quarter(row.period_code) for row in housing},
        key=lambda p: p.ordinal,
    )
    if any(b.ordinal != a.ordinal + 1 for a, b in zip(periods, periods[1:], strict=False)):
        raise ValueError("housing quarter grid is not contiguous")
    records = load_rnal_snapshot(paths["rnal"])
    if not records:
        raise ValueError("RNAL snapshot has no records")
    # Existing panel validation checks every RNAL identifier AND parish name.
    # These reconstructed stocks are intentionally not released as historical truth.
    build_rnal_quarter_panel(records, reference, periods)
    context = build_census2021_context(paths["census"], paths["reference_csv"])

    report = {
        "schema_version": 1,
        "audit_date": audit_date.isoformat(),
        "status": "historical_rnal_coverage_not_established",
        "canonical_study_designated": False,
        "archive_status": "local_snapshots_retained; no_public_archive_deposited",
        "inputs": inputs,
        "acquisition": provenance,
        "audit_software": [
            fingerprint(path)
            for path in (
                Path(__file__).relative_to(Path.cwd()),
                config_path,
                Path("poetry.lock"),
                Path("pyproject.toml"),
                *sorted(Path("src/lisbon_spatial_dynamics").rglob("*.py")),
            )
        ],
        "geography": {"parishes": len(reference), "identifiers_and_names_validated": True},
        "housing": {
            "indicator": "0012234",
            "category": "Total",
            "rows": len(housing),
            "quarters": len(periods),
            "first_quarter": f"{periods[0].year}Q{periods[0].quarter}",
            "last_quarter": f"{periods[-1].year}Q{periods[-1].quarter}",
            "missing_values": sum(row.value_eur_m2 is None for row in housing),
            "annual_q4_years": [p.year for p in periods if p.quarter == 4],
        },
        "census": {
            "year": 2021,
            "parishes": len(context),
            "population_resident": sum(row.population_resident for row in context),
            "aggregation": "SUBSECCAO rows only; higher geographic totals excluded",
            "aggregate_consistency_checks_passed": True,
        },
        "rnal": {
            "records": len(records),
            "parishes": len({r.freguesia_id for r in records}),
            "cessation_dates_present": sum(r.ceased_on is not None for r in records),
            "missing_beds": sum(r.beds is None for r in records),
            "missing_users": sum(r.users is None for r in records),
            "earliest_registration": min(r.registered_on for r in records).isoformat(),
            "latest_registration": max(r.registered_on for r in records).isoformat(),
            "registrations_after_audit_date": sum(r.registered_on > audit_date for r in records),
            "registrations_before_2000": sum(r.registered_on.year < 2000 for r in records),
            "registration_year_counts": dict(
                sorted(Counter(r.registered_on.year for r in records).items())
            ),
            "interpretation": (
                "Counts describe records returned in this snapshot. Missing cessation dates "
                "do not establish absence of historical closures. The year-2000 threshold "
                "is an explicit date-quality screen, not a legal inception date. "
                "No records were removed or dates corrected."
            ),
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    write_housing_panel_csv(housing, output / "housing_quarter_panel.csv")
    write_census2021_context_csv(context, output / "census_context.csv")
    with (output / "rnal_snapshot_by_parish.csv").open("x", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(
            [
                "freguesia_id",
                "freguesia_name",
                "snapshot_records",
                "cessation_dates_present",
                "registrations_before_2000",
            ]
        )
        for parish in reference:
            subset = [r for r in records if r.freguesia_id == parish.freguesia_id]
            writer.writerow(
                [
                    parish.freguesia_id,
                    parish.name,
                    len(subset),
                    sum(r.ceased_on is not None for r in subset),
                    sum(r.registered_on.year < 2000 for r in subset),
                ]
            )
    report["outputs"] = [fingerprint(path) for path in sorted(output.glob("*.csv"))]
    with (output / "audit.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(output / "audit.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/source_audit_2026-10-01.toml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.config, args.output)
