"""Aggregate Censos 2021 subsection structure to canonical Lisboa freguesias."""

from __future__ import annotations

import csv
import io
import math
import unicodedata
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from lisbon_spatial_dynamics.spatial.annual_maps import ReferenceFeature


class CensusContextError(ValueError):
    """Raised when census structure cannot form the canonical context layer."""


@dataclass(frozen=True, slots=True)
class CensusContextRow:
    """Static 2021 demographic and built-environment context for one freguesia."""

    freguesia_id: str
    freguesia_name: str
    census_year: int
    population_resident: int
    classic_buildings: int
    pre1945_buildings: int
    repair_needed_buildings: int
    total_dwellings: int
    family_dwellings: int
    usual_residence_dwellings: int
    vacant_or_secondary_dwellings: int
    owner_occupied_dwellings: int
    rented_dwellings: int
    private_households: int
    age_0_14: int
    age_15_24: int
    age_25_64: int
    age_65_plus: int
    age_0_14_pct: Decimal
    age_15_24_pct: Decimal
    age_25_64_pct: Decimal
    age_65_plus_pct: Decimal
    owner_occupied_share_pct: Decimal
    rented_share_pct: Decimal
    vacant_or_secondary_family_share_pct: Decimal
    pre1945_building_share_pct: Decimal
    repair_needed_building_share_pct: Decimal
    dwellings_per_classic_building: Decimal


CENSUS_CONTEXT_COLUMNS: tuple[str, ...] = (
    "freguesia_id",
    "freguesia_name",
    "census_year",
    "population_resident",
    "classic_buildings",
    "pre1945_buildings",
    "repair_needed_buildings",
    "total_dwellings",
    "family_dwellings",
    "usual_residence_dwellings",
    "vacant_or_secondary_dwellings",
    "owner_occupied_dwellings",
    "rented_dwellings",
    "private_households",
    "age_0_14",
    "age_15_24",
    "age_25_64",
    "age_65_plus",
    "age_0_14_pct",
    "age_15_24_pct",
    "age_25_64_pct",
    "age_65_plus_pct",
    "owner_occupied_share_pct",
    "rented_share_pct",
    "vacant_or_secondary_family_share_pct",
    "pre1945_building_share_pct",
    "repair_needed_building_share_pct",
    "dwellings_per_classic_building",
)


_SOURCE_COLUMNS: Mapping[str, str] = {
    "population_resident": "N_INDIVIDUOS",
    "classic_buildings": "N_EDIFICIOS_CLASSICOS",
    "pre1945_buildings": "N_EDIFICIOS_CONSTR_ANTES 1945",
    "repair_needed_buildings": "N_EDIFICIOS_COM NECESSIDADES REPARAÇAO",
    "total_dwellings": "N_ALOJAMENTOS_TOTAL",
    "family_dwellings": "N_ALOJAMENTOS_FAMILIARES",
    "usual_residence_dwellings": "N_ALOJAMENTOS_ FAM_CLASS_RHABITUAL",
    "vacant_or_secondary_dwellings": (
        "N_ALOJAMENTOS_ FAM_CLASS_VAGOS OU RESID SECUNDARIA"
    ),
    "owner_occupied_dwellings": "N_RHABITUAL_PROP_OCUP",
    "rented_dwellings": "N_RHABITUAL_ARRENDADOS",
    "private_households": "N_AGREGADOS DOMESTICOS PRIVADOS",
    "age_0_14": "N_INDIVIDUOS_0A14",
    "age_15_24": "N_INDIVIDUOS_15A24",
    "age_25_64": "N_INDIVIDUOS_25A64",
    "age_65_plus": "N_INDIVIDUOS_65_OU_MAIS",
}

_REQUIRED_HEADERS = {
    _normalize_header("DTMNFR21"),
    *(_normalize_header(value) for value in _SOURCE_COLUMNS.values()),
}


