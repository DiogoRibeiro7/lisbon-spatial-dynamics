"""Typed data-source catalogue support.

The catalogue is intentionally dependency-free. Python 3.12's :mod:`tomllib`
parses the repository TOML catalogue, while this module validates the fields
that are required for reproducible source tracking.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self, cast
from urllib.parse import urlparse

type SourceKind = Literal["dataset", "portal", "platform"]
type SourceStatus = Literal["candidate", "catalogued", "access_required"]

_ALLOWED_KINDS = frozenset({"dataset", "portal", "platform"})
_ALLOWED_STATUSES = frozenset({"candidate", "catalogued", "access_required"})


class CatalogError(ValueError):
    """Raised when the data-source catalogue is malformed."""


@dataclass(frozen=True, slots=True)
class DataSource:
    """Metadata for one dataset, portal, or external data platform."""

    source_id: str
    name: str
    provider: str
    domain: str
    kind: SourceKind
    status: SourceStatus
    spatial_unit: str
    frequency: str
    temporal_coverage: str
    access: str
    licence: str
    landing_page: str
    notes: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        """Build and validate a data source from parsed TOML values.

        Args:
            raw: Parsed mapping containing one ``[[sources]]`` table.

        Returns:
            A validated, immutable data-source record.

        Raises:
            CatalogError: If a required field is missing or invalid.
        """
        kind = _required_choice(raw, "kind", _ALLOWED_KINDS)
        status = _required_choice(raw, "status", _ALLOWED_STATUSES)
        landing_page = _required_string(raw, "landing_page")
        _validate_http_url(landing_page)

        return cls(
            source_id=_required_string(raw, "source_id"),
            name=_required_string(raw, "name"),
            provider=_required_string(raw, "provider"),
            domain=_required_string(raw, "domain"),
            kind=cast(SourceKind, kind),
            status=cast(SourceStatus, status),
            spatial_unit=_required_string(raw, "spatial_unit"),
            frequency=_required_string(raw, "frequency"),
            temporal_coverage=_required_string(raw, "temporal_coverage"),
            access=_required_string(raw, "access"),
            licence=_required_string(raw, "licence"),
            landing_page=landing_page,
            notes=_required_string(raw, "notes"),
        )


def load_catalog(path: Path) -> tuple[DataSource, ...]:
    """Load and validate a TOML data-source catalogue.

    Args:
        path: Path to a TOML file containing a top-level ``sources`` array.

    Returns:
        Data sources in catalogue order.

    Raises:
        CatalogError: If the catalogue structure is invalid or contains
            duplicate source identifiers.
        OSError: If the file cannot be opened.
        tomllib.TOMLDecodeError: If the TOML syntax is invalid.
    """
    with path.open("rb") as stream:
        parsed = tomllib.load(stream)

    raw_sources = parsed.get("sources")
    if not isinstance(raw_sources, list):
        raise CatalogError("catalogue must contain one or more [[sources]] tables")

    sources: list[DataSource] = []
    seen_ids: set[str] = set()

    for index, raw_source in enumerate(raw_sources):
        if not isinstance(raw_source, Mapping):
            raise CatalogError(f"sources[{index}] must be a TOML table")

        source = DataSource.from_mapping(raw_source)
        if source.source_id in seen_ids:
            raise CatalogError(f"duplicate source_id: {source.source_id}")

        seen_ids.add(source.source_id)
        sources.append(source)

    if not sources:
        raise CatalogError("catalogue must contain at least one source")

    return tuple(sources)


def _required_string(raw: Mapping[str, object], key: str) -> str:
    """Return a required non-empty string field."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{key} must be a non-empty string")
    return value.strip()


def _required_choice(
    raw: Mapping[str, object],
    key: str,
    allowed: frozenset[str],
) -> str:
    """Return a required string constrained to an allowed set."""
    value = _required_string(raw, key)
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise CatalogError(f"{key} must be one of: {options}")
    return value


def _validate_http_url(value: str) -> None:
    """Validate that a catalogue URL is an absolute HTTP(S) URL."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CatalogError("landing_page must be an absolute HTTP(S) URL")
