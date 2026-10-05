"""Tests for the v1 study release build contract."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import zipfile
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.analysis.study_v1 import (
    STUDY_V1_VERSION,
    StudyV1BuildError,
    StudyV1Inputs,
    build_study_v1,
)


def _inputs(tmp_path: Path) -> StudyV1Inputs:
    paths = {
        "housing_snapshot": tmp_path / "housing.json",
        "rnal_snapshot": tmp_path / "rnal.json",
        "census_archive": tmp_path / "census.zip",
        "reference_csv": tmp_path / "reference.csv",
        "reference_geojson": tmp_path / "reference.geojson",
        "model_config": tmp_path / "models.toml",
    }
    for path in paths.values():
        path.write_bytes(b"placeholder")

    return StudyV1Inputs(**paths)


def test_study_v1_version_is_stable_release() -> None:
    assert STUDY_V1_VERSION == "1.1.0"


def test_missing_input_fails_before_creating_output(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    inputs.rnal_snapshot.unlink()
    output = tmp_path / "output"

    with pytest.raises(StudyV1BuildError, match="missing v1 study input files"):
        build_study_v1(inputs, output)

    assert not output.exists()


def test_existing_output_root_is_rejected(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "existing-result.txt"
    sentinel.write_text("keep this study", encoding="utf-8")

    with pytest.raises(FileExistsError):
        build_study_v1(inputs, output)

    assert sentinel.read_text(encoding="utf-8") == "keep this study"


def test_invalid_release_parameters_are_rejected(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)

    with pytest.raises(ValueError, match="expected_freguesias"):
        build_study_v1(inputs, tmp_path / "a", expected_freguesias=0)

    with pytest.raises(ValueError, match="permutations"):
        build_study_v1(inputs, tmp_path / "b", permutations=-1)

    with pytest.raises(ValueError, match="local_alpha"):
        build_study_v1(inputs, tmp_path / "c", local_alpha=1.0)


def _synthetic_inputs(tmp_path: Path) -> StudyV1Inputs:
    """Create source-shaped fixtures; these are not observations about Lisbon."""
    inputs = _inputs(tmp_path)
    rng = random.Random(2021)
    reference_rows: list[tuple[str, str, int]] = []
    features: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    periods = [(2019, 4), (2020, 1), (2020, 2), (2020, 3), (2020, 4)]
    housing: dict[str, list[dict[str, str]]] = {
        f"{quarter}.º Trimestre de {year}": [] for year, quarter in periods
    }
    census = io.StringIO()
    census_writer = csv.writer(census, delimiter=";", lineterminator="\n")
    census_writer.writerow(
        [
            "DTMNFR21",
            "N_INDIVIDUOS",
            "N_EDIFICIOS_CLASSICOS",
            "N_EDIFICIOS_CONSTR_ANTES 1945",
            "N_EDIFICIOS_COM NECESSIDADES REPARAÇAO",
            "N_ALOJAMENTOS_TOTAL",
            "N_ALOJAMENTOS_FAMILIARES",
            "N_ALOJAMENTOS_ FAM_CLASS_RHABITUAL",
            "N_ALOJAMENTOS_ FAM_CLASS_VAGOS OU RESID SECUNDARIA",
            "N_RHABITUAL_PROP_OCUP",
            "N_RHABITUAL_ARRENDADOS",
            "N_AGREGADOS DOMESTICOS PRIVADOS",
            "N_INDIVIDUOS_0A14",
            "N_INDIVIDUOS_15A24",
            "N_INDIVIDUOS_25A64",
            "N_INDIVIDUOS_65_OU_MAIS",
        ]
    )

    for index in range(24):
        identifier = f"1106{index:02d}"
        name = f"Synthetic parish {index}"
        population = rng.randint(2000, 9000)
        area = rng.randint(100, 500)
        reference_rows.append((identifier, name, area))
        x, y = index % 6, index // 6
        features.append(
            {
                "type": "Feature",
                "id": identifier,
                "properties": {"freguesia_id": identifier, "name": name, "area_ha": area},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1], [x, y]]],
                },
            }
        )
        baseline_housing = rng.randint(2000, 5000)
        growth = rng.uniform(0.05, 0.4)
        for period_index, (year, quarter) in enumerate(periods):
            housing[f"{quarter}.º Trimestre de {year}"].append(
                {
                    "geocod": f"1A0{identifier}",
                    "geodsg": name,
                    "dim_3": "H1",
                    "dim_3_t": "Total",
                    "valor": f"{baseline_housing * (1 + growth * period_index / 4):.6f}",
                }
            )
        for registered_on, count in [
            ("2018-06-01", rng.randint(2, 7)),
            ("2020-02-01", rng.randint(5, 30)),
        ]:
            for _ in range(count):
                records.append(
                    {
                        "NrRegisto": f"synthetic-{len(records)}/AL",
                        "DataRegisto": registered_on,
                        "CessadoEm": "",
                        "DTMNFR": identifier,
                        "Freguesia": name,
                        "Modalidade": "Apartamento",
                        "NrCamas": "2",
                        "NrUtentes": "4",
                    }
                )
        vacant = rng.randint(100, 250)
        usual = 1000 - vacant
        rented = rng.randint(200, 400)
        age_65 = rng.randint(population // 10, population // 3)
        age_14, age_24 = population // 7, population // 10
        census_writer.writerow(
            [
                identifier,
                population,
                500,
                rng.randint(50, 200),
                rng.randint(20, 120),
                1100,
                1000,
                usual,
                vacant,
                usual - rented,
                rented,
                usual,
                age_14,
                age_24,
                population - age_14 - age_24 - age_65,
                age_65,
            ]
        )

    with inputs.reference_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["freguesia_id", "name", "area_ha"])
        writer.writerows(reference_rows)
    inputs.reference_geojson.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    inputs.housing_snapshot.write_text(
        json.dumps([{"IndicadorCod": "0012234", "Dados": housing}]), encoding="utf-8"
    )
    inputs.rnal_snapshot.write_text(json.dumps({"records": records}), encoding="utf-8")
    with zipfile.ZipFile(inputs.census_archive, "w") as archive:
        archive.writestr("synthetic-census.csv", census.getvalue())
    model_config = Path(__file__).parents[1] / "configs" / "multivariable_models.toml"
    inputs.model_config.write_bytes(model_config.read_bytes())
    return inputs


def test_complete_study_builds_results_and_verifiable_manifest(tmp_path: Path) -> None:
    """Exercise every stage with the real model configuration and 24 fake parishes."""
    inputs = _synthetic_inputs(tmp_path)
    original_inputs = {path: path.read_bytes() for path in inputs.paths()}
    output = tmp_path / "study"

    result = build_study_v1(inputs, output, permutations=9, seed=42)

    assert all(path.exists() for path in result.paths())
    final_files = {path.name for path in result.final_results_directory.iterdir()}
    assert final_files == {
        "table_1_descriptive.csv",
        "table_2_spatial.csv",
        "table_3_models.csv",
        "table_4_diagnostics.csv",
        "findings.json",
        "findings.md",
        "figure_1_pressure_association.png",
        "figure_2_pressure_coefficients.png",
        "figure_3_primary_residuals.png",
    }
    with (result.final_results_directory / "table_3_models.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        models = list(csv.DictReader(stream))
    assert len(models) == 4
    assert {row["n_observations"] for row in models} == {"24"}
    findings = json.loads((result.final_results_directory / "findings.json").read_text())
    assert findings["study_window"] == {"baseline_year": 2019, "latest_common_year": 2020}

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["parameters"]["spatial_permutations"] == 9
    assert manifest["parameters"]["random_seed"] == 42
    assert len(manifest["inputs"]) == len(inputs.paths())
    for record in manifest["inputs"]:
        path = Path(record["path"])
        assert path.read_bytes() == original_inputs[path]
        assert record["sha256"] == hashlib.sha256(original_inputs[path]).hexdigest()
        assert record["size_bytes"] == len(original_inputs[path])
    manifest_files = {record["path"] for record in manifest["outputs"]}
    actual_files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path != result.manifest_path
    }
    assert manifest_files == actual_files
    for record in manifest["outputs"]:
        payload = (output / record["path"]).read_bytes()
        assert record["sha256"] == hashlib.sha256(payload).hexdigest()
        assert record["size_bytes"] == len(payload)


def test_failed_stage_removes_partial_outputs_and_preserves_inputs(tmp_path: Path) -> None:
    inputs = _synthetic_inputs(tmp_path)
    inputs.census_archive.write_bytes(b"not a ZIP archive")
    original_inputs = {path: path.read_bytes() for path in inputs.paths()}
    output = tmp_path / "failed-study"

    with pytest.raises(zipfile.BadZipFile):
        build_study_v1(inputs, output, permutations=9)

    assert not output.exists()
    assert all(path.read_bytes() == payload for path, payload in original_inputs.items())
