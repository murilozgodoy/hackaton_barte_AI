"""Leitor do extrato CSV do Banco Aurora.

ref_origem = número da linha física do arquivo ("L9"), contando o cabeçalho, 1-based.
SALDO ANTERIOR e SALDO FINAL não são lançamentos: ficam em attrs para conferência.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

from .comum import ErroLeitura, data_br, ler_texto, linhas_fisicas, normalizar, numero_br

_RE_DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_MAPA = {"DATA": "data", "LANCAMENTO": "descricao", "DOCUMENTO": "documento",
         "VALOR (R$)": "valor", "SALDO (R$)": "saldo"}


def ler_aurora(caminho: Path, rotulo: str) -> pd.DataFrame:
    caminho = Path(caminho)
    texto, encoding = ler_texto(caminho, esperado=["Lançamento", "SALDO ANTERIOR"])

    colunas, cabecalho_txt = None, []
    registros, ignoradas = [], []
    saldo_anterior = saldo_final = None
    for n, linha in enumerate(linhas_fisicas(texto), start=1):
        campos = [c.strip() for c in next(csv.reader([linha], delimiter=";"))] if linha else []
        if colunas is None:
            nomes = [normalizar(c) for c in campos]
            if "DATA" in nomes and "VALOR (R$)" in nomes:
                colunas = {_MAPA[nm]: j for j, nm in enumerate(nomes) if nm in _MAPA}
                faltando = [c for c in _MAPA.values() if c not in colunas]
                if faltando:
                    raise ErroLeitura(f"{caminho.name} L{n}: colunas ausentes: {faltando}")
            elif linha.strip(";").strip():
                cabecalho_txt.append(linha.strip(";").strip())
            continue
        if not any(campos):
            continue
        get = lambda k: campos[colunas[k]] if colunas[k] < len(campos) else ""
        desc = normalizar(get("descricao"))
        if desc == "SALDO ANTERIOR":
            saldo_anterior = {"valor": numero_br(get("saldo")), "linha": n, "data": data_br(get("data"))}
        elif desc == "SALDO FINAL":
            saldo_final = {"valor": numero_br(get("saldo")), "linha": n}
        elif _RE_DATA.match(get("data")):
            registros.append({
                "banco": rotulo,
                "ref_origem": f"L{n}",
                "linha_arquivo": n,
                "data": data_br(get("data")),
                "descricao": get("descricao"),
                "documento": get("documento") or None,
                "valor": numero_br(get("valor")),
                "saldo": numero_br(get("saldo")),
                "arquivo_origem": caminho.name,
            })
        else:
            ignoradas.append({"linha": n, "conteudo": linha})

    if colunas is None:
        raise ErroLeitura(f"{caminho.name}: linha de cabeçalho (Data;Lançamento;...;Valor (R$)) não encontrada")
    df = pd.DataFrame(registros)
    df["data"] = pd.to_datetime(df["data"])
    df.attrs.update(arquivo=caminho.name, encoding=encoding, cabecalho=cabecalho_txt,
                    saldo_anterior=saldo_anterior, saldo_final=saldo_final,
                    linhas_ignoradas=ignoradas)
    return df
