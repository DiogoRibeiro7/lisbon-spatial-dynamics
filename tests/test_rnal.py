"""Tests for privacy-minimised RNAL acquisition."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lisbon_spatial_dynamics.sources.rnal import (
    RNALConfig,
    RNALPayloadError,
    build_rnal_request,
    fetch_rnal_snapshot,
)


def _config() -> RNALConfig:
    path = Path(__file__).parents[1] / "configs" / "rnal_lisboa.toml"
    return RNALConfig.from_toml(path)


def _soap_response(
    *,
    municipality: str = "Lisboa",
    total: int = 1,
) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <list_RNALResponse xmlns="http://www.outsystems.com">
      <totalRegistos>{total}</totalRegistos>
      <list>
        <RNAL_Registo>
          <NrRegisto>12345/AL</NrRegisto>
          <DataRegisto>2018-03-10</DataRegisto>
          <NomeAlojamento>Example Stay</NomeAlojamento>
          <Modalidade>Apartamento</Modalidade>
          <NrCamas>2</NrCamas>
          <NrUtentes>4</NrUtentes>
          <Endereco>Rua Exemplo 1</Endereco>
          <CodPostal>1000-001</CodPostal>
          <Localidade>Lisboa</Localidade>
          <Freguesia>Alvalade</Freguesia>
          <Concelho>{municipality}</Concelho>
          <Distrito>Lisboa</Distrito>
          <TitulardaExploracao>
            <Tipo>Singular</Tipo>
            <Nome>Private Person</Nome>
            <Contribuinte>123456789</Contribuinte>
            <Telefone>210000000</Telefone>
            <Telemovel>910000000</Telemovel>
            <Email>private@example.com</Email>
          </TitulardaExploracao>
          <CessadoEm>2024-05-01</CessadoEm>
          <DTMNFR>110654</DTMNFR>
        </RNAL_Registo>
      </list>
    </list_RNALResponse>
  </soap:Body>
</soap:Envelope>
""".encode()


def test_config_targets_official_rnal_operation() -> None:
    config = _config()

    assert config.municipality == "Lisboa"
    assert config.endpoint_url.endswith("/RNT_External/WS_RNT.asmx")
    assert config.soap_action.endswith("/list_RNAL")


def test_request_contains_only_municipality_filter() -> None:
    payload = build_rnal_request(_config()).decode()

    assert "<Concelho>Lisboa</Concelho>" in payload
    assert "TitulardaExploracao" not in payload


def test_snapshot_discards_proprietor_personal_data(tmp_path: Path) -> None:
    config = _config()

    def poster(
        url: str,
        payload: bytes,
        headers: Mapping[str, str],
        timeout: float,
    ) -> bytes:
        assert url == config.endpoint_url
        assert timeout == 5.0
        assert b"<Concelho>Lisboa</Concelho>" in payload
        assert "SOAPAction" in headers
        return _soap_response()

    snapshot = fetch_rnal_snapshot(
        config,
        root=tmp_path,
        timeout=5.0,
        fetched_at=datetime(2026, 9, 27, 21, 0, tzinfo=UTC),
        poster=poster,
    )

    document = json.loads((tmp_path / snapshot.records_path).read_text(encoding="utf-8"))
    record = document["records"][0]

    assert snapshot.record_count == 1
    assert record["NrRegisto"] == "12345/AL"
    assert record["DTMNFR"] == "110654"
    assert record["CessadoEm"] == "2024-05-01"
    assert "TitulardaExploracao" not in record
    assert "Contribuinte" not in record
    assert "Email" not in record

    manifest = json.loads((tmp_path / snapshot.manifest_path).read_text(encoding="utf-8"))
    assert manifest["privacy"]["raw_response_written"] is False
    assert manifest["privacy"]["discarded_subtree"] == "TitulardaExploracao"


def test_reported_total_must_match_records(tmp_path: Path) -> None:
    config = _config()

    with pytest.raises(RNALPayloadError, match="reported total"):
        fetch_rnal_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 27, 21, 0, tzinfo=UTC),
            poster=lambda _url, _payload, _headers, _timeout: _soap_response(total=2),
        )


def test_wrong_municipality_is_rejected(tmp_path: Path) -> None:
    config = _config()

    with pytest.raises(RNALPayloadError, match="not 'Lisboa'"):
        fetch_rnal_snapshot(
            config,
            root=tmp_path,
            fetched_at=datetime(2026, 9, 27, 21, 0, tzinfo=UTC),
            poster=lambda _url, _payload, _headers, _timeout: _soap_response(municipality="Oeiras"),
        )
