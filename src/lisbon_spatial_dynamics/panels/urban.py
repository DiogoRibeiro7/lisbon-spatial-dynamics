"""Combined quarterly urban-change panel for Lisbon freguesias."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lisbon_spatial_dynamics.panels.rnal import RNALQuarterRow
from lisbon_spatial_dynamics.panels.temporal import HousingChangeRow


class UrbanPanelError(ValueError):
    """Raised when component panels cannot be joined one-to-one."""


@dataclass(frozen=True, slots=True)
class UrbanChangeRow:
    """One canonical freguesia-quarter observation across project domains."""

    period_code: str
    year: int
    quarter: int
    period_end: date
    freguesia_id: str
    freguesia_name: str
    housing_value_eur_m2: Decimal | None
    housing_qoq_abs_eur_m2: Decimal | None
    housing_qoq_pct: Decimal | None
    housing_yoy_abs_eur_m2: Decimal | None
    housing_yoy_pct: Decimal | None
    rnal_registrations: int
    rnal_cessations: int
    rnal_net_registrations: int
    rnal_active_registrations: int
    rnal_active_beds_known: int
    rnal_active_beds_missing: int
    rnal_active_users_known: int
    rnal_active_users_missing: int


URBAN_PANEL_COLUMNS: tuple[str, ...] = (
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
)


def load_housing_change_csv(path: Path) -> tuple[HousingChangeRow, ...]:
    """Load the analysis-ready housing-change CSV."""
    rows: list[HousingChangeRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "period_code",
            "year",
            "quarter",
            "period_end",
            "freguesia_id",
            "freguesia_name",
            "value_eur_m2",
            "qoq_abs_eur_m2",
            "qoq_pct",
            "yoy_abs_eur_m2",
            "yoy_pct",
        }
        _require_columns(reader.fieldnames, required, "housing change CSV")

        for index, raw in enumerate(reader, start=2):
            rows.append(
                HousingChangeRow(
                    period_code=_required(raw.get("period_code"), index, "period_code"),
                    year=_required_int(raw.get("year"), index, "year"),
                    quarter=_required_int(raw.get("quarter"), index, "quarter"),
                    period_end=_required_date(raw.get("period_end"), index, "period_end"),
                    freguesia_id=_required(raw.get("freguesia_id"), index, "freguesia_id"),
                    freguesia_name=_required(raw.get("freguesia_name"), index, "freguesia_name"),
                    value_eur_m2=_optional_decimal(raw.get("value_eur_m2"), index, "value_eur_m2"),
                    qoq_abs_eur_m2=_optional_decimal(
                        raw.get("qoq_abs_eur_m2"), index, "qoq_abs_eur_m2"
                    ),
                    qoq_pct=_optional_decimal(raw.get("qoq_pct"), index, "qoq_pct"),
                    yoy_abs_eur_m2=_optional_decimal(
                        raw.get("yoy_abs_eur_m2"), index, "yoy_abs_eur_m2"
                    ),
                    yoy_pct=_optional_decimal(raw.get("yoy_pct"), index, "yoy_pct"),
                )
            )

    if not rows:
        raise UrbanPanelError("housing change CSV cannot be empty")
    return tuple(rows)


def load_rnal_quarter_csv(path: Path) -> tuple[RNALQuarterRow, ...]:
    """Load the quarterly RNAL panel CSV."""
    rows: list[RNALQuarterRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "period_code",
            "year",
            "quarter",
            "period_end",
            "freguesia_id",
            "freguesia_name",
            "registrations",
            "cessations",
            "net_registrations",
            "active_registrations",
            "active_beds_known",
            "active_beds_missing",
            "active_users_known",
            "active_users_missing",
        }
        _require_columns(reader.fieldnames, required, "RNAL quarter CSV")

        for index, raw in enumerate(reader, start=2):
            rows.append(
                RNALQuarterRow(
                    period_code=_required(raw.get("period_code"), index, "period_code"),
                    year=_required_int(raw.get("year"), index, "year"),
                    quarter=_required_int(raw.get("quarter"), index, "quarter"),
                    period_end=_required_date(raw.get("period_end"), index, "period_end"),
                    freguesia_id=_required(raw.get("freguesia_id"), index, "freguesia_id"),
                    freguesia_name=_required(raw.get("freguesia_name"), index, "freguesia_name"),
                    registrations=_required_int(raw.get("registrations"), index, "registrations"),
                    cessations=_required_int(raw.get("cessations"), index, "cessations"),
                    net_registrations=_required_int(
                        raw.get("net_registrations"), index, "net_registrations"
                    ),
                    active_registrations=_required_int(
                        raw.get("active_registrations"),
                        index,
                        "active_registrations",
                    ),
                    active_beds_known=_required_int(
                        raw.get("active_beds_known"), index, "active_beds_known"
                    ),
                    active_beds_missing=_required_int(
                        raw.get("active_beds_missing"), index, "active_beds_missing"
                    ),
                    active_users_known=_required_int(
                        raw.get("active_users_known"), index, "active_users_known"
                    ),
                    active_users_missing=_required_int(
                        raw.get("active_users_missing"), index, "active_users_missing"
                    ),
                )
            )

    if not rows:
        raise UrbanPanelError("RNAL quarter CSV cannot be empty")
    return tuple(rows)


def build_urban_change_panel(
    housing: Sequence[HousingChangeRow],
    rnal: Sequence[RNALQuarterRow],
) -> tuple[UrbanChangeRow, ...]:
    """Join housing and RNAL panels exactly on freguesia and quarter.

    The component key sets must be identical. No left/right join is allowed
    because an apparently complete combined panel would otherwise conceal
    upstream coverage failures.
    """
    housing_by_key = _unique_housing_mapping(housing)
    rnal_by_key = _unique_rnal_mapping(rnal)

    housing_keys = set(housing_by_key)
    rnal_keys = set(rnal_by_key)

    if housing_keys != rnal_keys:
        housing_only = sorted(housing_keys - rnal_keys)
        rnal_only = sorted(rnal_keys - housing_keys)
        raise UrbanPanelError(
            "component panel keys differ; "
            f"housing_only={_preview_keys(housing_only)}, "
            f"rnal_only={_preview_keys(rnal_only)}"
        )

    output: list[UrbanChangeRow] = []

    for key in sorted(housing_keys):
        housing_row = housing_by_key[key]
        rnal_row = rnal_by_key[key]

        _validate_shared_dimensions(housing_row, rnal_row)

        output.append(
            UrbanChangeRow(
                period_code=housing_row.period_code,
                year=housing_row.year,
                quarter=housing_row.quarter,
                period_end=housing_row.period_end,
                freguesia_id=housing_row.freguesia_id,
                freguesia_name=housing_row.freguesia_name,
                housing_value_eur_m2=housing_row.value_eur_m2,
                housing_qoq_abs_eur_m2=housing_row.qoq_abs_eur_m2,
                housing_qoq_pct=housing_row.qoq_pct,
                housing_yoy_abs_eur_m2=housing_row.yoy_abs_eur_m2,
                housing_yoy_pct=housing_row.yoy_pct,
                rnal_registrations=rnal_row.registrations,
                rnal_cessations=rnal_row.cessations,
                rnal_net_registrations=rnal_row.net_registrations,
                rnal_active_registrations=rnal_row.active_registrations,
                rnal_active_beds_known=rnal_row.active_beds_known,
                rnal_active_beds_missing=rnal_row.active_beds_missing,
                rnal_active_users_known=rnal_row.active_users_known,
                rnal_active_users_missing=rnal_row.active_users_missing,
            )
        )

    if not output:
        raise UrbanPanelError("combined urban panel cannot be empty")

    return tuple(output)


def write_urban_change_csv(
    rows: Sequence[UrbanChangeRow],
    path: Path,
) -> None:
    """Write the combined urban-change panel without overwriting."""
    if not rows:
        raise UrbanPanelError("combined urban panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(URBAN_PANEL_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.period_code,
                    row.year,
                    row.quarter,
                    row.period_end.isoformat(),
                    row.freguesia_id,
                    row.freguesia_name,
                    _decimal_text(row.housing_value_eur_m2),
                    _decimal_text(row.housing_qoq_abs_eur_m2),
                    _decimal_text(row.housing_qoq_pct),
                    _decimal_text(row.housing_yoy_abs_eur_m2),
                    _decimal_text(row.housing_yoy_pct),
                    row.rnal_registrations,
                    row.rnal_cessations,
                    row.rnal_net_registrations,
                    row.rnal_active_registrations,
                    row.rnal_active_beds_known,
                    row.rnal_active_beds_missing,
                    row.rnal_active_users_known,
                    row.rnal_active_users_missing,
                )
            )


def _unique_housing_mapping(
    rows: Sequence[HousingChangeRow],
) -> dict[tuple[int, int, str], HousingChangeRow]:
    """Build a unique housing key mapping."""
    mapping: dict[tuple[int, int, str], HousingChangeRow] = {}

    for row in rows:
        key = (row.year, row.quarter, row.freguesia_id)
        if key in mapping:
            raise UrbanPanelError(f"duplicate housing key: {key}")
        mapping[key] = row

    return mapping


def _unique_rnal_mapping(
    rows: Sequence[RNALQuarterRow],
) -> dict[tuple[int, int, str], RNALQuarterRow]:
    """Build a unique RNAL key mapping."""
    mapping: dict[tuple[int, int, str], RNALQuarterRow] = {}

    for row in rows:
        key = (row.year, row.quarter, row.freguesia_id)
        if key in mapping:
            raise UrbanPanelError(f"duplicate RNAL key: {key}")
        mapping[key] = row

    return mapping


def _validate_shared_dimensions(
    housing: HousingChangeRow,
    rnal: RNALQuarterRow,
) -> None:
    """Require identical non-key shared dimensions across component panels."""
    if housing.period_code != rnal.period_code:
        raise UrbanPanelError(
            f"period_code mismatch for {housing.freguesia_id}: "
            f"{housing.period_code!r} != {rnal.period_code!r}"
        )
    if housing.period_end != rnal.period_end:
        raise UrbanPanelError(
            f"period_end mismatch for {housing.freguesia_id}: "
            f"{housing.period_end} != {rnal.period_end}"
        )
    if housing.freguesia_name != rnal.freguesia_name:
        raise UrbanPanelError(
            f"freguesia_name mismatch for {housing.freguesia_id}: "
            f"{housing.freguesia_name!r} != {rnal.freguesia_name!r}"
        )


def _require_columns(
    fieldnames: Sequence[str] | None,
    required: set[str],
    label: str,
) -> None:
    """Validate required CSV columns."""
    missing = required - set(fieldnames or ())
    if missing:
        raise UrbanPanelError(f"{label} is missing columns: " + ", ".join(sorted(missing)))


def _required(value: str | None, row: int, field: str) -> str:
    """Return a required CSV string."""
    if value is None or not value.strip():
        raise UrbanPanelError(f"row {row}.{field} must be non-empty")
    return value.strip()


def _required_int(value: str | None, row: int, field: str) -> int:
    """Parse a required integer CSV field."""
    raw = _required(value, row, field)
    try:
        return int(raw)
    except ValueError as exc:
        raise UrbanPanelError(f"row {row}.{field} must be an integer") from exc


def _required_date(value: str | None, row: int, field: str) -> date:
    """Parse a required ISO date CSV field."""
    raw = _required(value, row, field)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise UrbanPanelError(f"row {row}.{field} must be an ISO date") from exc


def _optional_decimal(
    value: str | None,
    row: int,
    field: str,
) -> Decimal | None:
    """Parse an optional decimal CSV field."""
    if value is None or not value.strip():
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise UrbanPanelError(f"row {row}.{field} must be numeric") from exc


def _decimal_text(value: Decimal | None) -> str:
    """Serialize an optional Decimal without scientific notation."""
    return "" if value is None else format(value, "f")


def _preview_keys(keys: Sequence[tuple[int, int, str]]) -> str:
    """Format a bounded diagnostic preview of unmatched keys."""
    if not keys:
        return "[]"

    preview = ", ".join(str(key) for key in keys[:5])
    suffix = "" if len(keys) <= 5 else f", ... (+{len(keys) - 5})"
    return f"[{preview}{suffix}]"
