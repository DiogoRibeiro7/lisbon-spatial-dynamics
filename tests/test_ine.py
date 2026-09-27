"""Tests for INE raw-data acquisition."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from lisbon_spatial_dynamics.sources.ine import (
    INEIndicatorConfig,
    INEPayloadError,
    SnapshotExistsError,
    fetch_ine_snapshot,
)


def _repository_config() -> INEIndicatorConfig:
    """Load the committed INE housing configuration."""
    path = Path(__file__).parents[1] / "configs" / "ine_housing.toml"
    return INEIndicatorConfig.from_toml(path)


def test_repository_ine_housing_config_loads() -> None:
    """The committed housing source should remain a valid INE configuration."""
    config = _repository_config()

    assert config.source_id == "ine_local_housing_prices"
    assert config.indicator_code == "0011364"
    assert config.language == "PT"
    assert config.output_directory == Path("data/raw/ine/housing/0011364")


def test_fetch_snapshot_writes_payloads_and_manifest(tmp_path: Path) -> None:
    """A successful acquisition should write immutable data, metadata and provenance."""
    config = _repository_config()
    calls: list[tuple[str, float]] = []

    data_payload = b'{"Dados": [{"valor": "2500"}]}'
    metadata_payload = b'{"IndicadorCod": "0011364"}'

    def fetcher(url: str, timeout: float) -> bytes:
        calls.append((url, timeout))
        if "pindicaMeta.jsp" in url:
            return metadata_payload
        return data_payload

    fetched_at = datetime(2026, 9, 27, 10, 30, tzinfo=UTC)
    snapshot = fetch_ine_snapshot(
        config,
        root=tmp_path,
        timeout=7.5,
        fetched_at=fetched_at,
        fetcher=fetcher,
    )

    assert len(calls) == 2
    assert {timeout for _, timeout in calls} == {7.5}

    data_path = tmp_path / snapshot.data.relative_path
    metadata_path = tmp_path / snapshot.metadata.relative_path
    manifest_path = tmp_path / snapshot.manifest.relative_path

    assert data_path.read_bytes() == data_payload
    assert metadata_path.read_bytes() == metadata_payload
    assert snapshot.data.sha256 == sha256(data_payload).hexdigest()
    assert snapshot.metadata.sha256 == sha256(metadata_payload).hexdigest()

    manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest_raw, dict)
    manifest = cast(dict[str, object], manifest_raw)

    assert manifest["indicator_code"] == "0011364"
    assert manifest["fetched_at"] == "2026-09-27T10:30:00+00:00"

    resources_raw = manifest["resources"]
    assert isinstance(resources_raw, dict)
    resources = cast(dict[str, object], resources_raw)

    data_resource_raw = resources["data"]
    assert isinstance(data_resource_raw, dict)
    data_resource = cast(dict[str, object], data_resource_raw)
    assert data_resource["sha256"] == snapshot.data.sha256


def test_invalid_json_is_rejected_before_files_are_written(tmp_path: Path) -> None:
    """Invalid upstream payloads must not create a partial raw snapshot."""
    config = _repository_config()

    def fetcher(url: str, timeout: float) -> bytes:
        del timeout
        if "pindicaMeta.jsp" in url:
            return b'{"metadata": true}'
        return b"<html>temporary upstream error</html>"

    with pytest.raises(INEPayloadError, match="indicator data"):
        fetch_ine_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 27, 10, 30, tzinfo=UTC),
            fetcher=fetcher,
        )

    assert not (tmp_path / config.output_directory).exists()


def test_existing_snapshot_is_not_overwritten(tmp_path: Path) -> None:
    """Raw snapshot paths are immutable once created."""
    config = _repository_config()
    fetched_at = datetime(2026, 9, 27, 10, 30, tzinfo=UTC)

    def fetcher(url: str, timeout: float) -> bytes:
        del url, timeout
        return b'{"ok": true}'

    fetch_ine_snapshot(
        config,
        root=tmp_path,
        fetched_at=fetched_at,
        fetcher=fetcher,
    )

    with pytest.raises(SnapshotExistsError):
        fetch_ine_snapshot(
            config,
            root=tmp_path,
            fetched_at=fetched_at,
            fetcher=fetcher,
        )


def test_naive_timestamp_is_rejected(tmp_path: Path) -> None:
    """Snapshot timestamps must carry timezone information."""
    config = _repository_config()

    with pytest.raises(ValueError, match="timezone-aware"):
        fetch_ine_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 27, 10, 30),
            fetcher=lambda _url, _timeout: b'{"ok": true}',
        )
