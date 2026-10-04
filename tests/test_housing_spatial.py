"""Single-metric spatial evidence must preserve identity, nulls and provenance."""

from __future__ import annotations

import csv
import importlib.util
import json
from dataclasses import replace
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from lisbon_spatial_dynamics.analysis.housing_spatial import CHANGE_COLUMNS, build_housing_map
from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import (
    analyse_local_moran_metric,
    analyse_local_morans_i,
)
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import (
    analyse_global_moran_metric,
    analyse_global_morans_i,
    build_queen_weights,
)
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import TrajectoryMapData

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara", "110607": "Beato", "110608": "Benfica"}


def fixtures() -> tuple[list[list[Any]], dict[str, Any]]:
    rows, features = [], []
    for index, (code, name) in enumerate(REFERENCE.items()):
        value = 10 * (index + 1)
        rows.append([code, name, 2019, 2025, 100, 100 + value, value, value])
        features.append(
            {
                "type": "Feature",
                "id": code,
                "properties": {"freguesia_id": code, "name": name, "municipality": "Lisboa"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[index, 0], [index + 1, 0], [index + 1, 1], [index, 1], [index, 0]]
                    ],
                },
            }
        )
    return rows, {"type": "FeatureCollection", "features": features}


def build(rows: list[list[Any]], document: dict[str, Any]) -> TrajectoryMapData:
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(CHANGE_COLUMNS)
    writer.writerows(rows)
    return build_housing_map(
        stream.getvalue(), json.dumps(document), REFERENCE, baseline_year=2019, latest_year=2025
    )


def test_housing_only_statistics_match_existing_dual_metric_calculations() -> None:
    data = build(*fixtures())
    assert all(feature.rnal_active_change_pct is None for feature in data.features)
    global_result = analyse_global_moran_metric(data, metric="housing_change_pct", permutations=99)
    local_result = analyse_local_moran_metric(data, metric="housing_change_pct", permutations=99)
    synthetic_both = replace(
        data,
        features=tuple(
            replace(feature, rnal_active_change_pct=feature.housing_change_pct)
            for feature in data.features
        ),
    )
    assert global_result == analyse_global_morans_i(synthetic_both, permutations=99)[0]
    assert local_result == analyse_local_morans_i(synthetic_both, permutations=99)[0]
    assert global_result.morans_i == pytest.approx(0.4)
    assert global_result.edge_count == 3
    assert [row.local_i for row in local_result.observations] == pytest.approx([0.6, 0.2, 0.2, 0.6])


@pytest.mark.parametrize(
    "failure",
    [
        "duplicate",
        "missing",
        "name",
        "window",
        "absolute",
        "percent",
        "nonfinite",
        "zero",
        "ragged",
    ],
)
def test_bad_housing_evidence_is_rejected(failure: str) -> None:
    rows, document = fixtures()
    if failure == "duplicate":
        rows.append(rows[0])
    elif failure == "missing":
        rows.pop()
    elif failure == "ragged":
        rows[0].pop()
    else:
        column, value = {
            "name": (1, "Wrong"),
            "window": (3, 2024),
            "absolute": (6, 1000),
            "percent": (7, 50),
            "nonfinite": (7, "NaN"),
            "zero": (4, 0),
        }[failure]
        rows[0][column] = value
    with pytest.raises(ValueError):
        build(rows, document)


@pytest.mark.parametrize(
    "failure", ["duplicate", "missing", "name", "feature_id", "municipality", "geometry_type"]
)
def test_bad_geographic_identity_is_rejected(failure: str) -> None:
    rows, document = fixtures()
    if failure == "duplicate":
        document["features"].append(document["features"][0])
    elif failure == "missing":
        document["features"].pop()
    else:
        feature = document["features"][0]
        if failure in {"name", "municipality"}:
            feature["properties"][failure] = "Wrong"
        elif failure == "feature_id":
            feature["id"] = "110699"
        else:
            feature["geometry"] = {"type": "Point", "coordinates": [0, 0]}
    with pytest.raises(ValueError):
        build(rows, document)


@pytest.mark.parametrize("permutations", [-1, 1.5, True])
def test_single_metric_functions_reject_invalid_permutation_counts(permutations: Any) -> None:
    data = build(*fixtures())
    with pytest.raises(ValueError):
        analyse_global_moran_metric(data, metric="housing_change_pct", permutations=permutations)
    with pytest.raises(ValueError):
        analyse_local_moran_metric(data, metric="housing_change_pct", permutations=permutations)


