"""Extract a canonical sales-count table from the pinned local INE capture."""

from __future__ import annotations

import argparse
import json
import tomllib
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import parse_reference
from lisbon_spatial_dynamics.transformations.housing_sales import extract_sales_reference


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def build(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"sales reference already exists: {output}")
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
    manifest = json.loads(captured["manifest"])
    acquisition = tomllib.loads(captured["acquisition_config"].decode("utf-8"))["indicator"]
    if manifest["indicator_code"] != "0014363" or acquisition["code"] != "0014363":
        raise ValueError("housing acquisition indicator differs")
    for name in ("data", "metadata"):
        resource = manifest["resources"][name]
        if (
            any(resource[key] != inputs[name][key] for key in ("path", "sha256", "size_bytes"))
            or resource["url"] != acquisition[f"{name}_url"]
        ):
            raise ValueError("housing acquisition provenance differs")
    reference = parse_reference(
        captured["reference"].decode("utf-8"), expected_count=config["parishes"]
    )
    payload = extract_sales_reference(
        captured["data"], captured["metadata"], reference, config["years"]
    ).encode("utf-8")
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "years": config["years"],
        "attribution": (
            "Instituto Nacional de Estatística (INE), indicator 0014363, "
            "rolling-year sales counts, methodology 2022, NUTS 2024."
        ),
        "licence": "CC-BY-4.0",
        "licence_source": "https://dados.gov.pt/pt/datasets/vendas-de-alojamentos-familiares-nos-ultimos-12-meses-metodologia-2022-n-o",
        "inputs": inputs,
        "acquisition": manifest,
        "transformation": (
            "Select configured Q4 periods, Lisbon municipality and its canonical parishes. "
            "Require published integer counts and reconcile parish sums with city totals. "
            "No imputation; each Q4 count covers the preceding 12 months."
        ),
        "archive_scope": (
            "Canonical aggregate CSV committed; original JSON responses "
            "retained locally outside Git."
        ),
        "output": fingerprint(output / "sales_panel.csv", payload),
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/transformations/housing_sales.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("src/lisbon_spatial_dynamics/sources/ine.py"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-sales-reference-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        (staging / "sales_panel.csv").write_bytes(payload)
        (staging / "provenance.json").write_bytes(
            (
                json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8")
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"sales reference already exists: {output}")
        staging.rename(output)
    print(f"Published sales reference: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_sales_reference_2026-10-05.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.config, args.output)


if __name__ == "__main__":
    main()
