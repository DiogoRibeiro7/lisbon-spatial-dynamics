"""Replay housing-only spatial diagnostics from committed housing and CAOP inputs."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import tomllib
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import parse_reference
from lisbon_spatial_dynamics.analysis.housing_spatial import build_housing_map, plot_housing_spatial
from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    analyse_local_moran_metric,
    write_local_morans_i_json,
)
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    analyse_global_moran_metric,
    build_queen_weights,
    write_morans_i_json,
)


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def analyse(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"spatial output already exists: {output}")
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
    geography = json.loads(captured["geometry_provenance"])
    source_audit = json.loads(captured["source_audit"])
    if (
        inputs["housing"] not in housing_report["outputs"]
        or inputs["reference"] != housing_report["inputs"]["reference"]
        or inputs["source_audit"] != housing_report["inputs"]["source_audit"]
        or inputs["reference"] not in source_audit["outputs"]
        or inputs["geometry"] != geography["archived"]
        or inputs["source_audit"] != geography["parent_audit"]
        or geography["original_canonical"] != source_audit["inputs"]["reference_geojson"]
        or geography["source_acquisition"] != source_audit["acquisition"]["geography"]["content"]
    ):
        raise ValueError("input provenance chain differs")
    if any(
        housing_report["summary"][key] != config[key]
        for key in ("baseline_year", "latest_year", "parishes")
    ):
        raise ValueError("housing report comparison window or coverage differs")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    data = build_housing_map(
        captured["housing"].decode("utf-8"),
        captured["geometry"].decode("utf-8"),
        reference,
        baseline_year=config["baseline_year"],
        latest_year=config["latest_year"],
    )
    global_result = analyse_global_moran_metric(
        data,
        metric="housing_change_pct",
        permutations=config["permutations"],
        seed=config["seed"],
    )
    local_result = analyse_local_moran_metric(
        data,
        metric="housing_change_pct",
        permutations=config["permutations"],
        seed=config["seed"],
        alpha=config["alpha"],
    )
    weights = build_queen_weights(data)
    pairs = [
        {
            "left_id": left,
            "right_id": right,
            "weight_left_to_right": 1 / len(weights.neighbors[left]),
            "weight_right_to_left": 1 / len(weights.neighbors[right]),
        }
        for left, neighbors in sorted(weights.neighbors.items())
        for right in neighbors
        if left < right
    ]
    local_rows = [
        {"map_label": index, **asdict(row)}
        for index, row in enumerate(local_result.observations, start=1)
    ]
    summary = {
        "baseline_year": data.baseline_year,
        "latest_year": data.latest_year,
        "parishes": len(data.features),
        "queen_pairs": weights.edge_count,
        "islands": list(global_result.islands),
        "global_morans_i": global_result.morans_i,
        "global_expected_i": global_result.expected_i,
        "global_permutation_p_two_sided": global_result.permutation_p_two_sided,
        "local_raw_p_at_or_below_alpha": sum(
            row.permutation_p_two_sided is not None
            and row.permutation_p_two_sided <= config["alpha"]
            for row in local_result.observations
        ),
        "local_significant_fdr": [
            {
                key: row[key]
                for key in (
                    "freguesia_id",
                    "freguesia_name",
                    "cluster_class",
                    "permutation_p_two_sided",
                    "fdr_q",
                )
            }
            for row in local_rows
            if row["significant_fdr"]
        ],
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "summary": summary,
        "inputs": inputs,
        "parameters": {key: config[key] for key in ("permutations", "seed", "alpha")},
        "interpretation": {
            "metric": (
                f"Nominal Q4-{data.baseline_year} to Q4-{data.latest_year} housing "
                "percentage change; no RNAL observations."
            ),
            "weights": (
                "Queen boundary contact, row-standardized; no snapping, buffer or distance cutoff."
            ),
            "global_null": "Randomly permute housing values; compare distance from -1/(n-1).",
            "local_null": (
                "Hold focal standardized value fixed; sample other values without "
                "replacement; compare absolute local I."
            ),
            "multiplicity": (
                "Benjamini-Hochberg across the housing local tests, at configured alpha."
            ),
            "map": (
                "Original topology in EPSG:4326; display reprojected "
                "to EPSG:3763 without simplification."
            ),
            "scope": (
                "Descriptive spatial association under one boundary/weight definition; "
                "no causal or RNAL effect."
            ),
            "archive": (
                "All replay inputs committed; original raw acquisitions "
                "are not re-downloaded or re-transformed."
            ),
        },
        "geography_attribution": geography["attribution"],
        "geography_licence": geography["licence"],
        "software": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("shapely", "pyproj", "matplotlib")},
        },
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).relative_to(Path.cwd()),
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
    with TemporaryDirectory(prefix=".housing-spatial-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        write_morans_i_json([global_result], staging / "global_moran.json")
        write_local_morans_i_json([local_result], staging / "local_moran.json")
        for path in staging.glob("*.json"):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        for filename, rows in {"queen_pairs.csv": pairs, "local_results.csv": local_rows}.items():
            with (staging / filename).open("x", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        plot_housing_spatial(data, local_result, staging / "housing_spatial.png")
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
            raise FileExistsError(f"spatial output already exists: {output}")
        staging.rename(output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_spatial_2026-10-04.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.config, args.output)


if __name__ == "__main__":
    main()
