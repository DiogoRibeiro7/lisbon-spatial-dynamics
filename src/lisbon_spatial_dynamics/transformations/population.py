"""Build a static 2021 population reference from Censos subsection data."""

from __future__ import annotations

import csv
import io
import math
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class CensusPopulationError(ValueError):
    """Raised when census population data cannot form the canonical reference."""


@dataclass(frozen=True, slots=True)
class CensusPopulationRow:
    """One canonical freguesia population reference for Censos 2021."""

    freguesia_id: str
    freguesia_name: str
    census_year: int
    population_resident: int
    area_ha: float
    population_density_per_km2: float


POPULATION_COLUMNS: tuple[str, ...] = (
    "freguesia_id",
    "freguesia_name",
    "census_year",
    "population_resident",
    "area_ha",
    "population_density_per_km2",
)

_REQUIRED_SOURCE_COLUMNS = {"DTMNFR21", "N_INDIVIDUOS"}


def build_census_population_reference(
    archive_path: Path,
    reference_csv: Path,
    *,
    expected_count: int = 24,
) -> tuple[CensusPopulationRow, ...]:
    """Aggregate national Censos 2021 subsection counts to Lisbon freguesias."""
    reference = _load_reference(reference_csv, expected_count=expected_count)
    population_by_id = {
        freguesia_id: 0
        for freguesia_id in reference
    }
    matched_subsections = 0

    with zipfile.ZipFile(archive_path) as archive:
        member_name, reader = _find_synthesis_table(archive)

        for row_index, row in enumerate(reader, start=2):
            freguesia_id = _required_text(
                row.get("DTMNFR21"),
                f"{member_name}:row {row_index}.DTMNFR21",
            )

            if freguesia_id not in population_by_id:
                continue

            population = _parse_non_negative_int(
                row.get("N_INDIVIDUOS"),
                f"{member_name}:row {row_index}.N_INDIVIDUOS",
            )
            population_by_id[freguesia_id] += population
            matched_subsections += 1

    if matched_subsections == 0:
        raise CensusPopulationError(
            "census archive contains no subsections for canonical Lisboa freguesias"
        )

    rows: list[CensusPopulationRow] = []

    for freguesia_id in sorted(reference):
        name, area_ha = reference[freguesia_id]
        population = population_by_id[freguesia_id]

        if population <= 0:
            raise CensusPopulationError(
                f"{freguesia_id} has non-positive aggregated population"
            )

        rows.append(
            CensusPopulationRow(
                freguesia_id=freguesia_id,
                freguesia_name=name,
                census_year=2021,
                population_resident=population,
                area_ha=area_ha,
                population_density_per_km2=population / (area_ha / 100.0),
            )
        )

    return tuple(rows)


def write_census_population_csv(
    rows: tuple[CensusPopulationRow, ...],
    path: Path,
) -> None:
    """Write the static population reference without overwriting."""
    if not rows:
        raise CensusPopulationError("population reference cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(POPULATION_COLUMNS)

        for row in rows:
            writer.writerow(
                (
                    row.freguesia_id,
                    row.freguesia_name,
                    row.census_year,
                    row.population_resident,
                    format(row.area_ha, ".12g"),
                    format(row.population_density_per_km2, ".12g"),
                )
            )


def _find_synthesis_table(
    archive: zipfile.ZipFile,
) -> tuple[str, csv.DictReader[str]]:
    """Find the text table containing required Census synthesis columns."""
    candidates = [
        member
        for member in archive.infolist()
        if not member.is_dir()
        and Path(member.filename).suffix.casefold() in {".csv", ".txt"}
    ]

    for member in candidates:
        payload = archive.read(member)
        text = _decode_text(payload)

        try:
            dialect = csv.Sniffer().sniff(
                text[:8192],
                delimiters=";,\t|",
            )
        except csv.Error:
            continue

        stream = io.StringIO(text)
        reader = csv.DictReader(stream, dialect=dialect)
        fieldnames = {
            field.strip()
            for field in (reader.fieldnames or ())
            if field is not None
        }

        if _REQUIRED_SOURCE_COLUMNS.issubset(fieldnames):
            return member.filename, reader

    raise CensusPopulationError(
        "could not find a census synthesis table containing "
        "DTMNFR21 and N_INDIVIDUOS"
    )


def _load_reference(
    path: Path,
    *,
    expected_count: int,
) -> dict[str, tuple[str, float]]:
    """Load canonical freguesia names and official CAOP area."""
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    reference: dict[str, tuple[str, float]] = {}

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"freguesia_id", "name", "area_ha"}
        missing = required - set(reader.fieldnames or ())

        if missing:
            raise CensusPopulationError(
                "reference CSV is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row_index, row in enumerate(reader, start=2):
            freguesia_id = _required_text(
                row.get("freguesia_id"),
                f"reference row {row_index}.freguesia_id",
            )
            name = _required_text(
                row.get("name"),
                f"reference row {row_index}.name",
            )
            area_ha = _parse_positive_float(
                row.get("area_ha"),
                f"reference row {row_index}.area_ha",
            )

            if freguesia_id in reference:
                raise CensusPopulationError(
                    f"duplicate reference freguesia_id: {freguesia_id}"
                )

            reference[freguesia_id] = (name, area_ha)

    if len(reference) != expected_count:
        raise CensusPopulationError(
            f"unexpected reference freguesia count: "
            f"{len(reference)} != {expected_count}"
        )

    return reference


def _decode_text(payload: bytes) -> str:
    """Decode INE text payload using explicit supported encodings."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise CensusPopulationError(
        "census synthesis table has an unsupported text encoding"
    )


def _required_text(value: str | None, context: str) -> str:
    """Return a required non-empty text field."""
    if value is None or not value.strip():
        raise CensusPopulationError(f"{context} must be non-empty")
    return value.strip()


def _parse_non_negative_int(
    value: str | None,
    context: str,
) -> int:
    """Parse a non-negative integer, accepting integer-valued decimals."""
    raw = _required_text(value, context).replace(",", ".")

    try:
        number = float(raw)
    except ValueError as exc:
        raise CensusPopulationError(
            f"{context} must be numeric"
        ) from exc

    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise CensusPopulationError(
            f"{context} must be a non-negative integer"
        )

    return int(number)


def _parse_positive_float(
    value: str | None,
    context: str,
) -> float:
    """Parse a positive finite float."""
    raw = _required_text(value, context).replace(",", ".")

    try:
        number = float(raw)
    except ValueError as exc:
        raise CensusPopulationError(
            f"{context} must be numeric"
        ) from exc

    if not math.isfinite(number) or number <= 0:
        raise CensusPopulationError(
            f"{context} must be positive and finite"
        )

    return number
