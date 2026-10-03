"""Historical transcription checks preserve facts, precision and visible discrepancies."""

from __future__ import annotations

import csv
import importlib.util
import json
import tomllib
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.cml_benchmarks import (
    COLUMNS,
    audit_transcription,
    parse_reference,
)

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara"}


def source_rows() -> list[list[Any]]:
    return [
        [18, 1, "110601", "Ajuda", 4, 6, 1],
        [18, 2, "110602", "Alcântara", 5, 4, -1],
        [18, 0, "1106", "LISBOA - TOTAL", 10, 10, 0],
        [19, 1, "110601", "Ajuda", 40, 60, 20],
        [19, 2, "110602", "Alcântara", 50, 40, -10],
        [19, 0, "1106", "LISBOA - TOTAL", 90, 100, 10],
    ]


def transcription(rows: list[list[Any]]) -> str:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return stream.getvalue()


def test_preserves_published_numbers_and_exposes_arithmetic_without_correction() -> None:
    summary, observations, arithmetic = audit_transcription(transcription(source_rows()), REFERENCE)
    assert summary["published_values_corrected"] == 0
    assert summary["parish_observations"] == 8
    assert len(observations) == 12  # Municipality totals remain separate from parish observations.
    assert {row["reference_month"] for row in observations} == {"2019-11", "2022-11"}
    assert {row["unit"] for row in observations} == {
        "capacity_weighted_al_units",
        "reported_user_capacity",
    }
    assert {row["pdf_page"] for row in observations} == {105, 107}
    weighted, capacity = summary["tables"]
    assert weighted["row_change_discrepancies"] == [
        {"geography_id": "110601", "calculated_minus_published_change": 1}
    ]
    assert weighted["column_sum_checks"][0] == {
        "field": "value_2019_11",
        "parish_sum": 9,
        "published_municipality": 10,
        "parish_sum_minus_published_municipality": -1,
    }
    assert capacity["row_change_discrepancies"] == []
    assert all(
        row["parish_sum_minus_published_municipality"] == 0 for row in capacity["column_sum_checks"]
    )
    assert capacity["parishes_decreased_from_displayed_levels"] == 1
    observed = next(
        row
        for row in observations
        if row["table_number"] == 18
        and row["geography_id"] == "1106"
        and row["reference_month"] == "2019-11"
    )
    assert observed["published_value"] == 10  # The inconsistent total is preserved.
    check = next(
        row for row in arithmetic if row["table_number"] == 18 and row["geography_id"] == "110601"
    )
    assert check["published_change"] == 1
    assert check["calculated_change_from_displayed_levels"] == 2


@pytest.mark.parametrize(
    "failure",
    [
        "duplicate",
        "missing_parish",
        "missing_total",
        "missing_table",
        "unknown_parish",
        "wrong_name",
        "row_order",
        "unknown_table",
        "bad_total",
        "fractional",
        "negative",
        "ragged",
    ],
)
def test_rejects_incomplete_or_ambiguous_transcription(failure: str) -> None:
    rows = source_rows()
    if failure == "duplicate":
        rows.append(rows[0].copy())
    elif failure == "missing_parish":
        rows.pop(0)
    elif failure == "missing_total":
        rows.pop(2)
    elif failure == "missing_table":
        rows = rows[:3]
    elif failure == "unknown_parish":
        rows[0][2] = "110699"
    elif failure == "wrong_name":
        rows[0][3] = "Different"
    elif failure == "row_order":
        rows[1][1] = 1
    elif failure == "unknown_table":
        rows[0][0] = 6
    elif failure == "bad_total":
        rows[2][3] = "Ajuda"
    elif failure == "fractional":
        rows[0][4] = "4.5"
    elif failure == "negative":
        rows[0][4] = -4
    else:
        rows[0].pop()
    with pytest.raises(ValueError):
        audit_transcription(transcription(rows), REFERENCE)


def test_reference_requires_exact_canonical_coverage() -> None:
    payload = "freguesia_id,freguesia_name\n110601,Ajuda\n110602,Alcântara\n"
    assert parse_reference(payload, expected_count=2) == REFERENCE
    with pytest.raises(ValueError, match="count"):
        parse_reference(payload, expected_count=24)
    with pytest.raises(ValueError, match="duplicate"):
        parse_reference(payload + "110601,Ajuda\n", expected_count=3)


