"""Privacy-minimised acquisition of RNAL records for Lisbon.

The Turismo de Portugal SOAP service returns establishment metadata together
with proprietor/contact information. This project deliberately discards the
proprietor subtree before writing any snapshot because those personal fields
are not required for neighbourhood-level research.
"""

from __future__ import annotations

import json
import tomllib
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

PostBytes = Callable[[str, bytes, Mapping[str, str], float], bytes]

_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
_OUTSYSTEMS_NS = "http://www.outsystems.com"
_USER_AGENT = (
    "lisbon-spatial-dynamics/0.1 (+https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics)"
)

_ALLOWED_FIELDS: tuple[str, ...] = (
    "NrRegisto",
    "DataRegisto",
    "NomeAlojamento",
    "Modalidade",
    "NrCamas",
    "NrUtentes",
    "Endereco",
    "CodPostal",
    "Localidade",
    "Freguesia",
    "Concelho",
    "Distrito",
    "CessadoEm",
    "DTMNFR",
)


class RNALConfigError(ValueError):
    """Raised when RNAL acquisition configuration is invalid."""


class RNALPayloadError(ValueError):
    """Raised when Turismo de Portugal returns an unexpected SOAP response."""


class RNALSnapshotExistsError(FileExistsError):
    """Raised when an RNAL snapshot would overwrite an existing artifact."""


@dataclass(frozen=True, slots=True)
class RNALConfig:
    """Configuration for one municipality-scoped RNAL acquisition."""

    source_id: str
    endpoint_url: str
    soap_action: str
    municipality: str
    output_directory: Path

    @classmethod
    def from_toml(cls, path: Path) -> RNALConfig:
        """Load and validate RNAL SOAP configuration."""
        with path.open("rb") as stream:
            raw = tomllib.load(stream)

        source = _require_mapping(raw.get("source"), "source")
        output = _require_mapping(raw.get("output"), "output")

        endpoint_url = _require_string(source, "endpoint_url", "source")
        _validate_http_url(endpoint_url, "source.endpoint_url")

        return cls(
            source_id=_require_string(source, "source_id", "source"),
            endpoint_url=endpoint_url,
            soap_action=_require_string(source, "soap_action", "source"),
            municipality=_require_string(source, "municipality", "source"),
            output_directory=Path(_require_string(output, "directory", "output")),
        )


@dataclass(frozen=True, slots=True)
class RNALSnapshot:
    """Artifacts produced by one privacy-minimised RNAL acquisition."""

    fetched_at: datetime
    records_path: Path
    manifest_path: Path
    record_count: int


def build_rnal_request(config: RNALConfig) -> bytes:
    """Build the SOAP 1.1 request body for one municipality."""
    municipality = escape(config.municipality)
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<soap:Envelope "
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body>"
        '<list_RNAL xmlns="http://www.outsystems.com">'
        f"<Concelho>{municipality}</Concelho>"
        "</list_RNAL>"
        "</soap:Body>"
        "</soap:Envelope>"
    )
    return xml.encode("utf-8")


