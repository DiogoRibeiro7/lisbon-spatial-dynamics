"""Acquisition of Lisbon parish boundaries from DGT CAOP."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

FetchBytes = Callable[[str, float], bytes]

_USER_AGENT = (
    "lisbon-spatial-dynamics/0.1 "
    "(+https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics)"
)


class CAOPConfigError(ValueError):
    """Raised when CAOP source configuration is invalid."""


class CAOPPayloadError(ValueError):
    """Raised when a CAOP response violates the expected contract."""


class CAOPSnapshotExistsError(FileExistsError):
    """Raised when a raw CAOP snapshot would overwrite an existing file."""


@dataclass(frozen=True, slots=True)
class CAOPConfig:
    """Configuration for the canonical Lisbon freguesia boundary query."""

    source_id: str
    layer_url: str
    municipality: str
    municipality_field: str
    id_field: str
    name_field: str
    out_fields: tuple[str, ...]
    expected_feature_count: int
    output_directory: Path

    @classmethod
    def from_toml(cls, path: Path) -> CAOPConfig:
        """Load and validate a CAOP source configuration."""
        with path.open("rb") as stream:
            raw = tomllib.load(stream)

        source = _require_mapping(raw.get("source"), "source")
        output = _require_mapping(raw.get("output"), "output")
        layer_url = _require_string(source, "layer_url")
        _validate_http_url(layer_url, "source.layer_url")

        out_fields_raw = source.get("out_fields")
        if not isinstance(out_fields_raw, list) or not out_fields_raw:
            raise CAOPConfigError("source.out_fields must be a non-empty array")

        out_fields: list[str] = []
        for index, field in enumerate(out_fields_raw):
            if not isinstance(field, str) or not field.strip():
                raise CAOPConfigError(
                    f"source.out_fields[{index}] must be a non-empty string"
                )
            out_fields.append(field.strip())

        expected_feature_count = source.get("expected_feature_count")
        if not isinstance(expected_feature_count, int) or expected_feature_count <= 0:
            raise CAOPConfigError("source.expected_feature_count must be positive")

        municipality_field = _require_string(source, "municipality_field")
        id_field = _require_string(source, "id_field")
        name_field = _require_string(source, "name_field")

        required_fields = {municipality_field, id_field, name_field}
        if not required_fields.issubset(out_fields):
            raise CAOPConfigError(
                "source.out_fields must include municipality, id and name fields"
            )

        return cls(
            source_id=_require_string(source, "source_id"),
            layer_url=layer_url.rstrip("/"),
            municipality=_require_string(source, "municipality"),
            municipality_field=municipality_field,
            id_field=id_field,
            name_field=name_field,
            out_fields=tuple(out_fields),
            expected_feature_count=expected_feature_count,
            output_directory=Path(_require_string(output, "directory")),
        )


@dataclass(frozen=True, slots=True)
class CAOPSnapshot:
    """Files created by one CAOP reference-geography acquisition."""

    fetched_at: datetime
    geojson_path: Path
    metadata_path: Path
    manifest_path: Path


def build_caop_query_url(config: CAOPConfig) -> str:
    """Build the official ArcGIS GeoJSON query for Lisbon freguesias."""
    municipality = config.municipality.replace("'", "''")
    params = {
        "where": f"{config.municipality_field}='{municipality}'",
        "outFields": ",".join(config.out_fields),
        "returnGeometry": "true",
        "outSR": "4326",
        "orderByFields": config.id_field,
        "f": "geojson",
    }
    return f"{config.layer_url}/query?{urlencode(params)}"


def fetch_caop_snapshot(
    config: CAOPConfig,
    *,
    root: Path,
    timeout: float = 30.0,
    fetched_at: datetime | None = None,
    fetcher: FetchBytes | None = None,
) -> CAOPSnapshot:
    """Fetch and validate the canonical Lisbon freguesia boundary snapshot."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    timestamp = fetched_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("fetched_at must be timezone-aware")

    timestamp_utc = timestamp.astimezone(UTC)
    stamp = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")

    geojson_relative = config.output_directory / f"{stamp}.geojson"
    metadata_relative = config.output_directory / f"{stamp}.layer.json"
    manifest_relative = config.output_directory / f"{stamp}.manifest.json"

    geojson_path = root / geojson_relative
    metadata_path = root / metadata_relative
    manifest_path = root / manifest_relative

    for path in (geojson_path, metadata_path, manifest_path):
        if path.exists():
            raise CAOPSnapshotExistsError(f"snapshot file already exists: {path}")

    fetch_bytes = fetcher or _fetch_url
    query_url = build_caop_query_url(config)
    metadata_url = f"{config.layer_url}?f=pjson"

    geojson_payload = fetch_bytes(query_url, timeout)
    metadata_payload = fetch_bytes(metadata_url, timeout)

    _validate_geojson(geojson_payload, config)
    _validate_metadata(metadata_payload, config)

    manifest = {
        "schema_version": 1,
        "source_id": config.source_id,
        "fetched_at": timestamp_utc.isoformat(),
        "municipality": config.municipality,
        "expected_feature_count": config.expected_feature_count,
        "resources": {
            "geojson": {
                "url": query_url,
                "path": geojson_relative.as_posix(),
                "sha256": sha256(geojson_payload).hexdigest(),
                "size_bytes": len(geojson_payload),
            },
            "layer_metadata": {
                "url": metadata_url,
                "path": metadata_relative.as_posix(),
                "sha256": sha256(metadata_payload).hexdigest(),
                "size_bytes": len(metadata_payload),
            },
        },
    }
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        + b"\n"
    )

    _write_new_file(geojson_path, geojson_payload)
    _write_new_file(metadata_path, metadata_payload)
    _write_new_file(manifest_path, manifest_payload)

    return CAOPSnapshot(
        fetched_at=timestamp_utc,
        geojson_path=geojson_relative,
        metadata_path=metadata_relative,
        manifest_path=manifest_relative,
    )


