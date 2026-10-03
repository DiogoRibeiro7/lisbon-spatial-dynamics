"""Replay a checked transcription of CML's November 2019/2022 parish benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import tomllib
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import audit_transcription, parse_reference


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def audit(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"benchmark output already exists: {output}")
    config_bytes = config_path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    if config["source"]["reference_months"] != ["2019-11", "2022-11"]:
        raise ValueError("source reference months differ from the transcribed columns")
    captured, inputs = {}, {}
    for name, pinned in config["inputs"].items():
        path = Path(pinned["path"])
        payload = path.read_bytes()
        actual = fingerprint(path, payload)
        if any(actual[key] != pinned[key] for key in ("sha256", "size_bytes")):
            raise ValueError(f"input integrity mismatch: {path}")
        captured[name], inputs[name] = payload, actual
    source_manifest = json.loads(captured["source_manifest"])
    if any(source_manifest[key] != inputs["source_pdf"][key] for key in ("sha256", "size_bytes")):
        raise ValueError("source acquisition manifest does not identify the pinned PDF")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    summary, observations, arithmetic = audit_transcription(
        captured["transcription"].decode("utf-8"), reference
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_date": config["audit_date"],
        "summary": summary,
        "inputs": inputs,
        "source": config["source"],
        "transcription": config["transcription"],
        "software": {"python": platform.python_version()},
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).relative_to(Path.cwd()),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
        "archive_status": "Source PDF retained locally; transcribed aggregate facts committed.",
        "verification_scope": (
            "Replay verifies the source PDF identity and transcription bytes, coverage and "
            "arithmetic. It does not automatically extract PDF cells or independently prove "
            "the manual transcription. Source-page review is documented separately."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".cml-benchmarks-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        artifacts = []
        for filename, rows in {
            "published_observations.csv": observations,
            "arithmetic_checks.csv": arithmetic,
        }.items():
            path = staging / filename
            with path.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            artifacts.append(fingerprint(output / filename, path.read_bytes()))
        report["outputs"] = artifacts
        (staging / "audit.json").write_bytes(
            (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"benchmark output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/cml_benchmarks_2026-10-03.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.config, args.output)


if __name__ == "__main__":
    main()