@pytest.fixture(scope="module")
def audit_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/audit_cml_benchmarks.py"
    spec = importlib.util.spec_from_file_location("cml_benchmark_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit_config(tmp_path: Path, audit_module: ModuleType) -> Path:
    source_pdf = tmp_path / "report.pdf"
    source_pdf.write_bytes(b"%PDF-synthetic-source-identity-only")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(audit_module.fingerprint(source_pdf, source_pdf.read_bytes())), encoding="utf-8"
    )
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "freguesia_id,freguesia_name\n110601,Ajuda\n110602,Alcântara\n", encoding="utf-8"
    )
    source_csv = tmp_path / "transcription.csv"
    source_csv.write_text(transcription(source_rows()), encoding="utf-8")
    lines = [
        'audit_date = "2026-10-03"',
        "parishes = 2",
        "[source]",
        'title = "Synthetic"',
        'reference_months = ["2019-11", "2022-11"]',
        "[transcription]",
        'method = "Fixture"',
    ]
    for name, path in {
        "source_pdf": source_pdf,
        "source_manifest": manifest,
        "reference": reference,
        "transcription": source_csv,
    }.items():
        lines.append(f"[inputs.{name}]")
        lines.extend(
            f"{key} = {json.dumps(value)}"
            for key, value in audit_module.fingerprint(path, path.read_bytes()).items()
        )
    config = tmp_path / "config.toml"
    config.write_text("\n".join(lines), encoding="utf-8")
    return config


def test_offline_replay_requires_complete_atomic_bundle(
    tmp_path: Path, audit_module: ModuleType, audit_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        pytest.fail("offline benchmark attempted network access")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    original_write = Path.write_bytes

    def failed_write(path: Path, payload: bytes) -> int:
        if path.name == "audit.json":
            raise OSError("simulated publication failure")
        return original_write(path, payload)

    output = tmp_path / "output"
    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_bytes", failed_write)
        with pytest.raises(OSError, match="simulated"):
            audit_module.audit(audit_config, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".cml-benchmarks-*"))
    audit_module.audit(audit_config, output)
    expected_files = {"audit.json", "published_observations.csv", "arithmetic_checks.csv"}
    assert {path.name for path in output.iterdir()} == expected_files
    report = json.loads((output / "audit.json").read_bytes())
    assert len(report["outputs"]) == 2
    for artifact in report["outputs"]:
        path = Path(artifact["path"])
        assert path.parent == output
        assert audit_module.fingerprint(path, path.read_bytes()) == artifact
    with pytest.raises(FileExistsError):
        audit_module.audit(audit_config, output)
    replay = tmp_path / "replay"
    audit_module.audit(audit_config, replay)
    for name in expected_files - {"audit.json"}:
        assert (output / name).read_bytes() == (replay / name).read_bytes()
    (tmp_path / "transcription.csv").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        audit_module.audit(audit_config, tmp_path / "tampered")
    assert not (tmp_path / "tampered").exists()


def test_transcription_is_parsed_from_exact_verified_bytes(
    tmp_path: Path, audit_module: ModuleType, audit_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "transcription.csv"
    original = Path.read_bytes
    captured = original(path)
    calls = 0

    def changed_after_read(target: Path) -> bytes:
        nonlocal calls
        payload = original(target)
        if target == path:
            calls += 1
            target.write_bytes(b"changed after capture")
        return payload

    output = tmp_path / "output"
    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", changed_after_read)
        audit_module.audit(audit_config, output)
    report = json.loads((output / "audit.json").read_bytes())
    assert calls == 1
    assert report["inputs"]["transcription"] == audit_module.fingerprint(path, captured)
    assert report["summary"]["tables"][1]["published_municipality_2022_11"] == 100


def test_reference_months_cannot_be_relabelled(
    tmp_path: Path, audit_module: ModuleType, audit_config: Path
) -> None:
    audit_config.write_text(
        audit_config.read_text(encoding="utf-8").replace('"2022-11"', '"2022-12"'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reference months"):
        audit_module.audit(audit_config, tmp_path / "wrong_month")
    assert not (tmp_path / "wrong_month").exists()


def test_committed_transcription_matches_pins_and_preserves_source_discrepancies() -> None:
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads(
        (root / "configs/cml_benchmarks_2026-10-03.toml").read_text(encoding="utf-8")
    )
    captured = {}
    for name in ("reference", "transcription"):
        pin = config["inputs"][name]
        payload = (root / pin["path"]).read_bytes()
        assert sha256(payload).hexdigest() == pin["sha256"]
        assert len(payload) == pin["size_bytes"]
        captured[name] = payload.decode("utf-8")
    summary, observations, _ = audit_transcription(
        captured["transcription"], parse_reference(captured["reference"], expected_count=24)
    )
    assert len(observations) == 100 and summary["parish_observations"] == 96
    weighted, capacity = summary["tables"]
    assert weighted["published_municipality_change"] == 1138
    assert weighted["calculated_municipality_change_from_displayed_levels"] == 1139
    assert {row["geography_id"] for row in weighted["row_change_discrepancies"]} == {
        "1106",
        "110639",
        "110659",
        "110662",
    }
    assert capacity["published_municipality_2019_11"] == 111492
    assert capacity["published_municipality_2022_11"] == 116218
    assert capacity["published_municipality_change"] == 4726
    assert capacity["row_change_discrepancies"] == []