def build_census2021_context(
    archive_path: Path,
    reference_csv: Path,
    *,
    expected_count: int = 24,
) -> tuple[CensusContextRow, ...]:
    """Aggregate official subsection counts to the canonical Lisboa freguesias."""
    reference = _load_reference(reference_csv, expected_count=expected_count)
    totals: dict[str, dict[str, int]] = {
        freguesia_id: {field: 0 for field in _SOURCE_COLUMNS}
        for freguesia_id in reference
    }
    matched_subsections = 0

    with zipfile.ZipFile(archive_path) as archive:
        member_name, reader = _find_synthesis_table(archive)

        for row_index, raw_row in enumerate(reader, start=2):
            row = {
                _normalize_header(key): value
                for key, value in raw_row.items()
                if key is not None
            }
            freguesia_id = _required_text(
                row.get(_normalize_header("DTMNFR21")),
                f"{member_name}:row {row_index}.DTMNFR21",
            )

            if freguesia_id not in totals:
                continue

            for target_field, source_field in _SOURCE_COLUMNS.items():
                totals[freguesia_id][target_field] += _parse_non_negative_int(
                    row.get(_normalize_header(source_field)),
                    f"{member_name}:row {row_index}.{source_field}",
                )

            matched_subsections += 1

    if matched_subsections == 0:
        raise CensusContextError(
            "census archive contains no subsections for canonical Lisboa freguesias"
        )

    output: list[CensusContextRow] = []

    for freguesia_id in sorted(reference):
        name = reference[freguesia_id]
        values = totals[freguesia_id]
        _validate_aggregates(freguesia_id, values)

        population = values["population_resident"]
        classic_buildings = values["classic_buildings"]
        family_dwellings = values["family_dwellings"]
        usual_residence = values["usual_residence_dwellings"]

        output.append(
            CensusContextRow(
                freguesia_id=freguesia_id,
                freguesia_name=name,
                census_year=2021,
                population_resident=population,
                classic_buildings=classic_buildings,
                pre1945_buildings=values["pre1945_buildings"],
                repair_needed_buildings=values["repair_needed_buildings"],
                total_dwellings=values["total_dwellings"],
                family_dwellings=family_dwellings,
                usual_residence_dwellings=usual_residence,
                vacant_or_secondary_dwellings=values[
                    "vacant_or_secondary_dwellings"
                ],
                owner_occupied_dwellings=values["owner_occupied_dwellings"],
                rented_dwellings=values["rented_dwellings"],
                private_households=values["private_households"],
                age_0_14=values["age_0_14"],
                age_15_24=values["age_15_24"],
                age_25_64=values["age_25_64"],
                age_65_plus=values["age_65_plus"],
                age_0_14_pct=_pct(values["age_0_14"], population),
                age_15_24_pct=_pct(values["age_15_24"], population),
                age_25_64_pct=_pct(values["age_25_64"], population),
                age_65_plus_pct=_pct(values["age_65_plus"], population),
                owner_occupied_share_pct=_pct(
                    values["owner_occupied_dwellings"],
                    usual_residence,
                ),
                rented_share_pct=_pct(
                    values["rented_dwellings"],
                    usual_residence,
                ),
                vacant_or_secondary_family_share_pct=_pct(
                    values["vacant_or_secondary_dwellings"],
                    family_dwellings,
                ),
                pre1945_building_share_pct=_pct(
                    values["pre1945_buildings"],
                    classic_buildings,
                ),
                repair_needed_building_share_pct=_pct(
                    values["repair_needed_buildings"],
                    classic_buildings,
                ),
                dwellings_per_classic_building=(
                    Decimal(values["total_dwellings"])
                    / Decimal(classic_buildings)
                ),
            )
        )

    return tuple(output)


def write_census2021_context_csv(
    rows: Sequence[CensusContextRow],
    path: Path,
) -> None:
    """Write the static census context table without overwriting."""
    if not rows:
        raise CensusContextError("census context cannot be empty")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(CENSUS_CONTEXT_COLUMNS)

        for row in rows:
            writer.writerow(_context_values(row))


