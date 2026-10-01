"""Acquisition of the official INE Censos 2021 subsection synthesis file."""

from __future__ import annotations

import json
import tomllib
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

FetchBytes = Callable[[str, float], bytes]

_USER_AGENT = (
    "lisbon-spatial-dynamics/0.1 (+https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics)"
)


class CensusConfigError(ValueError):
    """Raised when Censos 2021 source configuration is invalid."""


class CensusPayloadError(ValueError):
    """Raised when the downloaded Censos 2021 archive is invalid."""


class CensusSnapshotExistsError(FileExistsError):
    """Raised when a census snapshot would overwrite an existing artifact."""


@dataclass(frozen=True, slots=True)
class Census2021Config:
    """Configuration for the official INE subsection synthesis archive."""

    source_id: str
    archive_url: str
    output_directory: Path

    @classmethod
    def from_toml(cls, path: Path) -> Census2021Config:
        """Load and validate census source configuration."""
        with path.open("rb") as stream:
            raw = tomllib.load(stream)

        source = _require_mapping(raw.get("source"), "source")
        output = _require_mapping(raw.get("output"), "output")

        archive_url = _require_string(source, "archive_url", "source")
        _validate_http_url(archive_url, "source.archive_url")

        return cls(
            source_id=_require_string(source, "source_id", "source"),
            archive_url=archive_url,
            output_directory=Path(_require_string(output, "directory", "output")),
        )


@dataclass(frozen=True, slots=True)
class Census2021Snapshot:
    """Artifacts produced by one census archive acquisition."""

    fetched_at: datetime
    archive_path: Path
    manifest_path: Path
    member_count: int


def fetch_census2021_snapshot(
    config: Census2021Config,
    *,
    root: Path,
    timeout: float = 120.0,
    fetched_at: datetime | None = None,
    fetcher: FetchBytes | None = None,
) -> Census2021Snapshot:
    """Fetch and validate the official Censos 2021 synthesis ZIP."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    timestamp = fetched_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("fetched_at must be timezone-aware")

    timestamp_utc = timestamp.astimezone(UTC)
    stamp = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")

    archive_relative = config.output_directory / f"{stamp}.zip"
    manifest_relative = config.output_directory / f"{stamp}.manifest.json"
    archive_path = root / archive_relative
    manifest_path = root / manifest_relative

    for path in (archive_path, manifest_path):
        if path.exists():
            raise CensusSnapshotExistsError(f"snapshot file already exists: {path}")

    fetch_bytes = fetcher or _fetch_url
    payload = fetch_bytes(config.archive_url, timeout)
    members = _validate_archive(payload)

    manifest = {
        "schema_version": 1,
        "source_id": config.source_id,
        "fetched_at": timestamp_utc.isoformat(),
        "resource": {
            "url": config.archive_url,
            "path": archive_relative.as_posix(),
            "sha256": sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "member_count": len(members),
            "members": members,
        },
    }
    manifest_payload = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )

    _write_new_file(archive_path, payload)
    _write_new_file(manifest_path, manifest_payload)

    return Census2021Snapshot(
        fetched_at=timestamp_utc,
        archive_path=archive_relative,
        manifest_path=manifest_relative,
        member_count=len(members),
    )


def _validate_archive(payload: bytes) -> tuple[str, ...]:
    """Return sorted lookup names using zipfile's UTF-8/CP437 decoding contract.

    Do not guess a different legacy encoding: provenance names must remain
    usable with ZipFile.getinfo/read on the unchanged acquired archive.
    """
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise CensusPayloadError(f"census ZIP contains a corrupt member: {bad_member}")

            members = tuple(
                sorted(member.filename for member in archive.infolist() if not member.is_dir())
            )
    except zipfile.BadZipFile as exc:
        raise CensusPayloadError("census payload is not a valid ZIP archive") from exc

    if not members:
        raise CensusPayloadError("census ZIP contains no files")

    return members


def _fetch_url(url: str, timeout: float) -> bytes:
    """Fetch the census archive."""
    request = Request(
        url,
        headers={"User-Agent": _USER_AGENT},
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
        raise CensusSnapshotExistsError(f"snapshot file already exists: {path}") from exc


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required TOML table."""
    if not isinstance(value, Mapping):
        raise CensusConfigError(f"{context} must be a TOML table")
    return value


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CensusConfigError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _validate_http_url(value: str, field: str) -> None:
    """Validate an absolute HTTP(S) URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CensusConfigError(f"{field} must be an absolute HTTP(S) URL")
