"""Replay the fixed housing spatial sensitivity specification from committed inputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import tomllib
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import parse_reference
from lisbon_spatial_dynamics.analysis.housing_spatial_sensitivity import (
    CONTIGUITIES,
    METRICS,
    analyse_housing_sensitivity,
    plot_housing_sensitivity,
)


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def analyse(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"sensitivity output already exists: {output}")
    config_bytes = config_path.read_bytes()
    config = tomllib.loads(config_bytes.decode("utf-8"))
    if tuple(config["metrics"]) != METRICS or tuple(config["contiguities"]) != CONTIGUITIES:
        raise ValueError("the declared six-scenario specification differs")
    captured, inputs = {}, {}
    for name, pinned in config["inputs"].items():
        path = Path(pinned["path"])
        payload = path.read_bytes()
        actual = fingerprint(path, payload)
        if any(actual[key] != pinned[key] for key in ("sha256", "size_bytes")):
            raise ValueError(f"input integrity mismatch: {path}")
        captured[name], inputs[name] = payload, actual
    parent = json.loads(captured["spatial_report"])
    if any(inputs[name] != parent["inputs"][name] for name in ("housing", "geometry", "reference")):
        raise ValueError("primary spatial report input links differ")
    if any(
        parent["summary"][key] != config[key]
        for key in ("baseline_year", "latest_year", "parishes")
    ):
        raise ValueError("primary spatial comparison window or coverage differs")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    summary, datasets = analyse_housing_sensitivity(
        captured["housing"].decode("utf-8"),
        captured["geometry"].decode("utf-8"),
        reference,
        baseline_year=config["baseline_year"],
        latest_year=config["latest_year"],
        permutations=config["permutations"],
        seed=config["seed"],
        alpha=config["alpha"],
    )
    primary = datasets["global_scenarios.csv"][0]
    if not math.isclose(primary["morans_i"], parent["summary"]["global_morans_i"], abs_tol=1e-12):
        raise ValueError("primary global statistic does not reproduce")
    same_randomization = all(
        config[key] == parent["parameters"][key] for key in ("permutations", "seed")
    )
    if (
        same_randomization
        and primary["permutation_p_two_sided"]
        != parent["summary"]["global_permutation_p_two_sided"]
    ):
        raise ValueError("primary permutation p-value does not reproduce")
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "parameters": {
            key: config[key] for key in ("metrics", "contiguities", "permutations", "seed", "alpha")
        },
        "primary_reproduction": {
            "statistic_verified": True,
            "p_value_verified": same_randomization,
        },
        "geography_attribution": parent["geography_attribution"],
        "geography_licence": parent["geography_licence"],
        "interpretation": {
            "design": (
                "Exploratory follow-up to the known primary result; "
                "all six scenarios fixed before their computation."
            ),
            "metrics": (
                "Percentage change, natural log(latest)-log(baseline), "
                "and nominal EUR/m2 difference; distinct estimands."
            ),
            "weights": (
                "Queen boundary contact; rook additionally requires positive "
                "shared-boundary length; row standardized, no snapping or buffers."
            ),
            "global_test": (
                "Same seed/shuffle sequence for every scenario; "
                "distance from -1/(n-1), (extreme+1)/(permutations+1)."
            ),
            "multiplicity": (
                "Holm step-down Bonferroni adjustment across all six global scenarios, "
                "including any duplicate graphs."
            ),
            "influence": (
                "Queen/percentage only; remove one parish, induce remaining graph and "
                "renormalize rows; recompute centring and n/S0. "
                "No omission p-values or confidence intervals."
            ),
            "islands": (
                "Retained with zero-weight rows; no replacement links. "
                "Island codes are recorded in output tables."
            ),
            "limits": (
                "No local retesting, historical-boundary sensitivity, "
                "inflation/composition adjustment, causal inference or RNAL effect."
            ),
            "archive": (
                "Verified committed aggregates and polygons linked to the primary spatial "
                "report; no raw-source reacquisition or transformation."
            ),
        },
        "software": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("numpy", "shapely", "matplotlib")},
        },
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).relative_to(Path.cwd()),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_spatial_sensitivity.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/housing_spatial.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/spatial_autocorrelation.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/local_spatial_autocorrelation.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("src/lisbon_spatial_dynamics/spatial/trajectory_choropleths.py"),
                    Path("pyproject.toml"),
                    Path("poetry.lock"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-sensitivity-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name, rows in datasets.items():
            with (staging / name).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        plot_housing_sensitivity(
            datasets,
            staging / "sensitivity.png",
            baseline_year=config["baseline_year"],
            latest_year=config["latest_year"],
        )
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
            raise FileExistsError(f"sensitivity output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_spatial_sensitivity_2026-10-04.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
