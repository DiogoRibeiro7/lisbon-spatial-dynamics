"""Acquire only coordinates and geography fields for a pinned RNAL conflict cohort."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlencode

from lisbon_spatial_dynamics.sources.rnal_geodata import LAYER_URL, GetBytes, _get

FIELDS = ("NrRNAL", "DTMNFR", "Concelho", "FiabilidadeGeo")


def validate_locations(rows: list[dict[str, Any]], expected: Mapping[int, str]) -> None:
    """Require the exact selected registrations and unchanged GIS parish labels."""
    seen: set[int] = set()
    for row in rows:
        number = row.get("NrRNAL")
        if not isinstance(number, int) or isinstance(number, bool) or number in seen:
            raise ValueError("invalid or duplicate location registration ID")
        seen.add(number)
        if number not in expected or row.get("DTMNFR") != expected[number]:
            raise ValueError("location cohort or parish differs from pinned GIS snapshot")
        if row.get("Concelho") != "Lisboa":
            raise ValueError("location outside Lisboa municipality filter")
        if row.get("FiabilidadeGeo") is not None and not isinstance(row["FiabilidadeGeo"], str):
            raise ValueError("invalid georeferencing reliability label")
        point = row.get("geometry")
        if point is not None:
            if not isinstance(point, dict) or set(point) != {"x", "y"}:
                raise ValueError("location geometry must be a point or null")
            for key, bound in (("x", 180), ("y", 90)):
                value = point[key]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or abs(value) > bound
                ):
                    raise ValueError("invalid WGS84 coordinate")
    if seen != set(expected):
        raise ValueError("location response is missing selected registrations")


def fetch_locations(
    expected: Mapping[int, str],
    output: Path,
    *,
    timeout: float = 60,
    getter: GetBytes = _get,
) -> Path:
    """Retain sanitized locations without names, addresses or proprietor fields."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"location output already exists: {output}")
    if (
        timeout <= 0
        or not expected
        or any(type(number) is not int or number <= 0 for number in expected)
    ):
        raise ValueError("positive timeout and non-empty positive registration IDs required")
    started = datetime.now(UTC)
    requests: list[dict[str, object]] = []

    def request(base: str, params: dict[str, object]) -> tuple[dict[str, Any], bytes]:
        url = base + "?" + urlencode({"f": "json", **params})
        payload = getter(url, timeout)
        document = json.loads(payload)
        if (
            not isinstance(document, dict)
            or "error" in document
            or document.get("exceededTransferLimit")
        ):
            raise ValueError("location request failed or exceeded transfer limit")
        requests.append(
            {"url": url, "sha256": sha256(payload).hexdigest(), "size_bytes": len(payload)}
        )
        return document, payload

    layer, metadata = request(LAYER_URL, {})
    if set(FIELDS) - {field["name"] for field in layer["fields"]}:
        raise ValueError("required location fields missing from layer schema")
    batch_size = min(100, int(layer["maxRecordCount"]))
    if batch_size <= 0:
        raise ValueError("invalid location transfer limit")
    records: list[dict[str, Any]] = []
    ids = sorted(expected)
    for offset in range(0, len(ids), batch_size):
        batch = ids[offset : offset + batch_size]
        document, _ = request(
            LAYER_URL + "/query",
            {
                "where": "Concelho='Lisboa' AND NrRNAL IN (" + ",".join(map(str, batch)) + ")",
                "outFields": ",".join(FIELDS),
                "returnGeometry": "true",
                "outSR": "4326",
            },
        )
        if (
            document.get("spatialReference", {}).get(
                "latestWkid", document.get("spatialReference", {}).get("wkid")
            )
            != 4326
        ):
            raise ValueError("location response must declare EPSG:4326")
        rows = []
        for feature in document["features"]:
            row = {field: feature["attributes"][field] for field in FIELDS}
            geometry = feature.get("geometry")
            row["geometry"] = (
                None if geometry is None else {key: geometry[key] for key in ("x", "y")}
            )
            rows.append(row)
        validate_locations(rows, {number: expected[number] for number in batch})
        records.extend(rows)
    validate_locations(records, expected)
    files = {
        "locations.json": (
            json.dumps({"records": records}, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode(),
        "layer.json": metadata,
    }
    manifest = {
        "source_id": "turismo_portugal_rnal_conflict_locations",
        "schema_version": 1,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "record_count": len(records),
        "crs": "EPSG:4326",
        "requests": requests,
        "privacy": {
            "stored_attributes": list(FIELDS),
            "stored_geometry_fields": ["x", "y"],
            "raw_feature_responses_written": False,
        },
        "resources": [
            {"file": name, "sha256": sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in files.items()
        ],
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".rnal-locations-", dir=output.parent) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for name, payload in files.items():
            (staging / name).write_bytes(payload)
        if output.exists() or output.is_symlink():
            raise FileExistsError(f"location output already exists: {output}")
        staging.rename(output)
    return output / "manifest.json"
