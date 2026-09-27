"""Temporal normalization and change metrics for the Lisbon housing panel."""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DivisionByZero
from pathlib import Path

from lisbon_spatial_dynamics.panels.housing import HousingPanelRow

_PERIOD_RE = re.compile(r"^(?P<quarter>[1-4])\.º Trimestre de (?P<year>\d{4})$")

CHANGE_COLUMNS: tuple[str, ...] = (
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
)


class HousingTimeError(ValueError):
    """Raised when housing periods or longitudinal structure are invalid."""


@dataclass(frozen=True, slots=True, order=True)
class QuarterPeriod:
    """Normalized quarterly period parsed from an INE label."""

    year: int
    quarter: int
    source_label: str

    @property
    def ordinal(self) -> int:
        """Return a monotonic quarter index."""
        return self.year * 4 + self.quarter - 1

    @property
    def period_end(self) -> date:
        """Return the calendar end date of the reference quarter."""
        month = self.quarter * 3
        day = 31 if month in {3, 12} else 30
        return date(self.year, month, day)


@dataclass(frozen=True, slots=True)
class HousingChangeRow:
    """One canonical housing observation enriched with temporal changes."""

    period_code: str
    year: int
    quarter: int
    period_end: date
    freguesia_id: str
    freguesia_name: str
    value_eur_m2: Decimal | None
    qoq_abs_eur_m2: Decimal | None
    qoq_pct: Decimal | None
    yoy_abs_eur_m2: Decimal | None
    yoy_pct: Decimal | None


def parse_ine_quarter(label: str) -> QuarterPeriod:
    """Parse an INE Portuguese quarterly label strictly."""
    match = _PERIOD_RE.fullmatch(label.strip())
    if match is None:
        raise HousingTimeError(f"unsupported INE quarter label: {label!r}")

    return QuarterPeriod(
        year=int(match.group("year")),
        quarter=int(match.group("quarter")),
        source_label=label.strip(),
    )


def build_housing_change_panel(
    rows: Sequence[HousingPanelRow],
) -> tuple[HousingChangeRow, ...]:
    """Normalize quarter labels and calculate QoQ and YoY change measures.

    Quarter-on-quarter change compares overlapping rolling-12-month values and
    should therefore be interpreted as short-horizon movement in the published
    rolling statistic, not as a non-overlapping quarterly price change.
    """
    if not rows:
        raise HousingTimeError("housing panel cannot be empty")

    by_freguesia: dict[str, dict[int, tuple[QuarterPeriod, HousingPanelRow]]] = {}
    names: dict[str, str] = {}

    for row in rows:
        period = parse_ine_quarter(row.period_code)
        freguesia_periods = by_freguesia.setdefault(row.freguesia_id, {})

        if period.ordinal in freguesia_periods:
            raise HousingTimeError(
                f"duplicate quarter for {row.freguesia_id}: {row.period_code}"
            )

        known_name = names.get(row.freguesia_id)
        if known_name is not None and known_name != row.freguesia_name:
            raise HousingTimeError(
                f"inconsistent freguesia name for {row.freguesia_id}"
            )
        names[row.freguesia_id] = row.freguesia_name
        freguesia_periods[period.ordinal] = (period, row)

    output: list[HousingChangeRow] = []

    for freguesia_id in sorted(by_freguesia):
        periods = by_freguesia[freguesia_id]

        for ordinal in sorted(periods):
            period, row = periods[ordinal]
            previous = periods.get(ordinal - 1)
            prior_year = periods.get(ordinal - 4)

            qoq_abs, qoq_pct = _change(
                row.value_eur_m2,
                None if previous is None else previous[1].value_eur_m2,
            )
            yoy_abs, yoy_pct = _change(
                row.value_eur_m2,
                None if prior_year is None else prior_year[1].value_eur_m2,
            )

            output.append(
                HousingChangeRow(
                    period_code=row.period_code,
                    year=period.year,
                    quarter=period.quarter,
                    period_end=period.period_end,
                    freguesia_id=freguesia_id,
                    freguesia_name=row.freguesia_name,
                    value_eur_m2=row.value_eur_m2,
                    qoq_abs_eur_m2=qoq_abs,
                    qoq_pct=qoq_pct,
                    yoy_abs_eur_m2=yoy_abs,
                    yoy_pct=yoy_pct,
                )
            )

    return tuple(
        sorted(
            output,
            key=lambda row: (row.year, row.quarter, row.freguesia_id),
        )
    )


def load_housing_panel_csv(path: Path) -> tuple[HousingPanelRow, ...]:
    """Load the canonical housing panel CSV."""
    rows: list[HousingPanelRow] = []

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "period_code",
            "freguesia_id",
            "freguesia_name",
            "indicator_code",
            "source_geography_code",
            "source_geography_name",
            "category_code",
            "category_name",
            "value_eur_m2",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise HousingTimeError(
                "housing panel CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for index, raw in enumerate(reader, start=2):
            value_raw = (raw.get("value_eur_m2") or "").strip()
            value = None if not value_raw else Decimal(value_raw)

            rows.append(
                HousingPanelRow(
                    period_code=_required(raw, "period_code", index),
                    freguesia_id=_required(raw, "freguesia_id", index),
                    freguesia_name=_required(raw, "freguesia_name", index),
                    indicator_code=_required(raw, "indicator_code", index),
                    source_geography_code=_required(
                        raw, "source_geography_code", index
                    ),
                    source_geography_name=_required(
                        raw, "source_geography_name", index
                    ),
                    category_code=_required(raw, "category_code", index),
                    category_name=_required(raw, "category_name", index),
                    value_eur_m2=value,
                )
            )

    return tuple(rows)


def write_housing_change_csv(
    rows: Sequence[HousingChangeRow],
    path: Path,
) -> None:
    """Write the analysis-ready housing change panel without overwriting."""
    if not rows:
        raise HousingTimeError("housing change panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(CHANGE_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.period_code,
                    row.year,
                    row.quarter,
                    row.period_end.isoformat(),
                    row.freguesia_id,
                    row.freguesia_name,
                    _decimal_text(row.value_eur_m2),
                    _decimal_text(row.qoq_abs_eur_m2),
                    _decimal_text(row.qoq_pct),
                    _decimal_text(row.yoy_abs_eur_m2),
                    _decimal_text(row.yoy_pct),
                )
            )


def _change(
    current: Decimal | None,
    previous: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Return absolute and percentage change, preserving missingness."""
    if current is None or previous is None:
        return None, None

    absolute = current - previous

    try:
        percentage = (absolute / previous) * Decimal("100")
    except DivisionByZero:
        percentage = None

    return absolute, percentage


def _required(raw: dict[str, str | None], key: str, row: int) -> str:
    """Return a required CSV value."""
    value = raw.get(key)
    if value is None or not value.strip():
        raise HousingTimeError(f"row {row}.{key} must be non-empty")
    return value.strip()


def _decimal_text(value: Decimal | None) -> str:
    """Serialize optional decimals without scientific notation."""
    return "" if value is None else format(value, "f")
