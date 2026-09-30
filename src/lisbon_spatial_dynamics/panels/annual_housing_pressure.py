"""Join annual housing dynamics with population-normalized RNAL pressure."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lisbon_spatial_dynamics.panels.annual import AnnualUrbanRow
from lisbon_spatial_dynamics.panels.rnal_pressure_annual import (
    AnnualRNALPressureRow,
)


class AnnualHousingPressureError(ValueError):
    """Raised when annual housing and RNAL-pressure panels cannot be joined safely."""


@dataclass(frozen=True, slots=True)
class AnnualHousingPressureRow:
    """One annual freguesia observation combining housing and RNAL pressure."""

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
    housing_value_eur_m2: Decimal | None
    housing_yoy_abs_eur_m2: Decimal | None
    housing_yoy_pct: Decimal | None
    housing_change_from_baseline_abs_eur_m2: Decimal | None
    housing_change_from_baseline_pct: Decimal | None
    rnal_registrations_year: int | None
    rnal_cessations_year: int | None
    rnal_net_registrations_year: int | None
    rnal_registrations_year_per_1000: Decimal | None
    rnal_cessations_year_per_1000: Decimal | None
    rnal_net_registrations_year_per_1000: Decimal | None
    rnal_active_registrations_year_end: int
    rnal_active_registrations_per_1000_year_end: Decimal
    rnal_active_registrations_per_1000_change_from_baseline: Decimal
    rnal_active_beds_known_year_end: int
    rnal_active_beds_missing_year_end: int
    rnal_active_beds_known_per_1000_year_end: Decimal
    rnal_active_beds_known_per_1000_change_from_baseline: Decimal
    rnal_active_users_known_year_end: int
    rnal_active_users_missing_year_end: int
    rnal_active_users_known_per_1000_year_end: Decimal
    rnal_active_users_known_per_1000_change_from_baseline: Decimal


ANNUAL_HOUSING_PRESSURE_COLUMNS: tuple[str, ...] = (
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
    "housing_value_eur_m2",
    "housing_yoy_abs_eur_m2",
    "housing_yoy_pct",
    "housing_change_from_baseline_abs_eur_m2",
    "housing_change_from_baseline_pct",
    "rnal_registrations_year",
    "rnal_cessations_year",
    "rnal_net_registrations_year",
    "rnal_registrations_year_per_1000",
    "rnal_cessations_year_per_1000",
    "rnal_net_registrations_year_per_1000",
    "rnal_active_registrations_year_end",
    "rnal_active_registrations_per_1000_year_end",
    "rnal_active_registrations_per_1000_change_from_baseline",
    "rnal_active_beds_known_year_end",
    "rnal_active_beds_missing_year_end",
    "rnal_active_beds_known_per_1000_year_end",
    "rnal_active_beds_known_per_1000_change_from_baseline",
    "rnal_active_users_known_year_end",
    "rnal_active_users_missing_year_end",
    "rnal_active_users_known_per_1000_year_end",
    "rnal_active_users_known_per_1000_change_from_baseline",
)


def load_annual_rnal_pressure_csv(
    path: Path,
) -> tuple[AnnualRNALPressureRow, ...]:
    """Load the stable annual RNAL-pressure CSV contract."""
    rows: list[AnnualRNALPressureRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = set(ANNUAL_RNAL_PRESSURE_REQUIRED_COLUMNS)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise AnnualHousingPressureError(
                "annual RNAL pressure CSV is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row_index, raw in enumerate(reader, start=2):
            rows.append(
                AnnualRNALPressureRow(
                    year=_required_int(raw.get("year"), row_index, "year"),
                    baseline_year=_required_int(
                        raw.get("baseline_year"), row_index, "baseline_year"
                    ),
                    period_code=_required(
                        raw.get("period_code"), row_index, "period_code"
                    ),
                    period_end=_required_date(
                        raw.get("period_end"), row_index, "period_end"
                    ),
                    freguesia_id=_required(
                        raw.get("freguesia_id"), row_index, "freguesia_id"
                    ),
                    freguesia_name=_required(
                        raw.get("freguesia_name"), row_index, "freguesia_name"
                    ),
                    population_reference_year=_required_int(
                        raw.get("population_reference_year"),
                        row_index,
                        "population_reference_year",
                    ),
                    population_resident=_required_positive_int(
                        raw.get("population_resident"),
                        row_index,
                        "population_resident",
                    ),
                    population_density_per_km2=_required_positive_decimal(
                        raw.get("population_density_per_km2"),
                        row_index,
                        "population_density_per_km2",
                    ),
                    flow_quarters_observed=_required_int(
                        raw.get("flow_quarters_observed"),
                        row_index,
                        "flow_quarters_observed",
                    ),
                    registrations_year=_optional_int(
                        raw.get("registrations_year"),
                        row_index,
                        "registrations_year",
                    ),
                    cessations_year=_optional_int(
                        raw.get("cessations_year"),
                        row_index,
                        "cessations_year",
                    ),
                    net_registrations_year=_optional_int(
                        raw.get("net_registrations_year"),
                        row_index,
                        "net_registrations_year",
                    ),
                    registrations_year_per_1000=_optional_decimal(
                        raw.get("registrations_year_per_1000"),
                        row_index,
                        "registrations_year_per_1000",
                    ),
                    cessations_year_per_1000=_optional_decimal(
                        raw.get("cessations_year_per_1000"),
                        row_index,
                        "cessations_year_per_1000",
                    ),
                    net_registrations_year_per_1000=_optional_decimal(
                        raw.get("net_registrations_year_per_1000"),
                        row_index,
                        "net_registrations_year_per_1000",
                    ),
                    active_registrations_year_end=_required_non_negative_int(
                        raw.get("active_registrations_year_end"),
                        row_index,
                        "active_registrations_year_end",
                    ),
                    active_registrations_per_1000_year_end=_required_decimal(
                        raw.get("active_registrations_per_1000_year_end"),
                        row_index,
                        "active_registrations_per_1000_year_end",
                    ),
                    active_registrations_per_1000_change_from_baseline=_required_decimal(
                        raw.get(
                            "active_registrations_per_1000_change_from_baseline"
                        ),
                        row_index,
                        "active_registrations_per_1000_change_from_baseline",
                    ),
                    active_beds_known_year_end=_required_non_negative_int(
                        raw.get("active_beds_known_year_end"),
                        row_index,
                        "active_beds_known_year_end",
                    ),
                    active_beds_missing_year_end=_required_non_negative_int(
                        raw.get("active_beds_missing_year_end"),
                        row_index,
                        "active_beds_missing_year_end",
                    ),
                    active_beds_known_per_1000_year_end=_required_decimal(
                        raw.get("active_beds_known_per_1000_year_end"),
                        row_index,
                        "active_beds_known_per_1000_year_end",
                    ),
                    active_beds_known_per_1000_change_from_baseline=_required_decimal(
                        raw.get(
                            "active_beds_known_per_1000_change_from_baseline"
                        ),
                        row_index,
                        "active_beds_known_per_1000_change_from_baseline",
                    ),
                    active_users_known_year_end=_required_non_negative_int(
                        raw.get("active_users_known_year_end"),
                        row_index,
                        "active_users_known_year_end",
                    ),
                    active_users_missing_year_end=_required_non_negative_int(
                        raw.get("active_users_missing_year_end"),
                        row_index,
                        "active_users_missing_year_end",
                    ),
                    active_users_known_per_1000_year_end=_required_decimal(
                        raw.get("active_users_known_per_1000_year_end"),
                        row_index,
                        "active_users_known_per_1000_year_end",
                    ),
                    active_users_known_per_1000_change_from_baseline=_required_decimal(
                        raw.get(
                            "active_users_known_per_1000_change_from_baseline"
                        ),
                        row_index,
                        "active_users_known_per_1000_change_from_baseline",
                    ),
                )
            )

    if not rows:
        raise AnnualHousingPressureError(
            "annual RNAL pressure CSV cannot be empty"
        )

    return tuple(rows)


ANNUAL_RNAL_PRESSURE_REQUIRED_COLUMNS: tuple[str, ...] = (
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


def build_annual_housing_pressure_panel(
    housing_rows: Sequence[AnnualUrbanRow],
    pressure_rows: Sequence[AnnualRNALPressureRow],
) -> tuple[AnnualHousingPressureRow, ...]:
    """Join annual housing and RNAL-pressure panels exactly by freguesia-year."""
    if not housing_rows:
        raise AnnualHousingPressureError("annual housing panel cannot be empty")
    if not pressure_rows:
        raise AnnualHousingPressureError("annual RNAL pressure panel cannot be empty")

    housing_by_key = _unique_housing_mapping(housing_rows)
    pressure_by_key = _unique_pressure_mapping(pressure_rows)

    housing_keys = set(housing_by_key)
    pressure_keys = set(pressure_by_key)

    if housing_keys != pressure_keys:
        housing_only = sorted(housing_keys - pressure_keys)
        pressure_only = sorted(pressure_keys - housing_keys)
        raise AnnualHousingPressureError(
            "annual housing/pressure key sets differ; "
            f"housing_only={_preview_keys(housing_only)}, "
            f"pressure_only={_preview_keys(pressure_only)}"
        )

    output: list[AnnualHousingPressureRow] = []

    for key in sorted(housing_keys):
        housing = housing_by_key[key]
        pressure = pressure_by_key[key]

        _validate_shared_dimensions(housing, pressure)
        _validate_raw_rnal_consistency(housing, pressure)

        output.append(
            AnnualHousingPressureRow(
                year=housing.year,
                baseline_year=housing.baseline_year,
                period_code=housing.period_code,
                period_end=housing.period_end,
                freguesia_id=housing.freguesia_id,
                freguesia_name=housing.freguesia_name,
                population_reference_year=pressure.population_reference_year,
                population_resident=pressure.population_resident,
                population_density_per_km2=pressure.population_density_per_km2,
                flow_quarters_observed=housing.flow_quarters_observed,
                housing_value_eur_m2=housing.housing_value_eur_m2,
                housing_yoy_abs_eur_m2=housing.housing_yoy_abs_eur_m2,
                housing_yoy_pct=housing.housing_yoy_pct,
                housing_change_from_baseline_abs_eur_m2=(
                    housing.housing_change_from_baseline_abs_eur_m2
                ),
                housing_change_from_baseline_pct=(
                    housing.housing_change_from_baseline_pct
                ),
                rnal_registrations_year=housing.rnal_registrations_year,
                rnal_cessations_year=housing.rnal_cessations_year,
                rnal_net_registrations_year=housing.rnal_net_registrations_year,
                rnal_registrations_year_per_1000=(
                    pressure.registrations_year_per_1000
                ),
                rnal_cessations_year_per_1000=(
                    pressure.cessations_year_per_1000
                ),
                rnal_net_registrations_year_per_1000=(
                    pressure.net_registrations_year_per_1000
                ),
                rnal_active_registrations_year_end=(
                    housing.rnal_active_registrations_year_end
                ),
                rnal_active_registrations_per_1000_year_end=(
                    pressure.active_registrations_per_1000_year_end
                ),
                rnal_active_registrations_per_1000_change_from_baseline=(
                    pressure.active_registrations_per_1000_change_from_baseline
                ),
                rnal_active_beds_known_year_end=(
                    housing.rnal_active_beds_known_year_end
                ),
                rnal_active_beds_missing_year_end=(
                    housing.rnal_active_beds_missing_year_end
                ),
                rnal_active_beds_known_per_1000_year_end=(
                    pressure.active_beds_known_per_1000_year_end
                ),
                rnal_active_beds_known_per_1000_change_from_baseline=(
                    pressure.active_beds_known_per_1000_change_from_baseline
                ),
                rnal_active_users_known_year_end=(
                    housing.rnal_active_users_known_year_end
                ),
                rnal_active_users_missing_year_end=(
                    housing.rnal_active_users_missing_year_end
                ),
                rnal_active_users_known_per_1000_year_end=(
                    pressure.active_users_known_per_1000_year_end
                ),
                rnal_active_users_known_per_1000_change_from_baseline=(
                    pressure.active_users_known_per_1000_change_from_baseline
                ),
            )
        )

    return tuple(output)


def write_annual_housing_pressure_csv(
    rows: Sequence[AnnualHousingPressureRow],
    path: Path,
) -> None:
    """Write the joined annual research panel without overwriting."""
    if not rows:
        raise AnnualHousingPressureError(
            "annual housing-pressure panel cannot be empty"
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(ANNUAL_HOUSING_PRESSURE_COLUMNS)

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
                    _optional_decimal_text(row.housing_value_eur_m2),
                    _optional_decimal_text(row.housing_yoy_abs_eur_m2),
                    _optional_decimal_text(row.housing_yoy_pct),
                    _optional_decimal_text(
                        row.housing_change_from_baseline_abs_eur_m2
                    ),
                    _optional_decimal_text(
                        row.housing_change_from_baseline_pct
                    ),
                    _optional_int_text(row.rnal_registrations_year),
                    _optional_int_text(row.rnal_cessations_year),
                    _optional_int_text(row.rnal_net_registrations_year),
                    _optional_decimal_text(
                        row.rnal_registrations_year_per_1000
                    ),
                    _optional_decimal_text(
                        row.rnal_cessations_year_per_1000
                    ),
                    _optional_decimal_text(
                        row.rnal_net_registrations_year_per_1000
                    ),
                    row.rnal_active_registrations_year_end,
                    _decimal_text(
                        row.rnal_active_registrations_per_1000_year_end
                    ),
                    _decimal_text(
                        row.rnal_active_registrations_per_1000_change_from_baseline
                    ),
                    row.rnal_active_beds_known_year_end,
                    row.rnal_active_beds_missing_year_end,
                    _decimal_text(
                        row.rnal_active_beds_known_per_1000_year_end
                    ),
                    _decimal_text(
                        row.rnal_active_beds_known_per_1000_change_from_baseline
                    ),
                    row.rnal_active_users_known_year_end,
                    row.rnal_active_users_missing_year_end,
                    _decimal_text(
                        row.rnal_active_users_known_per_1000_year_end
                    ),
                    _decimal_text(
                        row.rnal_active_users_known_per_1000_change_from_baseline
                    ),
                )
            )


def _unique_housing_mapping(
    rows: Sequence[AnnualUrbanRow],
) -> dict[tuple[int, str], AnnualUrbanRow]:
    """Build a unique annual housing mapping."""
    mapping: dict[tuple[int, str], AnnualUrbanRow] = {}

    for row in rows:
        key = (row.year, row.freguesia_id)
        if key in mapping:
            raise AnnualHousingPressureError(
                f"duplicate annual housing key: {key}"
            )
        mapping[key] = row

    return mapping


def _unique_pressure_mapping(
    rows: Sequence[AnnualRNALPressureRow],
) -> dict[tuple[int, str], AnnualRNALPressureRow]:
    """Build a unique annual pressure mapping."""
    mapping: dict[tuple[int, str], AnnualRNALPressureRow] = {}

    for row in rows:
        key = (row.year, row.freguesia_id)
        if key in mapping:
            raise AnnualHousingPressureError(
                f"duplicate annual pressure key: {key}"
            )
        mapping[key] = row

    return mapping


def _validate_shared_dimensions(
    housing: AnnualUrbanRow,
    pressure: AnnualRNALPressureRow,
) -> None:
    """Require shared dimensions and baseline metadata to agree."""
    checks: tuple[tuple[str, object, object], ...] = (
        ("baseline_year", housing.baseline_year, pressure.baseline_year),
        ("period_code", housing.period_code, pressure.period_code),
        ("period_end", housing.period_end, pressure.period_end),
        ("freguesia_name", housing.freguesia_name, pressure.freguesia_name),
        (
            "flow_quarters_observed",
            housing.flow_quarters_observed,
            pressure.flow_quarters_observed,
        ),
    )

    for field, left, right in checks:
        if left != right:
            raise AnnualHousingPressureError(
                f"{housing.year}/{housing.freguesia_id} {field} mismatch: "
                f"{left!r} != {right!r}"
            )


def _validate_raw_rnal_consistency(
    housing: AnnualUrbanRow,
    pressure: AnnualRNALPressureRow,
) -> None:
    """Cross-check RNAL raw values duplicated across both annual panels."""
    checks: tuple[tuple[str, object, object], ...] = (
        (
            "registrations_year",
            housing.rnal_registrations_year,
            pressure.registrations_year,
        ),
        (
            "cessations_year",
            housing.rnal_cessations_year,
            pressure.cessations_year,
        ),
        (
            "net_registrations_year",
            housing.rnal_net_registrations_year,
            pressure.net_registrations_year,
        ),
        (
            "active_registrations_year_end",
            housing.rnal_active_registrations_year_end,
            pressure.active_registrations_year_end,
        ),
        (
            "active_beds_known_year_end",
            housing.rnal_active_beds_known_year_end,
            pressure.active_beds_known_year_end,
        ),
        (
            "active_beds_missing_year_end",
            housing.rnal_active_beds_missing_year_end,
            pressure.active_beds_missing_year_end,
        ),
        (
            "active_users_known_year_end",
            housing.rnal_active_users_known_year_end,
            pressure.active_users_known_year_end,
        ),
        (
            "active_users_missing_year_end",
            housing.rnal_active_users_missing_year_end,
            pressure.active_users_missing_year_end,
        ),
    )

    for field, left, right in checks:
        if left != right:
            raise AnnualHousingPressureError(
                f"{housing.year}/{housing.freguesia_id} raw RNAL "
                f"{field} mismatch: {left!r} != {right!r}"
            )


def _preview_keys(keys: Sequence[tuple[int, str]]) -> str:
    """Format a bounded diagnostic preview."""
    if not keys:
        return "[]"

    preview = ", ".join(str(key) for key in keys[:5])
    suffix = "" if len(keys) <= 5 else f", ... (+{len(keys) - 5})"
    return f"[{preview}{suffix}]"


def _required(value: str | None, row: int, field: str) -> str:
    """Return a required CSV string."""
    if value is None or not value.strip():
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be non-empty"
        )
    return value.strip()


def _required_int(value: str | None, row: int, field: str) -> int:
    """Parse a required integer."""
    raw = _required(value, row, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be an integer"
        ) from exc


def _required_non_negative_int(
    value: str | None,
    row: int,
    field: str,
) -> int:
    """Parse a required non-negative integer."""
    number = _required_int(value, row, field)
    if number < 0:
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be non-negative"
        )
    return number


def _required_positive_int(
    value: str | None,
    row: int,
    field: str,
) -> int:
    """Parse a required positive integer."""
    number = _required_int(value, row, field)
    if number <= 0:
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be positive"
        )
    return number


def _optional_int(
    value: str | None,
    row: int,
    field: str,
) -> int | None:
    """Parse an optional integer."""
    if value is None or not value.strip():
        return None
    return _required_int(value, row, field)


def _required_date(value: str | None, row: int, field: str) -> date:
    """Parse a required ISO date."""
    raw = _required(value, row, field)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be an ISO date"
        ) from exc


def _required_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal:
    """Parse a required Decimal."""
    raw = _required(value, row, field)
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be numeric"
        ) from exc


def _required_positive_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal:
    """Parse a required positive Decimal."""
    number = _required_decimal(value, row, field)
    if number <= 0:
        raise AnnualHousingPressureError(
            f"row {row}.{field} must be positive"
        )
    return number


def _optional_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal | None:
    """Parse an optional Decimal."""
    if value is None or not value.strip():
        return None
    return _required_decimal(value, row, field)


def _decimal_text(value: Decimal) -> str:
    """Serialize Decimal values without scientific notation."""
    return format(value, "f")


def _optional_decimal_text(value: Decimal | None) -> str:
    """Serialize an optional Decimal."""
    return "" if value is None else _decimal_text(value)


def _optional_int_text(value: int | None) -> str:
    """Serialize an optional integer."""
    return "" if value is None else str(value)
