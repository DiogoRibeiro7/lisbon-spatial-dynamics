"""Enrich the annual housing-pressure panel with static Censos 2021 context."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from lisbon_spatial_dynamics.panels.annual_housing_pressure import (
    ANNUAL_HOUSING_PRESSURE_COLUMNS,
    AnnualHousingPressureRow,
)
from lisbon_spatial_dynamics.transformations.census_context import (
    CensusContextRow,
)


class AnnualContextError(ValueError):
    """Raised when annual research rows cannot be enriched with census context."""


@dataclass(frozen=True, slots=True)
class AnnualContextRow:
    """One annual research row plus static Censos 2021 context."""

    annual: AnnualHousingPressureRow
    census: CensusContextRow


CENSUS_ENRICHMENT_COLUMNS: tuple[str, ...] = (
    "census_context_year",
    "census_classic_buildings",
    "census_pre1945_buildings",
    "census_repair_needed_buildings",
    "census_total_dwellings",
    "census_family_dwellings",
    "census_usual_residence_dwellings",
    "census_vacant_or_secondary_dwellings",
    "census_owner_occupied_dwellings",
    "census_rented_dwellings",
    "census_private_households",
    "census_age_0_14",
    "census_age_15_24",
    "census_age_25_64",
    "census_age_65_plus",
    "census_age_0_14_pct",
    "census_age_15_24_pct",
    "census_age_25_64_pct",
    "census_age_65_plus_pct",
    "census_owner_occupied_share_pct",
    "census_rented_share_pct",
    "census_vacant_or_secondary_family_share_pct",
    "census_pre1945_building_share_pct",
    "census_repair_needed_building_share_pct",
    "census_dwellings_per_classic_building",
)

ANNUAL_CONTEXT_COLUMNS: tuple[str, ...] = (
    *ANNUAL_HOUSING_PRESSURE_COLUMNS,
    *CENSUS_ENRICHMENT_COLUMNS,
)


def build_annual_context_panel(
    annual_rows: Sequence[AnnualHousingPressureRow],
    context_rows: Sequence[CensusContextRow],
) -> tuple[AnnualContextRow, ...]:
    """Join static context to every annual row by canonical freguesia ID."""
    if not annual_rows:
        raise AnnualContextError("annual housing-pressure panel cannot be empty")
    if not context_rows:
        raise AnnualContextError("census context cannot be empty")

    context_by_id: dict[str, CensusContextRow] = {}
    for row in context_rows:
        if row.freguesia_id in context_by_id:
            raise AnnualContextError(f"duplicate census context freguesia_id: {row.freguesia_id}")
        context_by_id[row.freguesia_id] = row

    annual_ids = {row.freguesia_id for row in annual_rows}
    context_ids = set(context_by_id)

    if annual_ids != context_ids:
        missing = sorted(annual_ids - context_ids)
        extra = sorted(context_ids - annual_ids)
        raise AnnualContextError(
            f"annual/context key mismatch; missing_context={missing}, context_only={extra}"
        )

    output: list[AnnualContextRow] = []

    for annual in sorted(
        annual_rows,
        key=lambda row: (row.year, row.freguesia_id),
    ):
        census = context_by_id[annual.freguesia_id]

        if annual.freguesia_name != census.freguesia_name:
            raise AnnualContextError(
                f"{annual.freguesia_id} name mismatch: "
                f"{annual.freguesia_name!r} != {census.freguesia_name!r}"
            )
        if annual.population_reference_year != census.census_year:
            raise AnnualContextError(
                f"{annual.freguesia_id} census year mismatch: "
                f"{annual.population_reference_year} != {census.census_year}"
            )
        if annual.population_resident != census.population_resident:
            raise AnnualContextError(
                f"{annual.freguesia_id} population mismatch: "
                f"{annual.population_resident} != {census.population_resident}"
            )

        output.append(AnnualContextRow(annual=annual, census=census))

    return tuple(output)


def write_annual_context_csv(
    rows: Sequence[AnnualContextRow],
    path: Path,
) -> None:
    """Write the enriched annual research panel without overwriting."""
    if not rows:
        raise AnnualContextError("annual context panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(ANNUAL_CONTEXT_COLUMNS)

        for row in rows:
            annual_values = tuple(
                _serialize(getattr(row.annual, column))
                for column in ANNUAL_HOUSING_PRESSURE_COLUMNS
            )
            writer.writerow(
                (
                    *annual_values,
                    row.census.census_year,
                    row.census.classic_buildings,
                    row.census.pre1945_buildings,
                    row.census.repair_needed_buildings,
                    row.census.total_dwellings,
                    row.census.family_dwellings,
                    row.census.usual_residence_dwellings,
                    row.census.vacant_or_secondary_dwellings,
                    row.census.owner_occupied_dwellings,
                    row.census.rented_dwellings,
                    row.census.private_households,
                    row.census.age_0_14,
                    row.census.age_15_24,
                    row.census.age_25_64,
                    row.census.age_65_plus,
                    _serialize(row.census.age_0_14_pct),
                    _serialize(row.census.age_15_24_pct),
                    _serialize(row.census.age_25_64_pct),
                    _serialize(row.census.age_65_plus_pct),
                    _serialize(row.census.owner_occupied_share_pct),
                    _serialize(row.census.rented_share_pct),
                    _serialize(row.census.vacant_or_secondary_family_share_pct),
                    _serialize(row.census.pre1945_building_share_pct),
                    _serialize(row.census.repair_needed_building_share_pct),
                    _serialize(row.census.dwellings_per_classic_building),
                )
            )


def _serialize(value: object) -> object:
    """Serialize typed annual/context values to stable CSV primitives."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return value
