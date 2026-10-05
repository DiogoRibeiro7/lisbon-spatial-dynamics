"""Strict extraction of published Q4 rolling-year INE sales counts."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from typing import Any

INDICATOR = "0014363"
MUNICIPALITY = "1106"
TITLE = (
    "Vendas de alojamentos familiares nos últimos 12 meses (Metodologia 2022 - N.º) "
    "por Localização geográfica (NUTS - 2024); Trimestral - INE, Estatísticas de preços "
    "da habitação ao nível local (Metodologia 2022)"
)
COLUMNS = (
    "year",
    "period_code",
    "geography_level",
    "geography_id",
    "geography_name",
    "indicator_code",
    "source_geography_code",
    "sales",
)


@dataclass(frozen=True, slots=True)
class SalesRow:
    """One published count; municipality and parish observations remain distinct."""

    year: int
    geography_id: str
    geography_name: str
    sales: int


def _geographies(reference: Mapping[str, str], years: Sequence[int]) -> dict[str, str]:
    if (
        not reference
        or not years
        or len(set(years)) != len(years)
        or any(type(y) is not int or not 1 <= y <= 9999 for y in years)
        or any(
            len(code) != 6
            or not code.isascii()
            or not code.isdigit()
            or not code.startswith(MUNICIPALITY)
            or not name
            for code, name in reference.items()
        )
    ):
        raise ValueError("Lisbon parish reference and unique calendar years required")
    return {MUNICIPALITY: "Lisboa", **reference}


def parse_sales_reference(
    payload: str, reference: Mapping[str, str], years: Sequence[int]
) -> tuple[SalesRow, ...]:
    """Require all parish and city keys, integer counts and exact annual reconciliation."""
    geographies = _geographies(reference, years)
    reader = csv.DictReader(StringIO(payload, newline=""))
    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("unexpected sales reference columns")
    rows: dict[tuple[int, str], SalesRow] = {}
    for item in reader:
        if None in item or any(value is None for value in item.values()):
            raise ValueError("malformed sales reference row")
        year, code = int(item["year"]), item["geography_id"]
        if (
            str(year) != item["year"]
            or year not in years
            or code not in geographies
            or item["geography_name"] != geographies[code]
            or item["geography_level"] != ("municipality" if code == MUNICIPALITY else "parish")
            or item["period_code"] != f"4.º Trimestre de {year}"
            or item["indicator_code"] != INDICATOR
            or item["source_geography_code"] != f"1A0{code}"
        ):
            raise ValueError("sales identity or Q4 period differs")
        raw = item["sales"]
        if not raw.isascii() or not raw.isdigit():
            raise ValueError("sales must be a published nonnegative integer; missing is not zero")
        key = (year, code)
        if key in rows:
            raise ValueError("duplicate sales observation")
        rows[key] = SalesRow(year, code, geographies[code], int(raw))
    if set(rows) != {(year, code) for year in years for code in geographies}:
        raise ValueError("incomplete sales coverage")
    for year in years:
        city = rows[year, MUNICIPALITY].sales
        if city <= 0 or sum(rows[year, code].sales for code in reference) != city:
            raise ValueError("parish sales do not reconcile with a positive municipality count")
    return tuple(rows[key] for key in sorted(rows))


def _document(payload: bytes) -> dict[str, Any]:
    document = json.loads(payload)
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise ValueError("expected exactly one INE sales indicator document")
    result: dict[str, Any] = document[0]
    if result.get("IndicadorCod") != INDICATOR or result.get("Sucesso") != {
        "Verdadeiro": [{"Msg": "OK"}]
    }:
        raise ValueError("unexpected or unsuccessful sales indicator")
    return result


def extract_sales_reference(
    data: bytes, metadata: bytes, reference: Mapping[str, str], years: Sequence[int]
) -> str:
    """Verify source units, dimensions and every value before publishing a canonical CSV."""
    geographies = _geographies(reference, years)
    document, meta = _document(data), _document(metadata)
    if (
        document.get("IndicadorDsg") != TITLE
        or meta.get("IndicadorNome") != TITLE
        or meta.get("Periodic") != "Trimestral"
        or meta.get("Potencia10") != "0"
        or meta.get("PrecisaoDecimal") != "0"
        or meta.get("UnidadeMedida") != "Número (N.º)"
    ):
        raise ValueError("metadata differs from the rolling-year sales count contract")
    try:
        descriptions = meta["Dimensoes"]["Descricao_Dim"]
        if sorted(d["dim_num"] for d in descriptions) != ["1", "2"]:
            raise ValueError("unexpected sales dimensions")
        dimensions: dict[str, Any] = {}
        for group in meta["Dimensoes"]["Categoria_Dim"]:
            if dimensions.keys() & group.keys():
                raise ValueError("duplicate sales dimension metadata")
            dimensions.update(group)
        required = [
            *((1, f"S5A{year}4", f"4.º Trimestre de {year}") for year in years),
            *((2, f"1A0{code}", name) for code, name in geographies.items()),
        ]
        for dim, code, name in required:
            entries = dimensions[f"Dim_Num{dim}_{code}"]
            if len(entries) != 1 or any(
                entries[0][key] != value
                for key, value in {"dim_num": str(dim), "cat_id": code, "categ_dsg": name}.items()
            ):
                raise ValueError("sales dimension identity differs")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed sales dimension metadata") from exc
    observations = document.get("Dados")
    if not isinstance(observations, dict) or set(observations) != {
        f"4.º Trimestre de {year}" for year in years
    }:
        raise ValueError("sales Q4 coverage differs")
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    for year in sorted(years):
        period = f"4.º Trimestre de {year}"
        records = observations[period]
        if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
            raise ValueError("malformed sales observations")
        for row in sorted(records, key=lambda r: str(r.get("geocod"))):
            geo = row.get("geocod")
            if (
                not isinstance(geo, str)
                or geo not in {f"1A0{code}" for code in geographies}
                or row.get("geodsg") != geographies[geo[3:]]
                or any(k.startswith("dim_") for k in row)
            ):
                raise ValueError("unexpected sales geography or extra dimension")
            value, displayed = row.get("valor"), row.get("ind_string")
            if (
                not isinstance(value, str)
                or not isinstance(displayed, str)
                or row.get("sinal_conv")
                or row.get("sinal_conv_desc")
                or displayed.replace(" ", "").replace("\u00a0", "") != value
            ):
                raise ValueError("unpublished, flagged or inconsistent sales count")
            code = geo[3:]
            writer.writerow(
                [
                    year,
                    period,
                    "municipality" if code == MUNICIPALITY else "parish",
                    code,
                    geographies[code],
                    INDICATOR,
                    geo,
                    value,
                ]
            )
    result = stream.getvalue()
    parse_sales_reference(result, reference, years)
    return result
