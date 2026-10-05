"""Publish historical accommodation-capacity context from committed audited aggregates."""

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

from lisbon_spatial_dynamics.analysis.historical_capacity import (
    analyse_historical_capacity,
    plot_historical_capacity,
)


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def analyse(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"historical capacity output already exists: {output}")
    config_bytes = config_path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    inputs, captured = {}, {}
    for name, pinned in config["inputs"].items():
        path = Path(pinned["path"])
        payload = path.read_bytes()
        actual = fingerprint(path, payload)
        if any(actual[key] != pinned[key] for key in ("sha256", "size_bytes")):
            raise ValueError(f"input integrity mismatch: {path}")
        inputs[name], captured[name] = actual, payload
    parent = json.loads(captured["benchmark_report"])
    source_audit = json.loads(captured["source_audit"])
    if (
        inputs["reference"] != parent["inputs"]["reference"]
        or inputs["transcription"] != parent["inputs"]["transcription"]
        or inputs["reference"] not in source_audit["outputs"]
        or parent["source"]["reference_months"] != ["2019-11", "2022-11"]
    ):
        raise ValueError("benchmark or Census provenance links differ")
    summary, tables, benchmark = analyse_historical_capacity(
        captured["transcription"].decode("utf-8"),
        captured["reference"].decode("utf-8"),
        expected_parishes=config["parishes"],
        baseline_top_n=config["baseline_top_n"],
    )
    if benchmark != parent["summary"]:
        raise ValueError("replayed benchmark summary differs from published audit")
    census = source_audit["census"]
    if (
        census["year"] != 2021
        or census["parishes"] != summary["parishes"]
        or census["population_resident"] != summary["municipality"]["population_resident_2021"]
        or census["municipality_population_check"]["passed"] is not True
    ):
        raise ValueError("population denominator differs from the audited Census")
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "benchmark_summary_verified": True,
        "census_total_verified": True,
        "source": parent["source"],
        "source_document_recorded_by_parent": parent["inputs"]["source_pdf"],
        "attribution": (
            "Câmara Municipal de Lisboa, December 2022 monitoring report, table 19 "
            "(underlying Turismo de Portugal/RNAL data); "
            "Instituto Nacional de Estatística, Censos 2021."
        ),
        "interpretation": {
            "measure": (
                "Reported user-capacity places from table 19; "
                "not establishments or weighted AL units."
            ),
            "denominator": (
                "Capacity * 1000 / resident population in Census 2021, "
                "held fixed for both source months."
            ),
            "change": "(Capacity_2022_11 - Capacity_2019_11) * 1000 / Population_2021.",
            "municipality": (
                "Sum parish capacities and populations before division; "
                "do not average parish ratios."
            ),
            "dates": (
                "November 2019 and November 2022; exact observation days are unspecified. "
                "No Q4 relabelling or interpolation."
            ),
            "cohort": (
                "Select the configured number of largest-capacity parishes at baseline; "
                "break ties by parish ID. Hold membership fixed at the later month."
            ),
            "shares": (
                "Group capacity / municipality capacity * 100; share change is in percentage "
                "points. This denominator differs from the population reference."
            ),
            "limits": (
                "Reported capacity is not occupancy, visitors, overnight stays or verified "
                "operation. Ratios can exceed 1000 and are not percentages. "
                "No contemporaneous per-capita, housing association, RNAL stock reconstruction "
                "or causal estimate."
            ),
            "archive": (
                "Replay uses committed aggregate facts and pinned audit reports. It does not "
                "reopen the locally retained PDF or Census workbook; transcription requires "
                "source-page review. No source-document redistribution licence is asserted."
            ),
            "precision": (
                "Fresh Decimal precision-28 context; decimal CSV values "
                "and numeric float JSON summaries."
            ),
        },
        "software": {"python": platform.python_version(), "matplotlib": version("matplotlib")},
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/analysis/historical_capacity.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".historical-capacity-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name, rows in tables.items():
            with (staging / name).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        plot_historical_capacity(tables["parish_capacity.csv"], staging / "historical_capacity.png")
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
            raise FileExistsError(f"historical capacity output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/historical_capacity_2026-10-05.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
