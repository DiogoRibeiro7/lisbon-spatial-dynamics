"""Synthetic denominator/cohort checks and replay of immutable audited aggregates.

Integration tests use the four committed inputs pinned in the historical-capacity
configuration. They require neither the local source PDF nor a live data service.
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

from lisbon_spatial_dynamics.analysis.cml_benchmarks import COLUMNS
from lisbon_spatial_dynamics.analysis.historical_capacity import analyse_historical_capacity

IDENTITIES = {"110601": "Ajuda", "110602": "Alcântara", "110607": "Beato"}
CONFIG = Path("configs/historical_capacity_2026-10-05.toml")


def table(rows: list[dict[str, Any]], columns: tuple[str, ...] | None = None) -> str:
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns or tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def inputs() -> tuple[str, str]:
    rows = []
    for number, levels in (
        (18, [(30, 31), (40, 42), (50, 53)]),
        (19, [(400, 200), (400, 500), (200, 300)]),
    ):
        for i, ((code, name), (a, b)) in enumerate(zip(IDENTITIES.items(), levels, strict=True), 1):
            rows.append(dict(zip(COLUMNS, (number, i, code, name, a, b, b - a), strict=True)))
        a, b = sum(v[0] for v in levels), sum(v[1] for v in levels)
        rows.append(
            dict(zip(COLUMNS, (number, 0, "1106", "LISBOA - TOTAL", a, b, b - a), strict=True))
        )
    census = [
        {
            "freguesia_id": code,
            "freguesia_name": name,
            "census_year": 2021,
            "population_resident": pop,
        }
        for (code, name), pop in zip(IDENTITIES.items(), [100, 300, 600], strict=True)
    ]
    return table(rows), table(census)


def analyse(
    transcription: str, census: str, n: int = 1
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    return analyse_historical_capacity(transcription, census, expected_parishes=3, baseline_top_n=n)


def test_capacity_normalization_and_municipality_denominator() -> None:
    summary, tables, benchmark = analyse(*inputs())
    rows = tables["parish_capacity.csv"]
    city = tables["municipality_capacity.csv"][0]
    assert summary["parishes_increased"] == 2 and summary["parishes_decreased"] == 1
    assert benchmark["reference_months"] == ["2019-11", "2022-11"]
    assert [r["population_resident_2021"] for r in rows] == [100, 300, 600]
    assert rows[0]["baseline_capacity_per_1000_2021_residents"] == 4000
    assert rows[0]["latest_capacity_per_1000_2021_residents"] == 2000
    assert rows[0]["capacity_change_per_1000_2021_residents"] == -2000
    assert rows[0]["capacity_change_pct"] == -50
    assert city["population_resident_2021"] == 1000
    assert city["baseline_capacity"] == city["latest_capacity"] == 1000
    assert city["baseline_capacity_per_1000_2021_residents"] == 1000
    assert city["capacity_change_per_1000_2021_residents"] == 0
    assert sum(r["baseline_capacity_per_1000_2021_residents"] for r in rows) / 3 != 1000
    assert all(r["baseline_month"] == "2019-11" and r["latest_month"] == "2022-11" for r in rows)


def test_baseline_cohort_ties_and_membership_are_explicit() -> None:
    summary, tables, _ = analyse(*inputs())
    assert summary["baseline_largest_capacity_cohort"] == [
        {"freguesia_id": "110601", "freguesia_name": "Ajuda"}
    ]
    cohort, rest = tables["concentration.csv"]
    assert cohort["baseline_capacity"] == 400 and cohort["latest_capacity"] == 200
    assert cohort["baseline_municipality_capacity_share_pct"] == 40
    assert cohort["latest_municipality_capacity_share_pct"] == 20  # Not the new leader's 50%.
    assert cohort["capacity_share_change_pp"] == -20
    assert cohort["capacity_change"] == -200 and rest["capacity_change"] == 200
    assert (
        sum(r["latest_municipality_capacity_share_pct"] for r in tables["concentration.csv"]) == 100
    )


def test_order_and_decimal_context_do_not_change_evidence() -> None:
    source, census = inputs()
    expected = analyse(source, census)
    shuffled_source = table(list(reversed(list(csv.DictReader(StringIO(source))))))
    shuffled_census = table(list(reversed(list(csv.DictReader(StringIO(census))))))
    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_UP
        assert analyse(shuffled_source, shuffled_census) == expected


@pytest.mark.parametrize("population", ["0", "-1", "", "1.5", "NaN", "Infinity"])
def test_invalid_population_denominators_fail(population: str) -> None:
    source, census = inputs()
    rows = list(csv.DictReader(StringIO(census)))
    rows[0]["population_resident"] = population
    with pytest.raises(ValueError, match="Census 2021"):
        analyse(source, table(rows))


@pytest.mark.parametrize(
    "failure", ["year", "missing", "duplicate", "name", "short", "duplicate_column"]
)
def test_population_identity_and_coverage_failures(failure: str) -> None:
    source, census = inputs()
    rows = list(csv.DictReader(StringIO(census)))
    if failure == "year":
        rows[0]["census_year"] = "2019"
    elif failure == "missing":
        rows.pop()
    elif failure == "duplicate":
        rows.append(rows[0])
    elif failure == "name":
        rows[0]["freguesia_name"] = "Wrong"
    text = table(rows)
    if failure == "short":
        lines = text.splitlines()
        lines[1] = lines[1].rsplit(",", 1)[0]
        text = "\n".join(lines) + "\n"
    elif failure == "duplicate_column":
        text = text.replace("census_year,population_resident", "census_year,census_year")
    with pytest.raises(ValueError):
        analyse(source, text)


@pytest.mark.parametrize("n", [0, 3, 4, True, 1.5])
def test_cohort_requires_nonempty_proper_integer_subset(n: Any) -> None:
    with pytest.raises(ValueError, match="proper subset"):
        analyse(*inputs(), n=n)


@pytest.mark.parametrize("field", ["reported_change", "value_2019_11", "value_2022_11"])
def test_capacity_arithmetic_must_reconcile(field: str) -> None:
    source, census = inputs()
    rows = list(csv.DictReader(StringIO(source)))
    rows[-1][field] = str(int(rows[-1][field]) + 1)
    with pytest.raises(ValueError, match="must reconcile"):
        analyse(table(rows), census)


def test_weighted_units_are_not_substituted_for_capacity() -> None:
    source, census = inputs()
    expected, expected_tables, _ = analyse(source, census)
    rows = list(csv.DictReader(StringIO(source)))
    rows[3]["value_2019_11"] = "121"  # Preserve and report the weighted table discrepancy.
    actual, actual_tables, benchmark = analyse(table(rows), census)
    assert actual == expected and actual_tables == expected_tables
    assert benchmark["tables"][0]["row_change_discrepancies"]


@pytest.mark.parametrize("all_zero", [False, True])
def test_zero_capacity_semantics(all_zero: bool) -> None:
    source, census = inputs()
    rows = list(csv.DictReader(StringIO(source)))
    capacities = [r for r in rows if r["table_number"] == "19" and r["geography_id"] != "1106"]
    for row in capacities if all_zero else capacities[:1]:
        row["value_2019_11"] = "0"
        if all_zero:
            row["value_2022_11"] = "0"
        row["reported_change"] = row["value_2022_11"]
    for field in COLUMNS[-3:]:
        rows[-1][field] = str(sum(int(r[field]) for r in capacities))
    if all_zero:
        with pytest.raises(ValueError, match="positive municipality"):
            analyse(table(rows), census)
    else:
        _, tables, _ = analyse(table(rows), census)
        first = tables["parish_capacity.csv"][0]
        assert first["capacity_change_pct"] is None
        assert first["capacity_change_per_1000_2021_residents"] == Decimal(2000)


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_historical_capacity.py"
    spec = importlib.util.spec_from_file_location("historical_capacity_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_replay_uses_verified_aggregate_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes
    seen: set[str] = set()

    def read_once(path: Path) -> bytes:
        if path.name in {"published_values.csv", "census_context.csv"}:
            assert path.name not in seen
            seen.add(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "result"
    path = "scripts/analyse_historical_capacity.py"
    monkeypatch.setattr(sys, "argv", [path, "--output", str(output)])
    runpy.run_path(path, run_name="__main__")
    report = json.loads((output / "analysis.json").read_bytes())
    assert (
        len(seen) == 2 and report["benchmark_summary_verified"] and report["census_total_verified"]
    )
    assert report["summary"]["parishes"] == 24
    city = report["summary"]["municipality"]
    assert (
        city["baseline_capacity"],
        city["latest_capacity"],
        city["population_resident_2021"],
    ) == (111492, 116218, 545796)
    assert report["summary"]["concentration"][0]["capacity_change"] == -417
    assert set(p.name for p in output.iterdir()) == {
        "analysis.json",
        "parish_capacity.csv",
        "municipality_capacity.csv",
        "concentration.csv",
        "historical_capacity.png",
    }
    for item in report["outputs"] + report["code_and_configuration"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]


@pytest.mark.parametrize("failure", ["hash", "existing", "parent", "summary", "census", "render"])
def test_replay_failure_is_atomic(
    tmp_path: Path, script: ModuleType, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    text = CONFIG.read_text(encoding="utf-8")
    output = tmp_path / "result"
    if failure == "hash":
        text = text.replace("size_bytes = 1944", "size_bytes = 1")
    elif failure == "existing":
        output.mkdir()
    elif failure in {"parent", "summary", "census"}:
        path = Path(
            "results/source-audit/2026-10-01/audit.json"
            if failure == "census"
            else "results/cml-benchmarks/2026-10-03/audit.json"
        )
        original = path.read_bytes()
        document = json.loads(original)
        if failure == "parent":
            document["inputs"]["transcription"]["sha256"] = "0" * 64
        elif failure == "summary":
            document["summary"]["parishes"] = 23
        else:
            document["census"]["population_resident"] = 1
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

        monkeypatch.setattr(script, "plot_historical_capacity", fail)
    config = tmp_path / "config.toml"
    config.write_text(text, encoding="utf-8")
    with pytest.raises((ValueError, FileExistsError, OSError)):
        script.analyse(config, output)
    assert not output.exists() or not list(output.iterdir())
    assert not list(tmp_path.glob(".historical-capacity-*"))
