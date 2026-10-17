"""Classificação dos lançamentos dos extratos bancários no plano de contas.

conta_codigo é a CONTRAPARTIDA do movimento. Para cada lançamento:
  REGRA   uma regra CLASSIFICAR_CONTA casou (menor prioridade vence): confiança 1
  IA      nenhuma regra casou e há ANTHROPIC_API_KEY: sugestão da IA, confiança < 1,
          e pendência REVISAR_IA (a IA só recebe banco, data, descrição e valor da
          linha, mais a lista de contas analíticas)
  HUMANO  nenhuma regra casou (ou duas de mesma prioridade discordam) e não há IA:
          conta vazia, confiança 0, pendência EXTRATO_NAO_IDENTIFICADO

Transferências entre contas próprias: um débito numa conta transitória em um banco
que não tem crédito de mesmo valor em outro banco dentro do mês fica "em trânsito"
(pendência EM_TRANSITO, informativa). A detecção é genérica: vale para qualquer
conta contábil que receba lançamentos dos dois bancos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from .regras import Config

PREFIXO_ID = "LAN-"
COLUNAS = ["id_saida", "banco", "ref_origem", "data", "descricao", "valor", "conta_codigo", "metodo", "confianca",
           "conta_descricao", "regra_id", "arquivo_origem", "tipo_pendencia", "subtipo", "motivo", "justificativa"]
COLUNAS_RASTRO = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]
UM, ZERO = Decimal("1"), Decimal("0")


@dataclass
class ResultadoExtratos:
    lancamentos: pd.DataFrame
    rastro: pd.DataFrame
    em_transito: pd.DataFrame
    avisos: list[str] = field(default_factory=list)


def classificar(extratos: list[pd.DataFrame], config: Config, plano: pd.DataFrame, usar_ia: bool = True
                ) -> ResultadoExtratos:
    descricao_conta = dict(zip(plano["cod_conta"], plano["descricao"]))
    registros, avisos = [], []
    for df in extratos:
        for r in df.itertuples(index=False):
            registros.append(_classificar_linha(r, config, descricao_conta))

    pendentes = [i for i, reg in enumerate(registros) if reg["metodo"] is None]
    if pendentes and usar_ia:
        _sugerir_com_ia(registros, pendentes, plano, descricao_conta, avisos)
    for i in pendentes:
        reg = registros[i]
        if reg["metodo"] is None:
            reg.update(metodo="HUMANO", confianca=ZERO, conta_codigo="", tipo_pendencia="EXTRATO_NAO_IDENTIFICADO",
                       subtipo=reg["subtipo"] or "SEM_REGRA",
                       motivo=reg["motivo"] or "nenhuma regra CLASSIFICAR_CONTA cobre este lançamento")

    lanc = pd.DataFrame(registros, columns=COLUNAS)
    lanc["id_saida"] = [f"{PREFIXO_ID}{i:04d}" for i in range(1, len(lanc) + 1)]
    rastro = pd.DataFrame({
        "id_saida": lanc["id_saida"], "arquivo_origem": lanc["arquivo_origem"], "ref_origem": lanc["ref_origem"],
        "valor": lanc["valor"], "regra_id": lanc["regra_id"], "taxa_pct": None,
    })[COLUNAS_RASTRO]
    return ResultadoExtratos(lanc, rastro, _em_transito(lanc), avisos)


def _classificar_linha(r, config: Config, descricao_conta: dict) -> dict:
    reg = dict.fromkeys(COLUNAS)
    reg.update(banco=r.banco, ref_origem=r.ref_origem, data=r.data, descricao=r.descricao, valor=r.valor,
               arquivo_origem=r.arquivo_origem)
    c = config.classificar(r.banco, r.descricao, r.valor, r.data.date())
    if c.regra is not None:
        p = c.regra.params
        reg.update(conta_codigo=p["conta"], conta_descricao=descricao_conta.get(p["conta"]), metodo="REGRA",
                   confianca=UM, regra_id=c.regra.id)
        if p.get("gera_pendencia"):
            reg.update(tipo_pendencia=c.regra.tipo_pendencia, subtipo=c.regra.subtipo, motivo=c.regra.o_que_fazer)
    elif c.conflito:
        ids = ", ".join(f"{x.id} ({x.params['conta']})" for x in c.conflito)
        reg.update(subtipo="CONFLITO_DE_REGRAS",
                   motivo=f"regras de mesma prioridade indicam contas diferentes: {ids}", regra_id=None)
    return reg


def _sugerir_com_ia(registros: list, pendentes: list[int], plano: pd.DataFrame, descricao_conta: dict,
                    avisos: list[str]) -> None:
    from . import ia  # import tardio: o pacote anthropic é opcional

    if not ia.disponivel():
        avisos.append(f"{len(pendentes)} lançamento(s) sem regra; sem ANTHROPIC_API_KEY, ficam para classificação manual")
        return
    linhas = [{"ref": registros[i]["ref_origem"], "banco": registros[i]["banco"],
               "data": registros[i]["data"].strftime("%Y-%m-%d"), "descricao": registros[i]["descricao"],
               "valor": str(registros[i]["valor"])} for i in pendentes
              if registros[i]["subtipo"] != "CONFLITO_DE_REGRAS"]
    if not linhas:
        return
    contas = plano[plano["aceita_lancto"]][["cod_conta", "descricao"]].to_dict("records")
    try:
        sugestoes = ia.sugerir_contas(linhas, contas)
    except Exception as e:  # qualquer falha da IA cai para HUMANO, nunca derruba o fechamento
        avisos.append(f"IA indisponível ({type(e).__name__}: {e}); lançamentos sem regra ficam para classificação manual")
        return
    for i in pendentes:
        s = sugestoes.get(registros[i]["ref_origem"])
        if not s or s["conta_codigo"] not in descricao_conta:
            continue
        registros[i].update(conta_codigo=s["conta_codigo"], conta_descricao=descricao_conta[s["conta_codigo"]],
                            metodo="IA", confianca=s["confianca"], regra_id=None, tipo_pendencia="REVISAR_IA",
                            subtipo="SUGESTAO_IA", justificativa=s.get("justificativa"),
                            motivo=f"conta sugerida pela IA (confiança {s['confianca']}); revisar e, se recorrente, "
                                   "criar regra CLASSIFICAR_CONTA")


def _em_transito(lanc: pd.DataFrame) -> pd.DataFrame:
    """Débitos em conta transitória sem crédito de mesmo valor em outro banco (e vice-versa)."""
    colunas = ["id_saida", "banco", "ref_origem", "data", "descricao", "valor", "conta_codigo", "motivo"]
    base = lanc[(lanc["metodo"] == "REGRA") & (lanc["conta_codigo"] != "")]
    pendentes = []
    for conta, g in base.groupby("conta_codigo"):
        # só é transferência entre contas próprias se a conta recebe débito num banco e crédito em outro
        bancos_debito = set(g.loc[g["valor"] < 0, "banco"])
        bancos_credito = set(g.loc[g["valor"] > 0, "banco"])
        if not bancos_debito or not bancos_credito or len(bancos_debito | bancos_credito) < 2:
            continue
        debitos = g[g["valor"] < 0].sort_values("data").to_dict("records")
        creditos = g[g["valor"] > 0].sort_values("data").to_dict("records")
        usados = set()
        for d in debitos:
            par = next((c for c in creditos if c["id_saida"] not in usados and c["banco"] != d["banco"]
                        and c["valor"] == -d["valor"] and c["data"] >= d["data"]), None)
            if par is None:
                pendentes.append({**{k: d[k] for k in colunas[:-1]},
                                  "motivo": f"saiu do {d['banco']} em {d['data'].date()} e não há crédito de "
                                            f"{-d['valor']} em outro banco até o fim do extrato"})
            else:
                usados.add(par["id_saida"])
        for c in creditos:
            if c["id_saida"] not in usados:
                pendentes.append({**{k: c[k] for k in colunas[:-1]},
                                  "motivo": f"entrou no {c['banco']} em {c['data'].date()} sem débito "
                                            f"correspondente em outro banco neste mês (saiu no mês anterior?)"})
    return pd.DataFrame(pendentes, columns=colunas)
