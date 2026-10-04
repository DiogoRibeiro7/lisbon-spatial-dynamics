"""Publish Q4 housing evidence using only the committed primary-source audit bundle."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import tomllib
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import parse_reference
from lisbon_spatial_dynamics.analysis.housing_history import (
    analyse_housing_history,
    plot_housing_changes,
)
from lisbon_spatial_dynamics.panels.temporal import parse_housing_panel_csv


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def analyse(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"housing output already exists: {output}")
    config_bytes = config_path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    captured, inputs = {}, {}
    for name, pinned in config["inputs"].items():
        path = Path(pinned["path"])
        payload = path.read_bytes()
        actual = fingerprint(path, payload)
        if any(actual[key] != pinned[key] for key in ("sha256", "size_bytes")):
            raise ValueError(f"input integrity mismatch: {path}")
        captured[name], inputs[name] = payload, actual
    parent = json.loads(captured["source_audit"])
    for name in ("housing", "reference"):
        if inputs[name] not in parent["outputs"]:
            raise ValueError(f"source audit does not identify the pinned {name} input")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    rows = parse_housing_panel_csv(captured["housing"].decode("utf-8"))
    summary, datasets = analyse_housing_history(
        rows, reference, baseline_year=config["baseline_year"], latest_year=config["latest_year"]
    )
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "housing_acquisition": parent["acquisition"]["housing"]["content"],
        "software": {"python": platform.python_version(), "matplotlib": version("matplotlib")},
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).relative_to(Path.cwd()),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_history.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("src/lisbon_spatial_dynamics/panels/housing.py"),
                    Path("src/lisbon_spatial_dynamics/panels/temporal.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
        "interpretation": {
            "measure": "Nominal median dwelling sale value per m² in the preceding 12 months.",
            "category": "Total dwellings (H1), INE indicator 0012234.",
            "geography": "24 canonical Lisbon parishes, matched in the original CAOP2025 audit.",
            "aggregation": (
                "Each parish has equal weight; a median of parish medians "
                "is not the municipal median."
            ),
            "change": "100 * (latest Q4 / baseline Q4 - 1), using each parish's own baseline.",
            "limitations": (
                "No inflation adjustment, transaction-composition adjustment, "
                "RNAL association or causal claim."
            ),
            "precision": (
                "Decimal arithmetic at precision 28; CSV preserves decimals; "
                "JSON summary uses numeric floats."
            ),
            "archive_scope": (
                "Replay uses committed aggregates; original INE files remain "
                "locally retained, not publicly archived."
            ),
            "verification_scope": (
                "Verifies aggregate bytes against the pinned parent audit; "
                "does not re-fetch or re-transform the raw INE capture."
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-history-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for filename, values in datasets.items():
            with (staging / filename).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(values[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(values)
        plot_housing_changes(datasets["parish_changes.csv"], staging / "housing_changes.png")
        report["outputs"] = [
            fingerprint(output / path.name, path.read_bytes()) for path in sorted(staging.iterdir())
        ]
        (staging / "analysis.json").write_bytes(
            (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
                "utf-8"
            )
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"housing output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_history_2026-10-04.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
