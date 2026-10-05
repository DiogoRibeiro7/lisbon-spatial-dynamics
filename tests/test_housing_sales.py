"""Sales source-contract tests and offline replay of the immutable aggregate bundle."""

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

from lisbon_spatial_dynamics.analysis.housing_sales import analyse_housing_sales, plot_housing_sales
from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.transformations.housing_sales import (
    COLUMNS,
    INDICATOR,
    MUNICIPALITY,
    TITLE,
    extract_sales_reference,
    parse_sales_reference,
)

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara", "110607": "Beato"}
YEARS = [2019, 2020, 2021]


def source() -> tuple[bytes, bytes]:
    success = {"Verdadeiro": [{"Msg": "OK"}]}
    data: dict[str, Any] = {
        "IndicadorCod": INDICATOR,
        "IndicadorDsg": TITLE,
        "Sucesso": success,
        "Dados": {},
    }
    values = {"110601": [100, 80, 50], "110602": [50, 60, 100], "110607": [850, 860, 850]}
    geographies = {MUNICIPALITY: "Lisboa", **REFERENCE}
    for offset, year in enumerate(YEARS):
        counts = {code: series[offset] for code, series in values.items()}
        counts[MUNICIPALITY] = sum(counts.values())
        data["Dados"][f"4.º Trimestre de {year}"] = [
            {
                "geocod": f"1A0{code}",
                "geodsg": geographies[code],
                "valor": str(count),
                "ind_string": f"{count:,}".replace(",", " "),
            }
            for code, count in counts.items()
        ]
    dimensions = [
        *((1, f"S5A{year}4", f"4.º Trimestre de {year}") for year in YEARS),
        *((2, f"1A0{code}", name) for code, name in geographies.items()),
    ]
    meta = {
        "IndicadorCod": INDICATOR,
        "IndicadorNome": TITLE,
        "Sucesso": success,
        "Periodic": "Trimestral",
        "Potencia10": "0",
        "PrecisaoDecimal": "0",
        "UnidadeMedida": "Número (N.º)",
        "Dimensoes": {
            "Descricao_Dim": [{"dim_num": "1"}, {"dim_num": "2"}],
            "Categoria_Dim": [
                {f"Dim_Num{dim}_{code}": [{"dim_num": str(dim), "cat_id": code, "categ_dsg": name}]}
                for dim, code, name in dimensions
            ],
        },
    }
    return json.dumps([data]).encode(), json.dumps([meta]).encode()


def canonical() -> str:
    return extract_sales_reference(*source(), REFERENCE, YEARS)


def housing() -> list[HousingPanelRow]:
    prices = {"110601": [100, 120, 150], "110602": [200, 190, 180], "110607": [100, 150, 200]}
    return [
        HousingPanelRow(
            f"4.º Trimestre de {year}",
            code,
            name,
            "0012234",
            f"1A0{code}",
            name,
            "H1",
            "Total",
            Decimal(prices[code][offset]),
        )
        for offset, year in enumerate(YEARS)
        for code, name in REFERENCE.items()
    ]


