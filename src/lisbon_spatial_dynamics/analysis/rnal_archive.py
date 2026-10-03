"""Assess community RNAL exports without turning absence into closure events."""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from lisbon_spatial_dynamics.panels.rnal import RNALRecord

EXPORT_FIELDS = (
    "etl_timestamp",
    "Nº de registo",
    "Data do registo",
    "Nº Utentes",
    "Localização (Freguesia)",
    "Localização (Concelho)",
)
RECORD_FIELDS = {"registration_id", "registered_on", "freguesia_id", "users"}


def normalized_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def registration_number(value: str) -> int:
    if not re.fullmatch(r"[0-9]+/AL", value) or int(value[:-3]) <= 0:
        raise ValueError("invalid registry number format")
    return int(value[:-3])


def timestamp_from_filename(filename: str) -> str:
    match = re.fullmatch(r"al_(\d{8}_\d{6})\.csv\.gz", filename)
    if not match:
        raise ValueError("unexpected archive filename")
    return datetime.strptime(match[1], "%Y%m%d_%H%M%S").isoformat(sep=" ")


def minimize_export(payload: bytes, filename: str, reference: Mapping[str, str]) -> bytes:
    """Persist only Lisbon registry numbers, dates, canonical parish IDs and capacity.

    Source timestamps are publisher-supplied, with unspecified timezone. Raw exports
    can contain personal/contact data and must never be persisted by this function.
    """
    timestamp = timestamp_from_filename(filename)
    names = {normalized_name(name): code for code, name in reference.items()}
    if not names or len(names) != len(reference):
        raise ValueError("ambiguous parish reference")
    records: dict[int, dict[str, Any]] = {}
    source_rows = 0
    lisbon_source_rows = 0
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
        reader = csv.DictReader(io.TextIOWrapper(compressed, encoding="utf-8-sig", newline=""))
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not set(EXPORT_FIELDS).issubset(fields):
            raise ValueError("missing or duplicate export columns")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("ragged export row")
            source_rows += 1
            if row["etl_timestamp"] != timestamp:
                raise ValueError("export timestamp differs from filename")
            if normalized_name(row["Localização (Concelho)"]) != "lisboa":
                continue
            lisbon_source_rows += 1
            number = registration_number(row["Nº de registo"].strip())
            registered = row["Data do registo"].strip()
            if date.fromisoformat(registered).isoformat() != registered:
                raise ValueError("registration date must be ISO YYYY-MM-DD")
            if registered > timestamp[:10]:
                raise ValueError("registration follows export timestamp")
            parish = names.get(normalized_name(row["Localização (Freguesia)"]))
            if parish is None:
                raise ValueError("unknown Lisbon parish")
            raw_users = row["Nº Utentes"].strip()
            if raw_users and not re.fullmatch(r"[0-9]+", raw_users):
                raise ValueError("capacity must be a non-negative integer or blank")
            record = {
                "registration_id": number,
                "registered_on": registered,
                "freguesia_id": parish,
                "users": int(raw_users) if raw_users else None,
            }
            if number in records and records[number] != record:
                raise ValueError("conflicting duplicate Lisbon registry number")
            records[number] = record
    if not records:
        raise ValueError("export contains no Lisbon records")
    document = {
        "schema_version": 1,
        "source_file": filename,
        "source_timestamp": timestamp,
        "source_rows": source_rows,
        "lisbon_source_rows": lisbon_source_rows,
        "records": [records[key] for key in sorted(records)],
    }
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


@dataclass(frozen=True)
class ArchiveRecord:
    registered_on: date
    freguesia_id: str
    users: int | None


@dataclass(frozen=True)
class ArchiveSnapshot:
    source_file: str
    timestamp: str
    source_rows: int
    lisbon_source_rows: int
    records: dict[int, ArchiveRecord]


def parse_snapshot(payload: bytes, reference: Mapping[str, str]) -> ArchiveSnapshot:
    """Validate minimized bytes without reopening the file verified by the caller."""
    document = json.loads(payload)
    if (
        set(document)
        != {
            "schema_version",
            "source_file",
            "source_timestamp",
            "source_rows",
            "lisbon_source_rows",
            "records",
        }
        or document["schema_version"] != 1
    ):
        raise ValueError("invalid minimized archive schema")
    timestamp = timestamp_from_filename(document["source_file"])
    if document["source_timestamp"] != timestamp:
        raise ValueError("invalid minimized timestamp")
    records = {}
    for row in document["records"]:
        if set(row) != RECORD_FIELDS:
            raise ValueError("unexpected minimized record fields")
        key, users = row["registration_id"], row["users"]
        if type(key) is not int or key <= 0 or key in records:
            raise ValueError("duplicate or invalid minimized registry number")
        if users is not None and (type(users) is not int or users < 0):
            raise ValueError("invalid minimized capacity")
        registered = date.fromisoformat(row["registered_on"])
        if (
            registered.isoformat() != row["registered_on"]
            or registered.isoformat() > timestamp[:10]
        ):
            raise ValueError("invalid minimized registration date")
        if row["freguesia_id"] not in reference:
            raise ValueError("unknown minimized parish")
        records[key] = ArchiveRecord(registered, row["freguesia_id"], users)
    source_rows = document["source_rows"]
    lisbon_source_rows = document["lisbon_source_rows"]
    if (
        not records
        or type(source_rows) is not int
        or type(lisbon_source_rows) is not int
        or not len(records) <= lisbon_source_rows <= source_rows
    ):
        raise ValueError("invalid minimized row count")
    return ArchiveSnapshot(
        document["source_file"], timestamp, source_rows, lisbon_source_rows, records
    )


