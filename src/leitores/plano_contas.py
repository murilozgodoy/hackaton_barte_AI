"""Leitor do plano de contas exportado do ERP Fênix (CSV ';')."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .comum import ErroLeitura, data_br, ler_texto, linhas_fisicas, normalizar

COLUNAS_ESPERADAS = ["COD_CONTA", "DESCRICAO", "TIPO", "NATUREZA", "ACEITA_LANCTO",
                     "COD_SUPERIOR", "DT_CRIACAO"]


def ler_plano_contas(caminho: Path) -> pd.DataFrame:
    caminho = Path(caminho)
    texto, encoding = ler_texto(caminho, esperado=["COD_CONTA", "ACEITA_LANCTO"])
    cabecalho, registros = None, []
    for n, linha in enumerate(linhas_fisicas(texto), start=1):
        if not linha.strip():
            continue
        campos = [c.strip() for c in next(csv.reader([linha], delimiter=";"))]
        if cabecalho is None:
            cabecalho = [normalizar(c) for c in campos]
            faltando = [c for c in COLUNAS_ESPERADAS if c not in cabecalho]
            if faltando:
                raise ErroLeitura(f"{caminho.name}: colunas ausentes: {faltando}")
            continue
        r = dict(zip(cabecalho, campos))
        registros.append({
            "cod_conta": r["COD_CONTA"],
            "descricao": r["DESCRICAO"],
            "tipo": normalizar(r["TIPO"]),
            "natureza": normalizar(r["NATUREZA"]),
            "aceita_lancto": normalizar(r["ACEITA_LANCTO"]) == "S",
            "cod_superior": r["COD_SUPERIOR"] or None,
            "dt_criacao": data_br(r["DT_CRIACAO"]),
            "linha_arquivo": n,
            "ref_origem": r["COD_CONTA"],
            "arquivo_origem": caminho.name,
        })
    df = pd.DataFrame(registros)
    df.attrs.update(arquivo=caminho.name, encoding=encoding)
    return df
