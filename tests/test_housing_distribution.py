"""Synthetic quantile contracts and offline replay of immutable municipal evidence."""

from __future__ import annotations

import csv
import importlib.util
import json
import runpy
import sys
import tomllib
from decimal import ROUND_UP, Decimal, localcontext
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.housing_distribution import analyse_housing_distribution
from lisbon_spatial_dynamics.transformations.housing_quartiles import (
    COLUMNS,
    INDICATOR,
    QUARTILES,
    TITLE,
    extract_quartile_reference,
    parse_quartile_reference,
)

YEARS = [2019, 2020, 2021]


def source() -> tuple[bytes, bytes]:
    success = {"Verdadeiro": [{"Msg": "OK"}]}
    data = {
        "IndicadorCod": INDICATOR,
        "IndicadorDsg": TITLE,
        "Sucesso": success,
        "Dados": {
            str(year): [
                {
                    "geocod": "1A01106",
                    "geodsg": "Lisboa",
                    "dim_3": str(q),
                    "dim_3_t": QUARTILES[str(q)],
                    "valor": str(value),
                    "ind_string": str(value),
                }
                for q, value in enumerate(values, 1)
            ]
            for year, values in zip(
                YEARS, ((100, 200, 300), (180, 300, 420), (200, 400, 500)), strict=True
            )
        },
    }
    dimensions = [
        (2, "1A01106", "Lisboa"),
        *((1, f"S7A{y}", str(y)) for y in YEARS),
        *((3, code, name) for code, name in QUARTILES.items()),
    ]
    meta = {
        "IndicadorCod": INDICATOR,
        "IndicadorNome": TITLE,
        "Sucesso": success,
        "Periodic": "Anual",
        "UnidadeMedida": "Euro/ Metro quadrado (€/ m²)",
        "Potencia10": "0",
        "PrecisaoDecimal": "0",
        "Dimensoes": {
            "Descricao_Dim": [{"dim_num": str(d)} for d in range(1, 4)],
            "Categoria_Dim": [
                {f"Dim_Num{dim}_{code}": [{"dim_num": str(dim), "cat_id": code, "categ_dsg": name}]}
                for dim, code, name in dimensions
            ],
        },
    }
    return json.dumps([data]).encode(), json.dumps([meta]).encode()


def canonical() -> str:
    return extract_quartile_reference(*source(), YEARS)


