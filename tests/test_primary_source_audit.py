"""Coverage gates in the primary-source audit must reject incomplete evidence."""

from __future__ import annotations

import importlib.util
import zipfile
from io import BytesIO
from pathlib import Path
from types import ModuleType

import pytest
from openpyxl import Workbook

from lisbon_spatial_dynamics.panels.housing import HousingPanelRow

FIRST = "4.º Trimestre de 2019"
LAST = "1.º Trimestre de 2026"


@pytest.fixture(scope="module")
def audit_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/audit_primary_sources.py"
    spec = importlib.util.spec_from_file_location("primary_source_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _housing() -> list[HousingPanelRow]:
    rows = []
    for ordinal in range(2019 * 4 + 3, 2026 * 4 + 1):
        year, quarter = divmod(ordinal, 4)
        for parish in range(24):
            rows.append(
                HousingPanelRow(
                    f"{quarter + 1}.º Trimestre de {year}",
                    f"1106{parish:02d}",
                    f"Parish {parish}",
                    "0012234",
                    f"1A01106{parish:02d}",
                    f"Parish {parish}",
                    "H1",
                    "Total",
                    None,
                )
            )
    return rows


def test_complete_housing_window_is_accepted(audit_module: ModuleType) -> None:
    periods = audit_module.validate_housing_window(_housing(), FIRST, LAST, 624)
    assert len(periods) == 26
    assert (periods[0].year, periods[0].quarter) == (2019, 4)
    assert (periods[-1].year, periods[-1].quarter) == (2026, 1)


@pytest.mark.parametrize("omission", ["latest_only", "first", "last", "middle", "one_row"])
def test_truncated_housing_windows_fail(audit_module: ModuleType, omission: str) -> None:
    rows = _housing()
    if omission == "latest_only":
        rows = rows[-24:]
    elif omission == "first":
        rows = rows[24:]
    elif omission == "last":
        rows = rows[:-24]
    elif omission == "middle":
        del rows[120:144]
    else:
        rows.pop()
    with pytest.raises(ValueError, match="housing coverage does not match"):
        audit_module.validate_housing_window(rows, FIRST, LAST, 624)


def test_extra_housing_quarter_fails(audit_module: ModuleType) -> None:
    rows = _housing()
    rows.append(
        HousingPanelRow(
            "2.º Trimestre de 2026",
            "110654",
            "Alvalade",
            "0012234",
            "1A0110654",
            "Alvalade",
            "H1",
            "Total",
            None,
        )
    )
    with pytest.raises(ValueError, match="housing coverage does not match"):
        audit_module.validate_housing_window(rows, FIRST, LAST, 624)


def test_census_comparison_uses_published_municipality_total(
    tmp_path: Path,
    audit_module: ModuleType,
) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["MUNICIPIO", "FREGUESIA", "SECCAO", "SUBSECCAO", "N_INDIVIDUOS"])
    sheet.append(["1106", None, None, None, 200])
    sheet.append(["1106", "110654", None, None, 200])
    sheet.append(["1106", "110654", "110654001", "11065400101", 200])
    payload = BytesIO()
    workbook.save(payload)
    workbook.close()
    path = tmp_path / "census.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("synthesis.xlsx", payload.getvalue())
    check = audit_module.validate_census_total(path, "1106", 200)
    assert check == {
        "municipality_id": "1106",
        "reported_population": 200,
        "parish_population_sum": 200,
        "difference": 0,
        "passed": True,
    }
    with pytest.raises(ValueError, match="municipality population mismatch: 199 != 200"):
        audit_module.validate_census_total(path, "1106", 199)