def membership_change(
    earlier: Mapping[int, ArchiveRecord], later: Mapping[int, ArchiveRecord]
) -> dict[str, int]:
    shared = earlier.keys() & later.keys()
    return {
        "earlier_records": len(earlier),
        "later_records": len(later),
        "shared_records": len(shared),
        "earlier_only": len(earlier.keys() - later.keys()),
        "later_only": len(later.keys() - earlier.keys()),
        "net_change": len(later) - len(earlier),
        "shared_registration_date_changes": sum(
            earlier[key].registered_on != later[key].registered_on for key in shared
        ),
        "shared_parish_changes": sum(
            earlier[key].freguesia_id != later[key].freguesia_id for key in shared
        ),
        "shared_capacity_changes": sum(earlier[key].users != later[key].users for key in shared),
    }


def analyse_archive(
    snapshots: Sequence[ArchiveSnapshot],
    reference: Mapping[str, str],
    soap: Sequence[RNALRecord],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if len(snapshots) < 2:
        raise ValueError("at least two archive snapshots are required")
    ordered = sorted(snapshots, key=lambda snapshot: snapshot.timestamp)
    if len({snapshot.timestamp for snapshot in ordered}) != len(ordered):
        raise ValueError("duplicate archive timestamps")
    totals: list[dict[str, Any]] = []
    parishes: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    previously_seen: set[int] = set()
    for index, snapshot in enumerate(ordered):
        records = snapshot.records
        totals.append(
            {
                "source_timestamp": snapshot.timestamp,
                "source_file": snapshot.source_file,
                "source_rows_all_municipalities": snapshot.source_rows,
                "lisbon_source_rows": snapshot.lisbon_source_rows,
                "duplicate_lisbon_rows_collapsed": snapshot.lisbon_source_rows - len(records),
                "lisbon_records": len(records),
                "parishes_present": len({row.freguesia_id for row in records.values()}),
                "registered_on_min": min(row.registered_on for row in records.values()).isoformat(),
                "registered_on_max": max(row.registered_on for row in records.values()).isoformat(),
                "users_known": sum(row.users or 0 for row in records.values()),
                "users_missing_records": sum(row.users is None for row in records.values()),
                "users_zero_records": sum(row.users == 0 for row in records.values()),
            }
        )
        for code, name in sorted(reference.items()):
            subset = [row for row in records.values() if row.freguesia_id == code]
            parishes.append(
                {
                    "source_timestamp": snapshot.timestamp,
                    "freguesia_id": code,
                    "freguesia_name": name,
                    "records": len(subset),
                    "users_known": sum(row.users or 0 for row in subset),
                    "users_missing_records": sum(row.users is None for row in subset),
                }
            )
        if index:
            previous = ordered[index - 1]
            changes.append(
                {
                    "earlier_timestamp": previous.timestamp,
                    "later_timestamp": snapshot.timestamp,
                    "elapsed_calendar_days": (
                        date.fromisoformat(snapshot.timestamp[:10])
                        - date.fromisoformat(previous.timestamp[:10])
                    ).days,
                    **membership_change(previous.records, records),
                    "later_only_previously_seen": len(
                        (records.keys() - previous.records.keys()) & previously_seen
                    ),
                }
            )
        previously_seen.update(records)
    soap_records = {}
    for row in soap:
        number = registration_number(row.registration_id)
        if number in soap_records or row.freguesia_id not in reference:
            raise ValueError("duplicate SOAP number or unknown parish")
        soap_records[number] = ArchiveRecord(row.registered_on, row.freguesia_id, row.users)
    if not soap_records:
        raise ValueError("SOAP comparison requires records")
    latest = ordered[-1]
    soap_only = soap_records.keys() - latest.records.keys()
    comparison = membership_change(latest.records, soap_records)
    summary = {
        "snapshots": len(ordered),
        "first_timestamp": ordered[0].timestamp,
        "last_timestamp": latest.timestamp,
        "timestamp_timezone": "unspecified by publisher; not asserted to be UTC",
        "first_to_last_membership": membership_change(ordered[0].records, latest.records),
        "latest_archive_vs_soap": {
            "archive_records": comparison["earlier_records"],
            "soap_records": comparison["later_records"],
            "shared_records": comparison["shared_records"],
            "archive_only": comparison["earlier_only"],
            "soap_only": comparison["later_only"],
            "shared_registration_date_disagreements": comparison[
                "shared_registration_date_changes"
            ],
            "shared_parish_disagreements": comparison["shared_parish_changes"],
            "shared_capacity_disagreements": comparison["shared_capacity_changes"],
            "soap_only_registration_years": dict(
                sorted(Counter(soap_records[key].registered_on.year for key in soap_only).items())
            ),
        },
        "union_registry_numbers": len(previously_seen),
        "duplicate_lisbon_rows_collapsed": sum(
            snapshot.lisbon_source_rows - len(snapshot.records) for snapshot in ordered
        ),
        "consecutive_reappearance_observations": sum(
            row["later_only_previously_seen"] for row in changes
        ),
        "historical_completeness_established": False,
        "membership_differences_are_closure_events": False,
        "quarter_end_observations_imputed": False,
    }
    return summary, {
        "snapshot_summary.csv": totals,
        "snapshot_changes.csv": changes,
        "parish_snapshots.csv": parishes,
    }
