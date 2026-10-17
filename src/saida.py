"""Escrita dos CSVs de saída no formato fixo da correção automática.

CSV com ';', ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos, UTF-8. As colunas
obrigatórias vêm primeiro, na ordem do regulamento; colunas extras seguem depois.
"""
from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .dinheiro import CENTAVO

COLUNAS_OBRIGATORIAS = {
    "comissoes_por_lojista.csv": ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl"],
    "divergencias_taxa.csv": ["id_saida", "cnpj", "linha_negocio", "ref_origem", "taxa_contratada_pct",
                              "taxa_aplicada_pct", "diferenca_brl"],
    "notas_a_emitir.csv": ["id_saida", "tomador_cnpj", "tomador", "linha_negocio", "valor_brl", "discriminacao"],
    "lancamentos_classificados.csv": ["id_saida", "banco", "ref_origem", "data", "descricao", "valor",
                                      "conta_codigo", "metodo", "confianca"],
    "pendencias.csv": ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"],
    "rastro.csv": ["id_saida", "arquivo_origem", "ref_origem", "valor"],
}
# colunas Decimal que NÃO são dinheiro (não ganham 2 casas fixas)
_NAO_MONETARIAS = ("_pct", "taxa_pct", "confianca", "spread")


def formatar_celula(valor, coluna: str) -> str:
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    if isinstance(valor, Decimal):
        if coluna.endswith(_NAO_MONETARIAS[0]) or coluna in _NAO_MONETARIAS:
            return f"{valor.quantize(Decimal('0.000001')).normalize():f}"
        v = valor.quantize(CENTAVO)
        return "0.00" if v == 0 else f"{v:f}"
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(valor).strftime("%Y-%m-%d")
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, float):
        return repr(valor)
    return str(valor)


def escrever_csv(df: pd.DataFrame, caminho: Path, nome: str) -> Path:
    obrigatorias = COLUNAS_OBRIGATORIAS[nome]
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        raise ValueError(f"{nome}: colunas obrigatórias ausentes: {faltando}")
    colunas = obrigatorias + [c for c in df.columns if c not in obrigatorias]
    caminho = Path(caminho)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(colunas)
        for linha in df[colunas].itertuples(index=False, name=None):
            w.writerow([formatar_celula(v, c) for v, c in zip(linha, colunas)])
    return caminho
