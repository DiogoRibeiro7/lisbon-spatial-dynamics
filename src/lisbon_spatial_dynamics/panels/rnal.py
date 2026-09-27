"""Quarterly local-accommodation pressure panel from privacy-minimised RNAL data."""

from __future__ import annotations

import csv
import json
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import cast

from lisbon_spatial_dynamics.panels.housing import FreguesiaIndexRow
from lisbon_spatial_dynamics.panels.temporal import QuarterPeriod, parse_ine_quarter


class RNALPanelError(ValueError):
    """Raised when RNAL records cannot form a valid longitudinal panel."""


@dataclass(frozen=True, slots=True)
class RNALRecord:
    """One privacy-minimised RNAL establishment record."""

    registration_id: str
    registered_on: date
    ceased_on: date | None
    freguesia_id: str
    freguesia_name: str
    modality: str
    beds: int | None
    users: int | None


@dataclass(frozen=True, slots=True)
class RNALQuarterRow:
    """One freguesia-quarter local-accommodation stock observation."""

    period_code: str
    year: int
    quarter: int
    period_end: date
    freguesia_id: str
    freguesia_name: str
    registrations: int
    cessations: int
    net_registrations: int
    active_registrations: int
    active_beds_known: int
    active_beds_missing: int
    active_users_known: int
    active_users_missing: int


RNAL_PANEL_COLUMNS: tuple[str, ...] = (
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
)


