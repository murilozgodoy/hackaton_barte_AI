"""resumo.json (para agentes, nada de recalcular) e RELATORIO_FECHAMENTO.md (para pessoas).

Os dois são escritos pelo motor, sem IA. Valores monetários no JSON vão como string
decimal. O relatório é uma página: totais, notas, divergências, pendências por
responsável com o que fazer, lembretes das regras MANUAL, conciliação, avisos e
checagens. Sem data de geração, para o mesmo fechamento gerar sempre o mesmo arquivo.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .dinheiro import ZERO, brl, soma
from .notas import competencia_texto, primeiro_dia

NOMES_ARQUIVOS = {"comissoes": "comissoes_por_lojista.csv", "divergencias": "divergencias_taxa.csv",
                  "notas": "notas_a_emitir.csv", "lancamentos": "lancamentos_classificados.csv",
                  "pendencias": "pendencias.csv", "rastro": "rastro.csv"}


def _s(v) -> str | None:
    """Decimal -> string decimal com 2 casas; None fica None."""
    if v is None:
        return None
    return f"{Decimal(v).quantize(Decimal('0.01')):f}"


def valor_em_jogo(valores) -> Decimal:
    """Soma dos valores absolutos: pendências misturam sinais (spread negativo, saldo negativo, trânsito)."""
    return soma(abs(v) for v in valores if v is not None)


def _grupo(df: pd.DataFrame, coluna: str, col_valor: str) -> dict:
    out = {}
    for chave, g in df.groupby(coluna, sort=False):
        out[str(chave)] = {"quantidade": int(len(g)), "valor_em_jogo_brl": _s(valor_em_jogo(g[col_valor]))}
    return out


def resumo(f, config, arquivos: dict[str, Path], pasta_saida: Path) -> dict:
    div_chk = f.divergencias[f.divergencias["linha_negocio"] == "CHECKOUT"]
    div_rem = f.divergencias[f.divergencias["linha_negocio"] == "REMESSA"]
    met = f.lancamentos["metodo"].value_counts().to_dict()
    ref = primeiro_dia(f.competencia)
    conc = f.conciliacao
    return {
        "competencia": f.competencia,
        "status_integridade": "OK" if f.integro else "FALHA",
        "totais": {
            "comissao_checkout_brl": _s(soma(f.comissoes_checkout["comissao_brl"])),
            "comissao_remessa_brl": _s(soma(f.comissoes_remessa["comissao_brl"])),
            "notas": {"quantidade": int(len(f.notas)), "valor_total_brl": _s(soma(f.notas["valor_brl"]))},
            "divergencias": {
                "checkout": {"linhas": int(len(div_chk)), "valor_brl": _s(soma(div_chk["diferenca_brl"]))},
                "remessa": {"linhas": int(len(div_rem)), "valor_brl": _s(soma(div_rem["diferenca_brl"]))},
            },
            "pendencias": {
                "quantidade": int(len(f.pendencias)),
                "por_responsavel": _grupo(f.pendencias, "quem_decide", "valor_brl"),
                "por_tipo": _grupo(f.pendencias, "tipo", "valor_brl"),
            },
        },
        "lancamentos": {m: int(met.get(m, 0)) for m in ("REGRA", "IA", "HUMANO")},
        "orbe_destinos": {k: int(v) for k, v in f.destinos_orbe.items()},
        "ponte_destinos": {k: int(v) for k, v in f.destinos_ponte.items()},
        "conciliacao": {
            "adquirente_x_banco": {"conciliavel": False, "limitacao": conc["orbe_banco"]["limitacao"],
                                   "recebido_da_adquirente_brl": _s(conc["orbe_banco"]["recebido_da_adquirente"]),
                                   "repassado_a_lojistas_brl": _s(conc["orbe_banco"]["repassado_a_lojistas"])},
            "remessa_x_banco": {k: (_s(v) if isinstance(v, Decimal) else v) for k, v in conc["remessa_banco"].items()},
            "parceiro_cambio": {k: (_s(v) if isinstance(v, Decimal) else v) for k, v in conc["ponte"].items()},
        },
        "lembretes": [{"regra_id": r.id, "situacao": r.situacao, "o_que_fazer": r.o_que_fazer,
                       "quem_decide": r.quem_decide} for r in config.lembretes(ref)],
        "base_de_regras": {"regras_ativas": len(config.regras), "lojistas": int(len(config.cadastro)),
                           "ultima_alteracao_historico": str(config.historico_ultima_alteracao or "")},
        "integridade": [{"nome": c.nome, "ok": c.ok, "detalhe": c.detalhe} for c in f.checagens],
        "avisos": list(f.avisos),
        "arquivos": {k: Path(v).name for k, v in arquivos.items()},   # relativos à pasta deste resumo
    }


def escrever_resumo(res: dict, caminho: Path) -> Path:
    Path(caminho).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return Path(caminho)


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in l) + " |" for l in linhas]
    return "\n".join(out)


def markdown(f, config, res: dict) -> str:
    comp = competencia_texto(f.competencia)
    ref = primeiro_dia(f.competencia)
    t = res["totais"]
    partes = [f"# Fechamento Tarvo — competência {comp}", ""]
    if f.integro:
        partes.append("**Integridade: OK.** Todos os números abaixo têm rastro até as linhas de origem "
                      "(`rastro.csv`) e passaram nas checagens listadas no fim.")
    else:
        partes.append("# ⚠️ RELATÓRIO INVÁLIDO: a integridade falhou. Nenhum número abaixo pode ser usado. "
                      "Veja as checagens no fim.")
    b = res["base_de_regras"]
    partes += ["", f"Base de regras: {b['regras_ativas']} regras ativas, {b['lojistas']} lojistas no cadastro "
               f"(planilha de taxas + complemento). Última alteração registrada no histórico de regras: "
               f"{b['ultima_alteracao_historico'] or 'não informada'}.", ""]

    partes += ["## Totais do mês", "", _tabela(["Linha", "Lojistas", "Comissão"], [
        ["CHECKOUT", len(f.comissoes_checkout), brl(soma(f.comissoes_checkout["comissao_brl"]))],
        ["REMESSA", len(f.comissoes_remessa), brl(soma(f.comissoes_remessa["comissao_brl"]))],
        ["**Total**", "", f"**{brl(soma(f.comissoes['comissao_brl']))}**"],
    ]), ""]
    partes += [f"Notas a emitir: {t['notas']['quantidade']}, somando {brl(Decimal(t['notas']['valor_total_brl']))}. "
               f"Divergências de taxa: {t['divergencias']['checkout']['linhas']} transações de checkout "
               f"({brl(Decimal(t['divergencias']['checkout']['valor_brl']))}) e {t['divergencias']['remessa']['linhas']} "
               f"operações de remessa ({brl(Decimal(t['divergencias']['remessa']['valor_brl']))}). "
               f"Pendências: {t['pendencias']['quantidade']}.", ""]

    partes += ["## Notas a emitir", "", _tabela(["Nota", "Linha", "Tomador", "CNPJ", "Valor"], [
        [r.id_saida, r.linha_negocio, r.tomador, r.tomador_cnpj, brl(r.valor_brl)] for r in f.notas.itertuples()]), ""]
    for r in f.sem_nota.itertuples():
        partes.append(f"Sem nota: {r.lojista} ({r.cnpj}) fechou em {brl(r.comissao_brl)} "
                      f"({'zero' if r.comissao_brl == ZERO else 'negativo, vira pendência'}).")
    partes.append("")

    partes += ["## Divergências de taxa (contratada × aplicada)", ""]
    if f.divergencias.empty:
        partes.append("Nenhuma.")
    else:
        linhas = []
        for (linha, _cnpj), g in f.divergencias.groupby(["linha_negocio", "cnpj"], sort=False):
            linhas.append([linha, g["lojista"].iloc[0], len(g), f"{_fmt_pct(g['taxa_contratada_pct'])} × "
                           f"{_fmt_pct(g['taxa_aplicada_pct'])}", brl(soma(g["diferenca_brl"]))])
        linhas.sort(key=lambda l: -abs(Decimal(l[4].replace("R$", "").replace(".", "").replace(",", ".").replace("-", "").strip() or 0)))
        partes.append(_tabela(["Linha", "Lojista", "Transações", "Contratada × aplicada", "Diferença"], linhas))
        partes.append("")
        partes.append("Cada transação está em `divergencias_taxa.csv`. Nada foi ajustado automaticamente: "
                      "cada caso é uma pendência para decisão.")
    partes.append("")

    partes += ["## Pendências por responsável", ""]
    if f.pendencias.empty:
        partes.append("Nenhuma.")
    for quem, g in f.pendencias.groupby("quem_decide", sort=False):
        partes += [f"### {quem} — {len(g)} pendência(s), {brl(valor_em_jogo(g['valor_brl']))} em jogo", ""]
        for r in g.itertuples():
            valor = brl(r.valor_brl) if r.valor_brl is not None else "sem valor"
            partes.append(f"- **{r.id_saida} · {r.tipo}{(' / ' + r.subtipo) if r.subtipo else ''}** "
                          f"({r.ref_origem}, {valor}): {r.motivo}")
        partes.append("")

    lembretes = config.lembretes(ref)
    if lembretes:
        partes += ["## Lembretes do fechamento (regras em português, não executadas pelo sistema)", ""]
        for r in lembretes:
            partes.append(f"- **{r.id} · {r.situacao}** ({r.quem_decide}): {r.o_que_fazer}")
        partes.append("")

    c = f.conciliacao
    partes += ["## Conciliação entre fontes (informativa)", ""]
    ob = c["orbe_banco"]
    partes.append(f"- **Adquirente × banco:** {ob['limitacao']}. Totais informativos do mês: recebido da adquirente "
                  f"{brl(ob['recebido_da_adquirente'])} ({ob['qtd_recebimentos']} créditos); repassado a lojistas "
                  f"{brl(ob['repassado_a_lojistas'])} ({ob['qtd_repasses']} lançamentos).")
    rb = c["remessa_banco"]
    partes.append(f"- **Remessa × banco:** liquidado no parceiro {brl(rb['liquidado_na_ponte'])} = operações do relatório "
                  f"(Valor R$ + IOF) {brl(rb['operacoes_valor_mais_iof'])} "
                  f"(diferença {brl(rb['liquidado_menos_operacoes'])}). Recursos recebidos de lojistas "
                  f"{brl(rb['recursos_recebidos'])}: {brl(rb['recursos_menos_liquidado'])} acima do liquidado"
                  + (" (ver pendência RECURSO_SEM_OPERACAO)." if rb["recursos_menos_liquidado"] != ZERO else "."))
    pc = c["ponte"]
    if pc["diferenca"] is not None:
        partes.append(f"- **Parceiro de câmbio:** pelo total declarado ({brl(pc['spread_total_declarado'])}) o parceiro "
                      f"repassaria {brl(pc['repasse_pelo_total_declarado'])}; a nota é {brl(pc['comissao_calculada'])}. "
                      f"Diferença {brl(pc['diferenca'])} = {brl(pc['efeito_excluidas'])} (operações excluídas) "
                      f"{'+' if pc['efeito_duplicatas'] >= 0 else '−'} {brl(abs(pc['efeito_duplicatas']))} (repetições) "
                      f"+ {brl(pc['efeito_arredondamento'])} (arredondamento por operação)"
                      + (" — ver pendência REPASSE_PONTE_DIVERGENTE." if pc["diferenca"] != ZERO else "."))
    partes.append("")

    if f.avisos:
        partes += ["## Avisos", ""] + [f"- {a}" for a in f.avisos] + [""]

    partes += ["## Checagens de integridade", ""]
    partes += [f"- {'✅' if ch.ok else '❌'} {ch.nome}: {ch.detalhe}" for ch in f.checagens]
    partes += ["", "Arquivos: " + ", ".join(f"`{v}`" for v in res["arquivos"].values()) + ".", ""]
    return "\n".join(partes)


def _fmt_pct(serie) -> str:
    vals = sorted({v for v in serie if v is not None})
    txt = [f"{v.quantize(Decimal('0.01')).normalize():f}%" for v in vals]
    return txt[0] if len(txt) == 1 else f"{txt[0]}–{txt[-1]}"


def escrever_relatorio(texto: str, caminho: Path) -> Path:
    Path(caminho).write_text(texto, encoding="utf-8")
    return Path(caminho)
