"""Population-normalized RNAL pressure metrics."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from lisbon_spatial_dynamics.panels.rnal import RNALQuarterRow


class RNALPressureError(ValueError):
    """Raised when RNAL rows cannot be normalized to the census reference."""


@dataclass(frozen=True, slots=True)
class PopulationReferenceRow:
    """Static population denominator for one canonical freguesia."""

    freguesia_id: str
    freguesia_name: str
    census_year: int
    population_resident: int
    population_density_per_km2: Decimal


@dataclass(frozen=True, slots=True)
class RNALPressureRow:
    """One RNAL freguesia-quarter row normalized to a static census denominator."""

    period_code: str
    year: int
    quarter: int
    period_end: str
    freguesia_id: str
    freguesia_name: str
    population_reference_year: int
    population_resident: int
    population_density_per_km2: Decimal
    registrations: int
    cessations: int
    net_registrations: int
    active_registrations: int
    active_beds_known: int
    active_beds_missing: int
    active_users_known: int
    active_users_missing: int
    registrations_per_1000: Decimal
    cessations_per_1000: Decimal
    net_registrations_per_1000: Decimal
    active_registrations_per_1000: Decimal
    active_beds_known_per_1000: Decimal
    active_users_known_per_1000: Decimal


RNAL_PRESSURE_COLUMNS: tuple[str, ...] = (
    "period_code",
    "year",
    "quarter",
    "period_end",
    "freguesia_id",
    "freguesia_name",
    "population_reference_year",
    "population_resident",
    "population_density_per_km2",
    "registrations",
    "cessations",
    "net_registrations",
    "active_registrations",
    "active_beds_known",
    "active_beds_missing",
    "active_users_known",
    "active_users_missing",
    "registrations_per_1000",
    "cessations_per_1000",
    "net_registrations_per_1000",
    "active_registrations_per_1000",
    "active_beds_known_per_1000",
    "active_users_known_per_1000",
)


def load_population_reference(
    path: Path,
    *,
    expected_census_year: int = 2021,
) -> tuple[PopulationReferenceRow, ...]:
    """Load the static canonical population reference CSV."""
    rows: list[PopulationReferenceRow] = []
    seen_ids: set[str] = set()

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "freguesia_id",
            "freguesia_name",
            "census_year",
            "population_resident",
            "population_density_per_km2",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RNALPressureError(
                "population reference is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row_index, raw in enumerate(reader, start=2):
            freguesia_id = _required_text(
                raw.get("freguesia_id"),
                f"row {row_index}.freguesia_id",
            )
            if freguesia_id in seen_ids:
                raise RNALPressureError(
                    f"duplicate population freguesia_id: {freguesia_id}"
                )
            seen_ids.add(freguesia_id)

            census_year = _required_int(
                raw.get("census_year"),
                f"row {row_index}.census_year",
            )
            if census_year != expected_census_year:
                raise RNALPressureError(
                    f"unexpected census year for {freguesia_id}: "
                    f"{census_year} != {expected_census_year}"
                )

            population = _required_positive_int(
                raw.get("population_resident"),
                f"row {row_index}.population_resident",
            )
            density = _required_positive_decimal(
                raw.get("population_density_per_km2"),
                f"row {row_index}.population_density_per_km2",
            )

            rows.append(
                PopulationReferenceRow(
                    freguesia_id=freguesia_id,
                    freguesia_name=_required_text(
                        raw.get("freguesia_name"),
                        f"row {row_index}.freguesia_name",
                    ),
                    census_year=census_year,
                    population_resident=population,
                    population_density_per_km2=density,
                )
            )

    if not rows:
        raise RNALPressureError("population reference cannot be empty")

    return tuple(sorted(rows, key=lambda row: row.freguesia_id))


def build_rnal_population_pressure(
    rnal_rows: Sequence[RNALQuarterRow],
    population_rows: Sequence[PopulationReferenceRow],
) -> tuple[RNALPressureRow, ...]:
    """Normalize RNAL flows, stock, and known capacity per 1,000 residents.

    The same static census denominator is used for every quarter. This improves
    cross-freguesia comparability but does not model annual population change.
    """
    if not rnal_rows:
        raise RNALPressureError("RNAL quarter panel cannot be empty")
    if not population_rows:
        raise RNALPressureError("population reference cannot be empty")

    population_by_id = _population_mapping(population_rows)
    population_ids = set(population_by_id)

    rnal_ids = {row.freguesia_id for row in rnal_rows}
    if rnal_ids != population_ids:
        missing = sorted(rnal_ids - population_ids)
        extra = sorted(population_ids - rnal_ids)
        raise RNALPressureError(
            f"RNAL/population key mismatch; missing_population={missing}, "
            f"population_only={extra}"
        )

    seen_keys: set[tuple[int, int, str]] = set()
    output: list[RNALPressureRow] = []

    for row in sorted(
        rnal_rows,
        key=lambda item: (item.year, item.quarter, item.freguesia_id),
    ):
        key = (row.year, row.quarter, row.freguesia_id)
        if key in seen_keys:
            raise RNALPressureError(f"duplicate RNAL quarter key: {key}")
        seen_keys.add(key)

        population = population_by_id[row.freguesia_id]
        if row.freguesia_name != population.freguesia_name:
            raise RNALPressureError(
                f"name mismatch for {row.freguesia_id}: "
                f"{row.freguesia_name!r} != {population.freguesia_name!r}"
            )

        denominator = Decimal(population.population_resident)

        output.append(
            RNALPressureRow(
                period_code=row.period_code,
                year=row.year,
                quarter=row.quarter,
                period_end=row.period_end.isoformat(),
                freguesia_id=row.freguesia_id,
                freguesia_name=row.freguesia_name,
                population_reference_year=population.census_year,
                population_resident=population.population_resident,
                population_density_per_km2=population.population_density_per_km2,
                registrations=row.registrations,
                cessations=row.cessations,
                net_registrations=row.net_registrations,
                active_registrations=row.active_registrations,
                active_beds_known=row.active_beds_known,
                active_beds_missing=row.active_beds_missing,
                active_users_known=row.active_users_known,
                active_users_missing=row.active_users_missing,
                registrations_per_1000=_per_1000(row.registrations, denominator),
                cessations_per_1000=_per_1000(row.cessations, denominator),
                net_registrations_per_1000=_per_1000(
                    row.net_registrations,
                    denominator,
                ),
                active_registrations_per_1000=_per_1000(
                    row.active_registrations,
                    denominator,
                ),
                active_beds_known_per_1000=_per_1000(
                    row.active_beds_known,
                    denominator,
                ),
                active_users_known_per_1000=_per_1000(
                    row.active_users_known,
                    denominator,
                ),
            )
        )

    return tuple(output)


def write_rnal_population_pressure_csv(
    rows: Sequence[RNALPressureRow],
    path: Path,
) -> None:
    """Write the population-normalized RNAL panel without overwriting."""
    if not rows:
        raise RNALPressureError("RNAL pressure panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(RNAL_PRESSURE_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.period_code,
                    row.year,
                    row.quarter,
                    row.period_end,
                    row.freguesia_id,
                    row.freguesia_name,
                    row.population_reference_year,
                    row.population_resident,
                    _decimal_text(row.population_density_per_km2),
                    row.registrations,
                    row.cessations,
                    row.net_registrations,
                    row.active_registrations,
                    row.active_beds_known,
                    row.active_beds_missing,
                    row.active_users_known,
                    row.active_users_missing,
                    _decimal_text(row.registrations_per_1000),
                    _decimal_text(row.cessations_per_1000),
                    _decimal_text(row.net_registrations_per_1000),
                    _decimal_text(row.active_registrations_per_1000),
                    _decimal_text(row.active_beds_known_per_1000),
                    _decimal_text(row.active_users_known_per_1000),
                )
            )


def _population_mapping(
    rows: Sequence[PopulationReferenceRow],
) -> dict[str, PopulationReferenceRow]:
    """Build a unique population-reference mapping."""
    mapping: dict[str, PopulationReferenceRow] = {}

    for row in rows:
        if row.freguesia_id in mapping:
            raise RNALPressureError(
                f"duplicate population freguesia_id: {row.freguesia_id}"
            )
        if row.population_resident <= 0:
            raise RNALPressureError(
                f"{row.freguesia_id} has non-positive population"
            )
        mapping[row.freguesia_id] = row

    return mapping


def _per_1000(count: int, population: Decimal) -> Decimal:
    """Return count per 1,000 residents."""
    return Decimal(count) * Decimal("1000") / population


def _required_text(value: str | None, context: str) -> str:
    """Return a required non-empty text field."""
    if value is None or not value.strip():
        raise RNALPressureError(f"{context} must be non-empty")
    return value.strip()


def _required_int(value: str | None, context: str) -> int:
    """Parse a required integer."""
    raw = _required_text(value, context)
    try:
        return int(raw)
    except ValueError as exc:
        raise RNALPressureError(f"{context} must be an integer") from exc


def _required_positive_int(value: str | None, context: str) -> int:
    """Parse a required positive integer."""
    number = _required_int(value, context)
    if number <= 0:
        raise RNALPressureError(f"{context} must be positive")
    return number


def _required_positive_decimal(
    value: str | None,
    context: str,
) -> Decimal:
    """Parse a required positive Decimal."""
    raw = _required_text(value, context)
    try:
        number = Decimal(raw)
    except Exception as exc:
        raise RNALPressureError(f"{context} must be numeric") from exc

    if number <= 0:
        raise RNALPressureError(f"{context} must be positive")
    return number


def _decimal_text(value: Decimal) -> str:
    """Serialize Decimal values without scientific notation."""
    return format(value, "f")
