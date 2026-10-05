"""Replay sales-volume context alongside the committed nominal housing evidence."""

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
from lisbon_spatial_dynamics.analysis.housing_sales import analyse_housing_sales, plot_housing_sales
from lisbon_spatial_dynamics.panels.temporal import parse_housing_panel_csv


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def analyse(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"sales analysis already exists: {output}")
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
    provenance = json.loads(captured["sales_provenance"])
    parent = json.loads(captured["housing_report"])
    audit = json.loads(captured["source_audit"])
    if (
        inputs["sales"] != provenance["output"]
        or inputs["reference"] != provenance["inputs"]["reference"]
        or inputs["source_audit"] != parent["inputs"]["source_audit"]
        or any(
            inputs[name] != parent["inputs"][name] or inputs[name] not in audit["outputs"]
            for name in ("housing", "reference")
        )
        or provenance["years"] != list(range(config["baseline_year"], config["latest_year"] + 1))
    ):
        raise ValueError("sales or nominal provenance links differ")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    summary, tables, nominal = analyse_housing_sales(
        captured["sales"].decode("utf-8"),
        parse_housing_panel_csv(captured["housing"].decode("utf-8")),
        reference,
        baseline_year=config["baseline_year"],
        latest_year=config["latest_year"],
    )
    if nominal != parent["summary"]:
        raise ValueError("nominal summary differs from published evidence")
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "nominal_summary_verified": True,
        "capture_dates": {
            "sales": provenance["acquisition"]["fetched_at"],
            "sale_medians": parent["housing_acquisition"]["fetched_at"],
        },
        "attribution": provenance["attribution"] + " Sale medians: INE 0012234.",
        "licence": provenance["licence"],
        "software": {"python": platform.python_version(), "matplotlib": version("matplotlib")},
        "interpretation": {
            "counts": "INE 0014363 published sales in the preceding 12 months, observed at Q4.",
            "medians": "INE 0012234 Total dwelling sale median EUR/m2, same annual windows.",
            "alignment": (
                "Successive Q4 observations cover non-overlapping annual windows. "
                "Q4 counts are annual sales, "
                "not October-December sales. No sum of overlapping quarterly rolling-year counts."
            ),
            "changes": (
                "100 * (latest - baseline) / baseline; a zero parish baseline leaves "
                "percentage change undefined but preserves the absolute change. "
                "City growth uses published city counts, not the mean of parish changes."
            ),
            "shares": "Each parish count divided by the same year's reconciled city count.",
            "limits": (
                "Counts describe transactions, not unique properties or households. No dwelling "
                "category breakdown, sales-mix decomposition, pooled median reconstruction, "
                "constant-quality change, affordability, RNAL effect or causal estimate. "
                "The earlier nominal medians are not replaced or weighted by these counts."
            ),
            "precision": "Fresh Decimal precision-28 context; decimal CSVs and float JSON.",
            "archive": (
                "Replay consumes committed aggregates. Raw INE responses remain locally "
                "retained outside Git with hashes and extraction instructions. "
                "Counts and medians have separate documented capture dates."
            ),
        },
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_sales.py"),
                    Path("src/lisbon_spatial_dynamics/transformations/housing_sales.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_history.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("src/lisbon_spatial_dynamics/panels/temporal.py"),
                    Path("src/lisbon_spatial_dynamics/panels/housing.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-sales-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name, rows in tables.items():
            with (staging / name).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        plot_housing_sales(tables, staging / "housing_sales.png")
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
            raise FileExistsError(f"sales analysis already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_sales_2026-10-05.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
