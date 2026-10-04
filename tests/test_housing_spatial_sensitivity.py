"""Sensitivity checks must expose graph changes and preserve the primary statistic."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
from dataclasses import replace
from hashlib import sha256
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from lisbon_spatial_dynamics.analysis.housing_spatial import CHANGE_COLUMNS, build_housing_map
from lisbon_spatial_dynamics.analysis.housing_spatial_sensitivity import (
    analyse_housing_sensitivity,
    holm_adjust,
    moran_statistic,
    permutation_test,
    row_weights,
)
from lisbon_spatial_dynamics.analysis.spatial_autocorrelation import analyse_global_moran_metric

REFERENCE = {"110601": "Ajuda", "110602": "Alcântara", "110607": "Beato", "110608": "Benfica"}


def inputs(*, grid: bool = False) -> tuple[str, str]:
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(CHANGE_COLUMNS)
    features = []
    for i, (code, name) in enumerate(REFERENCE.items()):
        percent = 10 * (i + 1)
        writer.writerow([code, name, 2019, 2025, 100, 100 + percent, percent, percent])
        x, y = (i % 2, i // 2) if grid else (i, 0)
        features.append(
            {
                "type": "Feature",
                "id": code,
                "properties": {"freguesia_id": code, "name": name, "municipality": "Lisboa"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]],
                },
            }
        )
    return stream.getvalue(), json.dumps({"type": "FeatureCollection", "features": features})


def run(*, grid: bool = False) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    return analyse_housing_sensitivity(
        *inputs(grid=grid),
        REFERENCE,
        baseline_year=2019,
        latest_year=2025,
        permutations=99,
        seed=42,
        alpha=0.05,
    )


def test_primary_and_each_omission_match_existing_implementation() -> None:
    data = build_housing_map(*inputs(), REFERENCE, baseline_year=2019, latest_year=2025)
    summary, datasets = run()
    primary = analyse_global_moran_metric(data, metric="housing_change_pct", permutations=99)
    actual = datasets["global_scenarios.csv"][0]
    assert actual["morans_i"] == pytest.approx(0.4)
    assert actual["morans_i"] == pytest.approx(primary.morans_i)
    assert actual["permutation_p_two_sided"] == primary.permutation_p_two_sided
    assert summary["identical_graphs"]
    for row in datasets["leave_one_out.csv"]:
        subset = replace(
            data, features=tuple(f for f in data.features if f.freguesia_id != row["omitted_id"])
        )
        expected = analyse_global_moran_metric(subset, metric="housing_change_pct", permutations=0)
        assert row["morans_i"] == pytest.approx(expected.morans_i)
        assert row["neighbor_pairs"] == expected.edge_count
        assert row["islands"] == ";".join(expected.islands)
        assert row["retained_parishes"] == 3
        assert not any("p_value" in key for key in row)
    assert datasets["leave_one_out.csv"][1]["islands"] == "110601"


def test_rook_excludes_corner_only_contacts_and_retains_all_six_scenarios() -> None:
    summary, datasets = run(grid=True)
    assert summary["queen_pairs"] == 6
    assert summary["rook_pairs"] == 4
    assert not summary["identical_graphs"]
    assert len(datasets["global_scenarios.csv"]) == 6
    assert sum(not row["rook"] for row in datasets["neighbor_pairs.csv"]) == 2
    for row in datasets["neighbor_pairs.csv"]:
        assert row["queen_left_to_right"] == pytest.approx(1 / 3)
        assert row["rook_left_to_right"] == (0.5 if row["rook"] else 0)
    first = datasets["parish_metrics.csv"][0]
    assert first["percentage_change"] == 10
    assert first["absolute_change"] == 10
    assert first["log_change"] == pytest.approx(math.log(1.1))


def test_reordering_inputs_preserves_results() -> None:
    housing, geometry = inputs(grid=True)
    lines = housing.splitlines()
    document = json.loads(geometry)
    document["features"].reverse()
    actual = analyse_housing_sensitivity(
        "\n".join([lines[0], *reversed(lines[1:])]) + "\n",
        json.dumps(document),
        REFERENCE,
        baseline_year=2019,
        latest_year=2025,
        permutations=99,
        seed=42,
        alpha=0.05,
    )
    assert actual == run(grid=True)


@pytest.mark.parametrize(
    "p,expected",
    [
        ([0.03, 0.01, 0.04], [0.06, 0.03, 0.06]),
        ([0.01, 0.01, 0.5], [0.03, 0.03, 0.5]),
        ([0, 1], [0, 1]),
    ],
)
def test_holm_adjustment_including_unsorted_ties(p: list[float], expected: list[float]) -> None:
    assert holm_adjust(p) == pytest.approx(expected)


@pytest.mark.parametrize("p", [[], [float("nan")], [-0.1], [1.1]])
def test_holm_rejects_invalid_probabilities(p: list[float]) -> None:
    with pytest.raises(ValueError):
        holm_adjust(p)


@pytest.mark.parametrize(
    "graph",
    [
        [[False, True], [False, False]],
        [[True, False], [False, True]],
        [[False, False], [False, False]],
        [[False, True, False]],
        [[0, 1], [1, 0]],
    ],
)
def test_invalid_graphs_are_rejected(graph: Any) -> None:
    with pytest.raises(ValueError):
        row_weights(np.array(graph))


@pytest.mark.parametrize("values", [[1.0, 1.0, 1.0], [1.0, float("inf"), 3.0], [1.0, 2.0]])
def test_invalid_metric_values_are_rejected(values: list[float]) -> None:
    graph = np.array([[False, True, False], [True, False, True], [False, True, False]])
    with pytest.raises(ValueError):
        moran_statistic(np.array(values), graph)


@pytest.mark.parametrize("permutations", [0, -1, True, 1.5])
def test_invalid_permutation_counts_are_rejected(permutations: Any) -> None:
    with pytest.raises(ValueError):
        permutation_test(
            np.array([1.0, 2.0, 3.0]),
            np.zeros((3, 3), dtype=bool),
            permutations=permutations,
            seed=42,
        )


@pytest.fixture(scope="module")
def script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/analyse_housing_spatial_sensitivity.py"
    spec = importlib.util.spec_from_file_location("housing_sensitivity_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quick_config(tmp_path: Path) -> Path:
    path = tmp_path / "quick.toml"
    path.write_text(
        Path("configs/housing_spatial_sensitivity_2026-10-04.toml")
        .read_text(encoding="utf-8")
        .replace("permutations = 9999", "permutations = 99"),
        encoding="utf-8",
    )
    return path


def test_offline_replay_captures_inputs_once_and_hashes_complete_bundle(
    tmp_path: Path,
    script: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = Path.read_bytes
    seen: set[str] = set()

    def read_once(path: Path) -> bytes:
        if path.name in {"parish_changes.csv", "freguesias.geojson", "census_context.csv"}:
            assert path.name not in seen
            seen.add(path.name)
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_once)
    output = tmp_path / "result"
    script.analyse(quick_config(tmp_path), output)
    report = json.loads((output / "analysis.json").read_bytes())
    assert report["summary"]["scenarios"] == 6
    assert report["summary"]["parishes"] == 24
    assert report["primary_reproduction"] == {"statistic_verified": True, "p_value_verified": False}
    assert len(seen) == 3
    assert {path.name for path in output.iterdir()} == {
        "analysis.json",
        "global_scenarios.csv",
        "parish_metrics.csv",
        "neighbor_pairs.csv",
        "leave_one_out.csv",
        "sensitivity.png",
    }
    for item in report["outputs"]:
        payload = Path(item["path"]).read_bytes()
        assert sha256(payload).hexdigest() == item["sha256"]
        assert len(payload) == item["size_bytes"]
        if item["path"].endswith(".csv"):
            assert b"\r" not in payload


def test_failed_plot_leaves_no_partial_bundle(
    tmp_path: Path, script: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("render failed")

    monkeypatch.setattr(script, "plot_housing_sensitivity", fail)
    output = tmp_path / "result"
    with pytest.raises(OSError, match="render failed"):
        script.analyse(quick_config(tmp_path), output)
    assert not output.exists()
    assert not list(tmp_path.glob(".housing-sensitivity-*"))


@pytest.mark.parametrize("failure", ["hash", "specification", "existing"])
def test_replay_rejects_invalid_input_and_overwrite(
    tmp_path: Path, script: ModuleType, failure: str
) -> None:
    config = quick_config(tmp_path)
    text = config.read_text(encoding="utf-8")
    output = tmp_path / "result"
    if failure == "hash":
        text = text.replace("size_bytes = 1873", "size_bytes = 1")
    elif failure == "specification":
        text = text.replace('"log_change", ', "")
    else:
        output.mkdir()
    config.write_text(text, encoding="utf-8")
    with pytest.raises((ValueError, FileExistsError)):
        script.analyse(config, output)
    assert not output.exists() or not list(output.iterdir())


@pytest.mark.parametrize("failure", ["link", "coverage", "statistic", "p_value"])
def test_rehashed_parent_with_inconsistent_evidence_is_rejected(
    tmp_path: Path,
    script: ModuleType,
    failure: str,
) -> None:
    original = Path("results/housing-spatial/2026-10-04/analysis.json")
    original_bytes = original.read_bytes()
    parent = json.loads(original_bytes)
    if failure == "link":
        parent["inputs"]["geometry"]["size_bytes"] = 1
    elif failure == "coverage":
        parent["summary"]["latest_year"] = 2026
    elif failure == "statistic":
        parent["summary"]["global_morans_i"] = 0
    else:
        parent["parameters"]["permutations"] = 99
        parent["summary"]["global_permutation_p_two_sided"] = -1
    payload = json.dumps(parent).encode("utf-8")
    changed = tmp_path / "parent.json"
    changed.write_bytes(payload)
    config = quick_config(tmp_path)
    text = config.read_text(encoding="utf-8")
    text = text.replace(original.as_posix(), changed.as_posix())
    text = text.replace(sha256(original_bytes).hexdigest(), sha256(payload).hexdigest())
    text = text.replace(f"size_bytes = {len(original_bytes)}", f"size_bytes = {len(payload)}")
    config.write_text(text, encoding="utf-8")
    output = tmp_path / "result"
    with pytest.raises(ValueError, match="primary"):
        script.analyse(config, output)
    assert not output.exists()
