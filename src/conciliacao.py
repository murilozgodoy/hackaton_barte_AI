"""Conciliação informativa entre fontes (só números; não gera pendência).

Os lançamentos entram pelo `papel` que a regra CLASSIFICAR_CONTA lhes deu
(recebimento_adquirente, repasse_lojista, recurso_remessa, liquidacao_remessa), então
nenhum nome de banco, conta ou parceiro aparece aqui.
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .dinheiro import ZERO, arredondar, soma


def _por_papel(lancamentos: pd.DataFrame, papel: str) -> tuple[Decimal, int]:
    sel = lancamentos[lancamentos["papel"] == papel]
    return soma(sel["valor"]), int(len(sel))


def calcular(dados: dict[str, pd.DataFrame], ponte_linhas: pd.DataFrame, com_rem: pd.DataFrame,
             lancamentos: pd.DataFrame, participacao: Decimal, modo: str) -> dict:
    orbe, ponte = dados["orbe"], dados["ponte"]

    # Adquirente x banco: NÃO conciliável com os arquivos do mês. A adquirente liquida crédito
    # parcelado em parcelas mensais (salvo antecipação): o que entra no banco mistura parcelas de
    # vendas de meses anteriores e deixa de fora parcelas futuras das vendas deste mês. Sem a
    # agenda de recebíveis, os totais abaixo são só informativos e não se comparam entre si.
    liquido_orbe = soma(orbe["valor_liquido"])
    recebido, n_receb = _por_papel(lancamentos, "recebimento_adquirente")
    repassado, n_rep = _por_papel(lancamentos, "repasse_lojista")   # débitos negativos; devolução volta positiva
    orbe_banco = {
        "conciliavel": False,
        "limitacao": ("não conciliável com os arquivos disponíveis: a adquirente liquida crédito parcelado em "
                      "parcelas mensais (salvo antecipação); requer a agenda de recebíveis da adquirente"),
        "liquido_orbe": liquido_orbe,
        "liquido_orbe_por_tipo": {t: soma(g["valor_liquido"]) for t, g in orbe.groupby("tipo_lancamento")},
        "recebido_da_adquirente": recebido, "qtd_recebimentos": n_receb,
        "repassado_a_lojistas": -repassado, "qtd_repasses": n_rep,
    }

    # Remessa: recursos dos lojistas x liquidação na Ponte x operações do relatório (Valor R$ + IOF)
    recursos, n_rec = _por_papel(lancamentos, "recurso_remessa")
    liquidado, n_liq = _por_papel(lancamentos, "liquidacao_remessa")
    liquidado = -liquidado
    unicas = ponte.drop_duplicates("num_operacao")
    valor_mais_iof = soma(unicas["valor_brl"]) + soma(unicas["iof_brl"])
    remessa_banco = {
        "recursos_recebidos": recursos, "qtd_recursos": n_rec,
        "liquidado_na_ponte": liquidado, "qtd_liquidacoes": n_liq,
        "operacoes_valor_mais_iof": valor_mais_iof,
        "recursos_menos_liquidado": recursos - liquidado,
        "liquidado_menos_operacoes": liquidado - valor_mais_iof,
    }

    # Ponte: repasse que ela faria pelo total declarado x comissão calculada, e por que diferem
    total_declarado = ponte.attrs.get("totais_declarados", {}).get("SPREAD TOTAL R$:")
    comissao = soma(com_rem["comissao_brl"]) if len(com_rem) else ZERO
    excluidas = ponte_linhas[ponte_linhas["destino"] == "EXCLUIDO"]
    ignoradas = ponte_linhas[ponte_linhas["destino"] == "DUPLICATA_IGNORADA"]
    efeito_excluidas = -soma(excluidas["spread_brl"]) * participacao      # negativos tirados da base
    efeito_duplicatas = -soma(ignoradas["spread_brl"]) * participacao     # repetições tiradas da base
    repasse_pelo_total = arredondar(total_declarado * participacao, modo) if total_declarado is not None else None
    diferenca = (comissao - repasse_pelo_total) if repasse_pelo_total is not None else None
    ponte_info = {
        "spread_total_declarado": total_declarado,
        "spread_operacoes_unicas": soma(unicas["spread_brl"]),
        "repasse_pelo_total_declarado": repasse_pelo_total,
        "comissao_calculada": comissao,
        "diferenca": diferenca,
        "efeito_excluidas": efeito_excluidas, "qtd_excluidas": int(len(excluidas)),
        "efeito_duplicatas": efeito_duplicatas, "qtd_duplicatas": int(len(ignoradas)),
        "efeito_arredondamento": (diferenca - efeito_excluidas - efeito_duplicatas) if diferenca is not None else None,
    }
    return {"orbe_banco": orbe_banco, "remessa_banco": remessa_banco, "ponte": ponte_info}
