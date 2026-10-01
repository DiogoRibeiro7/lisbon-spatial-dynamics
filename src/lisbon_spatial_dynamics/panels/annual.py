"""Annual year-end urban-change panel for Lisbon freguesias."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation
from pathlib import Path

from lisbon_spatial_dynamics.panels.urban import UrbanChangeRow


class AnnualPanelError(ValueError):
    """Raised when quarterly urban rows cannot form a valid annual panel."""


@dataclass(frozen=True, slots=True)
class AnnualUrbanRow:
    """One freguesia-year observation anchored on the fourth quarter."""

    year: int
    baseline_year: int
    period_code: str
    period_end: date
    freguesia_id: str
    freguesia_name: str
    flow_quarters_observed: int
    housing_value_eur_m2: Decimal | None
    housing_yoy_abs_eur_m2: Decimal | None
    housing_yoy_pct: Decimal | None
    housing_change_from_baseline_abs_eur_m2: Decimal | None
    housing_change_from_baseline_pct: Decimal | None
    rnal_registrations_year: int | None
    rnal_cessations_year: int | None
    rnal_net_registrations_year: int | None
    rnal_active_registrations_year_end: int
    rnal_active_change_from_baseline_abs: int
    rnal_active_change_from_baseline_pct: Decimal | None
    rnal_active_beds_known_year_end: int
    rnal_active_beds_missing_year_end: int
    rnal_active_users_known_year_end: int
    rnal_active_users_missing_year_end: int


ANNUAL_PANEL_COLUMNS: tuple[str, ...] = (
    "year",
    "baseline_year",
    "period_code",
    "period_end",
    "freguesia_id",
    "freguesia_name",
    "flow_quarters_observed",
    "housing_value_eur_m2",
    "housing_yoy_abs_eur_m2",
    "housing_yoy_pct",
    "housing_change_from_baseline_abs_eur_m2",
    "housing_change_from_baseline_pct",
    "rnal_registrations_year",
    "rnal_cessations_year",
    "rnal_net_registrations_year",
    "rnal_active_registrations_year_end",
    "rnal_active_change_from_baseline_abs",
    "rnal_active_change_from_baseline_pct",
    "rnal_active_beds_known_year_end",
    "rnal_active_beds_missing_year_end",
    "rnal_active_users_known_year_end",
    "rnal_active_users_missing_year_end",
)


def load_urban_change_csv(path: Path) -> tuple[UrbanChangeRow, ...]:
    """Load the combined quarterly urban-change CSV."""
    rows: list[UrbanChangeRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "period_code",
            "year",
            "quarter",
            "period_end",
            "freguesia_id",
            "freguesia_name",
            "housing_value_eur_m2",
            "housing_qoq_abs_eur_m2",
            "housing_qoq_pct",
            "housing_yoy_abs_eur_m2",
            "housing_yoy_pct",
            "rnal_registrations",
            "rnal_cessations",
            "rnal_net_registrations",
            "rnal_active_registrations",
            "rnal_active_beds_known",
            "rnal_active_beds_missing",
            "rnal_active_users_known",
            "rnal_active_users_missing",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise AnnualPanelError(
                "urban change CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for index, raw in enumerate(reader, start=2):
            rows.append(
                UrbanChangeRow(
                    period_code=_required(raw.get("period_code"), index, "period_code"),
                    year=_required_int(raw.get("year"), index, "year"),
                    quarter=_required_int(raw.get("quarter"), index, "quarter"),
                    period_end=_required_date(raw.get("period_end"), index, "period_end"),
                    freguesia_id=_required(raw.get("freguesia_id"), index, "freguesia_id"),
                    freguesia_name=_required(raw.get("freguesia_name"), index, "freguesia_name"),
                    housing_value_eur_m2=_optional_decimal(
                        raw.get("housing_value_eur_m2"),
                        index,
                        "housing_value_eur_m2",
                    ),
                    housing_qoq_abs_eur_m2=_optional_decimal(
                        raw.get("housing_qoq_abs_eur_m2"),
                        index,
                        "housing_qoq_abs_eur_m2",
                    ),
                    housing_qoq_pct=_optional_decimal(
                        raw.get("housing_qoq_pct"),
                        index,
                        "housing_qoq_pct",
                    ),
                    housing_yoy_abs_eur_m2=_optional_decimal(
                        raw.get("housing_yoy_abs_eur_m2"),
                        index,
                        "housing_yoy_abs_eur_m2",
                    ),
                    housing_yoy_pct=_optional_decimal(
                        raw.get("housing_yoy_pct"),
                        index,
                        "housing_yoy_pct",
                    ),
                    rnal_registrations=_required_int(
                        raw.get("rnal_registrations"),
                        index,
                        "rnal_registrations",
                    ),
                    rnal_cessations=_required_int(
                        raw.get("rnal_cessations"),
                        index,
                        "rnal_cessations",
                    ),
                    rnal_net_registrations=_required_int(
                        raw.get("rnal_net_registrations"),
                        index,
                        "rnal_net_registrations",
                    ),
                    rnal_active_registrations=_required_int(
                        raw.get("rnal_active_registrations"),
                        index,
                        "rnal_active_registrations",
                    ),
                    rnal_active_beds_known=_required_int(
                        raw.get("rnal_active_beds_known"),
                        index,
                        "rnal_active_beds_known",
                    ),
                    rnal_active_beds_missing=_required_int(
                        raw.get("rnal_active_beds_missing"),
                        index,
                        "rnal_active_beds_missing",
                    ),
                    rnal_active_users_known=_required_int(
                        raw.get("rnal_active_users_known"),
                        index,
                        "rnal_active_users_known",
                    ),
                    rnal_active_users_missing=_required_int(
                        raw.get("rnal_active_users_missing"),
                        index,
                        "rnal_active_users_missing",
                    ),
                )
            )

    if not rows:
        raise AnnualPanelError("urban change CSV cannot be empty")

    return tuple(rows)


def build_annual_urban_panel(
    rows: Sequence[UrbanChangeRow],
) -> tuple[AnnualUrbanRow, ...]:
    """Build year-end comparisons with complete-year RNAL flows when available.

    A year enters the annual panel only when Q4 is present. RNAL registrations,
    cessations and net flows are summed only if quarters 1-4 are all present for
    the freguesia-year. Year-end stock/capacity always comes from Q4.
    """
    if not rows:
        raise AnnualPanelError("urban panel cannot be empty")

    grouped: dict[tuple[str, int], dict[int, UrbanChangeRow]] = {}
    names: dict[str, str] = {}

    for row in rows:
        key = (row.freguesia_id, row.year)
        quarters = grouped.setdefault(key, {})

        if row.quarter in quarters:
            raise AnnualPanelError(
                f"duplicate quarter for {row.freguesia_id}/{row.year}: Q{row.quarter}"
            )

        known_name = names.get(row.freguesia_id)
        if known_name is not None and known_name != row.freguesia_name:
            raise AnnualPanelError(f"inconsistent freguesia name for {row.freguesia_id}")
        names[row.freguesia_id] = row.freguesia_name
        quarters[row.quarter] = row

    q4_by_freguesia: dict[str, list[tuple[int, dict[int, UrbanChangeRow]]]] = {}

    for (freguesia_id, year), quarters in grouped.items():
        if 4 not in quarters:
            continue
        q4_by_freguesia.setdefault(freguesia_id, []).append((year, quarters))

    if not q4_by_freguesia:
        raise AnnualPanelError("urban panel contains no Q4 observations")

    output: list[AnnualUrbanRow] = []

    for freguesia_id in sorted(q4_by_freguesia):
        years = sorted(q4_by_freguesia[freguesia_id], key=lambda item: item[0])
        baseline_year, baseline_quarters = years[0]
        baseline_q4 = baseline_quarters[4]

        for year, quarters in years:
            q4 = quarters[4]
            observed_quarters = set(quarters)
            full_year = observed_quarters == {1, 2, 3, 4}

            housing_abs, housing_pct = _decimal_change_from_baseline(
                q4.housing_value_eur_m2,
                baseline_q4.housing_value_eur_m2,
            )

            rnal_active_abs = q4.rnal_active_registrations - baseline_q4.rnal_active_registrations
            rnal_active_pct = _integer_pct_change(
                q4.rnal_active_registrations,
                baseline_q4.rnal_active_registrations,
            )

            output.append(
                AnnualUrbanRow(
                    year=year,
                    baseline_year=baseline_year,
                    period_code=q4.period_code,
                    period_end=q4.period_end,
                    freguesia_id=freguesia_id,
                    freguesia_name=q4.freguesia_name,
                    flow_quarters_observed=len(observed_quarters),
                    housing_value_eur_m2=q4.housing_value_eur_m2,
                    housing_yoy_abs_eur_m2=q4.housing_yoy_abs_eur_m2,
                    housing_yoy_pct=q4.housing_yoy_pct,
                    housing_change_from_baseline_abs_eur_m2=housing_abs,
                    housing_change_from_baseline_pct=housing_pct,
                    rnal_registrations_year=(
                        sum(item.rnal_registrations for item in quarters.values())
                        if full_year
                        else None
                    ),
                    rnal_cessations_year=(
                        sum(item.rnal_cessations for item in quarters.values())
                        if full_year
                        else None
                    ),
                    rnal_net_registrations_year=(
                        sum(item.rnal_net_registrations for item in quarters.values())
                        if full_year
                        else None
                    ),
                    rnal_active_registrations_year_end=q4.rnal_active_registrations,
                    rnal_active_change_from_baseline_abs=rnal_active_abs,
                    rnal_active_change_from_baseline_pct=rnal_active_pct,
                    rnal_active_beds_known_year_end=q4.rnal_active_beds_known,
                    rnal_active_beds_missing_year_end=q4.rnal_active_beds_missing,
                    rnal_active_users_known_year_end=q4.rnal_active_users_known,
                    rnal_active_users_missing_year_end=q4.rnal_active_users_missing,
                )
            )

    return tuple(sorted(output, key=lambda row: (row.year, row.freguesia_id)))


def write_annual_urban_csv(
    rows: Sequence[AnnualUrbanRow],
    path: Path,
) -> None:
    """Write the annual urban-change panel without overwriting."""
    if not rows:
        raise AnnualPanelError("annual urban panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(ANNUAL_PANEL_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.year,
                    row.baseline_year,
                    row.period_code,
                    row.period_end.isoformat(),
                    row.freguesia_id,
                    row.freguesia_name,
                    row.flow_quarters_observed,
                    _decimal_text(row.housing_value_eur_m2),
                    _decimal_text(row.housing_yoy_abs_eur_m2),
                    _decimal_text(row.housing_yoy_pct),
                    _decimal_text(row.housing_change_from_baseline_abs_eur_m2),
                    _decimal_text(row.housing_change_from_baseline_pct),
                    _optional_int_text(row.rnal_registrations_year),
                    _optional_int_text(row.rnal_cessations_year),
                    _optional_int_text(row.rnal_net_registrations_year),
                    row.rnal_active_registrations_year_end,
                    row.rnal_active_change_from_baseline_abs,
                    _decimal_text(row.rnal_active_change_from_baseline_pct),
                    row.rnal_active_beds_known_year_end,
                    row.rnal_active_beds_missing_year_end,
                    row.rnal_active_users_known_year_end,
                    row.rnal_active_users_missing_year_end,
                )
            )


def _decimal_change_from_baseline(
    current: Decimal | None,
    baseline: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Return absolute and percentage change from one decimal baseline."""
    if current is None or baseline is None:
        return None, None

    absolute = current - baseline

    try:
        percentage = (absolute / baseline) * Decimal("100")
    except DivisionByZero:
        percentage = None

    return absolute, percentage