def _validate_geojson(payload: bytes, config: CAOPConfig) -> None:
    """Validate feature count, identifiers, municipality and polygon geometry."""
    raw = _load_json_object(payload, "CAOP GeoJSON")
    if raw.get("type") != "FeatureCollection":
        raise CAOPPayloadError("CAOP GeoJSON must be a FeatureCollection")

    features = raw.get("features")
    if not isinstance(features, list):
        raise CAOPPayloadError("CAOP GeoJSON features must be a list")
    if len(features) != config.expected_feature_count:
        raise CAOPPayloadError(
            "unexpected Lisbon freguesia count: "
            f"{len(features)} != {config.expected_feature_count}"
        )

    identifiers: set[str] = set()
    for index, feature_raw in enumerate(features):
        feature = _require_mapping(feature_raw, f"features[{index}]")
        properties = _require_mapping(
            feature.get("properties"), f"features[{index}].properties"
        )
        geometry = _require_mapping(
            feature.get("geometry"), f"features[{index}].geometry"
        )

        identifier = _require_string(
            properties, config.id_field, f"features[{index}].properties"
        )
        if identifier in identifiers:
            raise CAOPPayloadError(f"duplicate CAOP identifier: {identifier}")
        identifiers.add(identifier)

        _require_string(properties, config.name_field, f"features[{index}].properties")
        municipality = _require_string(
            properties, config.municipality_field, f"features[{index}].properties"
        )
        if municipality.casefold() != config.municipality.casefold():
            raise CAOPPayloadError(
                f"unexpected municipality in feature {identifier}: {municipality}"
            )

        geometry_type = geometry.get("type")
        if geometry_type not in {"Polygon", "MultiPolygon"}:
            raise CAOPPayloadError(
                f"feature {identifier} has unsupported geometry type: {geometry_type!r}"
            )
        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            raise CAOPPayloadError(f"feature {identifier} has empty geometry")


def _validate_metadata(payload: bytes, config: CAOPConfig) -> None:
    """Ensure the ArcGIS layer still exposes the fields used by the project."""
    raw = _load_json_object(payload, "CAOP layer metadata")
    fields = raw.get("fields")
    if not isinstance(fields, list):
        raise CAOPPayloadError("CAOP layer metadata fields must be a list")

    field_names: set[str] = set()
    for field_raw in fields:
        if not isinstance(field_raw, Mapping):
            continue
        name = field_raw.get("name")
        if isinstance(name, str):
            field_names.add(name)

    missing = set(config.out_fields) - field_names
    if missing:
        raise CAOPPayloadError(
            "CAOP layer is missing configured fields: " + ", ".join(sorted(missing))
        )

    formats = raw.get("supportedQueryFormats")
    if not isinstance(formats, str) or "geojson" not in formats.casefold():
        raise CAOPPayloadError("CAOP layer does not advertise GeoJSON query support")


def _fetch_url(url: str, timeout: float) -> bytes:
    """Fetch a DGT ArcGIS resource."""
    request = Request(
        url,
        headers={
            "Accept": "application/json, application/geo+json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _load_json_object(payload: bytes, label: str) -> Mapping[str, object]:
    """Parse a JSON object from raw bytes."""
    try:
        raw: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CAOPPayloadError(f"{label} is not valid JSON") from exc
    return _require_mapping(raw, label)


def _write_new_file(path: Path, payload: bytes) -> None:
    """Write one immutable raw snapshot file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise CAOPSnapshotExistsError(f"snapshot file already exists: {path}") from exc


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a JSON/TOML mapping."""
    if not isinstance(value, Mapping):
        raise CAOPPayloadError(f"{context} must be an object")
    return value


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CAOPPayloadError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _validate_http_url(value: str, field: str) -> None:
    """Validate an absolute HTTP(S) URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CAOPConfigError(f"{field} must be an absolute HTTP(S) URL")
