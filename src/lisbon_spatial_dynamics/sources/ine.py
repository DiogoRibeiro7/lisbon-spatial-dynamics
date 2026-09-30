"""Acquisition utilities for INE JSON indicators.

This module captures raw INE responses as immutable timestamped snapshots.
Transformation into analysis-ready tables is intentionally kept separate from
acquisition so that every downstream result can be traced to an exact source
payload.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

FetchBytes = Callable[[str, float], bytes]

_USER_AGENT = (
    "lisbon-spatial-dynamics/0.1 (+https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics)"
)


class INEConfigError(ValueError):
    """Raised when the INE ingestion configuration is invalid."""


class INEPayloadError(ValueError):
    """Raised when INE returns a payload that is not valid JSON."""


class SnapshotExistsError(FileExistsError):
    """Raised when an ingestion snapshot would overwrite existing raw data."""


@dataclass(frozen=True, slots=True)
class INEIndicatorConfig:
    """Configuration for one INE JSON indicator."""

    source_id: str
    indicator_code: str
    language: str
    data_url: str
    metadata_url: str
    output_directory: Path

    @classmethod
    def from_toml(cls, path: Path) -> INEIndicatorConfig:
        """Load an INE indicator configuration from TOML.

        Args:
            path: Path to the source-specific TOML configuration.

        Returns:
            Validated indicator configuration.

        Raises:
            INEConfigError: If a required field is missing or invalid.
            OSError: If the file cannot be opened.
            tomllib.TOMLDecodeError: If the TOML syntax is invalid.
        """
        with path.open("rb") as stream:
            parsed = tomllib.load(stream)

        indicator = _required_table(parsed, "indicator")
        output = _required_table(parsed, "output")

        indicator_code = _required_string(indicator, "code")
        if not indicator_code.isdigit():
            raise INEConfigError("indicator.code must contain digits only")

        language = _required_string(indicator, "language")
        data_url = _required_string(indicator, "data_url")
        metadata_url = _required_string(indicator, "metadata_url")

        _validate_http_url(data_url, "indicator.data_url")
        _validate_http_url(metadata_url, "indicator.metadata_url")

        return cls(
            source_id=_required_string(indicator, "source_id"),
            indicator_code=indicator_code,
            language=language,
            data_url=data_url,
            metadata_url=metadata_url,
            output_directory=Path(_required_string(output, "directory")),
        )


@dataclass(frozen=True, slots=True)
class SnapshotFile:
    """One file captured as part of an immutable raw snapshot."""

    relative_path: Path
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class INESnapshot:
    """Files and provenance produced by one INE acquisition."""

    fetched_at: datetime
    data: SnapshotFile
    metadata: SnapshotFile
    manifest: SnapshotFile


def fetch_ine_snapshot(
    config: INEIndicatorConfig,
    *,
    root: Path,
    timeout: float = 30.0,
    fetched_at: datetime | None = None,
    fetcher: FetchBytes | None = None,
) -> INESnapshot:
    """Fetch an INE indicator and persist an immutable raw snapshot.

    Both the indicator data and INE metadata are downloaded before anything is
    written. Each payload must be valid JSON. The manifest is written last and
    acts as the completion marker for the snapshot.

    Args:
        config: Validated source configuration.
        root: Repository or working root used to resolve the output directory.
        timeout: Per-request timeout in seconds.
        fetched_at: Optional timezone-aware timestamp, primarily for testing.
        fetcher: Optional byte-fetching function for deterministic testing.

    Returns:
        Metadata describing the three files written for the snapshot.

    Raises:
        INEPayloadError: If either downloaded payload is not valid JSON.
        SnapshotExistsError: If the timestamped snapshot already exists.
        ValueError: If timeout is non-positive or fetched_at is timezone-naive.
        OSError: If network or filesystem operations fail.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    timestamp = fetched_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("fetched_at must be timezone-aware")

    timestamp_utc = timestamp.astimezone(UTC)
    stamp = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")

    data_relative = config.output_directory / f"{stamp}.data.json"
    metadata_relative = config.output_directory / f"{stamp}.metadata.json"
    manifest_relative = config.output_directory / f"{stamp}.manifest.json"

    data_path = root / data_relative
    metadata_path = root / metadata_relative
    manifest_path = root / manifest_relative

    for path in (data_path, metadata_path, manifest_path):
        if path.exists():
            raise SnapshotExistsError(f"snapshot file already exists: {path}")

    fetch_bytes = fetcher or _fetch_url
    data_payload = fetch_bytes(config.data_url, timeout)
    metadata_payload = fetch_bytes(config.metadata_url, timeout)

    _validate_json_payload(data_payload, "indicator data")
    _validate_json_payload(metadata_payload, "indicator metadata")

    data_digest = _digest(data_payload)
    metadata_digest = _digest(metadata_payload)

    manifest_object: dict[str, object] = {
        "schema_version": 1,
        "source_id": config.source_id,
        "indicator_code": config.indicator_code,
        "language": config.language,
        "fetched_at": timestamp_utc.isoformat(),
        "resources": {
            "data": {
                "url": config.data_url,
                "path": data_relative.as_posix(),
                "sha256": data_digest,
                "size_bytes": len(data_payload),
            },
            "metadata": {
                "url": config.metadata_url,
                "path": metadata_relative.as_posix(),
                "sha256": metadata_digest,
                "size_bytes": len(metadata_payload),
            },
        },
    }
    manifest_payload = (
        json.dumps(
            manifest_object,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )

    _write_new_file(data_path, data_payload)
    _write_new_file(metadata_path, metadata_payload)
    _write_new_file(manifest_path, manifest_payload)

    return INESnapshot(
        fetched_at=timestamp_utc,
        data=SnapshotFile(
            relative_path=data_relative,
            sha256=data_digest,
            size_bytes=len(data_payload),
        ),
        metadata=SnapshotFile(
            relative_path=metadata_relative,
            sha256=metadata_digest,
            size_bytes=len(metadata_payload),
        ),
        manifest=SnapshotFile(
            relative_path=manifest_relative,
            sha256=_digest(manifest_payload),
            size_bytes=len(manifest_payload),
        ),
    )


def _fetch_url(url: str, timeout: float) -> bytes:
    """Fetch one JSON resource using a project-specific user agent."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return cast(bytes, response.read())


def _validate_json_payload(payload: bytes, label: str) -> None:
    """Require a JSON object or array while preserving the original bytes."""
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise INEPayloadError(f"{label} is not valid JSON") from exc

    if not isinstance(parsed, (dict, list)):
        raise INEPayloadError(f"{label} must contain a JSON object or array")


def _write_new_file(path: Path, payload: bytes) -> None:
    """Write bytes without allowing an existing raw snapshot to be replaced."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise SnapshotExistsError(f"snapshot file already exists: {path}") from exc


def _digest(payload: bytes) -> str:
    """Return a SHA-256 digest for provenance tracking."""
    return sha256(payload).hexdigest()


def _required_table(
    raw: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML table."""
    value = raw.get(key)
    if not isinstance(value, Mapping):
        raise INEConfigError(f"{key} must be a TOML table")
    return value


def _required_string(raw: Mapping[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise INEConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _validate_http_url(value: str, field: str) -> None:
    """Validate an absolute HTTP(S) resource URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise INEConfigError(f"{field} must be an absolute HTTP(S) URL")
