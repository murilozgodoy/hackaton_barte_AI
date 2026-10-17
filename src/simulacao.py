"""Efeito de uma regra proposta ANTES de gravar: fecha o mês duas vezes numa pasta temporária (base atual x base +
proposta) e compara os dois fechamentos. Nada é gravado na base real nem em saida/.

O que se compara, sempre por chave de negócio (CNPJ + linha de negócio, tipo + subtipo + CNPJ/referência), nunca por
id_saida (um lojista a mais renumera os ids seguintes):
  comissões por lojista que mudam, aparecem ou somem; notas novas, removidas ou com outro valor; pendências que
  aparecem, somem ou mudam de valor; divergências por natureza; linhas da carteira anterior que entrariam na
  comissão; lançamentos que mudam de conta (regras CLASSIFICAR_CONTA); totais e integridade do fechamento simulado.
"""
from __future__ import annotations

import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .comandos import COLUNAS_COMPLEMENTO_SIM, COLUNAS_REGRAS_SIM, Proposta, _anexar_csv
from .dinheiro import ZERO, brl, soma
from .fechamento import executar
from .notas import competencia_texto
from .regras import carregar_config


def _s(v) -> str | None:
    return None if v is None else f"{Decimal(v).quantize(Decimal('0.01')):f}"


def _comissoes(f) -> dict:
    return {(r.cnpj, r.linha_negocio): r for r in f.comissoes.itertuples(index=False)}


def _notas(f) -> dict:
    return {(r.tomador_cnpj, r.linha_negocio): r for r in f.notas.itertuples(index=False)}


def _pendencias(f) -> dict:
    out = {}
    for r in f.pendencias.itertuples(index=False):
        chave = (r.tipo, r.subtipo or "", r.cnpj or str(r.ref_origem))
        out[chave] = r
    return out


def _qtd(r) -> int:
    v = r.qtd_transacoes if r.linha_negocio == "CHECKOUT" else r.qtd_operacoes
    return int(v) if v is not None and not pd.isna(v) else 0


def simular(dir_regras: Path, proposta: Proposta, dados: dict, competencia: str, bancos: set[str],
            carteira: pd.DataFrame | None = None, contestacao_anterior: dict | None = None) -> dict:
    """Fecha com a base atual e com a base + proposta (cópia temporária) e devolve a comparação em números e em texto."""
    dir_regras = Path(dir_regras)
    tmp = Path(tempfile.mkdtemp(prefix="simulacao_regras_"))
    try:
        shutil.copytree(dir_regras, tmp / "regras")
        alvo = tmp / "regras" / proposta.alvo
        colunas = COLUNAS_REGRAS_SIM if proposta.alvo == "regras_negocio.csv" else COLUNAS_COMPLEMENTO_SIM
        _anexar_csv(alvo, [proposta.linha.get(c, "") for c in colunas])
        cfg_base = carregar_config(dir_regras, dados["taxas"], dados["plano_contas"], bancos)
        cfg_nova = carregar_config(tmp / "regras", dados["taxas"], dados["plano_contas"], bancos)
        base = executar(dados, cfg_base, competencia, usar_ia=False, carteira=carteira, contestacao_anterior=contestacao_anterior)
        nova = executar(dados, cfg_nova, competencia, usar_ia=False, carteira=carteira, contestacao_anterior=contestacao_anterior)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return comparar(base, nova, competencia)


