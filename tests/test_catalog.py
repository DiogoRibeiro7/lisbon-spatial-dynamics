"""Tests for the typed data-source catalogue."""

from __future__ import annotations

from pathlib import Path

import pytest

from lisbon_spatial_dynamics.catalog import CatalogError, load_catalog


def _write_catalog(tmp_path: Path, body: str) -> Path:
    """Write a temporary TOML catalogue and return its path."""
    path = tmp_path / "catalog.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_repository_catalog_loads() -> None:
    """The committed source catalogue should remain structurally valid."""
    path = Path(__file__).parents[1] / "configs" / "data_sources.toml"

    sources = load_catalog(path)

    assert len(sources) >= 4
    assert {source.source_id for source in sources} >= {
        "ine_local_housing_prices",
        "ine_census_geography",
        "lisboa_aberta",
        "strava_metro",
    }


def test_duplicate_source_ids_are_rejected(tmp_path: Path) -> None:
    """Source identifiers must be unique."""
    table = """
[[sources]]
source_id = "duplicate"
name = "Example"
provider = "Provider"
domain = "housing"
kind = "dataset"
status = "candidate"
spatial_unit = "freguesia"
frequency = "annual"
temporal_coverage = "2020-2025"
access = "public"
licence = "example"
landing_page = "https://example.com"
notes = "example"
"""
    path = _write_catalog(tmp_path, table + table)

    with pytest.raises(CatalogError, match="duplicate source_id"):
        load_catalog(path)


def test_invalid_status_is_rejected(tmp_path: Path) -> None:
    """Unknown lifecycle states should fail validation."""
    path = _write_catalog(
        tmp_path,
        """
[[sources]]
source_id = "example"
name = "Example"
provider = "Provider"
domain = "housing"
kind = "dataset"
status = "unknown"
spatial_unit = "freguesia"
frequency = "annual"
temporal_coverage = "2020-2025"
access = "public"
licence = "example"
landing_page = "https://example.com"
notes = "example"
""",
    )

    with pytest.raises(CatalogError, match="status must be one of"):
        load_catalog(path)


def test_non_http_landing_page_is_rejected(tmp_path: Path) -> None:
    """Catalogue landing pages must be absolute HTTP(S) URLs."""
    path = _write_catalog(
        tmp_path,
        """
[[sources]]
source_id = "example"
name = "Example"
provider = "Provider"
domain = "housing"
kind = "dataset"
status = "candidate"
spatial_unit = "freguesia"
frequency = "annual"
temporal_coverage = "2020-2025"
access = "public"
licence = "example"
landing_page = "example.com/data"
notes = "example"
""",
    )

    with pytest.raises(CatalogError, match="absolute HTTP"):
        load_catalog(path)
