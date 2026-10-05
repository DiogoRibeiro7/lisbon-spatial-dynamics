"""Replay municipality housing-distribution context from the committed quartile reference."""

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

from lisbon_spatial_dynamics.analysis.housing_distribution import (
    analyse_housing_distribution,
    plot_housing_distribution,
)


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def analyse(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"distribution analysis already exists: {output}")
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
    provenance = json.loads(captured["quartile_provenance"])
    if (
        inputs["quartiles"] != provenance["output"]
        or provenance["years"] != list(range(config["baseline_year"], config["latest_year"] + 1))
        or provenance["acquisition"]["indicator_code"] != "0013042"
    ):
        raise ValueError("quartile provenance links or annual window differ")
    summary, tables = analyse_housing_distribution(
        captured["quartiles"].decode("utf-8"),
        baseline_year=config["baseline_year"],
        latest_year=config["latest_year"],
    )
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "attribution": provenance["attribution"],
        "licence": provenance["licence"],
        "captured_at": provenance["acquisition"]["fetched_at"],
        "software": {"python": platform.python_version(), "matplotlib": version("matplotlib")},
        "interpretation": {
            "scope": "Published annual EUR/m2 quartiles for Lisbon municipality, INE 0013042.",
            "quantiles": "Q1, Q2 and Q3 are the 25th, 50th and 75th percentiles; Q2 is the median.",
            "absolute_spread": "Interquartile range (IQR) = Q3 - Q1, in EUR/m2.",
            "relative_spread": (
                "100 * (Q3 - Q1) / Q2, expressed as percent of the same year's median. "
                "Its endpoint difference is in percentage points."
            ),
            "changes": (
                "100 * (latest - baseline) / baseline for each quartile and the IQR. "
                "A zero baseline IQR gives undefined percentage change; absolute change remains."
            ),
            "figure": (
                "The shaded Q1-Q3 band is a transaction-distribution range, not a confidence "
                "interval. Each indexed line uses its own quartile's baseline as 100."
            ),
            "limits": (
                "Municipal quantiles cannot be assigned to parishes or reconstructed from parish "
                "medians. Municipal median change and median parish change are different "
                "statistics. Quantiles do not track the same dwellings over time. "
                "No fixed-quality, inflation, affordability, income-inequality, composition "
                "or RNAL effect is estimated."
            ),
            "archive": (
                "Replay consumes committed aggregates. Raw source responses remain locally "
                "retained outside Git and are linked by the reference provenance."
            ),
            "precision": "Fresh Decimal precision-28 context; decimal CSVs and float JSON.",
        },
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_distribution.py"),
                    Path("src/lisbon_spatial_dynamics/transformations/housing_quartiles.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-distribution-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name, rows in tables.items():
            with (staging / name).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        plot_housing_distribution(tables, staging / "housing_distribution.png")
        report["outputs"] = [
            fingerprint(output / path.name, path.read_bytes()) for path in sorted(staging.iterdir())
        ]
        (staging / "analysis.json").write_bytes(
            (
                json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8")
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"distribution analysis already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_distribution_2026-10-05.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
