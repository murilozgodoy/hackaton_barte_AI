"""Conciliação informativa entre fontes (só números; não gera pendência).

Orbe x Aurora: quanto a Orbe diz que liquidou aos lojistas (valor_liquido) e quanto
entrou/saiu no banco por conta contábil. Ponte: quanto a Ponte repassaria pelo total
dela x quanto a Tarvo tem a receber pelo cálculo próprio.
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .dinheiro import arredondar, soma


def calcular(dados: dict[str, pd.DataFrame], com_rem: pd.DataFrame, lancamentos: pd.DataFrame,
             participacao: Decimal, modo: str) -> dict:
    orbe, ponte = dados["orbe"], dados["ponte"]
    liquido_por_tipo = {t: soma(g["valor_liquido"]) for t, g in orbe.groupby("tipo_lancamento")}
    lanc = lancamentos[lancamentos["conta_codigo"].astype(str) != ""]
    por_conta = []
    for (banco, conta), g in lanc.groupby(["banco", "conta_codigo"]):
        por_conta.append({"banco": banco, "conta_codigo": conta, "conta_descricao": g["conta_descricao"].iloc[0],
                          "qtd": len(g), "creditos": soma(v for v in g["valor"] if v > 0),
                          "debitos": soma(v for v in g["valor"] if v < 0)})

    total_declarado = ponte.attrs.get("totais_declarados", {}).get("SPREAD TOTAL R$:")
    spread_unicos = soma(ponte.drop_duplicates("num_operacao")["spread_brl"])
    comissao_rem = soma(com_rem["comissao_brl"]) if len(com_rem) else Decimal("0")
    repasse_pelo_total = arredondar(total_declarado * participacao, modo) if total_declarado is not None else None
    return {
        "orbe": {"valor_bruto_total": soma(orbe["valor_bruto"]), "valor_taxa_total": soma(orbe["valor_taxa"]),
                 "valor_liquido_total": soma(orbe["valor_liquido"]), "valor_liquido_por_tipo": liquido_por_tipo},
        "extratos_por_conta": por_conta,
        "ponte": {"spread_total_declarado": total_declarado, "spread_operacoes_unicas": spread_unicos,
                  "repasse_pelo_total_declarado": repasse_pelo_total, "comissao_calculada": comissao_rem,
                  "diferenca": (comissao_rem - repasse_pelo_total) if repasse_pelo_total is not None else None},
    }
