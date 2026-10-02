"""Geographic evidence must preserve ambiguity, cohort integrity and privacy."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from pyproj import Transformer
from shapely.geometry import Point, box, mapping

from lisbon_spatial_dynamics.analysis.rnal_geography import (
    classify_point,
    conflict_cohort,
    project_boundaries,
    reconcile,
)
from lisbon_spatial_dynamics.panels.rnal import RNALRecord
from lisbon_spatial_dynamics.sources.rnal_locations import (
    FIELDS,
    fetch_locations,
    validate_locations,
)


def location(number: int = 1, x: float = -9.14, y: float = 38.72) -> dict[str, Any]:
    return {
        "NrRNAL": number,
        "DTMNFR": "110655",
        "Concelho": "Lisboa",
        "FiabilidadeGeo": "Fiavel",
        "geometry": {"x": x, "y": y},
    }


def documents() -> list[dict[str, Any]]:
    row = location()
    geometry = row.pop("geometry")
    return [
        {"fields": [{"name": name, "domain": None} for name in FIELDS], "maxRecordCount": 100},
        {
            "spatialReference": {"wkid": 4326},
            "features": [{"attributes": row, "geometry": geometry}],
        },
    ]


def capture(output: Path, payloads: list[dict[str, Any]]) -> list[str]:
    urls = []
    iterator = iter(payloads)

    def getter(url: str, timeout: float) -> bytes:
        urls.append(url)
        return json.dumps(next(iterator)).encode()

    fetch_locations({1: "110655"}, output, getter=getter)
    return urls


def test_acquisition_requests_only_selected_analytical_fields(tmp_path: Path) -> None:
    payloads = documents()
    payloads[1]["features"][0]["attributes"]["Contact"] = "PRIVATE SENTINEL"
    payloads[1]["features"][0]["geometry"]["z"] = 12
    urls = capture(tmp_path / "snapshot", payloads)
    params = parse_qs(urlparse(urls[1]).query)
    assert params["outFields"] == [",".join(FIELDS)]
    assert params["outSR"] == ["4326"]
    assert params["where"] == ["Concelho='Lisboa' AND NrRNAL IN (1)"]
    stored = json.loads((tmp_path / "snapshot/locations.json").read_bytes())
    assert stored["records"] == [location()]
    assert all(
        b"PRIVATE SENTINEL" not in path.read_bytes() for path in (tmp_path / "snapshot").iterdir()
    )


def test_acquisition_covers_cohort_across_server_limited_batches(tmp_path: Path) -> None:
    payloads = documents()
    payloads[0]["maxRecordCount"] = 1
    second = deepcopy(payloads[1])
    second["features"][0]["attributes"]["NrRNAL"] = 2
    payloads.append(second)
    iterator = iter(payloads)
    queries = []

    def getter(url: str, timeout: float) -> bytes:
        queries.append(url)
        return json.dumps(next(iterator)).encode()

    output = tmp_path / "snapshot"
    fetch_locations({1: "110655", 2: "110655"}, output, getter=getter)
    records = json.loads((output / "locations.json").read_bytes())["records"]
    assert {row["NrRNAL"] for row in records} == {1, 2}
    assert len(queries) == 3


@pytest.mark.parametrize(
    "failure",
    ["missing", "duplicate", "extra", "changed_parish", "crs", "truncated", "coordinate", "error"],
)
def test_invalid_acquisition_never_publishes(tmp_path: Path, failure: str) -> None:
    payloads = documents()
    feature = payloads[1]["features"][0]
    if failure == "missing":
        payloads[1]["features"] = []
    elif failure == "duplicate":
        payloads[1]["features"].append(deepcopy(feature))
    elif failure == "extra":
        feature["attributes"]["NrRNAL"] = 2
    elif failure == "changed_parish":
        feature["attributes"]["DTMNFR"] = "110654"
    elif failure == "crs":
        payloads[1]["spatialReference"] = {"wkid": 3857}
    elif failure == "truncated":
        payloads[1]["exceededTransferLimit"] = True
    elif failure == "error":
        payloads[1] = {"error": {"code": 500}}
    else:
        feature["geometry"]["x"] = float("nan")
    with pytest.raises(ValueError):
        capture(tmp_path / "snapshot", payloads)
    assert not (tmp_path / "snapshot").exists()


def test_failed_location_write_cleans_staging_and_preserves_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write = Path.write_bytes

    def failed_write(path: Path, payload: bytes) -> int:
        if path.name == "manifest.json":
            raise OSError("simulated failure")
        return original_write(path, payload)

    output = tmp_path / "snapshot"
    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_bytes", failed_write)
        with pytest.raises(OSError, match="simulated failure"):
            capture(output, documents())
    assert not output.exists()
    assert not list(tmp_path.glob(".rnal-locations-*"))
    capture(output, documents())
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        capture(output, documents())
    assert (output / "manifest.json").read_bytes() == before


@pytest.mark.parametrize(
    "point,expected",
    [
        (Point(10, 10), "supports_soap"),
        (Point(30, 10), "supports_gis"),
        (Point(50, 10), "supports_other_parish"),
        (Point(20, 10), "boundary_ambiguous"),
        (Point(0, 10), "boundary_ambiguous"),
        (Point(80, 10), "outside_reference"),
        (None, "missing_geometry"),
    ],
)
def test_coordinate_support_categories(point: Point | None, expected: str) -> None:
    polygons = {
        "110654": box(0, 0, 20, 20),
        "110655": box(20, 0, 40, 20),
        "110656": box(40, 0, 60, 20),
    }
    category, distance = classify_point(point, polygons, "110654", "110655")
    assert category == expected
    assert (distance is None) == (point is None)


def boundaries() -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"freguesia_id": code, "name": code},
                "geometry": mapping(polygon),
            }
            for code, polygon in [
                ("110654", box(-9.16, 38.71, -9.14, 38.73)),
                ("110655", box(-9.14, 38.71, -9.12, 38.73)),
            ]
        ],
    }


def test_projection_preserves_axis_order_and_uses_local_metres() -> None:
    polygons, _, projector = project_boundaries(boundaries(), expected_count=2)
    x, y = projector.transform(-9.15, 38.72)
    assert -100000 < x < -70000 and -120000 < y < -90000
    assert 3_000_000 < polygons["110654"].area < 5_000_000
    assert classify_point(Point(x, y), polygons, "110654", "110655")[0] == "supports_soap"


@pytest.mark.parametrize("failure", ["overlap", "duplicate", "crs", "count", "invalid", "degrees"])
def test_invalid_reference_fails(failure: str) -> None:
    document = boundaries()
    if failure == "overlap":
        document["features"][1]["geometry"] = document["features"][0]["geometry"]
    elif failure == "duplicate":
        document["features"][1]["properties"]["freguesia_id"] = "110654"
    elif failure == "crs":
        document["crs"] = {"name": "EPSG:3857"}
    elif failure == "count":
        document["features"].pop()
    elif failure == "invalid":
        document["features"][0]["geometry"] = mapping(Point(-9.15, 38.72))
    else:
        document["features"][0]["geometry"] = mapping(box(1000, 1000, 2000, 2000))
    with pytest.raises(ValueError):
        project_boundaries(document, expected_count=2)


def test_boundary_margin_is_strict_and_does_not_change_assignments() -> None:
    # Identity projection isolates metre-distance rules from projection numerics.
    projector = Transformer.from_crs(3763, 3763, always_xy=True)
    polygons = {"110654": box(0, 0, 20, 20), "110655": box(20, 0, 40, 20)}
    summary, rows = reconcile(
        {1: ("110654", "110655")},
        [location(x=30, y=10)],
        polygons,
        {key: key for key in polygons},
        projector,
        thresholds_m=[0, 10, 25],
    )
    sensitivity = summary["boundary_sensitivity"]
    assert isinstance(sensitivity, list)
    assert [entry["supports_gis"] for entry in sensitivity] == [1, 0, 0]
    assert sensitivity[1]["within_boundary_margin"] == 1
    assert summary["assignments_corrected"] == 0
    assert rows[0]["supports_gis"] == 1
    missing = location()
    missing["geometry"] = None
    validate_locations([missing], {1: "110655"})


def test_conflict_selection_uses_normalized_shared_registry_ids() -> None:
    soap = [RNALRecord("01/AL", date(2020, 1, 1), None, "110654", "A", "", 1, 1)]
    gis = [
        {
            "OBJECTID": 1,
            "NrRNAL": 1,
            "DTMNFR": "110655",
            "Freguesia": "B",
            "Concelho": "Lisboa",
            "DataRegisto": 0,
            "DataAberturaPublico": None,
            "NrUtentes": 1,
        }
    ]
    assert conflict_cohort(soap, gis) == {1: ("110654", "110655")}
    with pytest.raises(ValueError, match="duplicate"):
        conflict_cohort(soap + soap, gis)


@pytest.fixture(scope="module")
def audit_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/audit_rnal_geography.py"
    spec = importlib.util.spec_from_file_location("rnal_geography_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_input_tampering_fails(tmp_path: Path, audit_module: ModuleType) -> None:
    path = tmp_path / "locations.json"
    path.write_bytes(b"original")
    pinned = audit_module.fingerprint(path)
    path.write_bytes(b"modified")
    with pytest.raises(ValueError, match="integrity mismatch"):
        audit_module.verify(path, pinned)


@pytest.fixture
def audit_config(tmp_path: Path, audit_module: ModuleType, request: pytest.FixtureRequest) -> Path:
    capture(tmp_path / "locations", documents())
    soap = {
        "records": [
            {
                "NrRegisto": "1/AL",
                "DataRegisto": "2020-01-01",
                "DTMNFR": "110654",
                "Freguesia": "A",
                "CessadoEm": "",
            }
        ]
    }
    gis = {
        "records": [
            {
                "OBJECTID": 1,
                "NrRNAL": 1,
                "DTMNFR": "110655",
                "Freguesia": "B",
                "Concelho": "Lisboa",
                "DataRegisto": 0,
                "DataAberturaPublico": None,
                "NrUtentes": 1,
            }
        ]
    }
    inputs = {"locations_manifest": tmp_path / "locations/manifest.json"}
    for name, document in {"soap": soap, "gis": gis, "reference": boundaries()}.items():
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(document), encoding="utf-8")
        inputs[name] = path
    lines = [
        'audit_date = "2026-10-01"',
        "[expectations]",
        "conflicts = 1",
        "parishes = 2",
        "[analysis]",
        "boundary_margins_m = [0.0, 25.0, 100.0]",
    ]
    if getattr(request, "param", False):
        lines[4:4] = ["snapshot_records = 1", "population_2021 = 200"]
        lines.extend(['kind = "parish_sensitivity"', "reassignment_margin_m = 25.0"])
        population = tmp_path / "population.csv"
        population.write_text(
            "freguesia_id,census_year,population_resident\n110654,2021,100\n110655,2021,100\n",
            encoding="utf-8",
        )
        inputs["population"] = population
    for name, path in inputs.items():
        lines.append(f"[inputs.{name}]")
        lines.extend(
            f"{key} = {json.dumps(value)}" for key, value in audit_module.fingerprint(path).items()
        )
    config = tmp_path / "audit.toml"
    config.write_text("\n".join(lines), encoding="utf-8")
    return config


@pytest.mark.parametrize("audit_config", [False, True], indirect=True)
def test_offline_replay_hashes_and_atomic_failure(
    tmp_path: Path,
    audit_module: ModuleType,
    audit_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        pytest.fail("offline audit attempted network access")

    monkeypatch.setattr("lisbon_spatial_dynamics.sources.rnal_geodata.urlopen", no_network)
    output = tmp_path / "audit"
    original_write = Path.write_bytes

    def failed_write(path: Path, payload: bytes) -> int:
        if path.name == "audit.json":
            raise OSError("simulated publication failure")
        return original_write(path, payload)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_bytes", failed_write)
        with pytest.raises(OSError, match="simulated publication failure"):
            audit_module.audit(audit_config, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".rnal-geography-*"))
    audit_module.audit(audit_config, output)
    report = json.loads((output / "audit.json").read_bytes())
    assert report["summary"]["conflicting_records"] == 1
    assert report["summary"]["assignments_corrected"] == 0
    for artifact in report["outputs"]:
        assert Path(artifact["path"]).parent == output
        audit_module.verify(Path(artifact["path"]), artifact)
    with pytest.raises(FileExistsError):
        audit_module.audit(audit_config, output)
    replay = tmp_path / "replay"
    audit_module.audit(audit_config, replay)
    assert (output / "coordinate_support_by_parish.csv").read_bytes() == (
        replay / "coordinate_support_by_parish.csv"
    ).read_bytes()
    if (output / "parish_scenarios.csv").exists():
        assert (output / "parish_scenarios.csv").read_bytes() == (
            replay / "parish_scenarios.csv"
        ).read_bytes()
    (tmp_path / "locations/locations.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="integrity mismatch"):
        audit_module.audit(audit_config, tmp_path / "tampered")


@pytest.mark.parametrize("source,index", [("SOAP", 0), ("GIS", 1)])
def test_unknown_parish_fails_before_any_classification(
    source: str, index: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_classification(*args: object, **kwargs: object) -> None:
        pytest.fail("classification began before cohort validation")

    monkeypatch.setattr(
        "lisbon_spatial_dynamics.analysis.rnal_geography.classify_point", no_classification
    )
    pair = ["110654", "110655"]
    pair[index] = "110699"
    with pytest.raises(ValueError, match=f"{source} conflict parishes.*110699"):
        reconcile(
            {1: ("110654", "110655"), 2: (pair[0], pair[1])},
            [location(), location(number=2)],
            {"110654": box(0, 0, 20, 20), "110655": box(20, 0, 40, 20)},
            {"110654": "A", "110655": "B"},
            Transformer.from_crs(3763, 3763, always_xy=True),
            thresholds_m=[25],
        )
