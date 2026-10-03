"""Preserve CML's displayed historical values and expose arithmetic discrepancies."""

from __future__ import annotations

import csv
import re
from collections.abc import Mapping
from io import StringIO
from typing import Any

TABLES = {
    18: {
        "metric": "weighted_al",
        "unit": "capacity_weighted_al_units",
        "printed_page": 93,
        "pdf_page": 105,
    },
    19: {
        "metric": "capacity",
        "unit": "reported_user_capacity",
        "printed_page": 95,
        "pdf_page": 107,
    },
}
COLUMNS = (
    "table_number",
    "source_row",
    "geography_id",
    "geography_name",
    "value_2019_11",
    "value_2022_11",
    "reported_change",
)


def parse_reference(payload: str, *, expected_count: int) -> dict[str, str]:
    """Read canonical parish identities from the previously audited Census table."""
    reader = csv.DictReader(StringIO(payload))
    if not {"freguesia_id", "freguesia_name"} <= set(reader.fieldnames or []):
        raise ValueError("missing canonical reference columns")
    reference = {}
    for row in reader:
        code, name = row["freguesia_id"], row["freguesia_name"]
        if not re.fullmatch(r"1106[0-9]{2}", code) or code in reference or not name.strip():
            raise ValueError("invalid or duplicate canonical parish")
        reference[code] = name
    if expected_count <= 0 or len(reference) != expected_count:
        raise ValueError("canonical parish count mismatch")
    return reference


def _integer(value: str) -> int:
    if not re.fullmatch(r"-?(0|[1-9][0-9]*)", value):
        raise ValueError("published numeric fields must be explicit integers")
    return int(value)


def audit_transcription(
    payload: str, reference: Mapping[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate complete tables, keeping reported and calculated changes separate.

    Reference periods have month precision. Neither table is an unweighted
    registration series, and no end-of-month or quarter-end dates are invented.
    """
    if not reference:
        raise ValueError("canonical reference cannot be empty")
    reader = csv.DictReader(StringIO(payload))
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("unexpected benchmark transcription columns")
    tables: dict[int, dict[str, dict[str, Any]]] = {number: {} for number in TABLES}
    for raw in reader:
        if None in raw or any(value is None for value in raw.values()):
            raise ValueError("malformed benchmark row")
        table, source_row = _integer(raw["table_number"]), _integer(raw["source_row"])
        code, name = raw["geography_id"], raw["geography_name"]
        if table not in TABLES or code in tables[table]:
            raise ValueError("unknown table or duplicate geography")
        if code == "1106":
            if name != "LISBOA - TOTAL" or source_row != 0:
                raise ValueError("invalid published municipality total")
        elif code not in reference or reference[code] != name or source_row <= 0:
            raise ValueError("unknown parish, name mismatch or invalid source row")
        start, end, change = (_integer(raw[field]) for field in COLUMNS[-3:])
        if start < 0 or end < 0:
            raise ValueError("published levels cannot be negative")
        tables[table][code] = {
            "table_number": table,
            "source_row": source_row,
            "geography_id": code,
            "geography_name": name,
            "value_2019_11": start,
            "value_2022_11": end,
            "reported_change": change,
        }
    observations: list[dict[str, Any]] = []
    arithmetic: list[dict[str, Any]] = []
    summaries = []
    for table, indexed in tables.items():
        if set(indexed) != set(reference) | {"1106"}:
            raise ValueError(
                "each table must cover all canonical parishes and its municipality total"
            )
        parishes = [row for code, row in indexed.items() if code != "1106"]
        if sorted(row["source_row"] for row in parishes) != list(range(1, len(reference) + 1)):
            raise ValueError("parish source rows must be unique and consecutive")
        metadata = TABLES[table]
        mismatches = []
        for code in sorted(indexed):
            row = indexed[code]
            identity = {
                **metadata,
                "table_number": table,
                "geography_id": code,
                "geography_name": row["geography_name"],
                "scope": "municipality" if code == "1106" else "freguesia",
            }
            for period, field in (("2019-11", "value_2019_11"), ("2022-11", "value_2022_11")):
                observations.append(
                    {**identity, "reference_month": period, "published_value": row[field]}
                )
            calculated = row["value_2022_11"] - row["value_2019_11"]
            difference = calculated - row["reported_change"]
            arithmetic.append(
                {
                    **identity,
                    "published_change": row["reported_change"],
                    "calculated_change_from_displayed_levels": calculated,
                    "calculated_minus_published_change": difference,
                }
            )
            if difference:
                mismatches.append(
                    {"geography_id": code, "calculated_minus_published_change": difference}
                )
        total = indexed["1106"]
        column_checks = []
        for field in COLUMNS[-3:]:
            summed = sum(row[field] for row in parishes)
            column_checks.append(
                {
                    "field": field,
                    "parish_sum": summed,
                    "published_municipality": total[field],
                    "parish_sum_minus_published_municipality": summed - total[field],
                }
            )
        summaries.append(
            {
                **metadata,
                "table_number": table,
                "published_municipality_2019_11": total["value_2019_11"],
                "published_municipality_2022_11": total["value_2022_11"],
                "published_municipality_change": total["reported_change"],
                "calculated_municipality_change_from_displayed_levels": total["value_2022_11"]
                - total["value_2019_11"],
                "parishes_increased_from_displayed_levels": sum(
                    row["value_2022_11"] > row["value_2019_11"] for row in parishes
                ),
                "parishes_decreased_from_displayed_levels": sum(
                    row["value_2022_11"] < row["value_2019_11"] for row in parishes
                ),
                "row_change_discrepancies": mismatches,
                "column_sum_checks": column_checks,
            }
        )
    return (
        {
            "parishes": len(reference),
            "reference_months": ["2019-11", "2022-11"],
            "parish_observations": len(reference) * 4,
            "published_values_corrected": 0,
            "tables": summaries,
            "interpretation": (
                "Two published monthly-reference benchmarks, not a quarterly panel or unweighted "
                "registration counts. Displayed values and changes are preserved; discrepancies "
                "are diagnostics, and their cause is not inferred."
            ),
        },
        observations,
        arithmetic,
    )