def comparar(base, nova, competencia: str) -> dict:
    comp = competencia_texto(competencia)
    cb, cn = _comissoes(base), _comissoes(nova)
    comissoes = []
    for chave in sorted(set(cb) | set(cn)):
        a, d = cb.get(chave), cn.get(chave)
        va, vd = (a.comissao_brl if a is not None else None), (d.comissao_brl if d is not None else None)
        if va == vd:
            continue
        comissoes.append({"cnpj": chave[0], "linha_negocio": chave[1], "lojista": (d or a).lojista,
                          "antes_brl": _s(va), "depois_brl": _s(vd),
                          "qtd_antes": _qtd(a) if a is not None else 0, "qtd_depois": _qtd(d) if d is not None else 0})
    nb, nn = _notas(base), _notas(nova)
    notas = []
    for chave in sorted(set(nb) | set(nn)):
        a, d = nb.get(chave), nn.get(chave)
        va, vd = (a.valor_brl if a is not None else None), (d.valor_brl if d is not None else None)
        if va == vd:
            continue
        notas.append({"tomador_cnpj": chave[0], "linha_negocio": chave[1], "tomador": (d or a).tomador,
                      "antes_brl": _s(va), "depois_brl": _s(vd),
                      "id_depois": d.id_saida if d is not None else None,
                      "situacao": "nova" if a is None else ("removida" if d is None else "muda de valor")})
    pb, pn = _pendencias(base), _pendencias(nova)
    pendencias = []
    for chave in sorted(set(pb) | set(pn), key=str):
        a, d = pb.get(chave), pn.get(chave)
        va, vd = (a.valor_brl if a is not None else None), (d.valor_brl if d is not None else None)
        if a is not None and d is not None and va == vd:
            continue
        r = d or a
        pendencias.append({"tipo": chave[0], "subtipo": chave[1] or None, "cnpj_ou_ref": chave[2], "lojista": r.lojista,
                           "quem_decide": r.quem_decide, "antes_brl": _s(va), "depois_brl": _s(vd),
                           "situacao": "aparece" if a is None else ("some" if d is None else "muda de valor")})
    div = {}
    for nome, f in (("antes", base), ("depois", nova)):
        por = {}
        if len(f.divergencias):
            for nat, g in f.divergencias.groupby("natureza", sort=False):
                por[str(nat)] = {"linhas": int(len(g)), "valor_brl": _s(soma(g["diferenca_brl"]))}
        div[nome] = por
    refs_base = set(base.carteira["ref_origem"]) if len(base.carteira) else set()
    refs_nova = set(nova.carteira["ref_origem"]) if len(nova.carteira) else set()
    saem = refs_base - refs_nova
    carteira_antes = base.carteira[base.carteira["ref_origem"].isin(saem)] if saem else base.carteira.iloc[0:0]
    lanc = []
    lb = dict(zip(base.lancamentos["ref_origem"] + "|" + base.lancamentos["banco"], base.lancamentos["conta_codigo"]))
    for r in nova.lancamentos.itertuples(index=False):
        antes = lb.get(f"{r.ref_origem}|{r.banco}")
        if antes != r.conta_codigo:
            lanc.append({"banco": r.banco, "ref_origem": r.ref_origem, "descricao": r.descricao, "valor": _s(r.valor),
                         "conta_antes": antes or "", "conta_depois": r.conta_codigo or ""})
    totais = {
        "comissao_checkout_brl": {"antes": _s(soma(base.comissoes_checkout["comissao_brl"])), "depois": _s(soma(nova.comissoes_checkout["comissao_brl"]))},
        "comissao_remessa_brl": {"antes": _s(soma(base.comissoes_remessa["comissao_brl"])), "depois": _s(soma(nova.comissoes_remessa["comissao_brl"]))},
        "notas": {"antes": {"quantidade": int(len(base.notas)), "valor_brl": _s(soma(base.notas["valor_brl"]))},
                  "depois": {"quantidade": int(len(nova.notas)), "valor_brl": _s(soma(nova.notas["valor_brl"]))}},
        "pendencias": {"antes": int(len(base.pendencias)), "depois": int(len(nova.pendencias))},
    }
    res = {
        "competencia": competencia, "integridade_depois": "OK" if nova.integro else "FALHA",
        "comissoes_que_mudam": comissoes, "notas_que_mudam": notas, "pendencias_que_mudam": pendencias,
        "divergencias_por_natureza": div, "lancamentos_que_mudam_de_conta": lanc,
        "carteira_que_entraria": {"linhas": int(len(carteira_antes)),
                                  "valor_bruto_brl": _s(soma(carteira_antes["valor_bruto"])) if len(carteira_antes) else "0.00",
                                  "de_meses_anteriores": int((carteira_antes["idade_meses"] > 0).sum()) if len(carteira_antes) else 0},
        "totais": totais,
        "nada_muda": not (comissoes or notas or pendencias or lanc or div["antes"] != div["depois"]),
    }
    res["texto"] = _texto(res, comp)
    return res


