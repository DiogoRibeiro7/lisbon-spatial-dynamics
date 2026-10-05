"""Canonical INE dwelling-category medians with explicit unpublished observations."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from io import StringIO
from typing import Any

CATEGORIES = {"H1": "Total", "H11": "Novos", "H12": "Existentes"}
MISSING_DESCRIPTION = "Dado nulo ou não aplicável"
TITLE = (
    "Valor mediano das vendas de alojamentos familiares nos últimos 12 meses "
    "(Metodologia 2022 - €/ m²) por Localização geográfica (NUTS - 2024) e "
    "Categoria do alojamento familiar; Trimestral - INE, Estatísticas de preços "
    "da habitação ao nível local (Metodologia 2022)"
)
COLUMNS = (
    "year",
    "period_code",
    "freguesia_id",
    "freguesia_name",
    "indicator_code",
    "source_geography_code",
    "category_code",
    "category_name",
    "value_eur_m2",
    "source_flag",
    "source_flag_description",
)


@dataclass(frozen=True, slots=True)
class CategoryRow:
    """One requested category observation; a blank median is never a zero."""

    year: int
    freguesia_id: str
    freguesia_name: str
    category_code: str
    value_eur_m2: Decimal | None
    source_flag: str
    source_flag_description: str


def _document(payload: bytes) -> dict[str, Any]:
    document = json.loads(payload)
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise ValueError("expected exactly one INE indicator document")
    result: dict[str, Any] = document[0]
    if result.get("IndicadorCod") != "0012234" or result.get("Sucesso") != {
        "Verdadeiro": [{"Msg": "OK"}]
    }:
        raise ValueError("unexpected or unsuccessful housing indicator")
    return result


def parse_category_reference(
    payload: str, reference: Mapping[str, str], years: Sequence[int]
) -> tuple[CategoryRow, ...]:
    """Require every parish/year/category key, preserving INE's explicit '-' flag."""
    if (
        not reference
        or not years
        or len(set(years)) != len(years)
        or any(type(y) is not int or not 1 <= y <= 9999 for y in years)
    ):
        raise ValueError("nonempty reference and unique calendar years required")
    reader = csv.DictReader(StringIO(payload, newline=""))
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("unexpected category reference columns")
    rows: dict[tuple[int, str, str], CategoryRow] = {}
    for item in reader:
        if None in item or any(v is None for v in item.values()):
            raise ValueError("malformed category reference row")
        year, code, category = int(item["year"]), item["freguesia_id"], item["category_code"]
        if (
            str(year) != item["year"]
            or year not in years
            or code not in reference
            or category not in CATEGORIES
            or item["freguesia_name"] != reference[code]
            or item["category_name"] != CATEGORIES[category]
            or item["indicator_code"] != "0012234"
            or item["source_geography_code"] != f"1A0{code}"
            or item["period_code"] != f"4.º Trimestre de {year}"
        ):
            raise ValueError("category identity or Q4 period differs")
        raw, flag, description = (
            item["value_eur_m2"],
            item["source_flag"],
            item["source_flag_description"],
        )
        value = None
        if raw:
            if not raw.isascii() or not raw.isdigit() or int(raw) <= 0 or flag or description:
                raise ValueError("published median must be a positive integer without flags")
            value = Decimal(raw)
        elif (flag, description) != ("-", MISSING_DESCRIPTION):
            raise ValueError("missing median must retain the explicit INE source flag")
        key = (year, code, category)
        if key in rows:
            raise ValueError("duplicate category observation")
        rows[key] = CategoryRow(year, code, reference[code], category, value, flag, description)
    expected = {
        (year, code, category) for year in years for code in reference for category in CATEGORIES
    }
    if set(rows) != expected:
        raise ValueError("incomplete category coverage")
    return tuple(rows[key] for key in sorted(rows))


def extract_category_reference(
    data: bytes, metadata: bytes, reference: Mapping[str, str], years: Sequence[int]
) -> str:
    """Verify the source contract and extract a complete canonical category grid."""
    document, meta = _document(data), _document(metadata)
    if (
        document.get("IndicadorDsg") != TITLE
        or meta.get("IndicadorNome") != TITLE
        or meta.get("Periodic") != "Trimestral"
        or meta.get("Potencia10") != "0"
        or meta.get("PrecisaoDecimal") != "0"
        or meta.get("UnidadeMedida") != "Euro/ Metro quadrado (€/ m²)"
    ):
        raise ValueError("housing metadata differs from the category median contract")
    try:
        dimensions = {
            key: value
            for group in meta["Dimensoes"]["Categoria_Dim"]
            for key, value in group.items()
        }
        required = [
            *((1, f"S5A{year}4", f"4.º Trimestre de {year}") for year in years),
            *((2, f"1A0{code}", name) for code, name in reference.items()),
            *((3, code, name) for code, name in CATEGORIES.items()),
        ]
        for dimension, code, name in required:
            entries = dimensions[f"Dim_Num{dimension}_{code}"]
            if len(entries) != 1 or any(
                entries[0][key] != value
                for key, value in {
                    "dim_num": str(dimension),
                    "cat_id": code,
                    "categ_dsg": name,
                }.items()
            ):
                raise ValueError("housing dimension identity differs")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed housing dimension metadata") from exc
    observations = document.get("Dados")
    if not isinstance(observations, dict) or set(observations) != {
        f"4.º Trimestre de {year}" for year in years
    }:
        raise ValueError("housing category Q4 coverage differs")
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    for year in sorted(years):
        period = f"4.º Trimestre de {year}"
        records = observations[period]
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError("malformed category observations")
        for row in sorted(records, key=lambda r: (str(r.get("geocod")), str(r.get("dim_3")))):
            geo, category = row.get("geocod"), row.get("dim_3")
            if (
                not isinstance(geo, str)
                or geo not in {f"1A0{code}" for code in reference}
                or not isinstance(category, str)
                or category not in CATEGORIES
                or row.get("dim_3_t") != CATEGORIES[category]
                or row.get("geodsg") != reference[geo[3:]]
                or any(k.startswith("dim_") and k not in {"dim_3", "dim_3_t"} for k in row)
            ):
                raise ValueError("unexpected housing geography or category")
            value, flag, description = (
                row.get("valor"),
                row.get("sinal_conv", ""),
                row.get("sinal_conv_desc", ""),
            )
            displayed = row.get("ind_string")
            if value is None:
                if (flag, description, displayed) != ("-", MISSING_DESCRIPTION, "-"):
                    raise ValueError("unrecognised unpublished housing observation")
            elif (
                not isinstance(value, str)
                or not isinstance(displayed, str)
                or (displayed.replace(" ", "").replace("\u00a0", "") != value)
            ):
                raise ValueError("housing numeric and displayed medians differ")
            writer.writerow(
                [
                    year,
                    period,
                    geo[3:],
                    reference[geo[3:]],
                    "0012234",
                    geo,
                    category,
                    CATEGORIES[category],
                    value,
                    flag,
                    description,
                ]
            )
    result = stream.getvalue()
    parse_category_reference(result, reference, years)
    return result
