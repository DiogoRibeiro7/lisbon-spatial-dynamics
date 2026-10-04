"""Extract an attributed annual CPI reference from a pinned local INE acquisition."""

from __future__ import annotations

import argparse
import json
import tomllib
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from lisbon_spatial_dynamics.transformations.cpi import CPI_CODE, extract_cpi_reference


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def build(config_path: Path, output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"CPI reference already exists: {output}")
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
    if manifest["indicator_code"] != CPI_CODE or acquisition["code"] != CPI_CODE:
        raise ValueError("CPI acquisition indicator differs")
    for name in ("data", "metadata"):
        resource = manifest["resources"][name]
        if (
            any(resource[key] != inputs[name][key] for key in ("path", "sha256", "size_bytes"))
            or resource["url"] != acquisition[f"{name}_url"]
        ):
            raise ValueError("CPI acquisition provenance differs")
    csv_bytes = extract_cpi_reference(
        captured["data"], captured["metadata"], config["years"]
    ).encode("utf-8")
    provenance = {
        "schema_version": 1,
        "analysis_date": config["analysis_date"],
        "years": config["years"],
        "attribution": (
            "Instituto Nacional de Estatística (INE), annual CPI indicator 0014642, "
            "Portugal, Total, base 2025."
        ),
        "licence": "CC-BY-4.0",
        "licence_source": "https://dados.gov.pt/pt/datasets/indice-de-precos-no-consumidor-ipc-base-2025-0014642",
        "inputs": inputs,
        "acquisition": manifest,
        "transformation": (
            "Select the explicitly requested national Total annual observations; preserve "
            "published numeric index values. No base splicing or inflation-rate compounding."
        ),
        "archive_scope": (
            "Canonical CSV committed; original JSON responses retained locally outside Git."
        ),
        "output": fingerprint(output / "annual_cpi.csv", csv_bytes),
        "code_and_configuration": [
            fingerprint(config_path, config_bytes),
            *(
                fingerprint(path, path.read_bytes())
                for path in (
                    Path(__file__).resolve().relative_to(Path.cwd().resolve()),
                    Path("src/lisbon_spatial_dynamics/transformations/cpi.py"),
                    Path("src/lisbon_spatial_dynamics/sources/ine.py"),
                )
            ),
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".cpi-reference-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        (staging / "annual_cpi.csv").write_bytes(csv_bytes)
        (staging / "provenance.json").write_bytes(
            (
                json.dumps(
                    provenance, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
                )
                + "\n"
            ).encode("utf-8")
        )
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"CPI reference already exists: {output}")
        staging.rename(output)
    print(csv_bytes.decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/cpi_reference_2026-10-04.toml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.config, args.output)


if __name__ == "__main__":
    main()
