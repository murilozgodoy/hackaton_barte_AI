"""Conciliação informativa entre fontes (só números; não gera pendência por si).

Os lançamentos entram pelo `papel` que a regra CLASSIFICAR_CONTA lhes deu
(recebimento_adquirente, repasse_lojista, recurso_remessa, liquidacao_remessa), então
nenhum nome de banco, conta ou parceiro aparece aqui. Todo valor devolvido já está
arredondado ao centavo (HALF_UP por operação, igual ao rastro).
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .dinheiro import ZERO, arredondar, soma

MEIO_CENTAVO = Decimal("0.005")


def _por_papel(lancamentos: pd.DataFrame, papel: str) -> tuple[Decimal, int]:
    sel = lancamentos[lancamentos["papel"] == papel]
    return soma(sel["valor"]), int(len(sel))


def calcular(dados: dict[str, pd.DataFrame], ponte_linhas: pd.DataFrame, com_rem: pd.DataFrame,
             lancamentos: pd.DataFrame, participacao: Decimal, modo: str) -> dict:
    orbe, ponte = dados["orbe"], dados["ponte"]

    # Adquirente x banco: NÃO conciliável com os arquivos do mês (a explicação de negócio é a
    # regra MANUAL com assunto=conciliacao_adquirente). Totais só informativos.
    recebido, n_receb = _por_papel(lancamentos, "recebimento_adquirente")
    repassado, n_rep = _por_papel(lancamentos, "repasse_lojista")   # débitos negativos; devolução volta positiva
    orbe_banco = {
        "conciliavel": False,
        "liquido_orbe": soma(orbe["valor_liquido"]),
        "liquido_orbe_por_tipo": {t: soma(g["valor_liquido"]) for t, g in orbe.groupby("tipo_lancamento")},
        "recebido_da_adquirente": recebido, "qtd_recebimentos": n_receb,
        "repassado_a_lojistas": -repassado, "qtd_repasses": n_rep,
    }

    # Remessa: recursos dos lojistas x liquidação no parceiro x operações do relatório (Valor R$ + IOF)
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

    # Parceiro: repasse que ele faria pelo total declarado x comissão calculada, e por que diferem.
    # Cada linha do relatório que não entrou na comissão explica uma parte (HALF_UP por linha,
    # igual ao rastro da pendência); o resto só pode ser arredondamento se couber em meio
    # centavo por operação (mais o arredondamento do próprio repasse).
    total = ponte.attrs.get("spread_total_declarado")
    comissao = soma(com_rem["comissao_brl"]) if len(com_rem) else ZERO
    por_destino = {}
    for destino, g in ponte_linhas[ponte_linhas["destino"] != "COMISSAO"].groupby("destino", sort=False):
        por_destino[destino] = {"qtd": int(len(g)),
                                "efeito": soma(arredondar(-s * participacao, modo) for s in g["spread_brl"])}
    explicado = soma(d["efeito"] for d in por_destino.values())
    n_com = int((ponte_linhas["destino"] == "COMISSAO").sum())
    limite = (Decimal(n_com) + 1) * MEIO_CENTAVO
    if total is not None:
        repasse_pelo_total = arredondar(total["valor"] * participacao, modo)
        diferenca = comissao - repasse_pelo_total
        residual = diferenca - explicado
    else:
        repasse_pelo_total = diferenca = residual = None
    ponte_info = {
        "spread_total_declarado": total["valor"] if total else None,
        "total_declarado_ref": (f"linha {total['linha']} do relatório ({total['rotulo']})" if total else None),
        "spread_operacoes_unicas": soma(unicas["spread_brl"]),
        "repasse_pelo_total_declarado": repasse_pelo_total,
        "comissao_calculada": comissao,
        "diferenca": diferenca,
        "efeitos_por_destino": por_destino,
        "residual": residual,
        "residual_e_arredondamento": residual is not None and abs(residual) <= limite,
        "limite_arredondamento": limite,
    }
    return {"orbe_banco": orbe_banco, "remessa_banco": remessa_banco, "ponte": ponte_info}
