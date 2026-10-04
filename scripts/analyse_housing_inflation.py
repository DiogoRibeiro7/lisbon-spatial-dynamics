"""Replay CPI-adjusted housing evidence from committed aggregate inputs."""

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
from lisbon_spatial_dynamics.analysis.housing_inflation import (
    analyse_housing_inflation,
    plot_housing_inflation,
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
        raise FileExistsError(f"inflation output already exists: {output}")
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
    housing_report = json.loads(captured["housing_report"])
    audit = json.loads(captured["source_audit"])
    cpi = json.loads(captured["cpi_provenance"])
    if (
        inputs["cpi"] != cpi["output"]
        or inputs["source_audit"] != housing_report["inputs"]["source_audit"]
        or any(
            inputs[name] != housing_report["inputs"][name] or inputs[name] not in audit["outputs"]
            for name in ("housing", "reference")
        )
    ):
        raise ValueError("input provenance links differ")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    summary, datasets, nominal = analyse_housing_inflation(
        parse_housing_panel_csv(captured["housing"].decode("utf-8")),
        reference,
        captured["cpi"].decode("utf-8"),
        baseline_year=config["baseline_year"],
        latest_year=config["latest_year"],
    )
    if nominal != housing_report["summary"] or cpi["years"] != list(
        range(config["baseline_year"], config["latest_year"] + 1)
    ):
        raise ValueError("nominal evidence or CPI comparison window differs")
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "nominal_summary_verified": True,
        "cpi_attribution": cpi["attribution"],
        "cpi_licence": cpi["licence"],
        "interpretation": {
            "adjustment": (
                "Housing_t * annual_CPI_baseline / annual_CPI_t, in baseline-year euros per m2."
            ),
            "timing": (
                "Q4 housing medians cover the preceding calendar year; "
                "use annual national CPI averages, not December CPI."
            ),
            "precision": (
                "Decimal precision 28; preserve decimal CSV values, "
                "use numeric floats in JSON summary."
            ),
            "scope": (
                "A national consumption-price adjustment to published parish sale medians; "
                "not local inflation, income affordability or fixed-dwelling appreciation."
            ),
            "aggregation": (
                "Equal-parish summaries; a median of parish medians "
                "is not a municipal transaction median."
            ),
            "limits": (
                "Does not deflate individual transactions before computing their median "
                "or control for changes in sold-property composition. "
                "No RNAL effect or causal interpretation."
            ),
            "spatial": (
                "A common endpoint deflator is a positive affine transformation of "
                "percentage changes; standardized values and corresponding Moran results "
                "are unchanged algebraically."
            ),
            "archive": (
                "Replay uses committed housing aggregates and CPI reference; original CPI "
                "JSON is locally retained and linked by the reference provenance, "
                "not publicly archived."
            ),
        },
        "software": {"python": platform.python_version(), "matplotlib": version("matplotlib")},
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_inflation.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_history.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("src/lisbon_spatial_dynamics/transformations/cpi.py"),
                    Path("src/lisbon_spatial_dynamics/panels/temporal.py"),
                    Path("src/lisbon_spatial_dynamics/panels/housing.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-inflation-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name, rows in datasets.items():
            with (staging / name).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        plot_housing_inflation(datasets, staging / "housing_inflation.png")
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
            raise FileExistsError(f"inflation output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_inflation_2026-10-04.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
