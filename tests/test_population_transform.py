"""Tests for Censos 2021 population aggregation."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.transformations.population import (
    POPULATION_COLUMNS,
    CensusPopulationError,
    build_census_population_reference,
    write_census_population_csv,
)


def _archive(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "national.csv",
            "DTMNFR21;N_INDIVIDUOS;OTHER\n"
            "110654;10;x\n"
            "110654;5;y\n"
            "110656;20;z\n"
            "999999;100;outside\n",
        )


def _reference(path: Path) -> None:
    path.write_text(
        "freguesia_id,name,area_ha\n"
        "110654,Alvalade,100\n"
        "110656,Arroios,200\n",
        encoding="utf-8",
    )


def test_aggregate_subsections_to_canonical_freguesias(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"
    _archive(archive)
    _reference(reference)

    rows = build_census_population_reference(
        archive,
        reference,
        expected_count=2,
    )

    assert [row.freguesia_id for row in rows] == ["110654", "110656"]
    assert rows[0].population_resident == 15
    assert rows[0].population_density_per_km2 == pytest.approx(15.0)
    assert rows[1].population_resident == 20
    assert rows[1].population_density_per_km2 == pytest.approx(10.0)


def test_missing_population_for_reference_freguesia_fails(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"

    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(
            "national.csv",
            "DTMNFR21;N_INDIVIDUOS\n110654;10\n",
        )

    _reference(reference)

    with pytest.raises(CensusPopulationError, match="non-positive"):
        build_census_population_reference(
            archive,
            reference,
            expected_count=2,
        )


def test_writer_uses_stable_contract_and_is_immutable(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"
    _archive(archive)
    _reference(reference)

    rows = build_census_population_reference(
        archive,
        reference,
        expected_count=2,
    )
    output = tmp_path / "population.csv"

    write_census_population_csv(rows, output)

    with output.open(encoding="utf-8", newline="") as stream:
        table = list(csv.DictReader(stream))

    assert tuple(table[0]) == POPULATION_COLUMNS
    assert table[0]["population_resident"] == "15"

    with pytest.raises(FileExistsError):
        write_census_population_csv(rows, output)


def test_missing_required_source_columns_fails(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"

    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("bad.csv", "A;B\n1;2\n")

    _reference(reference)

    with pytest.raises(CensusPopulationError, match="DTMNFR21"):
        build_census_population_reference(
            archive,
            reference,
            expected_count=2,
        )
