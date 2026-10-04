"""Community export provenance, minimization and membership interpretation regressions."""

from __future__ import annotations

import csv
import gzip
import importlib.util
import io
import json
import tomllib
from datetime import date
from hashlib import sha1, sha256
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.rnal_archive import (
    CAPACITY_COLUMN_DEFINITIONS,
    EXPORT_FIELDS,
    analyse_archive,
    minimize_export,
    parse_snapshot,
    timestamp_from_filename,
)
from lisbon_spatial_dynamics.panels.rnal import RNALRecord

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara"}
FIRST = "al_20250525_151726.csv.gz"
SECOND = "al_20250607_141011.csv.gz"
THIRD = "al_20250703_203137.csv.gz"


def export(
    filename: str = FIRST,
    rows: list[list[str]] | None = None,
    fields: tuple[str, ...] = (*EXPORT_FIELDS, "Contacto Email"),
) -> bytes:
    if rows is None:
        rows = [
            ["1/AL", "2019-01-01", "0", "Ajuda", " Lisboa ", "private@example.invalid"],
            ["2/AL", "2020-01-01", "", "Alcântara", "Lisboa", "another@example.invalid"],
            ["3/AL", "2021-01-01", "4", "Unknown elsewhere", "Porto", "elsewhere@example.invalid"],
        ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(fields)
    writer.writerows([timestamp_from_filename(filename), *row] for row in rows)
    return gzip.compress(stream.getvalue().encode("utf-8-sig"), mtime=0)


def test_minimization_excludes_personal_fields_and_non_lisbon_rows() -> None:
    minimized = minimize_export(export(), FIRST, REFERENCE)
    assert b"example.invalid" not in minimized
    assert b"Contacto" not in minimized
    snapshot = parse_snapshot(minimized, REFERENCE)
    assert snapshot.source_rows == 3
    assert snapshot.lisbon_source_rows == 2
    assert set(snapshot.records) == {1, 2}
    assert snapshot.records[1].users == 0  # Zero is distinct from missing.
    assert snapshot.records[2].users is None
    assert snapshot.records[2].freguesia_id == "110602"


def test_duplicate_collapse_is_explicit_and_conflicts_are_rejected() -> None:
    row = ["1/AL", "2019-01-01", "5", "Ajuda", "Lisboa", "one@example.invalid"]
    duplicate = ["01/AL", "2019-01-01", "5", "Ajuda", "Lisboa", "two@example.invalid"]
    snapshot = parse_snapshot(
        minimize_export(export(rows=[row, duplicate]), FIRST, REFERENCE), REFERENCE
    )
    assert snapshot.lisbon_source_rows == 2
    assert len(snapshot.records) == 1
    # Only agreement on retained analytical fields is asserted, never full-row equality.
    duplicate[2] = "6"
    with pytest.raises(ValueError, match="conflicting duplicate"):
        minimize_export(export(rows=[row, duplicate]), FIRST, REFERENCE)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (0, "not-an-id", "registry number"),
        (0, "0/AL", "registry number"),
        (1, "20250101", "ISO"),
        (1, "2026-01-01", "follows export"),
        (2, "-1", "capacity"),
        (2, "1.5", "capacity"),
        (3, "Unknown", "unknown Lisbon parish"),
    ],
)
def test_invalid_analytical_fields_fail(field: int, value: str, message: str) -> None:
    row = ["1/AL", "2019-01-01", "5", "Ajuda", "Lisboa", "private@example.invalid"]
    row[field] = value
    with pytest.raises(ValueError, match=message):
        minimize_export(export(rows=[row]), FIRST, REFERENCE)


def test_schema_timestamp_and_ragged_rows_fail() -> None:
    with pytest.raises(ValueError, match="columns"):
        minimize_export(
            export(fields=(*EXPORT_FIELDS[:-1], "Other", "Contacto Email")), FIRST, REFERENCE
        )
    with pytest.raises(ValueError, match="columns"):
        minimize_export(export(fields=(*EXPORT_FIELDS, "etl_timestamp")), FIRST, REFERENCE)
    with pytest.raises(ValueError, match="timestamp differs"):
        minimize_export(export(), SECOND, REFERENCE)
    with pytest.raises(ValueError, match="ragged"):
        minimize_export(export(rows=[["1/AL"]]), FIRST, REFERENCE)


def soap_records() -> tuple[RNALRecord, ...]:
    return (
        RNALRecord("1/AL", date(2019, 1, 1), None, "110601", "Ajuda", "", None, 0),
        RNALRecord("2/AL", date(2020, 1, 1), None, "110602", "Alcântara", "", None, None),
        RNALRecord("9/AL", date(1965, 1, 1), None, "110601", "Ajuda", "", None, 6),
    )


