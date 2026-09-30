"""Stable housing-price transformation contract for INE JSON payloads."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast


class HousingTransformError(ValueError):
    """Raised when an INE housing payload violates the expected source contract."""


@dataclass(frozen=True, slots=True)
class HousingObservation:
    """One housing-price observation in the project-wide tabular contract."""

    indicator_code: str
    period_code: str
    geography_code: str
    geography_name: str
    category_code: str
    category_name: str
    value_eur_m2: Decimal | None


HOUSING_COLUMNS: tuple[str, ...] = (
    "indicator_code",
    "period_code",
    "geography_code",
    "geography_name",
    "category_code",
    "category_name",
    "value_eur_m2",
)


def parse_ine_housing_payload(payload: bytes) -> tuple[HousingObservation, ...]:
    """Flatten an INE JSON indicator payload into stable housing observations.

    INE returns a list of indicator objects. Each object contains a Dados
    mapping whose keys represent source period codes and whose values are lists
    of observations. Source period codes are preserved verbatim.

    Args:
        payload: Raw bytes captured from the INE JSON indicator endpoint.

    Returns:
        Observations in source order.

    Raises:
        HousingTransformError: If the JSON structure or required fields are
            malformed, or if a published value is not numeric.
    """
    try:
        parsed: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HousingTransformError("housing payload is not valid JSON") from exc

    if not isinstance(parsed, list) or not parsed:
        raise HousingTransformError("housing payload must be a non-empty JSON list")

    observations: list[HousingObservation] = []

    for indicator_index, indicator_raw in enumerate(parsed):
        indicator = _require_mapping(indicator_raw, f"indicator[{indicator_index}]")
        indicator_code = _require_string(indicator, "IndicadorCod", f"indicator[{indicator_index}]")
        data_raw = indicator.get("Dados")
        if not isinstance(data_raw, Mapping):
            raise HousingTransformError(f"indicator[{indicator_index}].Dados must be a JSON object")

        for period_raw, records_raw in data_raw.items():
            if not isinstance(period_raw, str) or not period_raw.strip():
                raise HousingTransformError("Dados period keys must be non-empty strings")
            period_code = period_raw.strip()

            if not isinstance(records_raw, list):
                raise HousingTransformError(f"Dados[{period_code!r}] must be a JSON list")

            for record_index, record_raw in enumerate(records_raw):
                context = f"Dados[{period_code!r}][{record_index}]"
                record = _require_mapping(record_raw, context)
                observations.append(
                    HousingObservation(
                        indicator_code=indicator_code,
                        period_code=period_code,
                        geography_code=_require_string(record, "geocod", context),
                        geography_name=_require_string(record, "geodsg", context),
                        category_code=_optional_string(record, "dim_3"),
                        category_name=_optional_string(record, "dim_3_t"),
                        value_eur_m2=_parse_value(record.get("valor"), context),
                    )
                )

    return tuple(observations)


def select_housing_observations(
    observations: Sequence[HousingObservation],
    *,
    geography_name: str,
    category_name: str = "Total",
) -> tuple[HousingObservation, ...]:
    """Select one named geography and dwelling category.

    Matching is exact after trimming and case folding. Geographic code prefixes
    are deliberately not inferred because INE coding systems differ between
    geographic standards.
    """
    geography_key = geography_name.strip().casefold()
    category_key = category_name.strip().casefold()

    return tuple(
        observation
        for observation in observations
        if observation.geography_name.casefold() == geography_key
        and observation.category_name.casefold() == category_key
    )


def write_housing_csv(
    observations: Sequence[HousingObservation],
    path: Path,
) -> None:
    """Write observations using the stable housing CSV contract.

    Existing files are never overwritten.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HOUSING_COLUMNS)

        for observation in observations:
            value = observation.value_eur_m2
            writer.writerow(
                (
                    observation.indicator_code,
                    observation.period_code,
                    observation.geography_code,
                    observation.geography_name,
                    observation.category_code,
                    observation.category_name,
                    "" if value is None else format(value, "f"),
                )
            )


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    """Validate and return a JSON object."""
    if not isinstance(value, Mapping):
        raise HousingTransformError(f"{context} must be a JSON object")
    return cast(Mapping[str, object], value)


def _require_string(
    record: Mapping[str, object],
    key: str,
    context: str,
) -> str:
    """Return a required non-empty string field."""
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HousingTransformError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _optional_string(record: Mapping[str, object], key: str) -> str:
    """Return a trimmed optional source dimension label."""
    value = record.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise HousingTransformError(f"{key} must be a string when present")
    return value.strip()


def _parse_value(value: object, context: str) -> Decimal | None:
    """Parse an INE numeric value while preserving missingness."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise HousingTransformError(f"{context}.valor must be a string or null")

    raw = value.strip()
    if not raw:
        return None

    try:
        return Decimal(raw.replace(",", "."))
    except InvalidOperation as exc:
        raise HousingTransformError(f"{context}.valor is not numeric: {raw!r}") from exc