def build_census2021_context_geojson(
    rows: Sequence[CensusContextRow],
    reference: Sequence[ReferenceFeature],
) -> dict[str, object]:
    """Join static census context to the exact canonical freguesia geometry."""
    if not rows:
        raise CensusContextError("census context cannot be empty")
    if not reference:
        raise CensusContextError("reference geometry cannot be empty")

    row_by_id = _unique_context_mapping(rows)
    reference_by_id = _unique_reference_mapping(reference)

    if set(row_by_id) != set(reference_by_id):
        missing = sorted(set(reference_by_id) - set(row_by_id))
        extra = sorted(set(row_by_id) - set(reference_by_id))
        raise CensusContextError(
            f"context/reference key mismatch; missing={missing}, extra={extra}"
        )

    features: list[dict[str, object]] = []

    for freguesia_id in sorted(reference_by_id):
        row = row_by_id[freguesia_id]
        feature = reference_by_id[freguesia_id]

        if row.freguesia_name != feature.name:
            raise CensusContextError(
                f"{freguesia_id} name mismatch: "
                f"{row.freguesia_name!r} != {feature.name!r}"
            )

        properties = dict(feature.properties)
        properties.update(_context_properties(row))

        features.append(
            {
                "type": "Feature",
                "id": freguesia_id,
                "properties": properties,
                "geometry": dict(feature.geometry),
            }
        )

    return {
        "type": "FeatureCollection",
        "name": "lisbon_census2021_context",
        "census_year": 2021,
        "feature_count": len(features),
        "features": features,
    }


def write_census2021_context_geojson(
    document: Mapping[str, object],
    path: Path,
) -> None:
    """Write the static context GeoJSON without overwriting."""
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)


def _find_synthesis_table(
    archive: zipfile.ZipFile,
) -> tuple[str, csv.DictReader[str]]:
    """Find the text table containing all required context columns."""
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
        normalized_fields = {
            _normalize_header(field)
            for field in (reader.fieldnames or ())
            if field is not None
        }

        if _REQUIRED_HEADERS.issubset(normalized_fields):
            return member.filename, reader

    raise CensusContextError(
        "could not find a census synthesis table containing the required "
        "2021 demographic and housing variables"
    )


