"""Minimal RNAL GIS snapshots for cross-feed coverage checks, not stock estimation."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LAYER_URL = "https://geo.turismodeportugal.pt/server/rest/services/TDP/OpenData_AL/MapServer/6"
ITEM_URL = "https://www.arcgis.com/sharing/rest/content/items/4e62eb1977564991bd01e61d7aa8266f"
FIELDS = (
    "OBJECTID",
    "NrRNAL",
    "DataRegisto",
    "DataAberturaPublico",
    "DTMNFR",
    "Freguesia",
    "Concelho",
    "NrUtentes",
)
GetBytes = Callable[[str, float], bytes]


def epoch_date(value: object) -> date | None:
    """Interpret ArcGIS epoch milliseconds in UTC, including pre-1970 dates."""
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("GIS date must be integer epoch milliseconds or null")
    try:
        return (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=value)).date()
    except OverflowError as exc:
        raise ValueError("GIS date outside supported range") from exc


def _positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_records(records: list[dict[str, Any]]) -> None:
    """Reject ambiguous identifiers and malformed comparison fields."""
    if not records:
        raise ValueError("GIS snapshot is empty")
    for field in ("OBJECTID", "NrRNAL"):
        values = [row.get(field) for row in records]
        if not all(_positive_integer(value) for value in values):
            raise ValueError(f"GIS {field} must be positive integers")
        if len(set(values)) != len(values):
            raise ValueError(f"duplicate GIS {field}")
    for row in records:
        if set(row) != set(FIELDS):
            raise ValueError("GIS snapshot fields differ from analytical whitelist")
        if row["Concelho"] != "Lisboa":
            raise ValueError("GIS record outside Lisboa")
        parish = row["DTMNFR"]
        if not isinstance(parish, str) or len(parish) != 6 or not parish.startswith("1106"):
            raise ValueError("invalid GIS parish identifier")
        if not isinstance(row["Freguesia"], str) or not row["Freguesia"].strip():
            raise ValueError("missing GIS parish name")
        if epoch_date(row["DataRegisto"]) is None:
            raise ValueError("missing GIS registration date")
        epoch_date(row["DataAberturaPublico"])
        users = row["NrUtentes"]
        if users is not None and (
            not isinstance(users, int) or isinstance(users, bool) or users < 0
        ):
            raise ValueError("invalid GIS user capacity")


def _get(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "lisbon-spatial-dynamics/1.0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload: bytes = response.read()
    return payload


def _json_bytes(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def fetch_snapshot(output: Path, *, timeout: float = 60, getter: GetBytes = _get) -> Path:
    """Capture analytical fields and metadata, checking the full object-ID roster.

    The roster is checked before and after download. This detects membership
    changes and truncation; it cannot guarantee a transactional snapshot of field
    values. Unexpected attributes and geometry are discarded in memory.
    """
    if output.exists():
        raise FileExistsError(f"snapshot output already exists: {output}")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    started = datetime.now(UTC)
    requests: list[dict[str, object]] = []

    def request(base: str, **params: object) -> tuple[dict[str, Any], bytes]:
        url = base + "?" + urlencode({"f": "json", **params})
        payload = getter(url, timeout)
        document = json.loads(payload)
        if not isinstance(document, dict) or "error" in document:
            raise ValueError("GIS request returned an error or invalid object")
        if document.get("exceededTransferLimit"):
            raise ValueError("GIS response exceeded transfer limit")
        requests.append(
            {"url": url, "sha256": sha256(payload).hexdigest(), "size_bytes": len(payload)}
        )
        return document, payload

    layer, layer_bytes = request(LAYER_URL)
    _, item_bytes = request(ITEM_URL)
    schema = {field["name"]: field["type"] for field in layer["fields"]}
    if set(FIELDS) - schema.keys():
        raise ValueError("GIS layer is missing required fields")
    if any(
        schema[field] != "esriFieldTypeDate" for field in ("DataRegisto", "DataAberturaPublico")
    ):
        raise ValueError("GIS date field type changed")
    # Unknown time references could change calendar-day comparisons.
    if layer.get("datesInUnknownTimezone"):
        raise ValueError("GIS dates use an unknown timezone")

    def roster() -> set[int]:
        document, _ = request(LAYER_URL + "/query", where="Concelho='Lisboa'", returnIdsOnly="true")
        ids = document.get("objectIds")
        if (
            document.get("objectIdFieldName") != "OBJECTID"
            or not isinstance(ids, list)
            or not ids
            or not all(_positive_integer(value) for value in ids)
        ):
            raise ValueError("invalid or empty GIS object-ID roster")
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate GIS roster identifiers")
        return set(ids)

    ids = roster()
    count, _ = request(LAYER_URL + "/query", where="Concelho='Lisboa'", returnCountOnly="true")
    if count.get("count") != len(ids):
        raise ValueError("GIS count differs from object-ID roster")
    batch_size = min(500, int(layer["maxRecordCount"]))
    if batch_size <= 0:
        raise ValueError("GIS maxRecordCount must be positive")
    records: list[dict[str, Any]] = []
    ordered = sorted(ids)
    for offset in range(0, len(ordered), batch_size):
        batch = ordered[offset : offset + batch_size]
        document, _ = request(
            LAYER_URL + "/query",
            where="Concelho='Lisboa'",
            objectIds=",".join(map(str, batch)),
            outFields=",".join(FIELDS),
            returnGeometry="false",
        )
        features = document.get("features")
        if not isinstance(features, list):
            raise ValueError("GIS response has no features array")
        # Do not persist unexpected provider fields, including contact data.
        rows = [{field: feature["attributes"][field] for field in FIELDS} for feature in features]
        validate_records(rows)
        if {row["OBJECTID"] for row in rows} != set(batch):
            raise ValueError("GIS batch differs from requested object IDs")
        records.extend(rows)
    validate_records(records)
    if roster() != ids:
        raise ValueError("GIS membership changed during acquisition; retry in a new capture")

    files = {
        "records.json": _json_bytes({"records": records}),
        "layer.json": layer_bytes,
        "item.json": item_bytes,
    }
    manifest = {
        "schema_version": 1,
        "source_id": "turismo_portugal_rnal_geodata_lisboa",
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "municipality": "Lisboa",
        "record_count": len(records),
        "membership_stable_during_capture": True,
        "transactional_snapshot": False,
        "requests": requests,
        "stored_fields": list(FIELDS),
        "raw_feature_responses_written": False,
        "resources": [
            {"file": name, "sha256": sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in files.items()
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in {**files, "manifest.json": _json_bytes(manifest)}.items():
        with (output / name).open("xb") as stream:
            stream.write(payload)
    return output / "manifest.json"