def _integer_pct_change(current: int, baseline: int) -> Decimal | None:
    """Return percentage change from an integer baseline."""
    if baseline == 0:
        return None

    return Decimal(current - baseline) / Decimal(baseline) * Decimal("100")


def _required(value: str | None, row: int, field: str) -> str:
    """Return a required CSV string."""
    if value is None or not value.strip():
        raise AnnualPanelError(f"row {row}.{field} must be non-empty")
    return value.strip()


def _required_int(value: str | None, row: int, field: str) -> int:
    """Parse a required integer CSV value."""
    raw = _required(value, row, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise AnnualPanelError(f"row {row}.{field} must be an integer") from exc


def _required_date(value: str | None, row: int, field: str) -> date:
    """Parse a required ISO date CSV value."""
    raw = _required(value, row, field)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise AnnualPanelError(f"row {row}.{field} must be an ISO date") from exc


def _optional_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal | None:
    """Parse an optional Decimal CSV value."""
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise AnnualPanelError(f"row {row}.{field} must be numeric") from exc


def _decimal_text(value: Decimal | None) -> str:
    """Serialize optional Decimal values."""
    return "" if value is None else format(value, "f")


def _optional_int_text(value: int | None) -> str:
    """Serialize optional integer values."""
    return "" if value is None else str(value)
