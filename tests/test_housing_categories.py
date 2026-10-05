"""Synthetic source/arithmetic checks and replay of immutable committed aggregate evidence.

Integration replay uses the dated source-audit, housing-history and dwelling-category
inputs pinned in configs/housing_categories_2026-10-05.toml. It needs no network or
local raw capture. Editing those inputs should fail integrity validation.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import runpy
import sys
from decimal import ROUND_UP, localcontext
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.housing_categories import analyse_housing_categories
from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.transformations.housing_categories import (
    CATEGORIES,
    COLUMNS,
    MISSING_DESCRIPTION,
    TITLE,
    extract_category_reference,
    parse_category_reference,
)

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara", "110607": "Beato"}
YEARS = [2019, 2020, 2021]


def source() -> tuple[bytes, bytes]:
    values: dict[str, dict[str, list[int | None]]] = {
        "110601": {"H1": [100, 120, 150], "H11": [200, None, 300], "H12": [80, 80, 88]},
        "110602": {"H1": [200, 200, 340], "H11": [None, None, 400], "H12": [100, None, 210]},
        "110607": {"H1": [100, 150, 200], "H11": [300, None, None], "H12": [100, 120, 220]},
    }
    success = {"Verdadeiro": [{"Msg": "OK"}]}
    data: dict[str, Any] = {
        "IndicadorCod": "0012234",
        "IndicadorDsg": TITLE,
        "Sucesso": success,
        "Dados": {},
    }
    for offset, year in enumerate(YEARS):
        rows = []
        for code, name in REFERENCE.items():
            for category, label in CATEGORIES.items():
                value = values[code][category][offset]
                row: dict[str, Any] = {
                    "geocod": f"1A0{code}",
                    "geodsg": name,
                    "dim_3": category,
                    "dim_3_t": label,
                }
                if value is None:
                    row.update(
                        {
                            "sinal_conv": "-",
                            "sinal_conv_desc": MISSING_DESCRIPTION,
                            "ind_string": "-",
                        }
                    )
                else:
                    row.update({"valor": str(value), "ind_string": str(value)})
                rows.append(row)
        data["Dados"][f"4.º Trimestre de {year}"] = rows
    dimensions = [
        *((1, f"S5A{year}4", f"4.º Trimestre de {year}") for year in YEARS),
        *((2, f"1A0{code}", name) for code, name in REFERENCE.items()),
        *((3, code, name) for code, name in CATEGORIES.items()),
    ]
    meta = {
        "IndicadorCod": "0012234",
        "IndicadorNome": TITLE,
        "Sucesso": success,
        "Periodic": "Trimestral",
        "Potencia10": "0",
        "PrecisaoDecimal": "0",
        "UnidadeMedida": "Euro/ Metro quadrado (€/ m²)",
        "Dimensoes": {
            "Categoria_Dim": [
                {
                    f"Dim_Num{dim}_{code}": [
                        {"dim_num": str(dim), "cat_id": code, "categ_dsg": name}
                    ]
                    for dim, code, name in dimensions
                }
            ]
        },
    }
    return json.dumps([data]).encode(), json.dumps([meta]).encode()


def canonical() -> str:
    return extract_category_reference(*source(), REFERENCE, YEARS)


def housing() -> list[HousingPanelRow]:
    return [
        HousingPanelRow(
            f"4.º Trimestre de {r.year}",
            r.freguesia_id,
            r.freguesia_name,
            "0012234",
            f"1A0{r.freguesia_id}",
            r.freguesia_name,
            "H1",
            "Total",
            r.value_eur_m2,
        )
        for r in parse_category_reference(canonical(), REFERENCE, YEARS)
        if r.category_code == "H1"
    ]


def csv_text(rows: list[dict[str, Any]]) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def test_extract_preserves_missing_keys_and_source_flags() -> None:
    payload = canonical()
    rows = parse_category_reference(payload, REFERENCE, YEARS)
    assert len(rows) == 27 and "\r" not in payload
    missing = [r for r in rows if r.value_eur_m2 is None]
    assert len(missing) == 6
    assert all(
        r.source_flag == "-" and r.source_flag_description == MISSING_DESCRIPTION for r in missing
    )


@pytest.mark.parametrize(
    "failure",
    [
        "root",
        "indicator",
        "success",
        "unit",
        "periodicity",
        "precision",
        "dimension",
        "period",
        "missing",
        "duplicate",
        "geography",
        "category",
        "extra_dimension",
        "flag",
        "displayed",
    ],
)
def test_raw_contract_failures(failure: str) -> None:
    raw_data, raw_meta = source()
    data, meta = json.loads(raw_data), json.loads(raw_meta)
    row = data[0]["Dados"]["4.º Trimestre de 2019"][0]
    if failure == "root":
        data = {}
    elif failure == "indicator":
        data[0]["IndicadorCod"] = "0011364"
    elif failure == "success":
        data[0]["Sucesso"] = {"Falso": []}
    elif failure == "unit":
        meta[0]["UnidadeMedida"] = "Euro"
    elif failure == "periodicity":
        meta[0]["Periodic"] = "Anual"
    elif failure == "precision":
        meta[0]["PrecisaoDecimal"] = "3"
    elif failure == "dimension":
        meta[0]["Dimensoes"] = None
    elif failure == "period":
        data[0]["Dados"]["1.º Trimestre de 2022"] = data[0]["Dados"].pop("4.º Trimestre de 2021")
    elif failure == "missing":
        data[0]["Dados"]["4.º Trimestre de 2019"].pop()
    elif failure == "duplicate":
        data[0]["Dados"]["4.º Trimestre de 2019"].append(row)
    elif failure == "geography":
        row["geocod"] = "1A0110600"
    elif failure == "category":
        row["dim_3"] = "H9"
    elif failure == "extra_dimension":
        row["dim_4"] = "X"
    elif failure == "flag":
        row["sinal_conv"] = "x"
    else:
        row["ind_string"] = "999"
    with pytest.raises(ValueError):
        extract_category_reference(
            json.dumps(data).encode(), json.dumps(meta).encode(), REFERENCE, YEARS
        )


@pytest.mark.parametrize(
    "failure",
    [
        "zero",
        "decimal",
        "nan",
        "indicator",
        "scope",
        "category",
        "period",
        "duplicate",
        "missing",
        "null_flag",
        "null_description",
        "flagged_value",
        "short",
        "long",
    ],
)
def test_canonical_contract_failures(failure: str) -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    row = rows[0]
    if failure in {"zero", "decimal", "nan"}:
        row["value_eur_m2"] = {"zero": "0", "decimal": "1.5", "nan": "NaN"}[failure]
    elif failure == "indicator":
        row["indicator_code"] = "0000000"
    elif failure == "scope":
        row["source_geography_code"] = "1A0110600"
    elif failure == "category":
        row["category_name"] = "Wrong"
    elif failure == "period":
        row["period_code"] = "3.º Trimestre de 2019"
    elif failure == "duplicate":
        rows.append(row)
    elif failure == "missing":
        rows.pop()
    elif failure in {"null_flag", "null_description"}:
        missing = next(r for r in rows if not r["value_eur_m2"])
        missing["source_flag" if failure == "null_flag" else "source_flag_description"] = ""
    elif failure == "flagged_value":
        row["source_flag"] = "-"
    text = csv_text(rows)
    if failure in {"short", "long"}:
        lines = text.splitlines()
        lines[1] = lines[1] + ",extra" if failure == "long" else lines[1].rsplit(",", 1)[0]
        text = "\n".join(lines) + "\n"
    with pytest.raises(ValueError):
        parse_category_reference(text, REFERENCE, YEARS)


def test_matched_cohorts_and_paired_gaps_are_distinct_statistics() -> None:
    summary, tables, nominal = analyse_housing_categories(
        canonical(), housing(), REFERENCE, baseline_year=2019, latest_year=2021
    )
    categories = {r["category_code"]: r for r in tables["matched_comparisons.csv"]}
    assert nominal["median_parish_change_pct"] == 70
    assert categories["H11"]["matched_parishes"] == 1
    assert categories["H11"]["median_matched_total_change_pct"] == 50
    assert categories["H11"]["parishes_with_all_years"] == 0
    assert categories["H12"]["matched_parishes"] == 3
    assert categories["H12"]["median_category_change_pct"] == 110
    assert categories["H12"]["median_matched_total_change_pct"] == 70
    assert categories["H12"]["median_paired_difference_pp"] == 20  # Not 110 - 70.
    assert categories["H12"]["parishes_with_all_years"] == 2
    assert len(summary["excluded_endpoints"]) == 2
    excluded = [r for r in tables["endpoint_changes.csv"] if not r["complete_endpoints"]]
    assert all(r["change_pct"] is None and r["difference_from_total_pp"] is None for r in excluded)
    assert summary["total_observations_verified"] == 9


def test_order_and_decimal_context_do_not_change_results() -> None:
    expected = analyse_housing_categories(
        canonical(), housing(), REFERENCE, baseline_year=2019, latest_year=2021
    )
    reversed_csv = csv_text(list(reversed(list(csv.DictReader(StringIO(canonical()))))))
    with localcontext() as context:
        context.prec = 4
        context.rounding = ROUND_UP
        assert (
            analyse_housing_categories(
                reversed_csv,
                list(reversed(housing())),
                REFERENCE,
                baseline_year=2019,
                latest_year=2021,
            )
            == expected
        )


def test_revised_total_cannot_silently_replace_published_evidence() -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    rows[0]["value_eur_m2"] = "101"
    with pytest.raises(ValueError, match="Total medians differ"):
        analyse_housing_categories(
            csv_text(rows), housing(), REFERENCE, baseline_year=2019, latest_year=2021
        )


def test_no_category_pairs_stays_missing() -> None:
    rows = list(csv.DictReader(StringIO(canonical())))
    for row in rows:
        if row["category_code"] == "H11":
            row.update(
                value_eur_m2="", source_flag="-", source_flag_description=MISSING_DESCRIPTION
            )
    summary, _, _ = analyse_housing_categories(
        csv_text(rows), housing(), REFERENCE, baseline_year=2019, latest_year=2021
    )
    result = next(r for r in summary["categories"] if r["category_code"] == "H11")
    assert result["matched_parishes"] == 0
    assert result["median_category_change_pct"] is None
    assert result["median_matched_total_change_pct"] is None


def raw_config(tmp_path: Path, *, bad_link: bool = False) -> Path:
    data, meta = source()
    inputs, resources = {}, {}
    for name, payload in (("data", data), ("metadata", meta)):
        path = tmp_path / f"{name}.json"
        path.write_bytes(payload)
        inputs[name] = {
            "path": path.as_posix(),
            "sha256": sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
        resources[name] = {**inputs[name], "url": f"https://example.test/{name}"}
    if bad_link:
        resources["data"]["sha256"] = "0" * 64
    additional = {
        "manifest": json.dumps({"indicator_code": "0012234", "resources": resources}),
        "acquisition_config": '[indicator]\ncode="0012234"\ndata_url="https://example.test/data"\nmetadata_url="https://example.test/metadata"\n',
        "reference": "freguesia_id,freguesia_name\n"
        + "".join(f"{code},{name}\n" for code, name in REFERENCE.items()),
    }
    for name, text in additional.items():
        path = tmp_path / f"{name}.txt"
        payload = text.encode()
        path.write_bytes(payload)
        inputs[name] = {
            "path": path.as_posix(),
            "sha256": sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }
    text = 'analysis_date="2026-10-04"\nparishes=3\nyears=[2019,2020,2021]\n'
    for name, r in inputs.items():
        text += (
            f'\n[inputs.{name}]\npath="{r["path"]}"\n'
            f'sha256="{r["sha256"]}"\nsize_bytes={r["size_bytes"]}\n'
        )
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_raw_builder_entry_point_and_broken_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, output = raw_config(tmp_path), tmp_path / "reference"
    path = "scripts/build_housing_category_reference.py"
    monkeypatch.setattr(sys, "argv", [path, "--config", str(config), "--output", str(output)])
    runpy.run_path(path, run_name="__main__")
    assert (output / "category_panel.csv").read_text(encoding="utf-8") == canonical()
    with pytest.raises(FileExistsError):
        runpy.run_path(path, run_name="__main__")
    raw_config(tmp_path, bad_link=True)
    monkeypatch.setattr(
        sys, "argv", [path, "--config", str(config), "--output", str(tmp_path / "bad")]
    )
    with pytest.raises(ValueError, match="provenance"):
        runpy.run_path(path, run_name="__main__")
    assert not (tmp_path / "bad").exists()


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_categories.py"
    spec = importlib.util.spec_from_file_location("housing_categories_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_replay_consumes_verified_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes
    seen: set[str] = set()

    def read_once(path: Path) -> bytes:
        if path.name in {"category_panel.csv", "housing_quarter_panel.csv", "census_context.csv"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "result"
    path = "scripts/analyse_housing_categories.py"
    monkeypatch.setattr(sys, "argv", [path, "--output", str(output)])
    runpy.run_path(path, run_name="__main__")
    report = json.loads((output / "analysis.json").read_bytes())
    assert len(seen) == 3 and report["nominal_summary_verified"]
    assert report["summary"]["category_rows"] == 504
    assert report["summary"]["total_observations_verified"] == 168
    assert [r["matched_parishes"] for r in report["summary"]["categories"]] == [24, 14, 24]
    assert set(p.name for p in output.iterdir()) == {
        "analysis.json",
        "endpoint_changes.csv",
        "annual_coverage.csv",
        "matched_comparisons.csv",
        "housing_categories.png",
    }
    for item in report["outputs"] + report["code_and_configuration"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]


@pytest.mark.parametrize("failure", ["hash", "existing", "parent", "render"])
def test_analysis_rejects_bad_evidence_without_partial_outputs(
    tmp_path: Path, script: ModuleType, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    text = Path("configs/housing_categories_2026-10-05.toml").read_text(encoding="utf-8")
    output = tmp_path / "result"
    if failure == "hash":
        text = text.replace("size_bytes = 53284", "size_bytes = 1")
    elif failure == "existing":
        output.mkdir()
    elif failure == "parent":
        path = Path("data/reference/ine-housing-categories/2026-10-04/provenance.json")
        original = path.read_bytes()
        document = json.loads(original)
        document["output"]["sha256"] = "0" * 64
        payload = json.dumps(document).encode()
        changed = tmp_path / "changed.json"
        changed.write_bytes(payload)
        text = (
            text.replace(path.as_posix(), changed.as_posix())
            .replace(sha256(original).hexdigest(), sha256(payload).hexdigest())
            .replace(f"size_bytes = {len(original)}", f"size_bytes = {len(payload)}")
        )
    else:

        def fail(*args: Any) -> None:
            raise OSError("render failed")

        monkeypatch.setattr(script, "plot_housing_categories", fail)
    config = tmp_path / "config.toml"
    config.write_text(text, encoding="utf-8")
    with pytest.raises((ValueError, FileExistsError, OSError)):
        script.analyse(config, output)
    assert not output.exists() or not list(output.iterdir())
    assert not list(tmp_path.glob(".housing-categories-*"))
