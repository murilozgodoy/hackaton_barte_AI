"""Escrita dos CSVs de saída no formato fixo da correção automática.

CSV com ';', ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos, UTF-8. As colunas
obrigatórias vêm primeiro, na ordem do regulamento; colunas extras seguem depois.
Dinheiro sai com 2 casas e já deve chegar arredondado (arredondar aqui esconderia
um erro de cálculo); taxas em % saem com pelo menos 2 casas e sem zeros à direita.
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
    "carteira_pendente.csv": ["arquivo_origem", "ref_origem", "cnpj", "ec", "data_venda", "produto", "valor_bruto",
                              "motivo", "competencia_origem"],
    "orbe_contestacao.csv": ["ref_origem", "cnpj", "lojista", "linha_negocio", "data", "produto", "taxa_contratada_pct",
                             "taxa_aplicada_pct", "valor_brl", "natureza"],
    "ponte_contestacao.csv": ["ref_origem", "cnpj", "lojista", "linha_negocio", "data", "produto", "taxa_contratada_pct",
                              "taxa_aplicada_pct", "valor_brl", "natureza"],
    "rastro.csv": ["id_saida", "arquivo_origem", "ref_origem", "valor"],
}
# colunas Decimal que não são dinheiro
COLUNAS_PCT_SUFIXOS = ("_pct", "_pp")
COLUNAS_PCT = {"taxa_pct", "participacao"}
COLUNAS_LIVRES = {"confianca"}


def formatar_pct(valor: Decimal) -> str:
    """Percentual com pelo menos 2 casas e até 6, sem zeros à direita: 2.69, 2.10, 1.501, 1.4984."""
    texto = f"{valor.quantize(Decimal('0.000001')):f}"
    inteiro, dec = texto.split(".")
    dec = dec.rstrip("0")
    return f"{inteiro}.{dec.ljust(2, '0')}"


def formatar_dinheiro(valor: Decimal, coluna: str) -> str:
    if valor != valor.quantize(CENTAVO):
        raise ValueError(f"coluna {coluna}: valor {valor} não está arredondado ao centavo")
    v = valor.quantize(CENTAVO)
    return "0.00" if v == 0 else f"{v:f}"


def formatar_celula(valor, coluna: str) -> str:
    if valor is None or valor is pd.NA or valor is pd.NaT:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    if isinstance(valor, Decimal):
        if coluna in COLUNAS_LIVRES:
            return f"{valor.normalize():f}"
        if coluna.endswith(COLUNAS_PCT_SUFIXOS) or coluna in COLUNAS_PCT:
            return formatar_pct(valor)
        return formatar_dinheiro(valor, coluna)
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