def fetch_rnal_snapshot(
    config: RNALConfig,
    *,
    root: Path,
    timeout: float = 60.0,
    fetched_at: datetime | None = None,
    poster: PostBytes | None = None,
) -> RNALSnapshot:
    """Fetch Lisbon RNAL records and persist only non-personal research fields.

    The complete SOAP response is held in memory long enough to validate and
    sanitise it. Proprietor/contact details are not serialised to disk.

    Args:
        config: Validated RNAL configuration.
        root: Working root used to resolve output paths.
        timeout: HTTP timeout in seconds.
        fetched_at: Optional timezone-aware acquisition timestamp.
        poster: Optional injectable HTTP POST function for deterministic tests.

    Returns:
        Metadata for the sanitised snapshot.

    Raises:
        RNALPayloadError: If the SOAP response is malformed or inconsistent.
        RNALSnapshotExistsError: If the timestamped output already exists.
        ValueError: If timeout or timestamp values are invalid.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    timestamp = fetched_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("fetched_at must be timezone-aware")

    timestamp_utc = timestamp.astimezone(UTC)
    stamp = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")

    records_relative = config.output_directory / f"{stamp}.records.json"
    manifest_relative = config.output_directory / f"{stamp}.manifest.json"
    records_path = root / records_relative
    manifest_path = root / manifest_relative

    for path in (records_path, manifest_path):
        if path.exists():
            raise RNALSnapshotExistsError(f"snapshot file already exists: {path}")

    request_payload = build_rnal_request(config)
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{config.soap_action}"',
        "User-Agent": _USER_AGENT,
    }
    post = poster or _post_url
    response_payload = post(
        config.endpoint_url,
        request_payload,
        headers,
        timeout,
    )

    records, reported_total = _parse_and_sanitise(response_payload, config.municipality)

    if reported_total != len(records):
        raise RNALPayloadError(
            f"reported total {reported_total} does not match parsed records {len(records)}"
        )

    records_document: dict[str, object] = {
        "schema_version": 1,
        "source_id": config.source_id,
        "municipality": config.municipality,
        "records": records,
    }
    records_payload = (
        json.dumps(
            records_document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )

    manifest_document: dict[str, object] = {
        "schema_version": 1,
        "source_id": config.source_id,
        "fetched_at": timestamp_utc.isoformat(),
        "municipality": config.municipality,
        "endpoint_url": config.endpoint_url,
        "soap_action": config.soap_action,
        "reported_total": reported_total,
        "written_record_count": len(records),
        "response_sha256": sha256(response_payload).hexdigest(),
        "sanitised_snapshot": {
            "path": records_relative.as_posix(),
            "sha256": sha256(records_payload).hexdigest(),
            "size_bytes": len(records_payload),
        },
        "privacy": {
            "stored_fields": list(_ALLOWED_FIELDS),
            "discarded_subtree": "TitulardaExploracao",
            "raw_response_written": False,
        },
    }
    manifest_payload = (
        json.dumps(
            manifest_document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )

    _write_new_file(records_path, records_payload)
    _write_new_file(manifest_path, manifest_payload)

    return RNALSnapshot(
        fetched_at=timestamp_utc,
        records_path=records_relative,
        manifest_path=manifest_relative,
        record_count=len(records),
    )


def _parse_and_sanitise(
    payload: bytes,
    municipality: str,
) -> tuple[list[dict[str, object]], int]:
    """Parse SOAP XML and retain only establishment-level analytical fields."""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RNALPayloadError("RNAL response is not valid XML") from exc

    fault = root.find(f".//{{{_SOAP_NS}}}Fault")
    if fault is not None:
        fault_text = " ".join(text.strip() for text in fault.itertext() if text.strip())
        raise RNALPayloadError(f"RNAL SOAP fault: {fault_text}")

    response = root.find(f".//{{{_OUTSYSTEMS_NS}}}list_RNALResponse")
    if response is None:
        raise RNALPayloadError("RNAL response element is missing")

    total_element = response.find(f"{{{_OUTSYSTEMS_NS}}}totalRegistos")
    if total_element is None or total_element.text is None:
        raise RNALPayloadError("RNAL totalRegistos is missing")

    try:
        reported_total = int(total_element.text.strip())
    except ValueError as exc:
        raise RNALPayloadError("RNAL totalRegistos is not an integer") from exc

    record_elements = response.findall(f".//{{{_OUTSYSTEMS_NS}}}RNAL_Registo")

    records: list[dict[str, object]] = []
    registration_ids: set[str] = set()

    for index, record_element in enumerate(record_elements):
        record: dict[str, object] = {}

        for field in _ALLOWED_FIELDS:
            child = record_element.find(f"{{{_OUTSYSTEMS_NS}}}{field}")
            value = "" if child is None or child.text is None else child.text.strip()
            record[field] = value

        registration_id = str(record["NrRegisto"]).strip()
        if not registration_id:
            raise RNALPayloadError(f"record {index} has empty NrRegisto")
        if registration_id in registration_ids:
            raise RNALPayloadError(f"duplicate NrRegisto: {registration_id}")
        registration_ids.add(registration_id)

        record_municipality = str(record["Concelho"]).strip()
        if record_municipality.casefold() != municipality.casefold():
            raise RNALPayloadError(
                f"record {registration_id} belongs to {record_municipality!r}, not {municipality!r}"
            )

        dtmnfr = str(record["DTMNFR"]).strip()
        if not dtmnfr:
            raise RNALPayloadError(f"record {registration_id} has empty DTMNFR")

        records.append(record)

    return records, reported_total


def _post_url(
    url: str,
    payload: bytes,
    headers: Mapping[str, str],
    timeout: float,
) -> bytes:
    """POST one SOAP request."""
    request = Request(
        url,
        data=payload,
        headers=dict(headers),
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return cast(bytes, response.read())


def _write_new_file(path: Path, payload: bytes) -> None:
    """Write immutable snapshot bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise RNALSnapshotExistsError(f"snapshot file already exists: {path}") from exc


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required TOML table."""
    if not isinstance(value, Mapping):
        raise RNALConfigError(f"{context} must be a TOML table")
    return value


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RNALConfigError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _validate_http_url(value: str, field: str) -> None:
    """Validate an absolute HTTP(S) URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RNALConfigError(f"{field} must be an absolute HTTP(S) URL")
