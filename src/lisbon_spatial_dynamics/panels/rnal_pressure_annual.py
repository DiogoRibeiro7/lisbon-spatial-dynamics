"""Annual population-normalized RNAL pressure panel."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lisbon_spatial_dynamics.panels.rnal_pressure import RNALPressureRow


class AnnualRNALPressureError(ValueError):
    """Raised when quarterly RNAL pressure cannot form a valid annual panel."""


@dataclass(frozen=True, slots=True)
class AnnualRNALPressureRow:
    """One Q4-anchored annual RNAL pressure observation."""

    year: int
    baseline_year: int
    period_code: str
    period_end: date
    freguesia_id: str
    freguesia_name: str
    population_reference_year: int
    population_resident: int
    population_density_per_km2: Decimal
    flow_quarters_observed: int
    registrations_year: int | None
    cessations_year: int | None
    net_registrations_year: int | None
    registrations_year_per_1000: Decimal | None
    cessations_year_per_1000: Decimal | None
    net_registrations_year_per_1000: Decimal | None
    active_registrations_year_end: int
    active_registrations_per_1000_year_end: Decimal
    active_registrations_per_1000_change_from_baseline: Decimal
    active_beds_known_year_end: int
    active_beds_missing_year_end: int
    active_beds_known_per_1000_year_end: Decimal
    active_beds_known_per_1000_change_from_baseline: Decimal
    active_users_known_year_end: int
    active_users_missing_year_end: int
    active_users_known_per_1000_year_end: Decimal
    active_users_known_per_1000_change_from_baseline: Decimal


ANNUAL_RNAL_PRESSURE_COLUMNS: tuple[str, ...] = (
    "year",
    "baseline_year",
    "period_code",
    "period_end",
    "freguesia_id",
    "freguesia_name",
    "population_reference_year",
    "population_resident",
    "population_density_per_km2",
    "flow_quarters_observed",
    "registrations_year",
    "cessations_year",
    "net_registrations_year",
    "registrations_year_per_1000",
    "cessations_year_per_1000",
    "net_registrations_year_per_1000",
    "active_registrations_year_end",
    "active_registrations_per_1000_year_end",
    "active_registrations_per_1000_change_from_baseline",
    "active_beds_known_year_end",
    "active_beds_missing_year_end",
    "active_beds_known_per_1000_year_end",
    "active_beds_known_per_1000_change_from_baseline",
    "active_users_known_year_end",
    "active_users_missing_year_end",
    "active_users_known_per_1000_year_end",
    "active_users_known_per_1000_change_from_baseline",
)


def load_rnal_population_pressure_csv(
    path: Path,
) -> tuple[RNALPressureRow, ...]:
    """Load the stable quarterly RNAL population-pressure CSV."""
    rows: list[RNALPressureRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
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
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise AnnualRNALPressureError(
                "RNAL pressure CSV is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row_index, raw in enumerate(reader, start=2):
            period_end = _required_text(
                raw.get("period_end"),
                f"row {row_index}.period_end",
            )
            _parse_iso_date(period_end, f"row {row_index}.period_end")

            rows.append(
                RNALPressureRow(
                    period_code=_required_text(
                        raw.get("period_code"),
                        f"row {row_index}.period_code",
                    ),
                    year=_required_int(
                        raw.get("year"),
                        f"row {row_index}.year",
                    ),
                    quarter=_required_int(
                        raw.get("quarter"),
                        f"row {row_index}.quarter",
                    ),
                    period_end=period_end,
                    freguesia_id=_required_text(
                        raw.get("freguesia_id"),
                        f"row {row_index}.freguesia_id",
                    ),
                    freguesia_name=_required_text(
                        raw.get("freguesia_name"),
                        f"row {row_index}.freguesia_name",
                    ),
                    population_reference_year=_required_int(
                        raw.get("population_reference_year"),
                        f"row {row_index}.population_reference_year",
                    ),
                    population_resident=_required_positive_int(
                        raw.get("population_resident"),
                        f"row {row_index}.population_resident",
                    ),
                    population_density_per_km2=_required_positive_decimal(
                        raw.get("population_density_per_km2"),
                        f"row {row_index}.population_density_per_km2",
                    ),
                    registrations=_required_int(
                        raw.get("registrations"),
                        f"row {row_index}.registrations",
                    ),
                    cessations=_required_int(
                        raw.get("cessations"),
                        f"row {row_index}.cessations",
                    ),
                    net_registrations=_required_int(
                        raw.get("net_registrations"),
                        f"row {row_index}.net_registrations",
                    ),
                    active_registrations=_required_non_negative_int(
                        raw.get("active_registrations"),
                        f"row {row_index}.active_registrations",
                    ),
                    active_beds_known=_required_non_negative_int(
                        raw.get("active_beds_known"),
                        f"row {row_index}.active_beds_known",
                    ),
                    active_beds_missing=_required_non_negative_int(
                        raw.get("active_beds_missing"),
                        f"row {row_index}.active_beds_missing",
                    ),
                    active_users_known=_required_non_negative_int(
                        raw.get("active_users_known"),
                        f"row {row_index}.active_users_known",
                    ),
                    active_users_missing=_required_non_negative_int(
                        raw.get("active_users_missing"),
                        f"row {row_index}.active_users_missing",
                    ),
                    registrations_per_1000=_required_decimal(
                        raw.get("registrations_per_1000"),
                        f"row {row_index}.registrations_per_1000",
                    ),
                    cessations_per_1000=_required_decimal(
                        raw.get("cessations_per_1000"),
                        f"row {row_index}.cessations_per_1000",
                    ),
                    net_registrations_per_1000=_required_decimal(
                        raw.get("net_registrations_per_1000"),
                        f"row {row_index}.net_registrations_per_1000",
                    ),
                    active_registrations_per_1000=_required_decimal(
                        raw.get("active_registrations_per_1000"),
                        f"row {row_index}.active_registrations_per_1000",
                    ),
                    active_beds_known_per_1000=_required_decimal(
                        raw.get("active_beds_known_per_1000"),
                        f"row {row_index}.active_beds_known_per_1000",
                    ),
                    active_users_known_per_1000=_required_decimal(
                        raw.get("active_users_known_per_1000"),
                        f"row {row_index}.active_users_known_per_1000",
                    ),
                )
            )

    if not rows:
        raise AnnualRNALPressureError("RNAL pressure CSV cannot be empty")

    return tuple(rows)


def build_annual_rnal_pressure(
    rows: Sequence[RNALPressureRow],
) -> tuple[AnnualRNALPressureRow, ...]:
    """Build Q4 pressure levels and complete-year pressure flows.

    Years without Q4 are excluded. Annual registrations, cessations, and net
    flows are reported only when all four quarters are observed. The static
    population denominator is required to remain constant for each freguesia.
    """
    if not rows:
        raise AnnualRNALPressureError("RNAL pressure panel cannot be empty")

    grouped: dict[tuple[str, int], dict[int, RNALPressureRow]] = {}
    reference_by_id: dict[str, tuple[str, int, int, Decimal]] = {}

    for row in rows:
        if row.quarter not in {1, 2, 3, 4}:
            raise AnnualRNALPressureError(
                f"invalid quarter for {row.freguesia_id}/{row.year}: {row.quarter}"
            )

        reference = (
            row.freguesia_name,
            row.population_reference_year,
            row.population_resident,
            row.population_density_per_km2,
        )
        previous_reference = reference_by_id.get(row.freguesia_id)
        if previous_reference is not None and previous_reference != reference:
            raise AnnualRNALPressureError(
                f"population reference changes within {row.freguesia_id}"
            )
        reference_by_id[row.freguesia_id] = reference

        key = (row.freguesia_id, row.year)
        quarters = grouped.setdefault(key, {})
        if row.quarter in quarters:
            raise AnnualRNALPressureError(
                f"duplicate quarter for {row.freguesia_id}/{row.year}: Q{row.quarter}"
            )
        quarters[row.quarter] = row

    q4_by_freguesia: dict[str, list[tuple[int, dict[int, RNALPressureRow]]]] = {}
    for (freguesia_id, year), quarters in grouped.items():
        if 4 in quarters:
            q4_by_freguesia.setdefault(freguesia_id, []).append((year, quarters))

    if not q4_by_freguesia:
        raise AnnualRNALPressureError("RNAL pressure panel contains no Q4 rows")

    output: list[AnnualRNALPressureRow] = []

    for freguesia_id in sorted(q4_by_freguesia):
        years = sorted(q4_by_freguesia[freguesia_id], key=lambda item: item[0])
        baseline_year, baseline_quarters = years[0]
        baseline_q4 = baseline_quarters[4]

        for year, quarters in years:
            q4 = quarters[4]
            observed = set(quarters)
            full_year = observed == {1, 2, 3, 4}
            denominator = Decimal(q4.population_resident)

            registrations_year = (
                sum(row.registrations for row in quarters.values())
                if full_year
                else None
            )
            cessations_year = (
                sum(row.cessations for row in quarters.values())
                if full_year
                else None
            )
            net_year = (
                sum(row.net_registrations for row in quarters.values())
                if full_year
                else None
            )

            output.append(
                AnnualRNALPressureRow(
                    year=year,
                    baseline_year=baseline_year,
                    period_code=q4.period_code,
                    period_end=_parse_iso_date(
                        q4.period_end,
                        f"{freguesia_id}/{year}.period_end",
                    ),
                    freguesia_id=freguesia_id,
                    freguesia_name=q4.freguesia_name,
                    population_reference_year=q4.population_reference_year,
                    population_resident=q4.population_resident,
                    population_density_per_km2=q4.population_density_per_km2,
                    flow_quarters_observed=len(observed),
                    registrations_year=registrations_year,
                    cessations_year=cessations_year,
                    net_registrations_year=net_year,
                    registrations_year_per_1000=_optional_rate(
                        registrations_year,
                        denominator,
                    ),
                    cessations_year_per_1000=_optional_rate(
                        cessations_year,
                        denominator,
                    ),
                    net_registrations_year_per_1000=_optional_rate(
                        net_year,
                        denominator,
                    ),
                    active_registrations_year_end=q4.active_registrations,
                    active_registrations_per_1000_year_end=(
                        q4.active_registrations_per_1000
                    ),
                    active_registrations_per_1000_change_from_baseline=(
                        q4.active_registrations_per_1000
                        - baseline_q4.active_registrations_per_1000
                    ),
                    active_beds_known_year_end=q4.active_beds_known,
                    active_beds_missing_year_end=q4.active_beds_missing,
                    active_beds_known_per_1000_year_end=(
                        q4.active_beds_known_per_1000
                    ),
                    active_beds_known_per_1000_change_from_baseline=(
                        q4.active_beds_known_per_1000
                        - baseline_q4.active_beds_known_per_1000
                    ),
                    active_users_known_year_end=q4.active_users_known,
                    active_users_missing_year_end=q4.active_users_missing,
                    active_users_known_per_1000_year_end=(
                        q4.active_users_known_per_1000
                    ),
                    active_users_known_per_1000_change_from_baseline=(
                        q4.active_users_known_per_1000
                        - baseline_q4.active_users_known_per_1000
                    ),
                )
            )

    return tuple(sorted(output, key=lambda row: (row.year, row.freguesia_id)))


def write_annual_rnal_pressure_csv(
    rows: Sequence[AnnualRNALPressureRow],
    path: Path,
) -> None:
    """Write the annual pressure panel without overwriting."""
    if not rows:
        raise AnnualRNALPressureError("annual RNAL pressure panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(ANNUAL_RNAL_PRESSURE_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.year,
                    row.baseline_year,
                    row.period_code,
                    row.period_end.isoformat(),
                    row.freguesia_id,
                    row.freguesia_name,
                    row.population_reference_year,
                    row.population_resident,
                    _decimal_text(row.population_density_per_km2),
                    row.flow_quarters_observed,
                    _optional_int_text(row.registrations_year),
                    _optional_int_text(row.cessations_year),
                    _optional_int_text(row.net_registrations_year),
                    _optional_decimal_text(row.registrations_year_per_1000),
                    _optional_decimal_text(row.cessations_year_per_1000),
                    _optional_decimal_text(row.net_registrations_year_per_1000),
                    row.active_registrations_year_end,
                    _decimal_text(row.active_registrations_per_1000_year_end),
                    _decimal_text(
                        row.active_registrations_per_1000_change_from_baseline
                    ),
                    row.active_beds_known_year_end,
                    row.active_beds_missing_year_end,
                    _decimal_text(row.active_beds_known_per_1000_year_end),
                    _decimal_text(
                        row.active_beds_known_per_1000_change_from_baseline
                    ),
                    row.active_users_known_year_end,
                    row.active_users_missing_year_end,
                    _decimal_text(row.active_users_known_per_1000_year_end),
                    _decimal_text(
                        row.active_users_known_per_1000_change_from_baseline
                    ),
                )
            )


def _optional_rate(
    count: int | None,
    population: Decimal,
) -> Decimal | None:
    """Return a per-1,000 rate when the annual count is complete."""
    if count is None:
        return None
    return Decimal(count) * Decimal("1000") / population


def _required_text(value: str | None, context: str) -> str:
    """Return a required non-empty CSV value."""
    if value is None or not value.strip():
        raise AnnualRNALPressureError(f"{context} must be non-empty")
    return value.strip()


def _required_int(value: str | None, context: str) -> int:
    """Parse a required integer."""
    raw = _required_text(value, context)
    try:
        return int(raw)
    except ValueError as exc:
        raise AnnualRNALPressureError(f"{context} must be an integer") from exc


def _required_non_negative_int(
    value: str | None,
    context: str,
) -> int:
    """Parse a required non-negative integer."""
    number = _required_int(value, context)
    if number < 0:
        raise AnnualRNALPressureError(f"{context} must be non-negative")
    return number


def _required_positive_int(value: str | None, context: str) -> int:
    """Parse a required positive integer."""
    number = _required_int(value, context)
    if number <= 0:
        raise AnnualRNALPressureError(f"{context} must be positive")
    return number


def _required_decimal(value: str | None, context: str) -> Decimal:
    """Parse a required Decimal."""
    raw = _required_text(value, context)
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise AnnualRNALPressureError(f"{context} must be numeric") from exc


def _required_positive_decimal(
    value: str | None,
    context: str,
) -> Decimal:
    """Parse a required positive Decimal."""
    number = _required_decimal(value, context)
    if number <= 0:
        raise AnnualRNALPressureError(f"{context} must be positive")
    return number


def _parse_iso_date(value: str, context: str) -> date:
    """Parse a required ISO date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AnnualRNALPressureError(f"{context} must be an ISO date") from exc


def _decimal_text(value: Decimal) -> str:
    """Serialize Decimal without scientific notation."""
    return format(value, "f")


def _optional_decimal_text(value: Decimal | None) -> str:
    """Serialize an optional Decimal."""
    return "" if value is None else _decimal_text(value)


def _optional_int_text(value: int | None) -> str:
    """Serialize an optional integer."""
    return "" if value is None else str(value)
