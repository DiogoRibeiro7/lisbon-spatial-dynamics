"""Tests for official Censos 2021 archive acquisition."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.sources.census2021 import (
    Census2021Config,
    CensusPayloadError,
    fetch_census2021_snapshot,
)


def _config() -> Census2021Config:
    path = Path(__file__).parents[1] / "configs" / "census2021_population.toml"
    return Census2021Config.from_toml(path)


def _zip_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "FS2021SubSeccao.csv",
            "DTMNFR21;N_INDIVIDUOS\n110654;10\n",
        )
    return buffer.getvalue()


def test_repository_config_targets_official_ine_archive() -> None:
    config = _config()

    assert config.source_id == "ine_census2021_subsection_population"
    assert config.archive_url.endswith("FS2021SubSeccaoTot.zip")


def test_snapshot_writes_archive_and_manifest(tmp_path: Path) -> None:
    config = _config()

    snapshot = fetch_census2021_snapshot(
        config,
        root=tmp_path,
        fetched_at=datetime(2026, 9, 29, 12, 0, tzinfo=UTC),
        fetcher=lambda _url, _timeout: _zip_payload(),
    )

    assert (tmp_path / snapshot.archive_path).exists()
    manifest = json.loads((tmp_path / snapshot.manifest_path).read_text(encoding="utf-8"))
    assert snapshot.member_count == 1
    assert manifest["resource"]["member_count"] == 1


def test_invalid_zip_is_rejected(tmp_path: Path) -> None:
    config = _config()

    with pytest.raises(CensusPayloadError, match="valid ZIP"):
        fetch_census2021_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 29, 12, 0, tzinfo=UTC),
            fetcher=lambda _url, _timeout: b"not a zip",
        )


def test_legacy_zip_member_names_round_trip_without_encoding_guesses(tmp_path: Path) -> None:
    """An unflagged CP850 name must retain zipfile's lookup spelling in provenance."""
    ascii_name = b"FS 2021 SubSeccao Tot.xlsx"
    legacy_name = "FS 2021 SubSecção Tot.xlsx".encode("cp850")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(ascii_name.decode("ascii"), b"fixture")
    payload = buffer.getvalue()
    assert len(ascii_name) == len(legacy_name) and payload.count(ascii_name) == 2
    payload = payload.replace(ascii_name, legacy_name)
    snapshot = fetch_census2021_snapshot(
        _config(),
        root=tmp_path,
        fetcher=lambda _url, _timeout: payload,
    )
    manifest = json.loads((tmp_path / snapshot.manifest_path).read_text(encoding="utf-8"))
    with zipfile.ZipFile(tmp_path / snapshot.archive_path) as archive:
        name = manifest["resource"]["members"][0]
        assert name == legacy_name.decode("cp437")
        assert archive.getinfo(name).flag_bits & 0x800 == 0
        assert archive.read(name) == b"fixture"
