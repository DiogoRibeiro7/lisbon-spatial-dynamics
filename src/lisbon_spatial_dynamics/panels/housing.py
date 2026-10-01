"""Join current INE housing observations to canonical Lisbon freguesias."""

from __future__ import annotations

import csv
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from lisbon_spatial_dynamics.transformations.housing import HousingObservation

CURRENT_HOUSING_INDICATOR = "0012234"

PANEL_COLUMNS: tuple[str, ...] = (
    "period_code",
    "freguesia_id",
    "freguesia_name",
    "indicator_code",
    "source_geography_code",
    "source_geography_name",
    "category_code",
    "category_name",
    "value_eur_m2",
)


class HousingPanelError(ValueError):
    """Raised when housing observations cannot be joined safely."""


class HousingPanelCoverageError(HousingPanelError):
    """Raised when a period does not cover the full reference geography."""


@dataclass(frozen=True, slots=True)
class FreguesiaIndexRow:
    """Minimal canonical freguesia record used by the housing join."""

    freguesia_id: str
    name: str


@dataclass(frozen=True, slots=True)
class HousingPanelRow:
    """One canonical freguesia-period housing observation."""

    period_code: str
    freguesia_id: str
    freguesia_name: str
    indicator_code: str
    source_geography_code: str
    source_geography_name: str
    category_code: str
    category_name: str
    value_eur_m2: Decimal | None


def load_freguesia_index(
    path: Path,
    *,
    expected_count: int = 24,
) -> tuple[FreguesiaIndexRow, ...]:
    """Load the canonical freguesia index produced by the CAOP transform."""
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    rows: list[FreguesiaIndexRow] = []
    seen_ids: set[str] = set()

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)

        required = {"freguesia_id", "name"}
        fieldnames = set(reader.fieldnames or ())
        missing_columns = required - fieldnames
        if missing_columns:
            raise HousingPanelError(
                "reference CSV is missing columns: " + ", ".join(sorted(missing_columns))
            )

        for row_index, raw in enumerate(reader, start=2):
            freguesia_id = _required_csv_value(
                raw.get("freguesia_id"),
                f"row {row_index}.freguesia_id",
            )
            name = _required_csv_value(raw.get("name"), f"row {row_index}.name")

            if freguesia_id in seen_ids:
                raise HousingPanelError(f"duplicate freguesia_id in reference CSV: {freguesia_id}")

            seen_ids.add(freguesia_id)
            rows.append(FreguesiaIndexRow(freguesia_id=freguesia_id, name=name))

    if len(rows) != expected_count:
        raise HousingPanelError(
            f"unexpected reference freguesia count: {len(rows)} != {expected_count}"
        )

    return tuple(sorted(rows, key=lambda row: row.freguesia_id))


def build_current_housing_freguesia_panel(
    observations: Sequence[HousingObservation],
    reference: Sequence[FreguesiaIndexRow],
    *,
    category_name: str = "Total",
) -> tuple[HousingPanelRow, ...]:
    """Join current NUTS 2024 INE housing observations to canonical freguesias.

    The join does not hard-code the current NUTS prefix. Instead, each INE
    geography code must end with exactly one known canonical DTMNFR identifier,
    and the INE geography label must agree with the CAOP freguesia name.

    Every source period must contain all reference freguesias. A source record
    with a missing published value is valid and remains null; a missing
    freguesia record is a coverage error.
    """
    if not reference:
        raise HousingPanelError("reference geography cannot be empty")

    reference_by_id = _reference_mapping(reference)
    expected_ids = set(reference_by_id)
    category_key = _normalise_name(category_name)

    period_order: list[str] = []
    joined_by_period: dict[str, dict[str, HousingPanelRow]] = {}

    for observation in observations:
        if observation.indicator_code != CURRENT_HOUSING_INDICATOR:
            continue
        if _normalise_name(observation.category_name) != category_key:
            continue

        matched_ids = [
            freguesia_id
            for freguesia_id in reference_by_id
            if observation.geography_code.endswith(freguesia_id)
        ]

        if not matched_ids:
            continue
        if len(matched_ids) != 1:
            raise HousingPanelError(
                "INE geography code matches multiple canonical freguesias: "
                f"{observation.geography_code}"
            )

        freguesia_id = matched_ids[0]
        canonical = reference_by_id[freguesia_id]

        if _normalise_name(observation.geography_name) != _normalise_name(canonical.name):
            raise HousingPanelError(
                "INE/CAOP geography-name mismatch for "
                f"{freguesia_id}: {observation.geography_name!r} != "
                f"{canonical.name!r}"
            )

        if observation.period_code not in joined_by_period:
            period_order.append(observation.period_code)
            joined_by_period[observation.period_code] = {}

        period_rows = joined_by_period[observation.period_code]
        if freguesia_id in period_rows:
            raise HousingPanelError(
                f"duplicate housing observation for {observation.period_code} / {freguesia_id}"
            )

        period_rows[freguesia_id] = HousingPanelRow(
            period_code=observation.period_code,
            freguesia_id=freguesia_id,
            freguesia_name=canonical.name,
            indicator_code=observation.indicator_code,
            source_geography_code=observation.geography_code,
            source_geography_name=observation.geography_name,
            category_code=observation.category_code,
            category_name=observation.category_name,
            value_eur_m2=observation.value_eur_m2,
        )

    if not period_order:
        raise HousingPanelError(
            "no current INE freguesia observations matched the reference geography"
        )

    panel: list[HousingPanelRow] = []

    for period_code in period_order:
        period_rows = joined_by_period[period_code]
        missing_ids = expected_ids - set(period_rows)
        if missing_ids:
            raise HousingPanelCoverageError(
                f"{period_code} is missing canonical freguesias: " + ", ".join(sorted(missing_ids))
            )

        panel.extend(period_rows[freguesia_id] for freguesia_id in sorted(expected_ids))

    return tuple(panel)


def write_housing_panel_csv(
    rows: Sequence[HousingPanelRow],
    path: Path,
) -> None:
    """Write the canonical housing panel without overwriting existing output."""
    if not rows:
        raise HousingPanelError("housing panel cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(PANEL_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.period_code,
                    row.freguesia_id,
                    row.freguesia_name,
                    row.indicator_code,
                    row.source_geography_code,
                    row.source_geography_name,
                    row.category_code,
                    row.category_name,
                    "" if row.value_eur_m2 is None else format(row.value_eur_m2, "f"),
                )
            )


def _reference_mapping(
    reference: Sequence[FreguesiaIndexRow],
) -> dict[str, FreguesiaIndexRow]:
    """Build a unique canonical identifier mapping."""
    mapping: dict[str, FreguesiaIndexRow] = {}

    for row in reference:
        if not row.freguesia_id.strip():
            raise HousingPanelError("reference freguesia_id cannot be empty")
        if not row.name.strip():
            raise HousingPanelError("reference freguesia name cannot be empty")
        if row.freguesia_id in mapping:
            raise HousingPanelError(f"duplicate reference freguesia_id: {row.freguesia_id}")
        mapping[row.freguesia_id] = row

    return mapping


def _normalise_name(value: str) -> str:
    """Normalise administrative labels for validation-only comparisons."""
    normalised = unicodedata.normalize("NFKC", value)
    return " ".join(normalised.split()).casefold()


def _required_csv_value(value: str | None, context: str) -> str:
    """Return a required non-empty CSV field."""
    if value is None or not value.strip():
        raise HousingPanelError(f"{context} must be a non-empty string")
    return value.strip()
