"""Divergências entre taxa contratada e taxa aplicada, uma linha por transação.

CHECKOUT: taxa aplicada pela Orbe diferente da contratada além da tolerância;
diferença = valor_bruto x (aplicada - contratada), arredondada por linha. Centavo de
truncamento da Orbe não é divergência porque a comparação é de taxa, não de valor.
REMESSA: já calculada por operação em remessa.py (valor cheio); aqui só entra na saída.

Natureza da diferença (coluna `natureza`): CONTRATO (contratada ≠ aplicada: cobrança da
contraparte) ou a que a regra TAXA_EXCECAO declarar em `divergencia=` (ex.: DEVOLUCAO_LOJISTA,
quando a condição especial não chegou à adquirente e a diferença é devolução ao lojista, não
cobrança da adquirente). Toda transação divergente sai em divergencias_taxa.csv, com a natureza
e a `observacao` que a regra declarar; só as de natureza CONTRATO entram na cobrança da
contraparte (saida/comunicacoes/*_contestacao.csv). A pendência de cada grupo tem rastro por transação.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .dinheiro import arredondar, pct
from .regras import NATUREZA_CONTRATO, Config

PREFIXO_ID = "DIV-"
COLUNAS = ["id_saida", "cnpj", "linha_negocio", "ref_origem", "taxa_contratada_pct", "taxa_aplicada_pct",
           "diferenca_brl", "lojista", "data", "produto", "valor_base_brl", "diferenca_pp", "arquivo_origem",
           "regra_id", "tipo_pendencia", "natureza", "observacao"]
COLUNAS_RASTRO = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]


@dataclass
class ResultadoDivergencias:
    divergencias: pd.DataFrame   # todas as naturezas, com id_saida: é o divergencias_taxa.csv
    rastro: pd.DataFrame         # id_saida -> transação


def contrato(div: pd.DataFrame) -> pd.DataFrame:
    """Só as divergências de contrato (as que se cobram da contraparte)."""
    return div[div["natureza"] == NATUREZA_CONTRATO] if len(div) else div


def fora_contrato(div: pd.DataFrame) -> pd.DataFrame:
    """As de outra natureza (ex.: devolução ao lojista), declarada pela regra TAXA_EXCECAO."""
    return div[div["natureza"] != NATUREZA_CONTRATO] if len(div) else div


def calcular(checkout_linhas: pd.DataFrame, remessa_linhas: pd.DataFrame, config: Config) -> ResultadoDivergencias:
    registros = []

    chk = checkout_linhas[checkout_linhas["destino"] == "COMISSAO"]
    for r in chk.itertuples(index=False):
        data = r.data_movimento.date()
        diferenca_pp = r.taxa_aplicada_pct - r.taxa_contratada_pct
        if abs(diferenca_pp) <= config.parametro("tolerancia_taxa_checkout_pp", data):
            continue
        regra_excecao = config.regra(r.regra_id)
        excecao = regra_excecao is not None and regra_excecao.tipo == "TAXA_EXCECAO"
        registros.append({
            "cnpj": r.cnpj, "linha_negocio": "CHECKOUT", "ref_origem": r.ref_origem,
            "taxa_contratada_pct": r.taxa_contratada_pct, "taxa_aplicada_pct": r.taxa_aplicada_pct,
            "diferenca_brl": arredondar(pct(diferenca_pp, r.valor_bruto), config.parametro("arredondamento", data)),
            "lojista": r.lojista, "data": r.data_movimento, "produto": r.produto, "valor_base_brl": r.valor_bruto,
            "diferenca_pp": diferenca_pp, "arquivo_origem": r.arquivo_origem, "regra_id": r.regra_id,
            "tipo_pendencia": (regra_excecao.tipo_pendencia if excecao and regra_excecao.tipo_pendencia
                               else "DIVERGENCIA_TAXA"),
            "natureza": regra_excecao.params.get("divergencia", NATUREZA_CONTRATO) if excecao else NATUREZA_CONTRATO,
            "observacao": (regra_excecao.params.get("observacao") or None) if excecao else None,
        })

    rem = remessa_linhas[(remessa_linhas["destino"] == "COMISSAO") & remessa_linhas["diferenca_brl"].notna()]
    for r in rem.itertuples(index=False):
        registros.append({
            "cnpj": r.cnpj, "linha_negocio": "REMESSA", "ref_origem": r.ref_origem,
            "taxa_contratada_pct": r.spread_contratado_pct, "taxa_aplicada_pct": r.spread_pct,
            "diferenca_brl": r.diferenca_brl, "lojista": r.lojista, "data": r.data_contratacao,
            "produto": f"spread {r.moeda}", "valor_base_brl": r.valor_brl, "diferenca_pp": r.diferenca_pp,
            "arquivo_origem": r.arquivo_origem, "regra_id": r.spread_contratado_origem,
            "tipo_pendencia": "DIVERGENCIA_TAXA", "natureza": NATUREZA_CONTRATO, "observacao": None,
        })

    if not registros:
        return ResultadoDivergencias(pd.DataFrame(columns=COLUNAS), pd.DataFrame(columns=COLUNAS_RASTRO))
    df = pd.DataFrame(registros).sort_values(["linha_negocio", "cnpj", "data", "ref_origem"]).reset_index(drop=True)
    df.insert(0, "id_saida", [f"{PREFIXO_ID}{i:04d}" for i in range(1, len(df) + 1)])
    rastro = pd.DataFrame({
        "id_saida": df["id_saida"], "arquivo_origem": df["arquivo_origem"], "ref_origem": df["ref_origem"],
        "valor": df["diferenca_brl"], "regra_id": df["regra_id"], "taxa_pct": df["taxa_contratada_pct"],
    })
    return ResultadoDivergencias(df[COLUNAS], rastro[COLUNAS_RASTRO])
