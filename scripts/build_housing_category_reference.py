"""Extract a canonical dwelling-category table from the pinned local INE capture."""

from __future__ import annotations

import argparse
import json
import tomllib
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.analysis.cml_benchmarks import parse_reference
from lisbon_spatial_dynamics.transformations.housing_categories import extract_category_reference


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def build(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"category reference already exists: {output}")
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
    if manifest["indicator_code"] != "0012234" or acquisition["code"] != "0012234":
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
    payload = extract_category_reference(
        captured["data"], captured["metadata"], reference, config["years"]
    ).encode("utf-8")
    report = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "years": config["years"],
        "attribution": (
            "Instituto Nacional de Estatística (INE), indicator 0012234, "
            "dwelling-category sale medians, methodology 2022, NUTS 2024."
        ),
        "licence": "CC-BY-4.0",
        "licence_source": "https://dados.gov.pt/datasets/valor-mediano-das-vendas-de-alojamentos-familiares-nos-ultimos-12-meses-metodologia-2022-eur-m2",
        "inputs": inputs,
        "acquisition": manifest,
        "transformation": (
            "Select the configured Q4 periods and canonical parishes with H1/H11/H12. "
            "Preserve every published median and explicit missing-value flag; no imputation."
        ),
        "archive_scope": (
            "Canonical aggregate CSV committed; original JSON responses "
            "retained locally outside Git."
        ),
        "output": fingerprint(output / "category_panel.csv", payload),
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/transformations/housing_categories.py"),
                    Path("src/lisbon_spatial_dynamics/analysis/cml_benchmarks.py"),
                    Path("src/lisbon_spatial_dynamics/sources/ine.py"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".housing-category-reference-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        (staging / "category_panel.csv").write_bytes(payload)
        (staging / "provenance.json").write_bytes(
            (
                json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8")
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"category reference already exists: {output}")
        staging.rename(output)
    print(f"Published category reference: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/housing_category_reference_2026-10-04.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.config, args.output)


if __name__ == "__main__":
    main()