def _texto(res: dict, comp: str) -> list[str]:
    linhas = []
    if res["nada_muda"]:
        return [f"Nenhum número do fechamento de {comp} muda com esta regra (comissões, notas, divergências, pendências e "
                f"lançamentos iguais). Integridade: {res['integridade_depois']}."]
    for c in res["comissoes_que_mudam"]:
        if c["antes_brl"] is None:
            linhas.append(f"{c['lojista']} ({c['cnpj']}, {c['linha_negocio']}) passa a gerar {brl(Decimal(c['depois_brl']))} em "
                          f"{c['qtd_depois']} transações (hoje fica fora da comissão).")
        elif c["depois_brl"] is None:
            linhas.append(f"{c['lojista']} ({c['cnpj']}, {c['linha_negocio']}) sai da comissão (hoje {brl(Decimal(c['antes_brl']))} em "
                          f"{c['qtd_antes']} transações).")
        else:
            linhas.append(f"{c['lojista']} ({c['cnpj']}, {c['linha_negocio']}): comissão {brl(Decimal(c['antes_brl']))} → "
                          f"{brl(Decimal(c['depois_brl']))} ({c['qtd_antes']} → {c['qtd_depois']} transações).")
    for n in res["notas_que_mudam"]:
        if n["situacao"] == "nova":
            linhas.append(f"Nova nota {n['id_depois']} ({n['linha_negocio']}) para {n['tomador']}: {brl(Decimal(n['depois_brl']))} "
                          f"(as notas seguintes são renumeradas).")
        elif n["situacao"] == "removida":
            linhas.append(f"A nota de {n['tomador']} ({n['linha_negocio']}, {brl(Decimal(n['antes_brl']))}) deixa de existir.")
        else:
            linhas.append(f"Nota de {n['tomador']} ({n['linha_negocio']}): {brl(Decimal(n['antes_brl']))} → {brl(Decimal(n['depois_brl']))}.")
    for p in res["pendencias_que_mudam"]:
        nome = p["tipo"] + (f"/{p['subtipo']}" if p["subtipo"] else "")
        quem = f"{p['lojista']}, " if p["lojista"] else ""
        if p["situacao"] == "some":
            linhas.append(f"Pendência {nome} ({quem}{brl(Decimal(p['antes_brl'])) if p['antes_brl'] else 'sem valor'}) some.")
        elif p["situacao"] == "aparece":
            linhas.append(f"Pendência {nome} ({quem}{brl(Decimal(p['depois_brl'])) if p['depois_brl'] else 'sem valor'}, "
                          f"{p['quem_decide']}) aparece.")
        else:
            linhas.append(f"Pendência {nome} ({quem}): {brl(Decimal(p['antes_brl']))} → {brl(Decimal(p['depois_brl']))}.")
    da, dd = res["divergencias_por_natureza"]["antes"], res["divergencias_por_natureza"]["depois"]
    if da != dd:
        def fmt(d):
            return ", ".join(f"{k} {v['linhas']} ({brl(Decimal(v['valor_brl']))})" for k, v in d.items()) or "nenhuma"
        linhas.append(f"Divergências por natureza: {fmt(da)} → {fmt(dd)}.")
    for l in res["lancamentos_que_mudam_de_conta"][:10]:
        linhas.append(f"Lançamento {l['banco']} {l['ref_origem']} \"{l['descricao']}\" ({brl(Decimal(l['valor']))}): conta "
                      f"{l['conta_antes'] or 'vazia'} → {l['conta_depois'] or 'vazia'}.")
    if len(res["lancamentos_que_mudam_de_conta"]) > 10:
        linhas.append(f"... e mais {len(res['lancamentos_que_mudam_de_conta']) - 10} lançamentos mudam de conta.")
    cart = res["carteira_que_entraria"]
    if cart["linhas"]:
        linhas.append(f"Carteira: {cart['linhas']} linhas que hoje ficam na carteira pendente ({brl(Decimal(cart['valor_bruto_brl']))} brutos; "
                      f"{cart['de_meses_anteriores']} vindas de meses anteriores) entrariam na comissão e na nota deste mês.")
    mudaram = {c["cnpj"] for c in res["comissoes_que_mudam"]}
    if len(mudaram) == 1 and not res["lancamentos_que_mudam_de_conta"]:
        linhas.append("Nenhum outro lojista muda.")
    t = res["totais"]
    linhas.append(f"Totais de {comp}: comissão CHECKOUT {brl(Decimal(t['comissao_checkout_brl']['antes']))} → "
                  f"{brl(Decimal(t['comissao_checkout_brl']['depois']))}; REMESSA {brl(Decimal(t['comissao_remessa_brl']['antes']))} → "
                  f"{brl(Decimal(t['comissao_remessa_brl']['depois']))}; notas {t['notas']['antes']['quantidade']} "
                  f"({brl(Decimal(t['notas']['antes']['valor_brl']))}) → {t['notas']['depois']['quantidade']} "
                  f"({brl(Decimal(t['notas']['depois']['valor_brl']))}); pendências {t['pendencias']['antes']} → {t['pendencias']['depois']}. "
                  f"Integridade do fechamento simulado: {res['integridade_depois']}.")
    return linhas