def table(rows: list[dict[str, Any]]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def analyse(text: str) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    return analyse_housing_distribution(text, baseline_year=2019, latest_year=2021)


def test_absolute_spread_can_widen_while_relative_spread_shrinks() -> None:
    payload = canonical()
    assert "\r" not in payload and len(parse_quartile_reference(payload, YEARS)) == 9
    summary, tables = analyse(payload)
    annual, endpoints = tables["annual_distribution.csv"], tables["endpoint_changes.csv"]
    assert [r["iqr_eur_m2"] for r in annual] == [200, 240, 300]
    assert [r["iqr_as_pct_of_median"] for r in annual] == [100, 80, 75]
    assert summary["iqr_as_pct_of_median_change_pp"] == -25
    assert endpoints[-1]["change_pct"] == 50
    assert endpoints[0]["change_pct"] == endpoints[1]["change_pct"] == 100
    assert annual[-1]["q1_index_baseline_100"] == annual[-1]["q2_index_baseline_100"] == 200
    assert annual[-1]["q3_index_baseline_100"] == Decimal("166.6666666666666666666666667")
    assert summary["geography_level"] == "municipality"


def test_equal_quartiles_allow_zero_spread_without_dividing_by_zero() -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    for row in rows:
        if row["year"] == "2019":
            row["value_eur_m2"] = "100"
    summary, tables = analyse(table(rows))
    assert summary["baseline_iqr_as_pct_of_median"] == 0
    change = tables["endpoint_changes.csv"][-1]
    assert change["change_eur_m2"] == 300 and change["change_pct"] is None
    json.dumps(summary, allow_nan=False)


def test_order_and_decimal_context_do_not_change_the_evidence() -> None:
    expected = analyse(canonical())
    rows = list(reversed(list(csv.DictReader(StringIO(canonical())))))
    with localcontext() as context:
        context.prec, context.rounding = 3, ROUND_UP
        assert analyse(table(rows)) == expected


@pytest.mark.parametrize(
    "failure",
    [
        "indicator",
        "success",
        "frequency",
        "unit",
        "precision",
        "scale",
        "title",
        "dimension",
        "duplicate_metadata",
        "period",
        "parish",
        "quartile_label",
        "extra_dimension",
        "missing",
        "flagged",
        "display",
        "duplicate",
        "coverage",
    ],
)
def test_extractor_rejects_changed_source_contract(failure: str) -> None:
    data, meta = (json.loads(p)[0] for p in source())
    row = data["Dados"]["2019"][0]
    if failure == "indicator":
        data["IndicadorCod"] = "0012234"
    elif failure == "success":
        meta["Sucesso"] = {}
    elif failure in {"frequency", "unit", "precision", "scale", "title"}:
        key = {
            "frequency": "Periodic",
            "unit": "UnidadeMedida",
            "precision": "PrecisaoDecimal",
            "scale": "Potencia10",
            "title": "IndicadorNome",
        }[failure]
        meta[key] = "wrong"
    elif failure == "dimension":
        meta["Dimensoes"]["Categoria_Dim"][0]["Dim_Num2_1A01106"][0]["categ_dsg"] = "Porto"
    elif failure == "duplicate_metadata":
        meta["Dimensoes"]["Categoria_Dim"].append(meta["Dimensoes"]["Categoria_Dim"][0])
    elif failure == "period":
        data["Dados"]["4.º Trimestre de 2019"] = data["Dados"].pop("2019")
    elif failure == "parish":
        row.update(geocod="1A0110601", geodsg="Ajuda")
    elif failure == "quartile_label":
        row["dim_3_t"] = "3.º quartil"
    elif failure == "extra_dimension":
        row["dim_4"] = "H1"
    elif failure == "missing":
        del row["valor"]
        row["ind_string"] = "-"
    elif failure == "flagged":
        row["sinal_conv"] = "x"
    elif failure == "display":
        row["ind_string"] = "999"
    elif failure == "duplicate":
        data["Dados"]["2019"].append(row)
    else:
        data["Dados"]["2019"].pop()
    with pytest.raises(ValueError):
        extract_quartile_reference(json.dumps([data]).encode(), json.dumps([meta]).encode(), YEARS)


@pytest.mark.parametrize("value", ["", "0", "-1", "1.5", "NaN", "Infinity", "1e3", "１２"])
def test_missing_nonpositive_or_fractional_quartiles_fail(value: str) -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    rows[0]["value_eur_m2"] = value
    with pytest.raises(ValueError, match="positive integers"):
        parse_quartile_reference(table(rows), YEARS)


@pytest.mark.parametrize(
    "failure", ["order", "short", "long", "header", "duplicate", "year", "geography"]
)
def test_canonical_reference_integrity(failure: str) -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    if failure == "order":
        rows[0]["value_eur_m2"] = "201"
    elif failure == "duplicate":
        rows.append(rows[0])
    elif failure == "year":
        rows[0]["year"] = "2022"
    elif failure == "geography":
        rows[0]["geography_code"] = "1A0110601"
    payload = table(rows)
    if failure in {"short", "long"}:
        lines = payload.splitlines()
        lines[1] = lines[1] + ",extra" if failure == "long" else lines[1].rsplit(",", 1)[0]
        payload = "\n".join(lines) + "\n"
    elif failure == "header":
        payload = payload.replace("quartile_name,value_eur_m2", "quartile_name,quartile_name")
    with pytest.raises(ValueError):
        parse_quartile_reference(payload, YEARS)


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def config_inputs(inputs: dict[str, Any]) -> str:
    return "".join(
        f'\n[inputs.{name}]\npath="{r["path"]}"\nsha256="{r["sha256"]}"\nsize_bytes={r["size_bytes"]}\n'
        for name, r in inputs.items()
    )


def test_raw_builder_verifies_manifest_and_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, resources = {}, {}
    for name, payload in zip(("data", "metadata"), source(), strict=True):
        path = tmp_path / f"{name}.json"
        path.write_bytes(payload)
        inputs[name] = fingerprint(path, payload)
        resources[name] = {**inputs[name], "url": f"https://example.test/{name}"}
    for name, text in {
        "manifest": json.dumps({"indicator_code": INDICATOR, "resources": resources}),
        "acquisition_config": '[indicator]\ncode="0013042"\ndata_url="https://example.test/data"\nmetadata_url="https://example.test/metadata"\n',
    }.items():
        path = tmp_path / f"{name}.txt"
        path.write_bytes(text.encode())
        inputs[name] = fingerprint(path, text.encode())
    config, output = tmp_path / "raw.toml", tmp_path / "result"
    config.write_text(
        'analysis_date="2026-10-05"\nyears=[2019,2020,2021]\n' + config_inputs(inputs),
        encoding="utf-8",
    )
    original, seen = Path.read_bytes, set()

    def read_once(path: Path) -> bytes:
        if path.name in {"data.json", "metadata.json"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    script = "scripts/build_housing_quartile_reference.py"
    monkeypatch.setattr(sys, "argv", [script, "--config", str(config), "--output", str(output)])
    runpy.run_path(script, run_name="__main__")
    assert len(seen) == 2
    assert (output / "quartiles.csv").read_text(encoding="utf-8") == canonical()
    with pytest.raises(FileExistsError):
        runpy.run_path(script, run_name="__main__")
    seen.clear()
    changed = tmp_path / "manifest.txt"
    document = json.loads(original(changed))
    document["resources"]["data"]["sha256"] = "0" * 64
    payload = json.dumps(document).encode()
    changed.write_bytes(payload)
    inputs["manifest"] = fingerprint(changed, payload)
    config.write_text(
        'analysis_date="2026-10-05"\nyears=[2019,2020,2021]\n' + config_inputs(inputs),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", [script, "--config", str(config), "--output", str(tmp_path / "bad")]
    )
    with pytest.raises(ValueError, match="provenance"):
        runpy.run_path(script, run_name="__main__")
    assert not (tmp_path / "bad").exists()


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_distribution.py"
    spec = importlib.util.spec_from_file_location("distribution_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_replay_consumes_verified_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, seen = Path.read_bytes, set()

    def read_once(path: Path) -> bytes:
        if path.name in {"quartiles.csv", "provenance.json"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "replay"
    path = "scripts/analyse_housing_distribution.py"
    monkeypatch.setattr(sys, "argv", [path, "--output", str(output)])
    runpy.run_path(path, run_name="__main__")
    report = json.loads((output / "analysis.json").read_bytes())
    assert len(seen) == 2
    assert report["summary"]["source_observations"] == 21
    assert report["summary"]["geography_level"] == "municipality"
    assert report["summary"]["endpoint_changes"][1]["latest_eur_m2"] == 4875
    assert report["summary"]["iqr_as_pct_of_median_change_pp"] == pytest.approx(-12.465096680556206)
    assert set(p.name for p in output.iterdir()) == {
        "analysis.json",
        "annual_distribution.csv",
        "endpoint_changes.csv",
        "housing_distribution.png",
    }
    for item in report["outputs"] + report["code_and_configuration"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"] and len(payload) == item["size_bytes"]


@pytest.mark.parametrize("failure", ["hash", "existing", "parent", "years", "render"])
def test_replay_failure_preserves_existing_files_and_leaves_no_bundle(
    tmp_path: Path,
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    config = tomllib.loads(
        Path("configs/housing_distribution_2026-10-05.toml").read_text(encoding="utf-8")
    )
    output = tmp_path / "result"
    if failure == "hash":
        config["inputs"]["quartiles"]["size_bytes"] = 1
    elif failure == "existing":
        output.mkdir()
        (output / "keep.txt").write_text("keep")
    elif failure in {"parent", "years"}:
        pinned = config["inputs"]["quartile_provenance"]
        document = json.loads(Path(pinned["path"]).read_bytes())
        if failure == "parent":
            document["output"]["sha256"] = "0" * 64
        else:
            document["years"] = [2020, 2021]
        changed, payload = tmp_path / "changed.json", json.dumps(document).encode()
        changed.write_bytes(payload)
        config["inputs"]["quartile_provenance"] = fingerprint(changed, payload)
    else:

        def fail(*args: Any) -> None:
            raise OSError("render failed")

        monkeypatch.setattr(script, "plot_housing_distribution", fail)
    path = tmp_path / "config.toml"
    path.write_text(
        'analysis_date="2026-10-05"\nbaseline_year=2019\nlatest_year=2025\n'
        + config_inputs(config["inputs"]),
        encoding="utf-8",
    )
    with pytest.raises((ValueError, FileExistsError, OSError)):
        script.analyse(path, output)
    if failure == "existing":
        assert (output / "keep.txt").read_text() == "keep"
    else:
        assert not output.exists()
    assert not list(tmp_path.glob(".housing-distribution-*"))