def test_tracks_reappearance_changes_and_missing_capacity_without_inventing_events() -> None:
    first = parse_snapshot(minimize_export(export(), FIRST, REFERENCE), REFERENCE)
    second = parse_snapshot(
        minimize_export(
            export(SECOND, [["2/AL", "2020-01-02", "7", "Ajuda", "Lisboa", "private"]]),
            SECOND,
            REFERENCE,
        ),
        REFERENCE,
    )
    third = parse_snapshot(minimize_export(export(THIRD), THIRD, REFERENCE), REFERENCE)
    summary, datasets = analyse_archive([third, first, second], REFERENCE, soap_records())
    changes = datasets["snapshot_changes.csv"]
    assert changes[0]["earlier_only"] == 1
    assert changes[0]["shared_registration_date_changes"] == 1
    assert changes[0]["shared_parish_changes"] == 1
    assert changes[0]["shared_capacity_changes"] == 1
    assert changes[1]["later_only_previously_seen"] == 1
    assert summary["consecutive_reappearance_observations"] == 1
    assert summary["first_to_last_membership"]["net_change"] == 0
    assert summary["latest_archive_vs_soap"]["soap_only_registration_years"] == {1965: 1}
    assert summary["membership_differences_are_closure_events"] is False
    assert summary["quarter_end_observations_imputed"] is False
    assert len(datasets["parish_snapshots.csv"]) == 6
    assert datasets["parish_snapshots.csv"][3]["records"] == 0
    with pytest.raises(ValueError, match="duplicate archive timestamps"):
        analyse_archive([first, first], REFERENCE, soap_records())


@pytest.mark.parametrize("failure", ["duplicate", "pii", "boolean_capacity", "count", "timestamp"])
def test_minimized_input_validation(failure: str) -> None:
    document = json.loads(minimize_export(export(), FIRST, REFERENCE))
    if failure == "duplicate":
        document["records"].append(document["records"][0])
    elif failure == "pii":
        document["records"][0]["email"] = "private@example.invalid"
    elif failure == "boolean_capacity":
        document["records"][0]["users"] = True
    elif failure == "count":
        document["lisbon_source_rows"] = 1
    else:
        document["source_timestamp"] = "2026-01-01 00:00:00"
    with pytest.raises(ValueError):
        parse_snapshot(json.dumps(document).encode(), REFERENCE)


@pytest.mark.parametrize("value", [None, True, 1, 1.5, "text", []])
def test_minimized_root_requires_a_json_object(value: object) -> None:
    with pytest.raises(ValueError, match="archive schema"):
        parse_snapshot(json.dumps(value).encode(), REFERENCE)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", True, "archive schema"),
        ("schema_version", 1.0, "archive schema"),
        ("source_file", 123, "source filename"),
        ("source_file", None, "source filename"),
        ("source_timestamp", 123, "timestamp"),
        ("records", None, "must be a list"),
        ("records", {}, "must be a list"),
        ("records", "records", "must be a list"),
    ],
)
def test_minimized_document_field_types_fail_uniformly(
    field: str, value: object, message: str
) -> None:
    document = json.loads(minimize_export(export(), FIRST, REFERENCE))
    document[field] = value
    with pytest.raises(ValueError, match=message):
        parse_snapshot(json.dumps(document).encode(), REFERENCE)


@pytest.mark.parametrize("value", [None, True, 1, "record", []])
def test_minimized_record_requires_a_json_object(value: object) -> None:
    document = json.loads(minimize_export(export(), FIRST, REFERENCE))
    document["records"][0] = value
    with pytest.raises(ValueError, match="record fields"):
        parse_snapshot(json.dumps(document).encode(), REFERENCE)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("registered_on", 123, "registration date"),
        ("registered_on", None, "registration date"),
        ("registered_on", [], "registration date"),
        ("freguesia_id", [], "parish"),
        ("freguesia_id", {}, "parish"),
        ("freguesia_id", 110601, "parish"),
        ("registration_id", True, "registry number"),
        ("registration_id", 1.0, "registry number"),
        ("users", 1.5, "capacity"),
        ("users", "4", "capacity"),
    ],
)
def test_minimized_record_field_types_fail_uniformly(
    field: str, value: object, message: str
) -> None:
    document = json.loads(minimize_export(export(), FIRST, REFERENCE))
    document["records"][0][field] = value
    with pytest.raises(ValueError, match=message):
        parse_snapshot(json.dumps(document).encode(), REFERENCE)