def _load_reference(
    path: Path,
    *,
    expected_count: int,
) -> dict[str, str]:
    """Load canonical freguesia identifiers and names."""
    if expected_count <= 0:
        raise ValueError("expected_count must be positive")

    reference: dict[str, str] = {}

    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"freguesia_id", "name"}
        missing = required - set(reader.fieldnames or ())

        if missing:
            raise CensusContextError(
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

            if freguesia_id in reference:
                raise CensusContextError(
                    f"duplicate reference freguesia_id: {freguesia_id}"
                )
            reference[freguesia_id] = name

    if len(reference) != expected_count:
        raise CensusContextError(
            f"unexpected reference freguesia count: "
            f"{len(reference)} != {expected_count}"
        )

    return reference


def _validate_aggregates(
    freguesia_id: str,
    values: Mapping[str, int],
) -> None:
    """Validate core consistency relationships after subsection aggregation."""
    for field in (
        "population_resident",
        "classic_buildings",
        "family_dwellings",
        "usual_residence_dwellings",
    ):
        if values[field] <= 0:
            raise CensusContextError(
                f"{freguesia_id} has non-positive {field}"
            )

    age_total = (
        values["age_0_14"]
        + values["age_15_24"]
        + values["age_25_64"]
        + values["age_65_plus"]
    )
    if age_total != values["population_resident"]:
        raise CensusContextError(
            f"{freguesia_id} age bands do not sum to total population"
        )

    if (
        values["owner_occupied_dwellings"]
        + values["rented_dwellings"]
        > values["usual_residence_dwellings"]
    ):
        raise CensusContextError(
            f"{freguesia_id} owner+rented dwellings exceed usual residences"
        )

    if (
        values["vacant_or_secondary_dwellings"]
        > values["family_dwellings"]
    ):
        raise CensusContextError(
            f"{freguesia_id} vacant/secondary dwellings exceed family dwellings"
        )

    for numerator in (
        "pre1945_buildings",
        "repair_needed_buildings",
    ):
        if values[numerator] > values["classic_buildings"]:
            raise CensusContextError(
                f"{freguesia_id} {numerator} exceeds classic buildings"
            )


def _context_values(row: CensusContextRow) -> tuple[object, ...]:
    """Return stable CSV values for one context row."""
    return (
        row.freguesia_id,
        row.freguesia_name,
        row.census_year,
        row.population_resident,
        row.classic_buildings,
        row.pre1945_buildings,
        row.repair_needed_buildings,
        row.total_dwellings,
        row.family_dwellings,
        row.usual_residence_dwellings,
        row.vacant_or_secondary_dwellings,
        row.owner_occupied_dwellings,
        row.rented_dwellings,
        row.private_households,
        row.age_0_14,
        row.age_15_24,
        row.age_25_64,
        row.age_65_plus,
        _decimal_text(row.age_0_14_pct),
        _decimal_text(row.age_15_24_pct),
        _decimal_text(row.age_25_64_pct),
        _decimal_text(row.age_65_plus_pct),
        _decimal_text(row.owner_occupied_share_pct),
        _decimal_text(row.rented_share_pct),
        _decimal_text(row.vacant_or_secondary_family_share_pct),
        _decimal_text(row.pre1945_building_share_pct),
        _decimal_text(row.repair_needed_building_share_pct),
        _decimal_text(row.dwellings_per_classic_building),
    )


def _context_properties(row: CensusContextRow) -> dict[str, object]:
    """Return interoperable GeoJSON properties for one context row."""
    values = _context_values(row)
    return {
        column: _json_value(value)
        for column, value in zip(CENSUS_CONTEXT_COLUMNS, values, strict=True)
        if column not in {"freguesia_id", "freguesia_name"}
    }


def _unique_context_mapping(
    rows: Sequence[CensusContextRow],
) -> dict[str, CensusContextRow]:
    """Build a unique context mapping."""
    mapping: dict[str, CensusContextRow] = {}

    for row in rows:
        if row.freguesia_id in mapping:
            raise CensusContextError(
                f"duplicate context freguesia_id: {row.freguesia_id}"
            )
        mapping[row.freguesia_id] = row

    return mapping


def _unique_reference_mapping(
    reference: Sequence[ReferenceFeature],
) -> dict[str, ReferenceFeature]:
    """Build a unique reference-feature mapping."""
    mapping: dict[str, ReferenceFeature] = {}

    for feature in reference:
        if feature.freguesia_id in mapping:
            raise CensusContextError(
                f"duplicate reference freguesia_id: {feature.freguesia_id}"
            )
        mapping[feature.freguesia_id] = feature

    return mapping


def _normalize_header(value: str) -> str:
    """Normalize source header whitespace and Unicode without changing semantics."""
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().split())


def _decode_text(payload: bytes) -> str:
    """Decode INE text payload using explicit supported encodings."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise CensusContextError(
        "census synthesis table has an unsupported text encoding"
    )


def _required_text(value: str | None, context: str) -> str:
    """Return a required non-empty text field."""
    if value is None or not value.strip():
        raise CensusContextError(f"{context} must be non-empty")
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
        raise CensusContextError(f"{context} must be numeric") from exc

    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise CensusContextError(
            f"{context} must be a non-negative integer"
        )

    return int(number)


def _pct(numerator: int, denominator: int) -> Decimal:
    """Return a percentage from positive integer denominator."""
    if denominator <= 0:
        raise CensusContextError("percentage denominator must be positive")
    return Decimal(numerator) * Decimal("100") / Decimal(denominator)


def _decimal_text(value: Decimal) -> str:
    """Serialize Decimal without scientific notation."""
    return format(value, "f")


def _json_value(value: object) -> object:
    """Convert Decimal CSV values to GeoJSON-compatible numeric values."""
    if isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        return float(value)
    return value
