"""Regression tests for the official mixed-hierarchy Census XLSX archive."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from lisbon_spatial_dynamics.transformations.census_context import build_census2021_context
from lisbon_spatial_dynamics.transformations.census_workbook import (
    CensusWorkbookError,
    find_workbook_table,
)
from lisbon_spatial_dynamics.transformations.population import build_census_population_reference

# These are the actual XLSX labels, deliberately independent of the reader's aliases.
HEADERS = [
    "FREGUESIA",
    "SUBSECCAO",
    "N_INDIVIDUOS",
    "N_EDIFICIOS_CLASSICOS",
    "N_EDIFICIOS_CONSTR_ANTES_1945",
    "N_EDIFICIOS_COM_NECESSIDADES_REPARACAO",
    "N_ALOJAMENTOS_TOTAL",
    "N_ALOJAMENTOS_FAMILIARES",
    "N_ALOJAMENTOS_FAM_CLASS_RHABITUAL",
    "N_ALOJAMENTOS_FAM_CLASS_VAGOS_OU_RESID_SECUNDARIA",
    "N_RHABITUAL_PROP_OCUP",
    "N_RHABITUAL_ARRENDADOS",
    "N_AGREGADOS_DOMESTICOS_PRIVADOS",
    "N_INDIVIDUOS_0_14",
    "N_INDIVIDUOS_15_24",
    "N_INDIVIDUOS_25_64",
    "N_INDIVIDUOS_65_OU_MAIS",
]
COUNTS = [100, 10, 2, 1, 30, 28, 20, 8, 10, 8, 40, 10, 10, 60, 20]


def _archive(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "FS_2021_SubSecção_Tot"
    sheet.append(["Resultados definitivos — síntese"])
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    payload = BytesIO()
    workbook.save(payload)
    workbook.close()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("FS 2021 SubSecção Tot.xlsx", payload.getvalue())


def test_population_and_context_exclude_all_hierarchy_totals(tmp_path: Path) -> None:
    archive = tmp_path / "census.zip"
    reference = tmp_path / "reference.csv"
    reference.write_text("freguesia_id,name,area_ha\n110654,Alvalade,100\n", encoding="utf-8")
    _archive(
        archive,
        HEADERS,
        [
            [None, None, *[value * 100 for value in COUNTS]],  # national aggregate
            ["110654", None, *[value * 2 for value in COUNTS]],  # parish aggregate
            ["110654", None, *[value * 2 for value in COUNTS]],  # section aggregate
            ["110654", "11065400101", *COUNTS],
            ["110654", "11065400102", *COUNTS],
            ["010101", "01010100101", *COUNTS],  # leading-zero ID outside Lisbon
            ["0302FA", "0302FA00101", *COUNTS],  # official alphanumeric parish ID
        ],
    )
    population = build_census_population_reference(archive, reference, expected_count=1)[0]
    context = build_census2021_context(archive, reference, expected_count=1)[0]
    assert population.population_resident == context.population_resident == 200
    assert population.population_density_per_km2 == 200
    assert context.classic_buildings == 20
    assert context.pre1945_buildings == 4
    assert context.repair_needed_buildings == 2
    assert context.usual_residence_dwellings == 40
    assert context.vacant_or_secondary_dwellings == 16
    assert context.private_households == 80
    assert (context.age_0_14, context.age_15_24, context.age_25_64, context.age_65_plus) == (
        20,
        20,
        120,
        40,
    )


@pytest.mark.parametrize("subsection", ["11065600101", "110654", "not-a-code"])
def test_inconsistent_subsection_identifiers_fail(tmp_path: Path, subsection: str) -> None:
    path = tmp_path / "bad.zip"
    _archive(path, HEADERS, [["110654", subsection, *COUNTS]])
    with zipfile.ZipFile(path) as archive:
        _, rows = find_workbook_table(archive, {"N_INDIVIDUOS"})
        with pytest.raises(CensusWorkbookError, match="inconsistent parish/subsection"):
            tuple(rows)


def test_duplicate_subsections_fail_instead_of_double_counting(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.zip"
    _archive(path, HEADERS, [["110654", "11065400101", *COUNTS]] * 2)
    with zipfile.ZipFile(path) as archive:
        _, rows = find_workbook_table(archive, {"N_INDIVIDUOS"})
        with pytest.raises(CensusWorkbookError, match="duplicate subsection"):
            tuple(rows)


def test_workbook_without_subsection_column_fails(tmp_path: Path) -> None:
    path = tmp_path / "aggregate.zip"
    _archive(path, ["FREGUESIA", "N_INDIVIDUOS"], [["110654", 100]])
    with (
        zipfile.ZipFile(path) as archive,
        pytest.raises(CensusWorkbookError, match="SUBSECCAO"),
    ):
        find_workbook_table(archive, {"N_INDIVIDUOS"})
