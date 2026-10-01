"""Compare two RNAL snapshots without interpreting membership changes as closures."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from datetime import date
from typing import Any

from lisbon_spatial_dynamics.panels.housing import FreguesiaIndexRow
from lisbon_spatial_dynamics.panels.rnal import RNALRecord
from lisbon_spatial_dynamics.sources.rnal_geodata import epoch_date, validate_records


def _name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def compare_snapshots(
    soap: Sequence[RNALRecord],
    gis: list[dict[str, Any]],
    reference: Sequence[FreguesiaIndexRow],
    *,
    benchmark_date: date,
    benchmark_count: int,
    early_before: date = date(2000, 1, 1),
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    """Return only aggregate coverage, disagreements and date-screening evidence.

    SOAP and GIS are two interfaces to the same provider. Agreement is not an
    independent validation of the registry or evidence of historical completeness.
    """
    validate_records(gis)
    if not soap or benchmark_count <= 0:
        raise ValueError("SOAP records and a positive historical benchmark are required")
    parishes = {row.freguesia_id: row.name for row in reference}
    if not parishes or len(parishes) != len(reference):
        raise ValueError("reference must contain unique parishes")
    soap_by_id: dict[int, RNALRecord] = {}
    for row in soap:
        if not re.fullmatch(r"[0-9]+/AL", row.registration_id):
            raise ValueError("SOAP registration ID must have digits/AL format")
        number = int(row.registration_id[:-3])
        if number <= 0 or number in soap_by_id:
            raise ValueError("duplicate or invalid normalized SOAP registration ID")
        soap_by_id[number] = row
        if row.freguesia_id not in parishes:
            raise ValueError("SOAP record has unknown parish")
    gis_by_id = {row["NrRNAL"]: row for row in gis}
    if any(row["DTMNFR"] not in parishes for row in gis):
        raise ValueError("GIS record has unknown parish")
    shared = soap_by_id.keys() & gis_by_id.keys()
    only_soap = soap_by_id.keys() - gis_by_id.keys()
    only_gis = gis_by_id.keys() - soap_by_id.keys()

    def mismatches(ids: set[int], field: str) -> int:
        return sum(
            {
                "registration_date": soap_by_id[key].registered_on,
                "parish": soap_by_id[key].freguesia_id,
                "users": soap_by_id[key].users,
            }[field]
            != {
                "registration_date": epoch_date(gis_by_id[key]["DataRegisto"]),
                "parish": gis_by_id[key]["DTMNFR"],
                "users": gis_by_id[key]["NrUtentes"],
            }[field]
            for key in ids
        )

    rows: list[dict[str, object]] = []
    for parish, name in sorted(parishes.items()):
        soap_ids = {key for key, row in soap_by_id.items() if row.freguesia_id == parish}
        gis_ids = {key for key, row in gis_by_id.items() if row["DTMNFR"] == parish}
        rows.append(
            {
                "freguesia_id": parish,
                "freguesia_name": name,
                "soap_records": len(soap_ids),
                "gis_records": len(gis_ids),
                "shared_same_parish": len(soap_ids & gis_ids),
                "soap_only": len(soap_ids & only_soap),
                "gis_only": len(gis_ids & only_gis),
                "shared_parish_disagreements_by_soap_parish": mismatches(
                    soap_ids & shared, "parish"
                ),
                "registration_date_disagreements_by_soap_parish": mismatches(
                    soap_ids & shared, "registration_date"
                ),
                "capacity_disagreements_by_soap_parish": mismatches(soap_ids & shared, "users"),
            }
        )
    soap_early = {key for key, row in soap_by_id.items() if row.registered_on < early_before}
    gis_dates = {key: epoch_date(row["DataRegisto"]) for key, row in gis_by_id.items()}
    gis_early = {key for key, value in gis_dates.items() if value and value < early_before}
    early_rows: list[dict[str, object]] = []
    years = {soap_by_id[key].registered_on.year for key in soap_early} | {
        value.year for key, value in gis_dates.items() if key in gis_early and value
    }
    for year in sorted(years):
        soap_ids = {key for key in soap_early if soap_by_id[key].registered_on.year == year}
        gis_ids = {
            key
            for key, value in gis_dates.items()
            if key in gis_early and value and value.year == year
        }
        early_rows.append(
            {
                "registration_year": year,
                "soap_records": len(soap_ids),
                "gis_records": len(gis_ids),
                "shared_with_same_registration_date": sum(
                    soap_by_id[key].registered_on == gis_dates[key] for key in soap_ids & gis_ids
                ),
                "gis_opening_before_screen": sum(
                    opened is not None and opened < early_before
                    for key in gis_ids
                    for opened in [epoch_date(gis_by_id[key]["DataAberturaPublico"])]
                ),
                "gis_opening_missing": sum(
                    gis_by_id[key]["DataAberturaPublico"] is None for key in gis_ids
                ),
            }
        )
    reconstructed = sum(
        row.registered_on <= benchmark_date
        and (row.ceased_on is None or row.ceased_on > benchmark_date)
        for row in soap
    )
    summary: dict[str, object] = {
        "soap_records": len(soap),
        "gis_records": len(gis),
        "shared_ids": len(shared),
        "soap_only_ids": len(only_soap),
        "gis_only_ids": len(only_gis),
        "gis_only_registration_years": dict(
            sorted(
                Counter(
                    value.year for key, value in gis_dates.items() if key in only_gis and value
                ).items()
            )
        ),
        "shared_registration_date_disagreements": mismatches(shared, "registration_date"),
        "shared_parish_disagreements": mismatches(shared, "parish"),
        "parish_assignment_disagreement_pairs": [
            {"soap_freguesia_id": pair[0], "gis_freguesia_id": pair[1], "records": count}
            for pair, count in sorted(
                Counter(
                    (soap_by_id[key].freguesia_id, gis_by_id[key]["DTMNFR"])
                    for key in shared
                    if soap_by_id[key].freguesia_id != gis_by_id[key]["DTMNFR"]
                ).items()
            )
        ],
        "shared_capacity_disagreements": mismatches(shared, "users"),
        "soap_parish_name_disagreements": sum(
            _name(row.freguesia_name) != _name(parishes[row.freguesia_id]) for row in soap
        ),
        "gis_parish_name_disagreements": sum(
            _name(row["Freguesia"]) != _name(parishes[row["DTMNFR"]]) for row in gis
        ),
        "soap_populated_cessation_dates": sum(row.ceased_on is not None for row in soap),
        "early_date_screen_before": early_before.isoformat(),
        "soap_early_dates": len(soap_early),
        "gis_early_dates": len(gis_early),
        "benchmark": {
            "date": benchmark_date.isoformat(),
            "published_registrations": benchmark_count,
            "soap_snapshot_cohort_at_date": reconstructed,
            "snapshot_cohort_minus_published": reconstructed - benchmark_count,
            "snapshot_cohort_percent_of_published": round(100 * reconstructed / benchmark_count, 4),
            "interpretation": "coverage discrepancy, not a count of identified closures",
        },
        "historical_completeness_established": False,
        "membership_differences_are_closure_events": False,
    }
    return summary, rows, early_rows