@pytest.mark.parametrize("field", ["source_rows", "lisbon_source_rows"])
@pytest.mark.parametrize("value", [None, True, 3.0, "3", []])
def test_row_counts_reject_non_integer_types(field: str, value: object) -> None:
    # Floats already failed before the review fix; keep the strict count contract.
    document = json.loads(minimize_export(export(), FIRST, REFERENCE))
    document[field] = value
    with pytest.raises(ValueError, match="row count"):
        parse_snapshot(json.dumps(document).encode(), REFERENCE)


def test_capacity_dictionary_covers_published_columns_and_units() -> None:
    root = Path(__file__).resolve().parents[1] / "results/rnal-archive"
    published = json.loads((root / "column_definitions.json").read_bytes())
    assert published == CAPACITY_COLUMN_DEFINITIONS
    assert published["users_known"]["unit"] == "reported accommodation places"
    assert published["users_missing_records"]["unit"] == "registry records"
    assert published["users_zero_records"]["unit"] == "registry records"
    for filename in ("snapshot_summary.csv", "parish_snapshots.csv"):
        with (root / "2026-10-03" / filename).open(encoding="utf-8", newline="") as stream:
            fields = next(csv.reader(stream))
        assert {field for field in fields if field.startswith("users_")} == {
            field for field, definition in published.items() if filename in definition["files"]
        }