def load_rnal_snapshot(path: Path) -> tuple[RNALRecord, ...]:
    """Load and validate a privacy-minimised RNAL JSON snapshot."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RNALPanelError("RNAL snapshot is not valid JSON") from exc

    document = _require_mapping(raw, "root")
    records_raw = document.get("records")
    if not isinstance(records_raw, list):
        raise RNALPanelError("RNAL snapshot records must be a list")

    records: list[RNALRecord] = []
    seen_ids: set[str] = set()

    for index, raw_record in enumerate(records_raw):
        context = f"records[{index}]"
        record = _require_mapping(raw_record, context)
        registration_id = _require_string(record, "NrRegisto", context)

        if registration_id in seen_ids:
            raise RNALPanelError(f"duplicate RNAL registration: {registration_id}")
        seen_ids.add(registration_id)

        registered_on = parse_rnal_date(
            _require_string(record, "DataRegisto", context),
            field=f"{context}.DataRegisto",
        )
        ceased_on = _optional_rnal_date(
            record.get("CessadoEm"),
            field=f"{context}.CessadoEm",
        )

        if ceased_on is not None and ceased_on < registered_on:
            raise RNALPanelError(
                f"{registration_id} cessation precedes registration"
            )

        records.append(
            RNALRecord(
                registration_id=registration_id,
                registered_on=registered_on,
                ceased_on=ceased_on,
                freguesia_id=_require_string(record, "DTMNFR", context),
                freguesia_name=_require_string(record, "Freguesia", context),
                modality=_optional_string(record.get("Modalidade"), f"{context}.Modalidade"),
                beds=_optional_non_negative_int(record.get("NrCamas"), f"{context}.NrCamas"),
                users=_optional_non_negative_int(
                    record.get("NrUtentes"), f"{context}.NrUtentes"
                ),
            )
        )

    return tuple(records)


def load_analysis_quarters(
    housing_changes_path: Path,
) -> tuple[QuarterPeriod, ...]:
    """Load unique ordered quarter definitions from the housing change panel."""
    periods: dict[int, QuarterPeriod] = {}

    with housing_changes_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"period_code", "year", "quarter", "period_end"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise RNALPanelError(
                "housing changes CSV is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row_index, row in enumerate(reader, start=2):
            label = _required_csv(row.get("period_code"), f"row {row_index}.period_code")
            period = parse_ine_quarter(label)

            year = _parse_required_int(row.get("year"), f"row {row_index}.year")
            quarter = _parse_required_int(row.get("quarter"), f"row {row_index}.quarter")
            period_end = _parse_iso_date(
                _required_csv(row.get("period_end"), f"row {row_index}.period_end"),
                f"row {row_index}.period_end",
            )

            if (period.year, period.quarter) != (year, quarter):
                raise RNALPanelError(
                    f"row {row_index} period fields disagree with {label!r}"
                )
            if period.period_end != period_end:
                raise RNALPanelError(
                    f"row {row_index} period_end disagrees with {label!r}"
                )

            existing = periods.get(period.ordinal)
            if existing is not None and existing.source_label != period.source_label:
                raise RNALPanelError(
                    f"multiple labels map to quarter ordinal {period.ordinal}"
                )
            periods[period.ordinal] = period

    if not periods:
        raise RNALPanelError("housing change panel contains no quarters")

    return tuple(periods[ordinal] for ordinal in sorted(periods))


def build_rnal_quarter_panel(
    records: Sequence[RNALRecord],
    reference: Sequence[FreguesiaIndexRow],
    periods: Sequence[QuarterPeriod],
) -> tuple[RNALQuarterRow, ...]:
    """Reconstruct RNAL flows and active stock on the housing quarter grid."""
    if not reference:
        raise RNALPanelError("reference geography cannot be empty")
    if not periods:
        raise RNALPanelError("analysis quarter grid cannot be empty")

    reference_by_id = _reference_mapping(reference)
    records_by_freguesia: dict[str, list[RNALRecord]] = {
        freguesia_id: [] for freguesia_id in reference_by_id
    }

    seen_registrations: set[str] = set()
    for record in records:
        if record.registration_id in seen_registrations:
            raise RNALPanelError(
                f"duplicate RNAL registration: {record.registration_id}"
            )
        seen_registrations.add(record.registration_id)

        canonical = reference_by_id.get(record.freguesia_id)
        if canonical is None:
            raise RNALPanelError(
                f"RNAL DTMNFR is outside canonical Lisboa reference: "
                f"{record.freguesia_id}"
            )
        if _normalise_name(record.freguesia_name) != _normalise_name(canonical.name):
            raise RNALPanelError(
                "RNAL/CAOP freguesia-name mismatch for "
                f"{record.freguesia_id}: {record.freguesia_name!r} != "
                f"{canonical.name!r}"
            )

        records_by_freguesia[record.freguesia_id].append(record)

    output: list[RNALQuarterRow] = []

    for period in sorted(periods, key=lambda item: item.ordinal):
        period_start = _quarter_start(period)
        period_end = period.period_end

        for freguesia_id in sorted(reference_by_id):
            canonical = reference_by_id[freguesia_id]
            freguesia_records = records_by_freguesia[freguesia_id]

            registrations = sum(
                period_start <= record.registered_on <= period_end
                for record in freguesia_records
            )
            cessations = sum(
                record.ceased_on is not None
                and period_start <= record.ceased_on <= period_end
                for record in freguesia_records
            )
            active = [
                record
                for record in freguesia_records
                if record.registered_on <= period_end
                and (record.ceased_on is None or record.ceased_on > period_end)
            ]

            beds_known = sum(record.beds or 0 for record in active if record.beds is not None)
            beds_missing = sum(record.beds is None for record in active)
            users_known = sum(
                record.users or 0 for record in active if record.users is not None
            )
            users_missing = sum(record.users is None for record in active)

            output.append(
                RNALQuarterRow(
                    period_code=period.source_label,
                    year=period.year,
                    quarter=period.quarter,
                    period_end=period_end,
                    freguesia_id=freguesia_id,
                    freguesia_name=canonical.name,
                    registrations=registrations,
                    cessations=cessations,
                    net_registrations=registrations - cessations,
                    active_registrations=len(active),
                    active_beds_known=beds_known,
                    active_beds_missing=beds_missing,
                    active_users_known=users_known,
                    active_users_missing=users_missing,
                )
            )

    return tuple(output)


def write_rnal_quarter_csv(
    rows: Sequence[RNALQuarterRow],
    path: Path,
) -> None:
    """Write the quarterly RNAL panel without overwriting existing output."""
    if not rows:
        raise RNALPanelError("RNAL quarter panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(RNAL_PANEL_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.period_code,
                    row.year,
                    row.quarter,
                    row.period_end.isoformat(),
                    row.freguesia_id,
                    row.freguesia_name,
                    row.registrations,
                    row.cessations,
                    row.net_registrations,
                    row.active_registrations,
                    row.active_beds_known,
                    row.active_beds_missing,
                    row.active_users_known,
                    row.active_users_missing,
                )
            )


def parse_rnal_date(value: str, *, field: str = "date") -> date:
    """Parse one explicit RNAL date representation.

    Turismo de Portugal documents RNAL date fields as strings. The parser
    therefore accepts only a small explicit set and rejects unknown forms.
    """
    raw = value.strip()
    if not raw:
        raise RNALPanelError(f"{field} must be non-empty")

    iso_candidate = raw.removesuffix("Z")
    try:
        return date.fromisoformat(iso_candidate)
    except ValueError:
        pass

    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass

    for pattern in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue

    raise RNALPanelError(f"unsupported RNAL date in {field}: {value!r}")


def _optional_rnal_date(value: object, *, field: str) -> date | None:
    """Parse an optional RNAL date."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RNALPanelError(f"{field} must be a string when present")
    if not value.strip():
        return None
    return parse_rnal_date(value, field=field)


