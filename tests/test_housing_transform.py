"""Tests for the stable INE housing transformation contract."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.sources.ine import INEIndicatorConfig
from lisbon_spatial_dynamics.transformations.housing import (
    HOUSING_COLUMNS,
    HousingTransformError,
    parse_ine_housing_payload,
    select_housing_observations,
    write_housing_csv,
)

_SAMPLE = b"""[
  {
    "IndicadorCod": "0011364",
    "Dados": {
      "period-a": [
        {
          "geocod": "1701106",
          "geodsg": "Lisboa",
          "dim_3": "T",
          "dim_3_t": "Total",
          "valor": "4250"
        },
        {
          "geocod": "1701105",
          "geodsg": "Cascais",
          "dim_3": "T",
          "dim_3_t": "Total",
          "valor": "3900"
        }
      ],
      "period-b": [
        {
          "geocod": "1701106",
          "geodsg": "Lisboa",
          "dim_3": "T",
          "dim_3_t": "Total"
        }
      ]
    }
  }
]"""


def test_parse_preserves_source_periods_and_missing_values() -> None:
    """The parser should flatten records without inventing missing values."""
    observations = parse_ine_housing_payload(_SAMPLE)

    assert len(observations) == 3
    assert observations[0].period_code == "period-a"
    assert observations[0].geography_code == "1701106"
    assert observations[0].value_eur_m2 == Decimal("4250")
    assert observations[2].period_code == "period-b"
    assert observations[2].value_eur_m2 is None


def test_select_lisbon_total_is_explicit() -> None:
    """Lisbon extraction should use labels rather than code-prefix guesses."""
    selected = select_housing_observations(
        parse_ine_housing_payload(_SAMPLE),
        geography_name=" lisboa ",
        category_name="TOTAL",
    )

    assert len(selected) == 2
    assert {row.geography_name for row in selected} == {"Lisboa"}


def test_write_csv_uses_stable_contract(tmp_path: Path) -> None:
    """CSV columns should remain stable and missing values should stay empty."""
    selected = select_housing_observations(
        parse_ine_housing_payload(_SAMPLE),
        geography_name="Lisboa",
    )
    path = tmp_path / "lisbon.csv"

    write_housing_csv(selected, path)

    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert tuple(rows[0]) == HOUSING_COLUMNS
    assert rows[0]["value_eur_m2"] == "4250"
    assert rows[1]["value_eur_m2"] == ""


def test_write_csv_does_not_overwrite(tmp_path: Path) -> None:
    """Processed artifacts should not be replaced implicitly."""
    path = tmp_path / "lisbon.csv"
    observations = parse_ine_housing_payload(_SAMPLE)

    write_housing_csv(observations, path)

    with pytest.raises(FileExistsError):
        write_housing_csv(observations, path)


def test_non_numeric_value_fails() -> None:
    """Unexpected source values should be surfaced rather than coerced."""
    payload = _SAMPLE.replace(b'"4250"', b'"not-a-number"')

    with pytest.raises(HousingTransformError, match="not numeric"):
        parse_ine_housing_payload(payload)


def test_current_nuts2024_config_loads() -> None:
    """The NUTS 2024 successor series should have a valid source config."""
    path = Path(__file__).parents[1] / "configs" / "ine_housing_current.toml"
    config = INEIndicatorConfig.from_toml(path)

    assert config.indicator_code == "0012234"
    assert config.output_directory == Path("data/raw/ine/housing/0012234")
