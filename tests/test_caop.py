"""Tests for the DGT CAOP Lisbon reference-geography acquisition."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.sources.caop import (
    CAOPConfig,
    CAOPPayloadError,
    build_caop_query_url,
    fetch_caop_snapshot,
)


def _repo_config() -> CAOPConfig:
    path = Path(__file__).parents[1] / "configs" / "caop_lisbon.toml"
    return CAOPConfig.from_toml(path)


def _geojson(count: int = 2) -> bytes:
    features = []
    for index in range(count):
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "dtmnfr": f"1106{index:02d}",
                    "freguesia": f"Parish {index}",
                    "municipio": "Lisboa",
                    "distrito_ilha": "Lisboa",
                    "nuts3_cod": "PT170",
                    "nuts3": "Área Metropolitana de Lisboa",
                    "nuts2": "Grande Lisboa",
                    "nuts1": "Continente",
                    "area_ha": 100.0 + index,
                    "designacao_simplificada": f"Parish {index}",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]],
                },
            }
        )
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def _metadata() -> bytes:
    fields = [
        {"name": name}
        for name in (
            "dtmnfr",
            "freguesia",
            "municipio",
            "distrito_ilha",
            "nuts3_cod",
            "nuts3",
            "nuts2",
            "nuts1",
            "area_ha",
            "designacao_simplificada",
        )
    ]
    return json.dumps(
        {"fields": fields, "supportedQueryFormats": "JSON, geoJSON, PBF"}
    ).encode()


def test_repository_config_targets_official_layer() -> None:
    config = _repo_config()

    assert config.municipality == "Lisboa"
    assert config.expected_feature_count == 24
    assert config.id_field == "dtmnfr"
    assert config.layer_url.endswith("/FreguesiaCAOP2025/FeatureServer/7")


def test_query_is_explicit_and_requests_wgs84_geojson() -> None:
    url = build_caop_query_url(_repo_config())

    assert "/query?" in url
    assert "outSR=4326" in url
    assert "f=geojson" in url
    assert "orderByFields=dtmnfr" in url


def test_snapshot_validates_and_writes_raw_files(tmp_path: Path) -> None:
    base = _repo_config()
    config = CAOPConfig(
        source_id=base.source_id,
        layer_url=base.layer_url,
        municipality=base.municipality,
        municipality_field=base.municipality_field,
        id_field=base.id_field,
        name_field=base.name_field,
        out_fields=base.out_fields,
        expected_feature_count=2,
        output_directory=base.output_directory,
    )

    def fetcher(url: str, timeout: float) -> bytes:
        assert timeout == 5.0
        return _metadata() if "f=pjson" in url else _geojson()

    snapshot = fetch_caop_snapshot(
        config,
        root=tmp_path,
        timeout=5.0,
        fetched_at=datetime(2026, 9, 27, 15, 0, tzinfo=UTC),
        fetcher=fetcher,
    )

    assert (tmp_path / snapshot.geojson_path).exists()
    assert (tmp_path / snapshot.metadata_path).exists()
    manifest = json.loads((tmp_path / snapshot.manifest_path).read_text())
    assert manifest["expected_feature_count"] == 2
    assert manifest["municipality"] == "Lisboa"


def test_wrong_feature_count_is_rejected(tmp_path: Path) -> None:
    config = _repo_config()

    def fetcher(url: str, timeout: float) -> bytes:
        del timeout
        return _metadata() if "f=pjson" in url else _geojson(2)

    with pytest.raises(CAOPPayloadError, match="freguesia count"):
        fetch_caop_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 27, 15, 0, tzinfo=UTC),
            fetcher=fetcher,
        )


def test_wrong_municipality_is_rejected(tmp_path: Path) -> None:
    base = _repo_config()
    config = CAOPConfig(
        source_id=base.source_id,
        layer_url=base.layer_url,
        municipality=base.municipality,
        municipality_field=base.municipality_field,
        id_field=base.id_field,
        name_field=base.name_field,
        out_fields=base.out_fields,
        expected_feature_count=1,
        output_directory=base.output_directory,
    )
    payload = json.loads(_geojson(1))
    payload["features"][0]["properties"]["municipio"] = "Oeiras"

    def fetcher(url: str, timeout: float) -> bytes:
        del timeout
        if "f=pjson" in url:
            return _metadata()
        return json.dumps(payload).encode()

    with pytest.raises(CAOPPayloadError, match="unexpected municipality"):
        fetch_caop_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 27, 15, 0, tzinfo=UTC),
            fetcher=fetcher,
        )