def _quarter_start(period: QuarterPeriod) -> date:
    """Return the first date of a quarter."""
    month = (period.quarter - 1) * 3 + 1
    return date(period.year, month, 1)


def _reference_mapping(
    reference: Sequence[FreguesiaIndexRow],
) -> dict[str, FreguesiaIndexRow]:
    """Build a unique reference mapping."""
    mapping: dict[str, FreguesiaIndexRow] = {}
    for row in reference:
        if row.freguesia_id in mapping:
            raise RNALPanelError(
                f"duplicate reference freguesia_id: {row.freguesia_id}"
            )
        mapping[row.freguesia_id] = row
    return mapping


def _normalise_name(value: str) -> str:
    """Normalize labels for validation comparisons only."""
    normalised = unicodedata.normalize("NFKC", value)
    return " ".join(normalised.split()).casefold()


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Return a required JSON mapping."""
    if not isinstance(value, Mapping):
        raise RNALPanelError(f"{context} must be an object")
    return cast(Mapping[str, object], value)


def _require_string(
    raw: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string field."""
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RNALPanelError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _optional_string(value: object, context: str) -> str:
    """Return an optional string field."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise RNALPanelError(f"{context} must be a string")
    return value.strip()


def _optional_non_negative_int(value: object, context: str) -> int | None:
    """Parse an optional non-negative integer field stored as text."""
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise RNALPanelError(f"{context} must be non-negative")
        return value
    if not isinstance(value, str):
        raise RNALPanelError(f"{context} must be a string or integer")

    raw = value.strip()
    if not raw:
        return None

    try:
        parsed = int(raw)
    except ValueError as exc:
        raise RNALPanelError(f"{context} must be an integer") from exc

    if parsed < 0:
        raise RNALPanelError(f"{context} must be non-negative")
    return parsed


def _required_csv(value: str | None, context: str) -> str:
    """Return a required CSV value."""
    if value is None or not value.strip():
        raise RNALPanelError(f"{context} must be non-empty")
    return value.strip()


def _parse_required_int(value: str | None, context: str) -> int:
    """Parse a required integer CSV value."""
    raw = _required_csv(value, context)
    try:
        return int(raw)
    except ValueError as exc:
        raise RNALPanelError(f"{context} must be an integer") from exc


def _parse_iso_date(value: str, context: str) -> date:
    """Parse a required ISO calendar date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RNALPanelError(f"{context} must be an ISO date") from exc