def test_feature_order_does_not_change_results() -> None:
    rows, document = fixtures()
    expected = build(rows, document)
    document["features"].reverse()
    actual = build(list(reversed(rows)), document)
    assert actual == expected
    assert build_queen_weights(actual).neighbors == build_queen_weights(expected).neighbors


@pytest.mark.parametrize("nested", [False, True])
def test_equal_or_contained_polygons_cannot_form_an_administrative_partition(nested: bool) -> None:
    rows, document = fixtures()
    document["features"][1]["geometry"] = (
        {
            "type": "Polygon",
            "coordinates": [[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8], [0.2, 0.2]]],
        }
        if nested
        else document["features"][0]["geometry"]
    )
    data = build(rows, document)
    with pytest.raises(ValueError, match="overlap"):
        build_queen_weights(data)


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_spatial.py"
    spec = importlib.util.spec_from_file_location("housing_spatial_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_replay_uses_verified_bytes_and_publishes_only_housing(
    tmp_path: Path,
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = Path.read_bytes
    reads: dict[str, int] = {}

    def read_once(path: Path) -> bytes:
        if path.name in {"parish_changes.csv", "freguesias.geojson"}:
            reads[path.name] = reads.get(path.name, 0) + 1
            assert reads[path.name] == 1
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    config = tmp_path / "quick.toml"
    config.write_text(
        Path("configs/housing_spatial_2026-10-04.toml")
        .read_text(encoding="utf-8")
        .replace("permutations = 9999", "permutations = 99"),
        encoding="utf-8",
    )
    output = tmp_path / "result"
    script.analyse(config, output)
    report = json.loads((output / "analysis.json").read_bytes())
    assert report["summary"]["parishes"] == 24
    assert report["summary"]["queen_pairs"] == 54
    assert report["summary"]["islands"] == []
    assert {path.name for path in output.iterdir()} == {
        "analysis.json",
        "global_moran.json",
        "local_moran.json",
        "queen_pairs.csv",
        "local_results.csv",
        "housing_spatial.png",
    }
    for name in ["global_moran.json", "local_moran.json"]:
        payload = (output / name).read_bytes()
        results = json.loads(payload)["results"]
        assert [result["metric"] for result in results] == ["housing_change_pct"]
        assert b"\r" not in payload
    for item in report["outputs"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]
    assert len(reads) == 2


def test_failed_map_leaves_no_partial_bundle(
    tmp_path: Path,
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_map(*args: Any) -> None:
        raise OSError("render failed")

    monkeypatch.setattr(script, "plot_housing_spatial", fail_map)
    config = tmp_path / "quick.toml"
    config.write_text(
        Path("configs/housing_spatial_2026-10-04.toml")
        .read_text(encoding="utf-8")
        .replace("permutations = 9999", "permutations = 0"),
        encoding="utf-8",
    )
    output = tmp_path / "result"
    with pytest.raises(OSError, match="render failed"):
        script.analyse(config, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".housing-spatial-*"))


def test_hash_failure_and_existing_output_are_rejected(tmp_path: Path, script: ModuleType) -> None:
    config = tmp_path / "bad.toml"
    config.write_text(
        Path("configs/housing_spatial_2026-10-04.toml")
        .read_text(encoding="utf-8")
        .replace("size_bytes = 1873", "size_bytes = 1"),
        encoding="utf-8",
    )
    output = tmp_path / "result"
    with pytest.raises(ValueError, match="integrity mismatch"):
        script.analyse(config, output)
    assert not output.exists()
    output.mkdir()
    with pytest.raises(FileExistsError):
        script.analyse(config, output)


def test_rehashed_geography_manifest_with_broken_parent_link_is_rejected(
    tmp_path: Path,
    script: ModuleType,
) -> None:
    original = Path("data/reference/caop2025-lisbon/provenance.json")
    original_bytes = original.read_bytes()
    document = json.loads(original_bytes)
    document["original_canonical"]["sha256"] = "0" * 64
    payload = json.dumps(document, ensure_ascii=False).encode("utf-8")
    changed = tmp_path / "provenance.json"
    changed.write_bytes(payload)
    config = tmp_path / "changed.toml"
    text = Path("configs/housing_spatial_2026-10-04.toml").read_text(encoding="utf-8")
    text = text.replace(original.as_posix(), changed.as_posix())
    text = text.replace(sha256(original_bytes).hexdigest(), sha256(payload).hexdigest())
    text = text.replace(f"size_bytes = {len(original_bytes)}", f"size_bytes = {len(payload)}")
    config.write_text(text, encoding="utf-8")
    output = tmp_path / "result"
    with pytest.raises(ValueError, match="provenance chain differs"):
        script.analyse(config, output)
    assert not output.exists()
