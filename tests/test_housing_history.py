"""Housing evidence keeps Q4 windows, parish weighting and input provenance explicit."""

from __future__ import annotations

import csv
import importlib.util
import json
from dataclasses import replace
from decimal import ROUND_UP, Decimal, localcontext
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.housing_history import analyse_housing_history
from lisbon_spatial_dynamics.panels.housing import PANEL_COLUMNS, HousingPanelRow
from lisbon_spatial_dynamics.panels.temporal import (
    load_housing_panel_csv,
    parse_housing_panel_csv,
)

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara"}


def housing() -> list[HousingPanelRow]:
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
        rows.append(
            replace(rows[-1], period_code="1.º Trimestre de 2022", value_eur_m2=Decimal(99999))
        )
    return rows


def analyse(rows: list[HousingPanelRow]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    return analyse_housing_history(rows, REFERENCE, baseline_year=2019, latest_year=2021)


def test_q4_changes_use_each_parish_baseline_and_ignore_later_q1() -> None:
    summary, tables = analyse(housing())
    assert summary["annual_rows"] == 6
    assert summary["excluded_rows"] == 2
    assert summary["excluded_periods"] == ["2022Q1"]
    assert summary["median_parish_change_pct"] == 60
    assert summary["minimum_parish_change_pct"] == 20
    assert summary["maximum_parish_change_pct"] == 100
    assert summary["parishes_increased"] == 2
    endpoints = tables["parish_changes.csv"]
    assert [row["latest_eur_m2"] for row in endpoints] == [200, 1200]
    assert [row["change_eur_m2"] for row in endpoints] == [100, 200]
    yearly = tables["yearly_summary.csv"]
    assert [row["median_parish_value_eur_m2"] for row in yearly] == [550, 525, 700]
    assert [row["parishes_below_previous_q4"] for row in yearly] == [None, 1, 0]
    # Median of individual changes is not percentage change in the median level.
    assert summary["median_parish_change_pct"] != (700 / 550 - 1) * 100
    annual = tables["annual_q4.csv"]
    assert annual[0]["q4_yoy_pct"] is None
    assert annual[2]["q4_yoy_pct"] == 50
    assert annual[3]["q4_yoy_pct"] == -10
    assert all(row["period_end"].endswith("-12-31") for row in annual)


def test_input_order_and_decimal_precision_do_not_change_results() -> None:
    rows = housing()
    rows[0] = replace(rows[0], value_eur_m2=Decimal(123))
    expected = analyse(rows)
    with localcontext() as context:
        context.prec = 6
        context.rounding = ROUND_UP
        assert analyse(list(reversed(rows))) == expected


@pytest.mark.parametrize(
    "value", [None, Decimal(0), Decimal(-1), Decimal("NaN"), Decimal("Infinity")]
)
def test_missing_nonfinite_and_nonpositive_values_fail(value: Decimal | None) -> None:
    rows = housing()
    rows[0] = replace(rows[0], value_eur_m2=value)
    with pytest.raises(ValueError, match="finite and strictly positive"):
        analyse(rows)


@pytest.mark.parametrize(
    "failure",
    [
        "duplicate",
        "missing_baseline",
        "missing_middle",
        "missing_latest",
        "name",
        "code",
        "indicator",
        "category",
        "source_name",
    ],
)
def test_malformed_or_incomplete_evidence_fails(failure: str) -> None:
    rows = housing()
    if failure == "duplicate":
        rows.append(rows[0])
    elif failure.startswith("missing_"):
        rows.pop({"missing_baseline": 0, "missing_middle": 1, "missing_latest": 2}[failure])
    else:
        field, value = {
            "name": ("freguesia_name", "Other"),
            "code": ("freguesia_id", "110699"),
            "indicator": ("indicator_code", "old_indicator"),
            "category": ("category_code", "H2"),
            "source_name": ("source_geography_name", "Other"),
        }[failure]
        changed: dict[str, Any] = {field: value}
        rows[0] = replace(rows[0], **changed)
    with pytest.raises(ValueError):
        analyse(rows)


def test_decreases_and_unchanged_endpoints_are_preserved() -> None:
    rows = housing()
    rows[2] = replace(rows[2], value_eur_m2=Decimal(100))
    rows[6] = replace(rows[6], value_eur_m2=Decimal(800))
    summary, _ = analyse(rows)
    assert summary["parishes_increased"] == 0
    assert summary["parishes_unchanged"] == 1
    assert summary["parishes_decreased"] == 1
    assert summary["median_parish_change_pct"] == -10


def test_captured_csv_parser_and_existing_path_loader_agree(tmp_path: Path) -> None:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(PANEL_COLUMNS)
    for row in housing():
        writer.writerow([getattr(row, name) for name in PANEL_COLUMNS])
    payload = stream.getvalue()
    path = tmp_path / "housing.csv"
    path.write_bytes(payload.encode("utf-8"))
    assert parse_housing_panel_csv(payload) == tuple(housing()) == load_housing_panel_csv(path)


@pytest.fixture(scope="module")
def report_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_history.py"
    spec = importlib.util.spec_from_file_location("housing_history_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_aggregate_replay_and_verified_bytes(
    tmp_path: Path,
    report_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_bytes = Path.read_bytes
    panel_reads = 0

    def read_once(path: Path) -> bytes:
        nonlocal panel_reads
        if path.name == "housing_quarter_panel.csv":
            panel_reads += 1
            assert panel_reads == 1
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "report"
    report_module.analyse(Path("configs/housing_history_2026-10-04.toml"), output)
    report = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    assert report["summary"]["annual_rows"] == 168
    assert report["summary"]["parishes_increased"] == 24
    assert report["summary"]["median_parish_change_pct"] == pytest.approx(47.52323486287442)
    assert {path.name for path in output.iterdir()} == {
        "annual_q4.csv",
        "parish_changes.csv",
        "yearly_summary.csv",
        "housing_changes.png",
        "analysis.json",
    }
    for artifact in report["outputs"]:
        payload = Path(artifact["path"]).read_bytes()
        assert sha256(payload).hexdigest() == artifact["sha256"]
        assert len(payload) == artifact["size_bytes"]
    assert (output / "housing_changes.png").read_bytes().startswith(b"\x89PNG")
    assert panel_reads == 1


def test_hash_mismatch_fails_before_publication(
    tmp_path: Path,
    report_module: ModuleType,
) -> None:
    config = Path("configs/housing_history_2026-10-04.toml").read_text(encoding="utf-8")
    path = tmp_path / "changed.toml"
    path.write_text(
        config.replace(
            "d69cb05743da7a3ae483a490b5ac73d8c670d095c3ede6186fa8d59be70a736a", "0" * 64
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report"
    with pytest.raises(ValueError, match="input integrity mismatch"):
        report_module.analyse(path, output)
    assert not output.exists()


def test_failed_figure_leaves_no_partial_bundle_and_existing_output_is_preserved(
    tmp_path: Path,
    report_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_plot(rows: Any, path: Path) -> None:
        path.write_bytes(b"partial figure")
        raise OSError("plot failed")

    monkeypatch.setattr(report_module, "plot_housing_changes", fail_plot)
    config = Path("configs/housing_history_2026-10-04.toml")
    output = tmp_path / "report"
    with pytest.raises(OSError, match="plot failed"):
        report_module.analyse(config, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".housing-history-*"))
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError):
        report_module.analyse(config, output)
    assert marker.read_text(encoding="utf-8") == "existing"
