"""Strict national annual CPI extraction and a small, reproducible reference contract."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any

CPI_CODE = "0014642"
CPI_BASE = 2025
CPI_TITLE = (
    "Índice de preços no consumidor (IPC, Base - 2025) por Localização geográfica "
    "e Agregados especiais; Anual - INE, Índice de preços no consumidor"
)
CPI_COLUMNS = (
    "year",
    "indicator_code",
    "index_base_year",
    "geography_code",
    "geography_name",
    "aggregate_code",
    "aggregate_name",
    "cpi_index",
)


def _positive_decimal(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("CPI value must be a numeric string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid CPI value") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("CPI values must be finite and positive")
    return result


def _document(payload: bytes) -> dict[str, Any]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise ValueError("expected one INE indicator document")
    document: dict[str, Any] = parsed[0]
    if document.get("IndicadorCod") != CPI_CODE or document.get("Sucesso") != {
        "Verdadeiro": [{"Msg": "OK"}]
    }:
        raise ValueError("unsuccessful or unexpected INE CPI indicator")
    return document


def extract_cpi_reference(data: bytes, metadata: bytes, years: Sequence[int]) -> str:
    """Extract exactly the requested Portugal/Total annual index observations."""
    document, meta = _document(data), _document(metadata)
    if (
        document.get("IndicadorDsg") != CPI_TITLE
        or meta.get("IndicadorNome") != CPI_TITLE
        or meta.get("Periodic") != "Anual"
        or meta.get("Potencia10") != "0"
        or meta.get("PrecisaoDecimal") != "3"
    ):
        raise ValueError("CPI metadata differs from the annual 2025-base contract")
    try:
        categories = {
            key: value
            for group in meta["Dimensoes"]["Categoria_Dim"]
            for key, value in group.items()
        }
        for dimension, code, name in (
            (2, "PT", "Portugal"),
            (3, "T", "Total"),
            *((1, f"S7A{year}", str(year)) for year in years),
        ):
            entries = categories[f"Dim_Num{dimension}_{code}"]
            if len(entries) != 1 or any(
                entries[0][key] != expected
                for key, expected in {
                    "dim_num": str(dimension),
                    "categ_cod": code,
                    "categ_dsg": name,
                }.items()
            ):
                raise ValueError("CPI dimension identity differs")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("missing or malformed CPI dimension metadata") from exc
    observations = document.get("Dados")
    if not isinstance(observations, dict) or set(observations) != {str(year) for year in years}:
        raise ValueError("CPI annual coverage differs")
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CPI_COLUMNS)
    for year in sorted(years):
        rows = observations[str(year)]
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("CPI requires exactly one observation per year")
        row = rows[0]
        if (
            row.get("geocod") != "PT"
            or row.get("geodsg") != "Portugal"
            or row.get("dim_3") != "T"
            or row.get("dim_3_t") != "Total"
            or row.get("sinal_conv")
            or any(key.startswith("dim_") and key not in {"dim_3", "dim_3_t"} for key in row)
        ):
            raise ValueError("CPI scope or observation flag differs")
        value = _positive_decimal(row.get("valor"))
        displayed = row.get("ind_string")
        if (
            not isinstance(displayed, str)
            or _positive_decimal(displayed.replace(",", ".")) != value
        ):
            raise ValueError("CPI displayed and numeric values differ")
        writer.writerow([year, CPI_CODE, CPI_BASE, "PT", "Portugal", "T", "Total", value])
    result = stream.getvalue()
    parse_cpi_reference(result, years)
    return result


def parse_cpi_reference(payload: str, years: Sequence[int]) -> dict[int, Decimal]:
    """Reject mixed bases/scopes, nonpositive values and incomplete or duplicate years."""
    if (
        not years
        or len(set(years)) != len(years)
        or any(type(y) is not int or not 1 <= y <= 9999 for y in years)
    ):
        raise ValueError("unique calendar years required")
    reader = csv.DictReader(StringIO(payload, newline=""))
    if tuple(reader.fieldnames or ()) != CPI_COLUMNS:
        raise ValueError("unexpected CPI reference columns")
    values = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed CPI reference row")
        if any(
            row[key] != expected
            for key, expected in {
                "indicator_code": CPI_CODE,
                "index_base_year": str(CPI_BASE),
                "geography_code": "PT",
                "geography_name": "Portugal",
                "aggregate_code": "T",
                "aggregate_name": "Total",
            }.items()
        ):
            raise ValueError("CPI reference scope or base differs")
        year = int(row["year"])
        if str(year) != row["year"] or year in values:
            raise ValueError("duplicate or malformed CPI year")
        value = _positive_decimal(row["cpi_index"])
        if year == CPI_BASE and value != Decimal(100):
            raise ValueError("CPI base-year index must equal 100")
        values[year] = value
    if set(values) != set(years):
        raise ValueError("CPI reference coverage differs")
    return values
