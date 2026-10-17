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


def checar_rastro(saidas: dict[str, tuple[pd.DataFrame, str]], rastro: pd.DataFrame) -> list[Checagem]:
    """Checagem 1: a soma do rastro por id_saida é igual ao valor reportado, para todo id com valor.

    `saidas` = {nome do arquivo: (DataFrame, coluna de valor)}. Também confere que todo
    id do rastro existe em alguma saída (nada órfão).
    """
    c: list[Checagem] = []
    somas = rastro.groupby("id_saida")["valor"].apply(_soma) if len(rastro) else pd.Series(dtype=object)
    ids_saida: set[str] = set()
    for nome, (df, coluna) in saidas.items():
        nao_batem, sem_rastro, conferidos = [], [], 0
        for id_saida, valor in zip(df["id_saida"], df[coluna]):
            ids_saida.add(id_saida)
            if valor is None or (not isinstance(valor, Decimal) and pd.isna(valor)):
                continue  # linha sem valor (ex.: pendência informativa) não precisa de rastro
            if id_saida not in somas.index:
                sem_rastro.append(id_saida)
                continue
            conferidos += 1
            if somas[id_saida] != valor:
                nao_batem.append(f"{id_saida}: reportado {valor}, rastro {somas[id_saida]}")
        ok = not nao_batem and not sem_rastro
        detalhe = (f"{conferidos} ids conferidos" if ok else
                   f"{len(nao_batem)} não batem {nao_batem[:3]}; {len(sem_rastro)} sem rastro {sem_rastro[:3]}")
        c.append(Checagem("integridade", f"1. soma do rastro = valor reportado ({nome})", ok, detalhe))
    orfaos = sorted(set(somas.index) - ids_saida)
    c.append(Checagem("integridade", "1. todo id do rastro existe nas saídas", not orfaos,
                      f"{len(somas)} ids no rastro" if not orfaos else f"órfãos: {orfaos[:5]}"))
    return c


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
