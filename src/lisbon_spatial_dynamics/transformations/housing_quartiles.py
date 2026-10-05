"""Published annual housing quartiles for Lisbon municipality, with no parish allocation."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from decimal import Decimal
from io import StringIO
from typing import Any

INDICATOR = "0013042"
QUARTILES = {"1": "1.º quartil", "2": "2.º quartil", "3": "3.º quartil"}
TITLE = (
    "Vendas de alojamentos familiares (Metodologia 2022 - €/ m²) por Localização "
    "geográfica (NUTS - 2024) e Quartis; Anual - INE, Estatísticas de preços da "
    "habitação ao nível local (Metodologia 2022)"
)
COLUMNS = (
    "year",
    "indicator_code",
    "geography_code",
    "geography_name",
    "quartile_code",
    "quartile_name",
    "value_eur_m2",
)


def _years(years: Sequence[int]) -> None:
    if (
        not years
        or len(set(years)) != len(years)
        or any(type(y) is not int or not 1 <= y <= 9999 for y in years)
    ):
        raise ValueError("unique calendar years required")


def parse_quartile_reference(payload: str, years: Sequence[int]) -> dict[tuple[int, str], Decimal]:
    """Require complete positive, ordered quartiles for the requested municipality years."""
    _years(years)
    reader = csv.DictReader(StringIO(payload, newline=""))
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("unexpected quartile reference columns")
    values = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed quartile reference row")
        year, quartile = int(row["year"]), row["quartile_code"]
        if (
            str(year) != row["year"]
            or year not in years
            or quartile not in QUARTILES
            or row["quartile_name"] != QUARTILES[quartile]
            or row["indicator_code"] != INDICATOR
            or row["geography_code"] != "1A01106"
            or row["geography_name"] != "Lisboa"
        ):
            raise ValueError("quartile reference identity or annual period differs")
        raw = row["value_eur_m2"]
        if not raw.isascii() or not raw.isdigit() or int(raw) <= 0:
            raise ValueError("quartiles must be published positive integers; missing is not zero")
        key = (year, quartile)
        if key in values:
            raise ValueError("duplicate quartile observation")
        values[key] = Decimal(raw)
    if set(values) != {(y, q) for y in years for q in QUARTILES}:
        raise ValueError("incomplete quartile coverage")
    for year in years:
        if not values[year, "1"] <= values[year, "2"] <= values[year, "3"]:
            raise ValueError("quartiles must be ordered Q1 <= Q2 <= Q3")
    return {key: values[key] for key in sorted(values)}


def _document(payload: bytes) -> dict[str, Any]:
    parsed = json.loads(payload)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise ValueError("expected one INE quartile indicator document")
    document: dict[str, Any] = parsed[0]
    if document.get("IndicadorCod") != INDICATOR or document.get("Sucesso") != {
        "Verdadeiro": [{"Msg": "OK"}]
    }:
        raise ValueError("unsuccessful or unexpected quartile indicator")
    return document


def extract_quartile_reference(data: bytes, metadata: bytes, years: Sequence[int]) -> str:
    """Validate annual units/geography/quantiles and preserve each published value."""
    _years(years)
    document, meta = _document(data), _document(metadata)
    if (
        document.get("IndicadorDsg") != TITLE
        or meta.get("IndicadorNome") != TITLE
        or meta.get("Periodic") != "Anual"
        or meta.get("Potencia10") != "0"
        or meta.get("PrecisaoDecimal") != "0"
        or meta.get("UnidadeMedida") != "Euro/ Metro quadrado (€/ m²)"
    ):
        raise ValueError("metadata differs from the annual sale-quartile contract")
    try:
        if sorted(d["dim_num"] for d in meta["Dimensoes"]["Descricao_Dim"]) != ["1", "2", "3"]:
            raise ValueError("unexpected quartile dimensions")
        categories: dict[str, Any] = {}
        for group in meta["Dimensoes"]["Categoria_Dim"]:
            if categories.keys() & group.keys():
                raise ValueError("duplicate quartile dimension metadata")
            categories.update(group)
        for dimension, code, name in (
            (2, "1A01106", "Lisboa"),
            *((1, f"S7A{year}", str(year)) for year in years),
            *((3, code, name) for code, name in QUARTILES.items()),
        ):
            entries = categories[f"Dim_Num{dimension}_{code}"]
            if len(entries) != 1 or any(
                entries[0][key] != expected
                for key, expected in {
                    "dim_num": str(dimension),
                    "cat_id": code,
                    "categ_dsg": name,
                }.items()
            ):
                raise ValueError("quartile dimension identity differs")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed quartile dimension metadata") from exc
    observations = document.get("Dados")
    if not isinstance(observations, dict) or set(observations) != {str(y) for y in years}:
        raise ValueError("quartile annual coverage differs")
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    for year in sorted(years):
        rows = observations[str(year)]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("malformed quartile observations")
        for row in sorted(rows, key=lambda r: str(r.get("dim_3"))):
            code = row.get("dim_3")
            if (
                not isinstance(code, str)
                or code not in QUARTILES
                or row.get("dim_3_t") != QUARTILES[code]
                or row.get("geocod") != "1A01106"
                or row.get("geodsg") != "Lisboa"
                or row.get("sinal_conv")
                or row.get("sinal_conv_desc")
                or any(k.startswith("dim_") and k not in {"dim_3", "dim_3_t"} for k in row)
            ):
                raise ValueError("quartile scope or observation flag differs")
            value, displayed = row.get("valor"), row.get("ind_string")
            if (
                not isinstance(value, str)
                or not isinstance(displayed, str)
                or displayed.replace(" ", "").replace("\u00a0", "") != value
            ):
                raise ValueError("unpublished or inconsistent quartile value")
            writer.writerow([year, INDICATOR, "1A01106", "Lisboa", code, QUARTILES[code], value])
    result = stream.getvalue()
    parse_quartile_reference(result, years)
    return result
