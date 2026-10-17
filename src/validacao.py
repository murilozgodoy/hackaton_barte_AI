"""Checagens de integridade que rodam em toda execução.

ERRO interrompe o fechamento (número não confiável). AVISO aparece no resumo
mas não impede a saída. Nada aqui depende do mês: só invariantes dos arquivos.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

CENTAVO = Decimal("0.01")


@dataclass
class Checagem:
    fonte: str
    nome: str
    ok: bool
    detalhe: str
    nivel: str = "ERRO"  # ERRO | AVISO | INFO


def _soma(serie) -> Decimal:
    return sum((v for v in serie if v is not None), Decimal("0"))


def _hu(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def validar_leitores(d: dict[str, pd.DataFrame]) -> list[Checagem]:
    c: list[Checagem] = []

    # Orbe
    o = d["orbe"]
    dup = o["id_transacao"].duplicated().sum()
    c.append(Checagem("orbe", "id_transacao único", dup == 0, f"{len(o)} linhas, {dup} ids repetidos"))
    ruins = sum(1 for b, t, l in zip(o.valor_bruto, o.valor_taxa, o.valor_liquido) if b - t != l)
    c.append(Checagem("orbe", "valor_liquido = valor_bruto - valor_taxa", ruins == 0,
                      f"{ruins} linhas não fecham"))

    # Taxas
    t = d["taxas"]
    c.append(Checagem("taxas", "CNPJ com 14 dígitos", t["cnpj"].str.fullmatch(r"\d{14}").all(),
                      f"{t['cnpj'].nunique()} CNPJs em {t['linha_planilha'].nunique()} linhas"))
    for ign in t.attrs.get("linhas_ignoradas", []):
        c.append(Checagem("taxas", "linha ignorada", True,
                          f"linha {ign['linha']} ({ign['motivo']}): {ign['conteudo']}", "INFO"))

    # Ponte
    p = d["ponte"]
    tot = p.attrs.get("totais_declarados", {})
    if "TOTAL DE OPERACOES:" in tot:
        n_decl = int(tot["TOTAL DE OPERACOES:"])
        c.append(Checagem("ponte", "linhas lidas = total declarado no relatório", len(p) == n_decl,
                          f"lidas {len(p)}, declarado {n_decl}"))
    if "SPREAD TOTAL R$:" in tot:
        s, s_decl = _soma(p.spread_brl), tot["SPREAD TOTAL R$:"]
        c.append(Checagem("ponte", "soma Spread R$ = total declarado no relatório", s == s_decl,
                          f"soma {s}, declarado {s_decl}"))
    ruins = sum(1 for me, tc, v in zip(p.valor_me, p.taxa_cliente, p.valor_brl) if _hu(me * tc) != v)
    c.append(Checagem("ponte", "Valor R$ = Valor ME x Taxa Cliente", ruins == 0,
                      f"{ruins} operações não fecham", "AVISO"))
    ruins = sum(1 for me, tc, px, s in zip(p.valor_me, p.taxa_cliente, p.ptax, p.spread_brl)
                if _hu((tc - px) * me) != s)
    c.append(Checagem("ponte", "Spread R$ = (Taxa Cliente - PTAX) x Valor ME", ruins == 0,
                      f"{ruins} operações não fecham", "AVISO"))
    rep = p["num_operacao"].duplicated(keep=False)
    c.append(Checagem("ponte", "Nº Operação repetido", True,
                      f"{p.loc[rep, 'num_operacao'].nunique()} número(s) aparecem mais de uma vez: "
                      f"{sorted(p.loc[rep, 'num_operacao'].unique())}", "INFO"))

    # Plano de contas
    pc = d["plano_contas"]
    c.append(Checagem("plano_contas", "COD_CONTA único", not pc["cod_conta"].duplicated().any(),
                      f"{len(pc)} contas, {int(pc['aceita_lancto'].sum())} aceitam lançamento"))

    # Aurora
    a = d["aurora"]
    ant, fim = a.attrs.get("saldo_anterior"), a.attrs.get("saldo_final")
    if ant and fim:
        soma = _soma(a.valor)
        c.append(Checagem("aurora", "saldo anterior + lançamentos = saldo final",
                          ant["valor"] + soma == fim["valor"],
                          f"{ant['valor']} + {soma} = {ant['valor'] + soma}; extrato diz {fim['valor']}"))
    else:
        c.append(Checagem("aurora", "saldo anterior e final presentes", False,
                          "não encontrei SALDO ANTERIOR ou SALDO FINAL"))
    if ant:
        corrente, quebras = ant["valor"], []
        for ref, v, s in zip(a.ref_origem, a.valor, a.saldo):
            corrente += v
            if s is not None and corrente != s:
                quebras.append(ref)
                corrente = s
        c.append(Checagem("aurora", "saldo linha a linha", not quebras,
                          f"{len(quebras)} linhas com saldo que não fecha {quebras[:5]}"))

    # Meridiano
    m = d["meridiano"]
    dup = m["ref_origem"].duplicated().sum()
    c.append(Checagem("meridiano", "FITID único", dup == 0, f"{len(m)} transações, {dup} FITIDs repetidos"))
    de, ate = m.attrs.get("periodo_de"), m.attrs.get("periodo_ate")
    if de and ate:
        fora = ((m["data"].dt.date < de) | (m["data"].dt.date > ate)).sum()
        c.append(Checagem("meridiano", "datas dentro do período do extrato", fora == 0,
                          f"{fora} transações fora de {de} a {ate}", "AVISO"))
    if m.attrs.get("saldo_final") is not None:
        implicito = m.attrs["saldo_final"] - _soma(m.valor)
        c.append(Checagem("meridiano", "saldo inicial (o OFX não informa)", True,
                          f"saldo final {m.attrs['saldo_final']} - lançamentos {_soma(m.valor)} "
                          f"= saldo inicial implícito {implicito}", "INFO"))
    return c
