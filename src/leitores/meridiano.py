"""Leitor do extrato OFX do Banco Meridiano.

Aceita OFX 1.x SGML (tags sem fechamento) e OFX 2.x XML. ref_origem = FITID.
O cabeçalho declara ENCODING:USASCII mas o arquivo traz bytes cp1252: o encoding
é detectado pelo conteúdo, não pelo cabeçalho.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from .comum import ErroLeitura, ler_texto, numero_ponto

_RE_TAG = re.compile(r"<([A-Z0-9.]+)>([^<\r\n]*)", re.IGNORECASE)


def _data_ofx(valor: str) -> date:
    m = re.match(r"(\d{4})(\d{2})(\d{2})", valor or "")
    if not m:
        raise ErroLeitura(f"Data OFX inválida: {valor!r}")
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _campos(trecho: str) -> dict:
    return {tag.upper(): valor.strip() for tag, valor in _RE_TAG.findall(trecho) if valor.strip()}


def ler_meridiano(caminho: Path, rotulo: str) -> pd.DataFrame:
    caminho = Path(caminho)
    texto, encoding = ler_texto(caminho, esperado=["<OFX>", "<STMTTRN>"])

    corpo = re.split(r"<BANKTRANLIST>", texto, flags=re.IGNORECASE)
    if len(corpo) < 2:
        raise ErroLeitura(f"{caminho.name}: bloco <BANKTRANLIST> não encontrado")
    lista = re.split(r"</BANKTRANLIST>", corpo[1], flags=re.IGNORECASE)[0]
    partes = re.split(r"<STMTTRN>", lista, flags=re.IGNORECASE)
    periodo, blocos = _campos(partes[0]), partes[1:]

    registros = []
    for ordem, bloco in enumerate(blocos, start=1):
        bloco = re.split(r"</STMTTRN>", bloco, flags=re.IGNORECASE)[0]
        c = _campos(bloco)
        if "FITID" not in c or "TRNAMT" not in c:
            raise ErroLeitura(f"{caminho.name}: transação {ordem} sem FITID ou TRNAMT")
        registros.append({
            "banco": rotulo,
            "ref_origem": c["FITID"],
            "ordem_arquivo": ordem,
            "data": _data_ofx(c.get("DTPOSTED")),
            "descricao": c.get("MEMO") or c.get("NAME") or "",
            "valor": numero_ponto(c["TRNAMT"]),
            "tipo_trn": c.get("TRNTYPE"),
            "documento": c.get("CHECKNUM"),
            "arquivo_origem": caminho.name,
        })

    cab = {**_campos(corpo[0]), **periodo}
    resto = _campos(re.split(r"</BANKTRANLIST>", corpo[1], flags=re.IGNORECASE)[-1])
    df = pd.DataFrame(registros)
    df["data"] = pd.to_datetime(df["data"])
    df.attrs.update(
        arquivo=caminho.name, encoding=encoding,
        conta=cab.get("ACCTID"), agencia=cab.get("BRANCHID"), banco_id=cab.get("BANKID"),
        periodo_de=_data_ofx(cab["DTSTART"]) if "DTSTART" in cab else None,
        periodo_ate=_data_ofx(cab["DTEND"]) if "DTEND" in cab else None,
        saldo_final=numero_ponto(resto.get("BALAMT")),
        saldo_final_data=_data_ofx(resto["DTASOF"]) if "DTASOF" in resto else None,
    )
    return df
