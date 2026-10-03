"""Acquire minimized, commit-pinned community exports or replay their coverage assessment."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import tomllib
from datetime import UTC, datetime
from hashlib import sha1, sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.request import Request, urlopen

from lisbon_spatial_dynamics.analysis.cml_benchmarks import parse_reference
from lisbon_spatial_dynamics.analysis.rnal_archive import (
    CAPACITY_COLUMN_DEFINITIONS,
    analyse_archive,
    minimize_export,
    parse_snapshot,
    timestamp_from_filename,
)
from lisbon_spatial_dynamics.analysis.rnal_capture_gaps import (
    COLUMN_DEFINITIONS as GAP_COLUMN_DEFINITIONS,
)
from lisbon_spatial_dynamics.analysis.rnal_capture_gaps import (
    DATASET_COLUMNS as GAP_DATASET_COLUMNS,
)
from lisbon_spatial_dynamics.analysis.rnal_capture_gaps import analyse_capture_gaps
from lisbon_spatial_dynamics.panels.rnal import parse_rnal_snapshot


def fingerprint(payload: bytes) -> dict[str, Any]:
    return {"sha256": sha256(payload).hexdigest(), "size_bytes": len(payload)}


def verified(path: Path, expected: dict[str, Any]) -> bytes:
    payload = path.read_bytes()
    if any(fingerprint(payload)[key] != expected[key] for key in ("sha256", "size_bytes")):
        raise ValueError(f"input integrity mismatch: {path}")
    return payload


def ensure_new(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"archive output already exists: {output}")


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    )


def get_bytes(url: str) -> bytes:
    with urlopen(
        Request(url, headers={"User-Agent": "lisbon-spatial-dynamics/1.0.1"}), timeout=90
    ) as response:
        return cast(bytes, response.read())


def source_base(config: dict[str, Any]) -> str:
    source = config["source"]
    if source["repository"] != "sztanko/al-pulse" or not re.fullmatch(
        r"[0-9a-f]{40}", source["revision"]
    ):
        raise ValueError("expected a full revision of the assessed community repository")
    files = [entry["file"] for entry in config["exports"]]
    if len(files) < 2 or len(set(files)) != len(files):
        raise ValueError("expected at least two unique export filenames")
    for filename in files:
        timestamp_from_filename(filename)
    return f"https://raw.githubusercontent.com/{source['repository']}/{source['revision']}/"


def fetch(config_path: Path, output: Path) -> None:
    ensure_new(output)
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    base = source_base(config)
    pinned_reference = config["inputs"]["reference"]
    reference = parse_reference(
        verified(Path(pinned_reference["path"]), pinned_reference).decode(),
        expected_count=config["parishes"],
    )
    started_at = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".rnal-archive-fetch-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        resources = []
        for entry in config["exports"]:
            filename = entry["file"]
            url = base + "downloads/al/" + filename
            payload = get_bytes(url)
            blob = sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
            if blob != entry["git_blob_sha1"] or len(payload) != entry["size_bytes"]:
                raise ValueError("download differs from the pinned Git tree")
            minimized = minimize_export(payload, filename, reference)
            target = filename.removesuffix(".csv.gz") + ".json"
            (staging / target).write_bytes(minimized)
            resources.append(
                {
                    "source_file": filename,
                    "url": url,
                    "download": {**fingerprint(payload), "git_blob_sha1": blob},
                    "minimized": {"file": target, **fingerprint(minimized)},
                }
            )
            print(f"Minimized {filename}", flush=True)
        provenance = []
        for relative in ("README.md", "scripts/fetch_al_list.py", "scripts/run_fetch.sh"):
            payload = get_bytes(base + relative)
            filename = "publisher_" + Path(relative).name
            (staging / filename).write_bytes(payload)
            provenance.append({"file": filename, "url": base + relative, **fingerprint(payload)})
        write_json(
            staging / "manifest.json",
            {
                "schema_version": 1,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "source": config["source"],
                "reference": pinned_reference,
                "resources": resources,
                "publisher_documents": provenance,
                "raw_export_retained": False,
                "privacy": (
                    "Only Lisbon registry number, registration date, parish ID "
                    "and user capacity retained."
                ),
            },
        )
        ensure_new(output)
        staging.rename(output)


def audit(config_path: Path, output: Path, *, analysis: str = "coverage") -> None:
    ensure_new(output)
    if analysis not in {"coverage", "capture-gaps"}:
        raise ValueError("unknown archive analysis")
    config_payload = config_path.read_bytes()
    config = tomllib.loads(config_payload.decode())
    base = source_base(config)
    captured = {
        name: verified(Path(pinned["path"]), pinned) for name, pinned in config["inputs"].items()
    }
    reference = parse_reference(captured["reference"].decode(), expected_count=config["parishes"])
    soap = parse_rnal_snapshot(captured["soap"].decode())
    soap_manifest = json.loads(captured["soap_manifest"])
    if (
        soap_manifest["sanitised_snapshot"] != config["inputs"]["soap"]
        or soap_manifest["municipality"] != "Lisboa"
        or soap_manifest["written_record_count"] != len(soap)
    ):
        raise ValueError("SOAP acquisition manifest differs from pinned snapshot")
    manifest = json.loads(captured["acquisition_manifest"])
    if (
        manifest["source"] != config["source"]
        or manifest["reference"] != config["inputs"]["reference"]
    ):
        raise ValueError("acquisition source or reference differs from pinned configuration")
    entries = {entry["file"]: entry for entry in config["exports"]}
    resources = manifest["resources"]
    if len(resources) != len(entries) or {r["source_file"] for r in resources} != entries.keys():
        raise ValueError("acquisition export set differs from configuration")
    directory = Path(config["inputs"]["acquisition_manifest"]["path"]).parent
    snapshots = []
    for resource in resources:
        filename = resource["source_file"]
        expected = entries[filename]
        if (
            resource["url"] != base + "downloads/al/" + filename
            or any(
                resource["download"][key] != expected[key]
                for key in ("git_blob_sha1", "size_bytes")
            )
            or resource["minimized"]["file"] != filename.removesuffix(".csv.gz") + ".json"
        ):
            raise ValueError("acquisition export identity mismatch")
        payload = verified(directory / resource["minimized"]["file"], resource["minimized"])
        snapshot = parse_snapshot(payload, reference)
        if snapshot.source_file != filename:
            raise ValueError("minimized source filename mismatch")
        snapshots.append(snapshot)
    documents = manifest["publisher_documents"]
    required_documents = {"README.md", "scripts/fetch_al_list.py", "scripts/run_fetch.sh"}
    if len(documents) != 3 or {d["url"] for d in documents} != {
        base + relative for relative in required_documents
    }:
        raise ValueError("unexpected publisher document set")
    for document in documents:
        if document["file"] != "publisher_" + document["url"].rsplit("/", 1)[1]:
            raise ValueError("unexpected publisher document filename")
        verified(directory / document["file"], document)
    if analysis == "coverage":
        summary, datasets = analyse_archive(snapshots, reference, soap)
        summary["soap_capture_utc"] = soap_manifest["fetched_at"]
    else:
        summary, datasets = analyse_capture_gaps(snapshots)
    code_paths = [
        Path(__file__).relative_to(Path.cwd()),
        Path("src/lisbon_spatial_dynamics/analysis/rnal_archive.py"),
        Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
        Path("src/lisbon_spatial_dynamics/panels/rnal.py"),
        Path("pyproject.toml"),
        Path("poetry.lock"),
    ]
    if analysis == "capture-gaps":
        code_paths.append(Path("src/lisbon_spatial_dynamics/analysis/rnal_capture_gaps.py"))
    report = {
        "schema_version": 1,
        "audit_date": config["audit_date"],
        "analysis": analysis,
        "summary": summary,
        "column_definitions": (
            CAPACITY_COLUMN_DEFINITIONS if analysis == "coverage" else GAP_COLUMN_DEFINITIONS
        ),
        "inputs": config["inputs"],
        "acquisition": manifest,
        "software": {"python": platform.python_version()},
        "code_and_configuration": [
            {"path": config_path.as_posix(), **fingerprint(config_payload)},
            *({"path": path.as_posix(), **fingerprint(path.read_bytes())} for path in code_paths),
        ],
        "interpretation": (
            "Community-maintained copies attributed to the official RNAL search export. "
            "Source timestamps and national completeness are not independently verified. "
            "Absence between captures is not a dated cessation or cancellation. "
            "Publisher documents are fingerprinted for provenance, not executed or parsed. "
            "Offline replay checks minimized bytes; "
            "reacquisition checks original Git blob identity."
        ),
        "archive_status": (
            "Minimized establishment data retained locally, only aggregates committed. "
            "Original national CSVs processed in memory; redistribution terms not established."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".rnal-archive-audit-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        artifacts = []
        for filename, rows in datasets.items():
            path = staging / filename
            with path.open("x", encoding="utf-8", newline="") as stream:
                columns = (
                    GAP_DATASET_COLUMNS[filename] if analysis == "capture-gaps" else list(rows[0])
                )
                writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            artifacts.append(
                {"path": (output / filename).as_posix(), **fingerprint(path.read_bytes())}
            )
        report["outputs"] = artifacts
        write_json(staging / "audit.json", report)
        ensure_new(output)
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "audit"))
    parser.add_argument("--config", type=Path, default=Path("configs/rnal_archive_2026-10-03.toml"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--analysis", choices=("coverage", "capture-gaps"), default="coverage")
    args = parser.parse_args()
    if args.command == "fetch":
        if args.analysis != "coverage":
            parser.error("--analysis applies only to the audit command")
        fetch(args.config, args.output)
    else:
        audit(args.config, args.output, analysis=args.analysis)


if __name__ == "__main__":
    main()
