"""Test adjustment arithmetic with synthetic inputs and replay committed aggregate evidence.

Script integration tests depend on the dated source-audit, nominal housing, and CPI
artifacts pinned in configs/housing_inflation_2026-10-04.toml. They need no network,
credentials, or uncommitted raw captures. These dated inputs are immutable; later
quarters belong in new bundles. Integrity failures on edited inputs are intentional.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import runpy
import sys
from decimal import ROUND_UP, Decimal, localcontext
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.housing_inflation import analyse_housing_inflation
from lisbon_spatial_dynamics.panels.housing import HousingPanelRow
from lisbon_spatial_dynamics.transformations.cpi import CPI_COLUMNS

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara"}


def inputs() -> tuple[list[HousingPanelRow], str]:
    rows = []
    for code, values in {"110601": [100, 150, 200], "110602": [1000, 900, 1200]}.items():
        for year, value in zip(range(2019, 2022), values, strict=True):
            rows.append(
                HousingPanelRow(
                    f"4.º Trimestre de {year}",
                    code,
                    REFERENCE[code],
                    "0012234",
                    f"1A0{code}",
                    REFERENCE[code],
                    "H1",
                    "Total",
                    Decimal(value),
                )
            )
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(CPI_COLUMNS)
    for year, value in [(2019, 80), (2020, 90), (2021, 100)]:
        writer.writerow([year, "0014642", 2025, "PT", "Portugal", "T", "Total", value])
    return rows, stream.getvalue()


def test_adjustment_uses_ratios_and_each_parish_baseline() -> None:
    rows, cpi = inputs()
    summary, tables, nominal = analyse_housing_inflation(
        rows, REFERENCE, cpi, baseline_year=2019, latest_year=2021
    )
    assert summary["cpi_change_pct"] == 25
    assert summary["median_nominal_change_pct"] == nominal["median_parish_change_pct"] == 60
    assert summary["median_cpi_adjusted_change_pct"] == 28
    assert summary["parishes_decreased_cpi_adjusted"] == 1
    endpoints = tables["parish_changes.csv"]
    assert [row["latest_cpi_adjusted_eur_m2"] for row in endpoints] == [160, 960]
    assert [row["cpi_adjusted_change_pct"] for row in endpoints] == [60, -4]
    # Subtracting the 25% CPI increase from nominal growth gives a wrong result.
    assert endpoints[0]["cpi_adjusted_change_pct"] != endpoints[0]["nominal_change_pct"] - 25
    for row in endpoints:
        assert (
            row["cpi_adjusted_change_pct"]
            == Decimal(".8") * (row["nominal_change_pct"] + 100) - 100
        )
    annual = tables["annual_adjusted.csv"]
    assert all(row["cpi_adjusted_q4_yoy_pct"] is None for row in annual if row["year"] == 2019)
    assert (
        next(row for row in annual if row["year"] == 2020 and row["freguesia_id"] == "110602")[
            "cpi_adjusted_q4_yoy_pct"
        ]
        == -20
    )
    assert [
        row["parishes_below_previous_cpi_adjusted_q4"] for row in tables["yearly_summary.csv"]
    ] == [None, 1, 0]


def test_order_and_ambient_decimal_context_do_not_change_results() -> None:
    rows, cpi = inputs()
    expected = analyse_housing_inflation(rows, REFERENCE, cpi, baseline_year=2019, latest_year=2021)
    with localcontext() as context:
        context.prec = 5
        context.rounding = ROUND_UP
        assert (
            analyse_housing_inflation(
                list(reversed(rows)), REFERENCE, cpi, baseline_year=2019, latest_year=2021
            )
            == expected
        )


def test_incomplete_housing_fails_before_adjustment() -> None:
    rows, cpi = inputs()
    with pytest.raises(ValueError, match="incomplete"):
        analyse_housing_inflation(rows[:-1], REFERENCE, cpi, baseline_year=2019, latest_year=2021)


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_inflation.py"
    spec = importlib.util.spec_from_file_location("housing_inflation_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_replay_uses_verified_bytes_and_preserves_nominal_summary(
    tmp_path: Path, script: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes
    seen: set[str] = set()

    def read_once(path: Path) -> bytes:
        if path.name in {"housing_quarter_panel.csv", "annual_cpi.csv", "census_context.csv"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "result"
    script_path = "scripts/analyse_housing_inflation.py"
    monkeypatch.setattr(sys, "argv", [script_path, "--output", str(output)])
    runpy.run_path(script_path, run_name="__main__")
    report = json.loads((output / "analysis.json").read_bytes())
    assert report["nominal_summary_verified"]
    assert report["summary"]["annual_rows"] == 168
    assert report["summary"]["cpi_years"] == 7
    assert report["summary"]["parishes"] == 24
    record = next(item for item in report["code_and_configuration"] if item["path"] == script_path)
    assert record["sha256"] == sha256(Path(script_path).read_bytes()).hexdigest()
    assert len(seen) == 3
    assert set(p.name for p in output.iterdir()) == {
        "analysis.json",
        "annual_adjusted.csv",
        "parish_changes.csv",
        "yearly_summary.csv",
        "housing_inflation.png",
    }
    for item in report["outputs"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]
        if item["path"].endswith(".csv"):
            assert b"\r" not in payload


def test_failed_render_leaves_no_partial_bundle(
    tmp_path: Path, script: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any) -> None:
        raise OSError("render failed")

    monkeypatch.setattr(script, "plot_housing_inflation", fail)
    output = tmp_path / "result"
    with pytest.raises(OSError, match="render failed"):
        script.analyse(Path("configs/housing_inflation_2026-10-04.toml"), output)
    assert not output.exists()
    assert not list(tmp_path.glob(".housing-inflation-*"))


@pytest.mark.parametrize("failure", ["hash", "existing", "parent"])
def test_bad_evidence_or_existing_output_fails(
    tmp_path: Path, script: ModuleType, failure: str
) -> None:
    text = Path("configs/housing_inflation_2026-10-04.toml").read_text(encoding="utf-8")
    output = tmp_path / "result"
    if failure == "hash":
        text = text.replace("size_bytes = 53284", "size_bytes = 1")
    elif failure == "existing":
        output.mkdir()
    else:
        original = Path("data/reference/ine-cpi/2026-10-04/provenance.json")
        original_bytes = original.read_bytes()
        parent = json.loads(original_bytes)
        parent["output"]["sha256"] = "0" * 64
        payload = json.dumps(parent).encode()
        changed = tmp_path / "cpi-provenance.json"
        changed.write_bytes(payload)
        text = (
            text.replace(original.as_posix(), changed.as_posix())
            .replace(sha256(original_bytes).hexdigest(), sha256(payload).hexdigest())
            .replace(f"size_bytes = {len(original_bytes)}", f"size_bytes = {len(payload)}")
        )
    config = tmp_path / "config.toml"
    config.write_text(text, encoding="utf-8")
    with pytest.raises((ValueError, FileExistsError)):
        script.analyse(config, output)
    assert not output.exists() or not list(output.iterdir())
