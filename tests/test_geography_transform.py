"""Tests for the canonical Lisbon reference-geography transformation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.transformations.geography import (
    REFERENCE_COLUMNS,
    ReferenceGeographyError,
    parse_caop_reference,
    write_reference_geography,
)


def _payload() -> bytes:
    document = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "dtmnfr": "110602",
                    "freguesia": "B",
                    "designacao_simplificada": "B",
                    "municipio": "Lisboa",
                    "distrito_ilha": "Lisboa",
                    "nuts3_cod": "PT170",
                    "nuts3": "Área Metropolitana de Lisboa",
                    "nuts2": "Grande Lisboa",
                    "nuts1": "Continente",
                    "area_ha": 200.5,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "dtmnfr": "110601",
                    "freguesia": "A",
                    "designacao_simplificada": "A",
                    "municipio": "Lisboa",
                    "distrito_ilha": "Lisboa",
                    "nuts3_cod": "PT170",
                    "nuts3": "Área Metropolitana de Lisboa",
                    "nuts2": "Grande Lisboa",
                    "nuts1": "Continente",
                    "area_ha": 100,
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[0, 0], [1, 0], [0, 0]]]],
                },
            },
        ],
    }
    return json.dumps(document).encode()


def test_parse_reference_sorts_by_canonical_identifier() -> None:
    """Reference rows should be deterministic regardless of upstream order."""
    rows = parse_caop_reference(_payload(), expected_count=2)

    assert [row.freguesia_id for row in rows] == ["110601", "110602"]
    assert rows[0].name == "A"
    assert rows[1].area_ha == 200.5


def test_wrong_municipality_is_rejected() -> None:
    """The canonical transform must never admit non-Lisbon features."""
    document = json.loads(_payload())
    document["features"][0]["properties"]["municipio"] = "Oeiras"

    with pytest.raises(ReferenceGeographyError, match="not Lisboa"):
        parse_caop_reference(json.dumps(document).encode(), expected_count=2)


def test_duplicate_identifier_is_rejected() -> None:
    """DTMNFR must remain one-to-one in the reference table."""
    document = json.loads(_payload())
    document["features"][1]["properties"]["dtmnfr"] = "110602"

    with pytest.raises(ReferenceGeographyError, match="duplicate"):
        parse_caop_reference(json.dumps(document).encode(), expected_count=2)


def test_write_reference_outputs_stable_csv_and_geojson(tmp_path: Path) -> None:
    """The transform should emit matching deterministic table and geometry artifacts."""
    rows = parse_caop_reference(_payload(), expected_count=2)
    csv_path = tmp_path / "freguesias.csv"
    geojson_path = tmp_path / "freguesias.geojson"

    write_reference_geography(
        rows,
        csv_path=csv_path,
        geojson_path=geojson_path,
    )

    with csv_path.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == REFERENCE_COLUMNS
    assert [row["freguesia_id"] for row in table] == ["110601", "110602"]

    document = json.loads(geojson_path.read_text(encoding="utf-8"))
    assert [feature["id"] for feature in document["features"]] == [
        "110601",
        "110602",
    ]
    assert document["features"][0]["properties"]["source"] == "DGT CAOP2025"


def test_outputs_are_immutable(tmp_path: Path) -> None:
    """Canonical processed artifacts should not be silently replaced."""
    rows = parse_caop_reference(_payload(), expected_count=2)
    csv_path = tmp_path / "freguesias.csv"
    geojson_path = tmp_path / "freguesias.geojson"

    write_reference_geography(
        rows,
        csv_path=csv_path,
        geojson_path=geojson_path,
    )

    with pytest.raises(FileExistsError):
        write_reference_geography(
            rows,
            csv_path=csv_path,
            geojson_path=geojson_path,
        )
