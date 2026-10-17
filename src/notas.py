"""Notas fiscais a emitir.

CHECKOUT: uma nota por lojista com comissão maior que zero (zero ou negativo não
emite; negativo vira pendência). REMESSA: uma nota única para o parceiro de câmbio
(tomador nos parâmetros) pelo total da participação do mês. O rastro de cada nota
são as mesmas transações que compõem a comissão.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .dinheiro import ZERO, soma
from .regras import Config

PREFIXO_ID = "NF-"
COLUNAS = ["id_saida", "tomador_cnpj", "tomador", "linha_negocio", "valor_brl", "discriminacao",
           "id_comissao", "qtd_itens", "competencia"]
COLUNAS_RASTRO = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]


def competencia_texto(competencia: str) -> str:
    """'2027-03' -> '03/2027'."""
    ano, mes = competencia.split("-")
    return f"{mes}/{ano}"


def primeiro_dia(competencia: str) -> date:
    ano, mes = competencia.split("-")
    return date(int(ano), int(mes), 1)


def calcular(com_chk: pd.DataFrame, com_rem: pd.DataFrame, rastro_chk: pd.DataFrame, rastro_rem: pd.DataFrame,
             config: Config, competencia: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """-> (notas, rastro das notas, comissões de checkout que não geram nota por saldo <= 0)."""
    ref = primeiro_dia(competencia)
    texto = competencia_texto(competencia)
    notas, rastros, sem_nota = [], [], []

    discr_chk = config.parametro("discriminacao_checkout", ref).replace("{competencia}", texto)
    for r in com_chk.itertuples(index=False):
        if r.comissao_brl <= ZERO:
            sem_nota.append(r._asdict())
            continue
        notas.append({"tomador_cnpj": r.cnpj, "tomador": r.lojista, "linha_negocio": "CHECKOUT",
                      "valor_brl": r.comissao_brl, "discriminacao": discr_chk, "id_comissao": r.id_saida,
                      "qtd_itens": r.qtd_transacoes, "competencia": competencia})
        rastros.append(rastro_chk[rastro_chk["id_saida"] == r.id_saida])

    total_rem = soma(com_rem["comissao_brl"]) if len(com_rem) else ZERO
    if total_rem > ZERO:
        notas.append({"tomador_cnpj": config.parametro("nota_remessa_tomador_cnpj", ref),
                      "tomador": config.parametro("nota_remessa_tomador_nome", ref), "linha_negocio": "REMESSA",
                      "valor_brl": total_rem,
                      "discriminacao": config.parametro("discriminacao_remessa", ref).replace("{competencia}", texto),
                      "id_comissao": ", ".join(com_rem["id_saida"]), "qtd_itens": int(com_rem["qtd_operacoes"].sum()),
                      "competencia": competencia})
        rastros.append(rastro_rem)
    elif len(com_rem):
        # participação do mês zerada ou negativa (ajustes do parceiro): sem nota única, vira pendência (não há nota
        # complementar nem valor negativo em nota)
        sem_nota.append({"id_saida": ", ".join(com_rem["id_saida"]), "cnpj": config.parametro("nota_remessa_tomador_cnpj", ref),
                         "lojista": config.parametro("nota_remessa_tomador_nome", ref), "linha_negocio": "REMESSA",
                         "comissao_brl": total_rem, "ec_orbe": None, "qtd_transacoes": int(com_rem["qtd_operacoes"].sum()),
                         "valor_bruto_total": None, "taxa_cobrada_orbe_brl": None})

    if not notas:
        return pd.DataFrame(columns=COLUNAS), pd.DataFrame(columns=COLUNAS_RASTRO), pd.DataFrame(sem_nota)
    df = pd.DataFrame(notas)
    df.insert(0, "id_saida", [f"{PREFIXO_ID}{i:04d}" for i in range(1, len(df) + 1)])
    partes = []
    for id_nf, rastro in zip(df["id_saida"], rastros):
        partes.append(rastro.assign(id_saida=id_nf))
    rastro_nf = pd.concat(partes, ignore_index=True)[COLUNAS_RASTRO] if partes else pd.DataFrame(columns=COLUNAS_RASTRO)
    return df[COLUNAS], rastro_nf, pd.DataFrame(sem_nota)