@pytest.fixture
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/audit_rnal_archive.py"
    spec = importlib.util.spec_from_file_location("archive_audit_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def input_pin(name: str, path: Path) -> str:
    payload = path.read_bytes()
    return (
        f'\n[inputs.{name}]\npath = "{path.as_posix()}"\n'
        f'sha256 = "{sha256(payload).hexdigest()}"\nsize_bytes = {len(payload)}\n'
    )


def prepare_config(
    tmp_path: Path, filenames: tuple[str, ...] = (FIRST, SECOND)
) -> tuple[Path, dict[str, bytes]]:
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "freguesia_id,freguesia_name\n110601,Ajuda\n110602,Alcântara\n", encoding="utf-8"
    )
    soap = tmp_path / "soap.json"
    soap.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "NrRegisto": "1/AL",
                        "DataRegisto": "2019-01-01",
                        "DTMNFR": "110601",
                        "Freguesia": "Ajuda",
                        "NrUtentes": 0,
                    },
                    {
                        "NrRegisto": "2/AL",
                        "DataRegisto": "2020-01-01",
                        "DTMNFR": "110602",
                        "Freguesia": "Alcântara",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    text = """audit_date = "2026-10-03"
parishes = 2
[source]
repository = "sztanko/al-pulse"
revision = "50322b0ae5680d24013fae4ee19d757350a8ba2c"
"""
    text += input_pin("reference", reference) + input_pin("soap", soap)
    soap_manifest = tmp_path / "soap_manifest.json"
    soap_manifest.write_text(
        json.dumps(
            {
                "sanitised_snapshot": tomllib.loads(text)["inputs"]["soap"],
                "municipality": "Lisboa",
                "written_record_count": 2,
                "fetched_at": "2026-10-01T10:38:59Z",
            }
        ),
        encoding="utf-8",
    )
    text += input_pin("soap_manifest", soap_manifest)
    payloads = {filename: export(filename) for filename in filenames}
    for filename, payload in payloads.items():
        blob = sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
        text += (
            f'\n[[exports]]\nfile = "{filename}"\ngit_blob_sha1 = "{blob}"\n'
            f"size_bytes = {len(payload)}\n"
        )
    config = tmp_path / "config.toml"
    config.write_text(text, encoding="utf-8")
    return config, payloads


def test_acquisition_replay_integrity_and_atomic_failure(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, payloads = prepare_config(tmp_path)
    monkeypatch.setattr(
        script,
        "get_bytes",
        lambda url: payloads.get(url.rsplit("/", 1)[1], b"publisher provenance"),
    )
    source = tmp_path / "source"
    script.fetch(config, source)
    assert not list(source.glob("*.gz"))
    assert all(b"example.invalid" not in file.read_bytes() for file in source.iterdir())
    with config.open("a", encoding="utf-8") as stream:
        stream.write(input_pin("acquisition_manifest", source / "manifest.json"))
    output = tmp_path / "output"
    script.audit(config, output)
    assert {file.name for file in output.iterdir()} == {
        "audit.json",
        "snapshot_summary.csv",
        "snapshot_changes.csv",
        "parish_snapshots.csv",
    }
    report = json.loads((output / "audit.json").read_bytes())
    assert report["summary"]["snapshots"] == 2
    assert report["column_definitions"] == CAPACITY_COLUMN_DEFINITIONS
    for artifact in report["outputs"]:
        assert (
            script.fingerprint(Path(artifact["path"]).read_bytes())["sha256"] == artifact["sha256"]
        )
    with pytest.raises(FileExistsError):
        script.audit(config, output)
    original_write = script.write_json

    def fail_write(path: Path, value: Any) -> None:
        raise OSError("simulated failed publication")

    monkeypatch.setattr(script, "write_json", fail_write)
    retry = tmp_path / "retry"
    with pytest.raises(OSError, match="failed publication"):
        script.audit(config, retry)
    assert not retry.exists()
    assert not list(tmp_path.glob(".rnal-archive-audit-*"))
    monkeypatch.setattr(script, "write_json", original_write)
    script.audit(config, retry)
    for filename in ("snapshot_summary.csv", "snapshot_changes.csv", "parish_snapshots.csv"):
        assert (retry / filename).read_bytes() == (output / filename).read_bytes()
    minimized = source / FIRST.replace(".csv.gz", ".json")
    minimized.write_bytes(minimized.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity mismatch"):
        script.audit(config, tmp_path / "tampered")
    assert not (tmp_path / "tampered").exists()


def test_fetch_checksum_failure_publishes_nothing(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, payloads = prepare_config(tmp_path)
    payloads[SECOND] = b"corrupted"
    monkeypatch.setattr(script, "get_bytes", lambda url: payloads[url.rsplit("/", 1)[1]])
    with pytest.raises(ValueError, match="pinned Git tree"):
        script.fetch(config, tmp_path / "source")
    assert not (tmp_path / "source").exists()
    assert not list(tmp_path.glob(".rnal-archive-fetch-*"))


def test_replay_parses_captured_verified_bytes(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, payloads = prepare_config(tmp_path)
    monkeypatch.setattr(
        script,
        "get_bytes",
        lambda url: payloads.get(url.rsplit("/", 1)[1], b"publisher provenance"),
    )
    source = tmp_path / "source"
    script.fetch(config, source)
    with config.open("a", encoding="utf-8") as stream:
        stream.write(input_pin("acquisition_manifest", source / "manifest.json"))
    original = script.verified
    poisoned = source / FIRST.replace(".csv.gz", ".json")

    def capture_then_mutate(path: Path, expected: dict[str, Any]) -> bytes:
        payload: bytes = original(path, expected)
        if path == poisoned:
            changed = json.loads(payload)
            changed["records"][0]["users"] = 9999
            path.write_bytes(json.dumps(changed).encode())
        return payload

    monkeypatch.setattr(script, "verified", capture_then_mutate)
    output = tmp_path / "output"
    script.audit(config, output)
    with (output / "snapshot_summary.csv").open(encoding="utf-8") as stream:
        first = next(csv.DictReader(stream))
    assert first["users_known"] == "0"


def test_gap_replay_without_anomalies_writes_header_only_cohorts_and_is_atomic(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, payloads = prepare_config(tmp_path, (FIRST, SECOND, THIRD))
    monkeypatch.setattr(
        script,
        "get_bytes",
        lambda url: payloads.get(url.rsplit("/", 1)[1], b"publisher provenance"),
    )
    source = tmp_path / "source"
    script.fetch(config, source)
    with config.open("a", encoding="utf-8") as stream:
        stream.write(input_pin("acquisition_manifest", source / "manifest.json"))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="unknown archive analysis"):
        script.audit(config, output, analysis="unknown")
    assert not output.exists()
    original_write = script.write_json

    def fail_write(path: Path, value: Any) -> None:
        raise OSError("simulated gap report failure")

    monkeypatch.setattr(script, "write_json", fail_write)
    with pytest.raises(OSError, match="gap report failure"):
        script.audit(config, output, analysis="capture-gaps")
    assert not output.exists()
    assert not list(tmp_path.glob(".rnal-archive-audit-*"))
    monkeypatch.setattr(script, "write_json", original_write)
    script.audit(config, output, analysis="capture-gaps")
    assert {path.name for path in output.iterdir()} == {
        "audit.json",
        "capture_windows.csv",
        "affected_cohorts.csv",
    }
    report = json.loads((output / "audit.json").read_bytes())
    assert report["analysis"] == "capture-gaps"
    assert report["summary"]["missing_middle_record_observations"] == 0
    assert "empty_middle_registration_month" in report["column_definitions"]
    assert "users_known" not in report["column_definitions"]
    with (output / "affected_cohorts.csv").open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames and "registration_month" in reader.fieldnames
        assert list(reader) == []
    for artifact in report["outputs"]:
        assert (
            script.fingerprint(Path(artifact["path"]).read_bytes())["sha256"] == artifact["sha256"]
        )
    with pytest.raises(FileExistsError):
        script.audit(config, output, analysis="capture-gaps")