def table(rows: list[dict[str, Any]]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def analyse(payload: str) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    return analyse_housing_sales(
        payload, housing(), REFERENCE, baseline_year=2019, latest_year=2021
    )


def test_counts_reconcile_and_city_change_is_not_mean_parish_change() -> None:
    payload = canonical()
    assert "\r" not in payload
    assert len(parse_sales_reference(payload, REFERENCE, YEARS)) == 12
    summary, tables, nominal = analyse(payload)
    assert summary["municipality_sales_change_pct"] == 0
    changes = [r["sales_change_pct"] for r in tables["endpoint_changes.csv"]]
    assert changes == [Decimal(-50), Decimal(100), Decimal(0)]
    assert sum(changes) / len(changes) != 0
    assert summary["parishes_with_higher_median_and_fewer_sales"] == 1
    assert summary["parishes_with_sales_growth"] == 1
    assert summary["parishes_with_sales_decline"] == 1
    assert summary["parishes_with_unchanged_sales"] == 1
    assert nominal["median_parish_change_pct"] == 50
    assert [r["sale_median_change_pct"] for r in tables["endpoint_changes.csv"]] == [50, -10, 100]
    assert tables["endpoint_changes.csv"][0]["sales_share_change_pp"] == -5
    assert [r["year_on_year_change_pct"] for r in tables["municipality_sales.csv"]] == [None, 0, 0]
    assert len(tables["annual_parish.csv"]) == 9


@pytest.mark.parametrize(
    "failure",
    [
        "indicator",
        "success",
        "unit",
        "frequency",
        "precision",
        "scale",
        "title",
        "dimensions",
        "dimension_name",
        "duplicate_metadata",
        "period",
        "geography",
        "extra_dimension",
        "display",
        "missing",
        "flagged",
        "duplicate_row",
        "missing_row",
    ],
)
def test_extractor_rejects_incompatible_source(failure: str) -> None:
    data, meta = (json.loads(p)[0] for p in source())
    row = data["Dados"]["4.º Trimestre de 2019"][0]
    if failure == "indicator":
        data["IndicadorCod"] = "0014351"  # Three-month sales are a different measure.
    elif failure == "success":
        meta["Sucesso"] = {}
    elif failure in {"unit", "frequency", "precision", "scale", "title"}:
        key = {
            "unit": "UnidadeMedida",
            "frequency": "Periodic",
            "precision": "PrecisaoDecimal",
            "scale": "Potencia10",
            "title": "IndicadorNome",
        }[failure]
        meta[key] = "wrong"
    elif failure == "dimensions":
        meta["Dimensoes"]["Descricao_Dim"].append({"dim_num": "3"})
    elif failure == "dimension_name":
        meta["Dimensoes"]["Categoria_Dim"][0]["Dim_Num1_S5A20194"][0]["categ_dsg"] = "Q1"
    elif failure == "duplicate_metadata":
        meta["Dimensoes"]["Categoria_Dim"].append(meta["Dimensoes"]["Categoria_Dim"][0])
    elif failure == "period":
        data["Dados"]["1.º Trimestre de 2019"] = data["Dados"].pop("4.º Trimestre de 2019")
    elif failure == "geography":
        row["geodsg"] = "Wrong"
    elif failure == "extra_dimension":
        row["dim_3"] = "H1"
    elif failure == "display":
        row["ind_string"] = "999"
    elif failure == "missing":
        del row["valor"]
        row.update(ind_string="-", sinal_conv="-", sinal_conv_desc="Dado nulo ou não aplicável")
    elif failure == "flagged":
        row["sinal_conv"] = "x"
    elif failure == "duplicate_row":
        data["Dados"]["4.º Trimestre de 2019"].append(row)
    else:
        data["Dados"]["4.º Trimestre de 2019"].pop()
    with pytest.raises(ValueError):
        extract_sales_reference(
            json.dumps([data]).encode(), json.dumps([meta]).encode(), REFERENCE, YEARS
        )


@pytest.mark.parametrize("value", ["", "-1", "1.5", "NaN", "Infinity", "1e3", "１２"])
def test_missing_or_invalid_counts_never_become_zero(value: str) -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    rows[1]["sales"] = value
    with pytest.raises(ValueError, match="nonnegative integer"):
        parse_sales_reference(table(rows), REFERENCE, YEARS)


@pytest.mark.parametrize(
    "failure", ["short", "long", "header", "duplicate", "coverage", "city", "zero_city", "identity"]
)
def test_parser_rejects_ragged_rows_and_unreconciled_coverage(failure: str) -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    if failure == "duplicate":
        rows.append(rows[0])
    elif failure == "coverage":
        rows.pop()
    elif failure == "city":
        rows[0]["sales"] = "999"
    elif failure == "zero_city":
        for row in rows:
            row["sales"] = "0"
    elif failure == "identity":
        rows[1]["geography_level"] = "municipality"
    payload = table(rows)
    if failure in {"short", "long"}:
        lines = payload.splitlines()
        lines[1] = lines[1] + ",extra" if failure == "long" else lines[1].rsplit(",", 1)[0]
        payload = "\n".join(lines) + "\n"
    elif failure == "header":
        payload = payload.replace("source_geography_code,sales", "sales,sales")
    with pytest.raises(ValueError):
        parse_sales_reference(payload, REFERENCE, YEARS)


def test_zero_baseline_preserves_absolute_change_and_renders(tmp_path: Path) -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    rows[1]["sales"] = "0"
    rows[0]["sales"] = "900"
    summary, tables, _ = analyse(table(rows))
    assert summary["parishes_with_zero_baseline_sales"] == 1
    assert summary["median_parish_sales_change_pct"] == 50
    assert tables["endpoint_changes.csv"][0]["sales_change_pct"] is None
    assert tables["endpoint_changes.csv"][0]["sales_change"] == 50
    plot_housing_sales(tables, tmp_path / "zero.png")
    assert (tmp_path / "zero.png").stat().st_size > 0


def test_order_and_callers_decimal_context_do_not_change_results() -> None:
    expected = analyse(canonical())
    rows = list(reversed(list(csv.DictReader(StringIO(canonical())))))
    with localcontext() as context:
        context.prec, context.rounding = 4, ROUND_UP
        assert analyse(table(rows)) == expected


def fingerprint(path: Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def config_text(inputs: dict[str, Any]) -> str:
    return "".join(
        f'\n[inputs.{name}]\npath="{r["path"]}"\nsha256="{r["sha256"]}"\nsize_bytes={r["size_bytes"]}\n'
        for name, r in inputs.items()
    )


def raw_config(tmp_path: Path, bad_link: bool = False) -> Path:
    inputs, resources = {}, {}
    for name, payload in zip(("data", "metadata"), source(), strict=True):
        path = tmp_path / f"{name}.json"
        path.write_bytes(payload)
        inputs[name] = fingerprint(path, payload)
        resources[name] = {**inputs[name], "url": f"https://example.test/{name}"}
    if bad_link:
        resources["data"]["sha256"] = "0" * 64
    for name, text in {
        "manifest": json.dumps({"indicator_code": INDICATOR, "resources": resources}),
        "acquisition_config": '[indicator]\ncode="0014363"\ndata_url="https://example.test/data"\nmetadata_url="https://example.test/metadata"\n',
        "reference": "freguesia_id,freguesia_name\n"
        + "".join(f"{c},{n}\n" for c, n in REFERENCE.items()),
    }.items():
        path = tmp_path / f"{name}.txt"
        payload = text.encode()
        path.write_bytes(payload)
        inputs[name] = fingerprint(path, payload)
    config = tmp_path / "raw.toml"
    config.write_text(
        'analysis_date="2026-10-05"\nparishes=3\nyears=[2019,2020,2021]\n' + config_text(inputs),
        encoding="utf-8",
    )
    return config


def test_raw_entry_point_checks_manifest_and_consumes_verified_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, output = raw_config(tmp_path), tmp_path / "reference"
    original, seen = Path.read_bytes, set()

    def read_once(path: Path) -> bytes:
        if path.name in {"data.json", "metadata.json", "reference.txt"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    script = "scripts/build_housing_sales_reference.py"
    monkeypatch.setattr(sys, "argv", [script, "--config", str(config), "--output", str(output)])
    runpy.run_path(script, run_name="__main__")
    assert (output / "sales_panel.csv").read_text(encoding="utf-8") == canonical()
    assert len(seen) == 3
    with pytest.raises(FileExistsError):
        runpy.run_path(script, run_name="__main__")
    seen.clear()
    raw_config(tmp_path, bad_link=True)
    monkeypatch.setattr(
        sys, "argv", [script, "--config", str(config), "--output", str(tmp_path / "bad")]
    )
    with pytest.raises(ValueError, match="provenance"):
        runpy.run_path(script, run_name="__main__")
    assert not (tmp_path / "bad").exists()


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_sales.py"
    spec = importlib.util.spec_from_file_location("housing_sales_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_replay_uses_verified_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, seen = Path.read_bytes, set()

    def read_once(path: Path) -> bytes:
        if path.name in {"sales_panel.csv", "housing_quarter_panel.csv", "census_context.csv"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "result"
    path = "scripts/analyse_housing_sales.py"
    monkeypatch.setattr(sys, "argv", [path, "--output", str(output)])
    runpy.run_path(path, run_name="__main__")
    report = json.loads((output / "analysis.json").read_bytes())
    assert len(seen) == 3 and report["nominal_summary_verified"]
    summary = report["summary"]
    assert summary["source_count_observations"] == 175
    assert summary["paired_parish_observations"] == 168
    assert summary["municipality_sales_change"] == -430
    assert summary["parishes_with_higher_median_and_fewer_sales"] == 17
    assert set(p.name for p in output.iterdir()) == {
        "analysis.json",
        "annual_parish.csv",
        "endpoint_changes.csv",
        "municipality_sales.csv",
        "housing_sales.png",
    }
    for item in report["outputs"] + report["code_and_configuration"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]


@pytest.mark.parametrize("failure", ["hash", "existing", "parent", "summary", "render"])
def test_replay_failure_leaves_no_partial_bundle(
    tmp_path: Path,
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    config = tomllib.loads(
        Path("configs/housing_sales_2026-10-05.toml").read_text(encoding="utf-8")
    )
    output = tmp_path / "result"
    if failure == "hash":
        config["inputs"]["sales"]["size_bytes"] = 1
    elif failure == "existing":
        output.mkdir()
        (output / "keep.txt").write_text("keep")
    elif failure in {"parent", "summary"}:
        name = "sales_provenance" if failure == "parent" else "housing_report"
        document = json.loads(Path(config["inputs"][name]["path"]).read_bytes())
        if failure == "parent":
            document["output"]["sha256"] = "0" * 64
        else:
            document["summary"]["parishes"] = 0
        payload = json.dumps(document).encode()
        changed = tmp_path / "changed.json"
        changed.write_bytes(payload)
        config["inputs"][name] = fingerprint(changed, payload)
    else:

        def fail(*args: Any) -> None:
            raise OSError("render failed")

        monkeypatch.setattr(script, "plot_housing_sales", fail)
    path = tmp_path / "config.toml"
    path.write_text(
        'analysis_date="2026-10-05"\nparishes=24\nbaseline_year=2019\nlatest_year=2025\n'
        + config_text(config["inputs"]),
        encoding="utf-8",
    )
    with pytest.raises((ValueError, FileExistsError, OSError)):
        script.analyse(path, output)
    if failure == "existing":
        assert (output / "keep.txt").read_text() == "keep"
    else:
        assert not output.exists()
    assert not list(tmp_path.glob(".housing-sales-*"))
