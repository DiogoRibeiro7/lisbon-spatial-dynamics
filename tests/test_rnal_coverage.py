"""Offline acquisition and comparison safeguards for the RNAL coverage audit."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from lisbon_spatial_dynamics.analysis.rnal_coverage import compare_snapshots
from lisbon_spatial_dynamics.panels.housing import FreguesiaIndexRow
from lisbon_spatial_dynamics.panels.rnal import RNALRecord
from lisbon_spatial_dynamics.sources.rnal_geodata import FIELDS, epoch_date, fetch_snapshot


def gis_row(number: int = 1, parish: str = "110654") -> dict[str, Any]:
    return {
        "OBJECTID": number,
        "NrRNAL": number,
        "DataRegisto": -1249171200000,
        "DataAberturaPublico": 1414540800000,
        "DTMNFR": parish,
        "Freguesia": "Alvalade",
        "Concelho": "Lisboa",
        "NrUtentes": 4,
    }


def soap_row(number: int = 1) -> RNALRecord:
    return RNALRecord(f"{number}/AL", date(1930, 6, 2), None, "110654", "Alvalade", "", 2, 4)


REFERENCE = [FreguesiaIndexRow("110654", "Alvalade"), FreguesiaIndexRow("110655", "Areeiro")]


def compare(
    soap: list[RNALRecord], gis: list[dict[str, Any]]
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    return compare_snapshots(
        soap, gis, REFERENCE, benchmark_date=date(2022, 11, 30), benchmark_count=10
    )


def responses() -> list[dict[str, Any]]:
    return [
        {
            "fields": [
                {
                    "name": field,
                    "type": "esriFieldTypeDate"
                    if field.startswith("Data")
                    else "esriFieldTypeString",
                }
                for field in FIELDS
            ],
            "maxRecordCount": 1,
        },
        {"description": "Synthetic fixture"},
        {"objectIdFieldName": "OBJECTID", "objectIds": [1, 2]},
        {"count": 2},
        {"features": [{"attributes": gis_row()}]},
        {"features": [{"attributes": gis_row(2)}]},
        {"objectIdFieldName": "OBJECTID", "objectIds": [2, 1]},
    ]


def capture(output: Path, documents: list[dict[str, Any]]) -> tuple[Path, list[str]]:
    urls: list[str] = []
    iterator = iter(documents)

    def getter(url: str, timeout: float) -> bytes:
        urls.append(url)
        return json.dumps(next(iterator)).encode()

    return fetch_snapshot(output, getter=getter), urls


def test_capture_paginates_and_discards_unrequested_personal_fields(tmp_path: Path) -> None:
    documents = responses()
    documents[4]["features"][0]["attributes"]["Contact"] = "PRIVATE SENTINEL"
    documents[4]["features"][0]["geometry"] = {"x": 99}
    manifest_path, urls = capture(tmp_path / "capture", documents)
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["record_count"] == 2
    assert manifest["membership_stable_during_capture"]
    for url in urls[4:6]:
        query = parse_qs(urlparse(url).query)
        assert query["outFields"] == [",".join(FIELDS)]
        assert query["returnGeometry"] == ["false"]
    for path in manifest_path.parent.iterdir():
        assert b"PRIVATE SENTINEL" not in path.read_bytes()
    for resource in manifest["resources"]:
        payload = (manifest_path.parent / resource["file"]).read_bytes()
        assert resource["sha256"] == sha256(payload).hexdigest()
        assert resource["size_bytes"] == len(payload)
    assert set(
        json.loads((manifest_path.parent / "records.json").read_bytes())["records"][0]
    ) == set(FIELDS)
    with pytest.raises(FileExistsError):
        capture(manifest_path.parent, documents)


@pytest.mark.parametrize(
    "failure",
    [
        "truncated",
        "missing_row",
        "wrong_id",
        "duplicate_registry",
        "roster_changed",
        "count_changed",
        "error",
        "unknown_zone",
    ],
)
def test_invalid_capture_never_writes_a_snapshot(tmp_path: Path, failure: str) -> None:
    documents = responses()
    if failure == "truncated":
        documents[4]["exceededTransferLimit"] = True
    elif failure == "missing_row":
        documents[4]["features"] = []
    elif failure == "wrong_id":
        documents[4]["features"][0]["attributes"]["OBJECTID"] = 3
    elif failure == "duplicate_registry":
        documents[5]["features"][0]["attributes"]["NrRNAL"] = 1
    elif failure == "roster_changed":
        documents[6]["objectIds"] = [1, 3]
    elif failure == "count_changed":
        documents[3]["count"] = 3
    elif failure == "unknown_zone":
        documents[0]["datesInUnknownTimezone"] = True
    else:
        documents[4] = {"error": {"code": 500}}
    output = tmp_path / "capture"
    with pytest.raises(ValueError):
        capture(output, documents)
    assert not output.exists()


def test_pre_epoch_dates_are_preserved_and_opening_date_is_not_substituted() -> None:
    assert epoch_date(-1249171200000) == date(1930, 6, 2)
    assert epoch_date(None) is None
    summary, _, early = compare([soap_row()], [gis_row()])
    assert summary["shared_registration_date_disagreements"] == 0
    assert early[0]["shared_with_same_registration_date"] == 1
    assert early[0]["gis_opening_before_screen"] == 0
    assert not summary["historical_completeness_established"]


@pytest.mark.parametrize("invalid", [True, 1.5, "0", 10**30])
def test_invalid_epoch_dates_fail(invalid: object) -> None:
    with pytest.raises(ValueError):
        epoch_date(invalid)


def test_membership_and_parish_differences_are_distinct() -> None:
    changed = gis_row(1, "110655")
    changed["Freguesia"] = "Areeiro"
    summary, rows, _ = compare([soap_row(), soap_row(3)], [changed, gis_row(2)])
    assert summary["shared_ids"] == 1
    assert summary["soap_only_ids"] == 1
    assert summary["gis_only_ids"] == 1
    assert summary["shared_parish_disagreements"] == 1
    assert rows[0]["shared_same_parish"] == 0
    assert rows[0]["soap_only"] == 1
    assert rows[1]["gis_only"] == 0
    assert summary["parish_assignment_disagreement_pairs"] == [
        {"soap_freguesia_id": "110654", "gis_freguesia_id": "110655", "records": 1}
    ]
    assert not summary["membership_differences_are_closure_events"]


def test_benchmark_excludes_future_registrations_and_already_ceased_records() -> None:
    soap = [
        soap_row(),
        replace(soap_row(2), ceased_on=date(2022, 11, 30)),
        replace(soap_row(3), registered_on=date(2022, 12, 1)),
        replace(soap_row(4), registered_on=date(2022, 11, 30)),
    ]
    summary, _, _ = compare(soap, [gis_row()])
    benchmark = summary["benchmark"]
    assert isinstance(benchmark, dict)
    assert benchmark["soap_snapshot_cohort_at_date"] == 2
    assert benchmark["snapshot_cohort_minus_published"] == -8


def test_normalized_id_collision_and_unknown_parish_fail() -> None:
    with pytest.raises(ValueError, match="normalized SOAP"):
        compare([soap_row(), replace(soap_row(), registration_id="01/AL")], [gis_row()])
    with pytest.raises(ValueError, match="unknown parish"):
        compare([soap_row()], [gis_row(parish="110699")])


@pytest.fixture(scope="module")
def audit_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/audit_rnal_coverage.py"
    spec = importlib.util.spec_from_file_location("rnal_coverage_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pinned_input_tampering_is_rejected(tmp_path: Path, audit_module: ModuleType) -> None:
    path = tmp_path / "snapshot.json"
    path.write_bytes(b"original")
    expected = audit_module.fingerprint(path)
    path.write_bytes(b"modified")
    with pytest.raises(ValueError, match="integrity mismatch"):
        audit_module.verify(path, expected)


def test_date_and_capacity_disagreements_are_counted_separately() -> None:
    changed = deepcopy(gis_row())
    changed["DataRegisto"] = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    changed["NrUtentes"] = None
    summary, _, early = compare([soap_row()], [changed])
    assert summary["shared_registration_date_disagreements"] == 1
    assert summary["shared_capacity_disagreements"] == 1
    assert summary["shared_parish_disagreements"] == 0
    assert early[0]["gis_records"] == 0


def test_offline_audit_replays_aggregates_and_rejects_tampered_resources(
    tmp_path: Path, audit_module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    gis_manifest, _ = capture(tmp_path / "gis", responses())
    soap_path = tmp_path / "soap.json"
    soap_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "NrRegisto": "1/AL",
                        "DataRegisto": "1930-06-02",
                        "CessadoEm": "",
                        "DTMNFR": "110654",
                        "Freguesia": "Alvalade",
                        "NrUtentes": "4",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    soap_manifest = tmp_path / "soap_manifest.json"
    soap_manifest.write_text(
        json.dumps(
            {
                "sanitised_snapshot": audit_module.fingerprint(soap_path),
                "written_record_count": 1,
                "fetched_at": "2026-10-01T00:00:00Z",
                "endpoint_url": "https://example.invalid/soap",
            }
        ),
        encoding="utf-8",
    )
    reference = tmp_path / "reference.csv"
    reference.write_text(
        "freguesia_id,name\n110654,Alvalade\n"
        + "".join(f"1106{n:02d},Parish {n}\n" for n in range(1, 24)),
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    lines = [
        'audit_date = "2026-10-01"',
        "[benchmark]",
        'date = "2022-11-30"',
        "registrations = 10",
    ]
    for name, path in {
        "soap_manifest": soap_manifest,
        "gis_manifest": gis_manifest,
        "reference": reference,
    }.items():
        lines.append(f"[inputs.{name}]")
        lines.extend(
            f"{key} = {json.dumps(value)}" for key, value in audit_module.fingerprint(path).items()
        )
    config.write_text("\n".join(lines), encoding="utf-8")

    def no_network(*args: object, **kwargs: object) -> None:
        pytest.fail("offline audit attempted network access")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    monkeypatch.setattr("lisbon_spatial_dynamics.sources.rnal_geodata.urlopen", no_network)
    output = tmp_path / "audit"
    audit_module.audit(config, output)
    report = json.loads((output / "audit.json").read_bytes())
    assert report["summary"]["shared_ids"] == 1
    assert report["summary"]["gis_only_ids"] == 1
    assert "1/AL" not in (output / "audit.json").read_text(encoding="utf-8")
    for artifact in report["outputs"]:
        audit_module.verify(Path(artifact["path"]), artifact)
    with pytest.raises(FileExistsError):
        audit_module.audit(config, output)
    second = tmp_path / "replay"
    audit_module.audit(config, second)
    for filename in ("parish_comparison.csv", "early_registration_years.csv"):
        assert (output / filename).read_bytes() == (second / filename).read_bytes()
    (gis_manifest.parent / "records.json").write_bytes(b"{}")
    failed_output = tmp_path / "failed"
    with pytest.raises(ValueError, match="integrity mismatch"):
        audit_module.audit(config, failed_output)
    assert not failed_output.exists()
