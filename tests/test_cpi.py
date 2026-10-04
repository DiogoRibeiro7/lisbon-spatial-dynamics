"""Annual national CPI extraction must reject altered scope, base and coverage."""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.transformations.cpi import (
    CPI_TITLE,
    extract_cpi_reference,
    parse_cpi_reference,
)


def source() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    success = {"Verdadeiro": [{"Msg": "OK"}]}
    data = [
        {
            "IndicadorCod": "0014642",
            "IndicadorDsg": CPI_TITLE,
            "Sucesso": success,
            "Dados": {
                str(y): [
                    {
                        "geocod": "PT",
                        "geodsg": "Portugal",
                        "dim_3": "T",
                        "dim_3_t": "Total",
                        "valor": v,
                        "ind_string": v.replace(".", ","),
                    }
                ]
                for y, v in [(2024, "97.717"), (2025, "100")]
            },
        }
    ]
    meta = [
        {
            "IndicadorCod": "0014642",
            "IndicadorNome": CPI_TITLE,
            "Sucesso": success,
            "Periodic": "Anual",
            "Potencia10": "0",
            "PrecisaoDecimal": "3",
            "Dimensoes": {
                "Categoria_Dim": [
                    {
                        f"Dim_Num{dim}_{code}": [
                            {"dim_num": str(dim), "categ_cod": code, "categ_dsg": name}
                        ]
                        for dim, code, name in [
                            (1, "S7A2024", "2024"),
                            (1, "S7A2025", "2025"),
                            (2, "PT", "Portugal"),
                            (3, "T", "Total"),
                        ]
                    }
                ]
            },
        }
    ]
    return data, meta


def extract(data: Any, meta: Any) -> str:
    return extract_cpi_reference(json.dumps(data).encode(), json.dumps(meta).encode(), [2024, 2025])


def test_extract_preserves_published_values_and_canonical_scope() -> None:
    text = extract(*source())
    assert "2024,0014642,2025,PT,Portugal,T,Total,97.717\n" in text
    assert parse_cpi_reference(text, [2024, 2025]) == {2024: Decimal("97.717"), 2025: Decimal(100)}


@pytest.mark.parametrize(
    "failure",
    [
        "root",
        "success",
        "indicator",
        "frequency",
        "dimension",
        "missing",
        "duplicate",
        "scope",
        "flag",
        "displayed",
        "null",
    ],
)
def test_ine_payload_contract_failures(failure: str) -> None:
    data, meta = source()
    row = data[0]["Dados"]["2024"][0]
    if failure == "root":
        with pytest.raises(ValueError):
            extract({}, meta)
        return
    if failure == "success":
        data[0]["Sucesso"] = {"Falso": []}
    elif failure == "indicator":
        data[0]["IndicadorCod"] = "0003863"
    elif failure == "frequency":
        meta[0]["Periodic"] = "Mensal"
    elif failure == "dimension":
        meta[0]["Dimensoes"] = None
    elif failure == "missing":
        data[0]["Dados"].pop("2024")
    elif failure == "duplicate":
        data[0]["Dados"]["2024"].append(row)
    elif failure == "scope":
        row["geocod"] = "1"
    elif failure == "flag":
        row["sinal_conv"] = "x"
    elif failure == "displayed":
        row["ind_string"] = "97,000"
    else:
        row["valor"] = None
    with pytest.raises(ValueError):
        extract(data, meta)


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "not-a-number"])
def test_nonpositive_or_nonfinite_cpi_fails(value: str) -> None:
    text = extract(*source()).replace("97.717", value)
    with pytest.raises(ValueError):
        parse_cpi_reference(text, [2024, 2025])


@pytest.mark.parametrize(
    "failure", ["base", "base_value", "geography", "aggregate", "year", "missing", "ragged"]
)
def test_reference_scope_and_coverage_are_explicit(failure: str) -> None:
    text = extract(*source())
    if failure == "base":
        text = text.replace(",2025,PT", ",2012,PT")
    elif failure == "base_value":
        text = text.replace(",100\n", ",99\n")
    elif failure == "geography":
        text = text.replace(",PT,Portugal", ",1,Continente")
    elif failure == "aggregate":
        text = text.replace(",T,Total", ",001,Total exceto habitação")
    elif failure == "year":
        text = text.replace("2024,0014642", "2025,0014642")
    elif failure == "missing":
        text = "\n".join(text.splitlines()[:2]) + "\n"
    else:
        text = text.replace(",97.717", "")
    with pytest.raises(ValueError):
        parse_cpi_reference(text, [2024, 2025])


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/build_cpi_reference.py"
    spec = importlib.util.spec_from_file_location("cpi_reference_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_config(tmp_path: Path, *, bad_link: bool = False) -> Path:
    data, metadata = source()
    resources = {}
    inputs = {}
    for name, document in [("data", data), ("metadata", metadata)]:
        path = tmp_path / f"{name}.json"
        payload = json.dumps(document).encode()
        path.write_bytes(payload)
        inputs[name] = {
            "path": path.as_posix(),
            "sha256": sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
        resources[name] = {**inputs[name], "url": f"https://example.test/{name}"}
    if bad_link:
        resources["data"]["sha256"] = "0" * 64
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"indicator_code": "0014642", "resources": resources}), encoding="utf-8"
    )
    acquisition = tmp_path / "acquisition.toml"
    acquisition.write_text(
        '[indicator]\ncode="0014642"\ndata_url="https://example.test/data"\nmetadata_url="https://example.test/metadata"\n',
        encoding="utf-8",
    )
    for name, path in [("manifest", manifest), ("acquisition_config", acquisition)]:
        payload = path.read_bytes()
        inputs[name] = {
            "path": path.as_posix(),
            "sha256": sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    text = 'analysis_date="2026-10-04"\nyears=[2024,2025]\n'
    for name, record in inputs.items():
        text += (
            f'\n[inputs.{name}]\npath="{record["path"]}"\n'
            f'sha256="{record["sha256"]}"\nsize_bytes={record["size_bytes"]}\n'
        )
    config = tmp_path / "config.toml"
    config.write_text(text, encoding="utf-8")
    return config


def test_raw_reference_replay_verifies_manifest_and_refuses_overwrite(
    tmp_path: Path, script: ModuleType
) -> None:
    config = raw_config(tmp_path)
    output = tmp_path / "reference"
    script.build(config, output)
    assert set(p.name for p in output.iterdir()) == {"annual_cpi.csv", "provenance.json"}
    report = json.loads((output / "provenance.json").read_bytes())
    assert (
        sha256((output / "annual_cpi.csv").read_bytes()).hexdigest() == report["output"]["sha256"]
    )
    with pytest.raises(FileExistsError):
        script.build(config, output)


def test_rehashed_manifest_with_broken_data_link_fails(tmp_path: Path, script: ModuleType) -> None:
    output = tmp_path / "reference"
    with pytest.raises(ValueError, match="provenance"):
        script.build(raw_config(tmp_path, bad_link=True), output)
    assert not output.exists()
