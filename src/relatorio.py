"""resumo.json (para agentes, nada de recalcular) e RELATORIO_FECHAMENTO.md (para pessoas).

Os dois são escritos pelo motor, sem IA. Valores monetários no JSON vão como string
decimal já arredondada ao centavo (um valor não arredondado é erro, não é arredondado
em silêncio). O relatório é uma página: totais, notas, divergências, pendências por
responsável com o que fazer, lembretes das regras MANUAL, conciliação, avisos e
checagens. Sem data de geração, para o mesmo fechamento gerar sempre o mesmo arquivo.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .dinheiro import CENTAVO, ZERO, brl, soma
from .notas import competencia_texto, primeiro_dia

ASSUNTO_CONCILIACAO_ADQUIRENTE = "conciliacao_adquirente"
ASSUNTO_RECURSO_SEM_OPERACAO = "recurso_sem_operacao"


def observacao_recursos(f, config) -> str | None:
    """Texto para a diferença recursos - liquidado na conciliação de remessa, quando há diferença."""
    rb = f.conciliacao["remessa_banco"]
    if rb["recursos_menos_liquidado"] == ZERO:
        return None
    ref = primeiro_dia(f.competencia)
    lembrete = config.lembrete_por_assunto(ASSUNTO_RECURSO_SEM_OPERACAO, ref)
    if lembrete is not None:
        return (f"Recursos recebidos de lojistas superam o liquidado no parceiro em {brl(rb['recursos_menos_liquidado'])}: "
                f"{lembrete.situacao}. {lembrete.o_que_fazer} (regra {lembrete.id}, {lembrete.quem_decide})")
    if config.dono_se_houver("RECURSO_SEM_OPERACAO", ref) is not None:
        return "ver pendência RECURSO_SEM_OPERACAO"
    return None


def _s(v) -> str | None:
    """Decimal -> string decimal com 2 casas; recusa valor que não esteja arredondado ao centavo."""
    if v is None:
        return None
    d = Decimal(v)
    if d != d.quantize(CENTAVO):
        raise ValueError(f"valor {d} não está arredondado ao centavo")
    return f"{d.quantize(CENTAVO):f}"


def valor_em_jogo(pend) -> Decimal:
    """Soma dos valores absolutos (pendências misturam sinais), sem as informativas (regra: informativa=true).

    Aceita o DataFrame de pendências ou uma série de valores (aí nada é informativo)."""
    if isinstance(pend, pd.DataFrame):
        sel = pend
        if "informativa" in sel.columns:
            sel = sel[~sel["informativa"].astype(bool)]
        if "incluida_em" in sel.columns:
            sel = sel[sel["incluida_em"].isna() | (sel["incluida_em"] == "")]
        return soma(abs(v) for v in sel["valor_brl"] if v is not None)
    return soma(abs(v) for v in pend if v is not None)


def _grupo(df: pd.DataFrame, coluna: str, col_valor: str) -> dict:
    out = {}
    for chave, g in df.groupby(coluna, sort=False):
        out[str(chave)] = {"quantidade": int(len(g)), "valor_brl": _s(valor_em_jogo(g)),
                           "informativas": int(g["informativa"].astype(bool).sum()),
                           "incluidas_em_outra": int(g["incluida_em"].notna().sum())}
    return out


def _conciliacao_json(conc: dict) -> dict:
    def conv(v):
        if isinstance(v, Decimal):
            # dinheiro sai com 2 casas; um limiar como o limite de arredondamento (meio centavo x n) sai como está
            return _s(v) if v == v.quantize(CENTAVO) else f"{v:f}"
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        return v
    ob = conc["orbe_banco"]
    return {
        "adquirente_x_banco": {"conciliavel": False, "recebido_da_adquirente_brl": _s(ob["recebido_da_adquirente"]),
                               "qtd_recebimentos": ob["qtd_recebimentos"],
                               "repassado_a_lojistas_brl": _s(ob["repassado_a_lojistas"]), "qtd_repasses": ob["qtd_repasses"]},
        "remessa_x_banco": conv(conc["remessa_banco"]),
        "parceiro_cambio": conv(conc["ponte"]),
    }


def resumo(f, config, arquivos: dict[str, Path], entrada: dict | None = None) -> dict:
    div_chk = f.divergencias[f.divergencias["linha_negocio"] == "CHECKOUT"]
    div_rem = f.divergencias[f.divergencias["linha_negocio"] == "REMESSA"]
    fora = f.divergencias_fora_contrato
    met = f.lancamentos["metodo"].value_counts().to_dict()
    ref = primeiro_dia(f.competencia)
    return {
        "competencia": f.competencia,
        "status_integridade": "OK" if f.integro else "FALHA",
        "entrada": entrada or {},
        "totais": {
            "comissao_checkout_brl": _s(soma(f.comissoes_checkout["comissao_brl"])),
            "comissao_remessa_brl": _s(soma(f.comissoes_remessa["comissao_brl"])),
            "notas": {"quantidade": int(len(f.notas)), "valor_total_brl": _s(soma(f.notas["valor_brl"]))},
            "divergencias": {
                "checkout": {"linhas": int(len(div_chk)), "valor_brl": _s(soma(div_chk["diferenca_brl"]))},
                "remessa": {"linhas": int(len(div_rem)), "valor_brl": _s(soma(div_rem["diferenca_brl"]))},
                # fora das divergências de contrato, por regra TAXA_EXCECAO (ex.: isenção que não chegou à adquirente)
                "devolucao_lojista": {"linhas": int(len(fora)), "valor_brl": _s(soma(fora["diferenca_brl"]))},
            },
            "pendencias": {
                "quantidade": int(len(f.pendencias)),
                "informativas": int(f.pendencias["informativa"].astype(bool).sum()) if len(f.pendencias) else 0,
                "em_jogo_brl": _s(valor_em_jogo(f.pendencias)) if len(f.pendencias) else "0.00",
                "nota": "valor_brl por responsável e por tipo é a soma dos valores absolutos (valor em jogo), sem as "
                        "pendências informativas nem as já incluídas em outra (incluida_em): nenhuma linha de origem "
                        "conta duas vezes",
                "por_responsavel": _grupo(f.pendencias, "quem_decide", "valor_brl"),
                "por_tipo": _grupo(f.pendencias, "tipo", "valor_brl"),
            },
        },
        "lancamentos": {m: int(met.get(m, 0)) for m in ("REGRA", "IA", "HUMANO")},
        "carteira_pendente": _carteira_json(f),
        "orbe_destinos": {k: int(v) for k, v in f.destinos_orbe.items()},
        "ponte_destinos": {k: int(v) for k, v in f.destinos_ponte.items()},
        "conciliacao": {**_conciliacao_json(f.conciliacao),
                        "remessa_x_banco": {**_conciliacao_json(f.conciliacao)["remessa_x_banco"],
                                            "observacao": observacao_recursos(f, config)}},
        "lembretes": [{"regra_id": r.id, "situacao": r.situacao, "o_que_fazer": r.o_que_fazer,
                       "quem_decide": r.quem_decide} for r in config.lembretes(ref)],
        "base_de_regras": {"regras_ativas": len(config.regras), "lojistas": int(len(config.cadastro)),
                           "ultima_alteracao_historico": str(config.historico_ultima_alteracao or "")},
        "integridade": [{"nome": c.nome, "ok": c.ok, "detalhe": c.detalhe} for c in f.checagens],
        "avisos": list(f.avisos),
        "arquivos": {k: (f"comunicacoes/{Path(v).name}" if k.startswith("comunicacoes/") else Path(v).name)
                     for k, v in arquivos.items()},   # relativos à pasta deste resumo
    }


def _carteira_json(f) -> dict:
    c = f.carteira
    de_antes = f.orbe_linhas[f.orbe_linhas["competencia_origem"].notna()] if "competencia_origem" in f.orbe_linhas.columns else f.orbe_linhas.iloc[0:0]
    return {"linhas": int(len(c)), "valor_bruto_brl": _s(soma(c["valor_bruto"])) if len(c) else "0.00",
            "de_meses_anteriores": int((c["idade_meses"] > 0).sum()) if len(c) else 0,
            "faturadas_de_meses_anteriores": int((de_antes["destino"] == "COMISSAO").sum())}


def escrever_resumo(res: dict, caminho: Path) -> Path:
    Path(caminho).write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return Path(caminho)


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> str:
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join("---" for _ in cabecalho) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in l) + " |" for l in linhas]
    return "\n".join(out)


def _fmt_pct(serie) -> str:
    vals = sorted({v.quantize(Decimal("0.01")) for v in serie if v is not None})
    txt = [f"{v.normalize():f}%" for v in vals]
    return txt[0] if len(txt) == 1 else f"{txt[0]}–{txt[-1]}"


def _assinado(v: Decimal) -> str:
    return ("+ " if v >= 0 else "− ") + brl(abs(v))


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
    entrada = res.get("entrada") or {}
    if entrada.get("arquivos"):
        partes += ["", "Arquivos do mês: " + ", ".join(f"`{a}`" for a in entrada["arquivos"].values())
                   + (" (competência inferida dos dados)." if entrada.get("competencia_inferida") else ".")]
    partes += ["", f"Base de regras: {b['regras_ativas']} regras ativas, {b['lojistas']} lojistas no cadastro "
               f"(planilha de taxas + complemento). Última alteração registrada no histórico de regras: "
               f"{b['ultima_alteracao_historico'] or 'não informada'}.", ""]

    total_com = soma(f.comissoes["comissao_brl"])
    total_nf = soma(f.notas["valor_brl"])
    partes += ["## Totais do mês", "", _tabela(["Linha", "Lojistas", "Comissão"], [
        ["CHECKOUT", len(f.comissoes_checkout), brl(soma(f.comissoes_checkout["comissao_brl"]))],
        ["REMESSA", len(f.comissoes_remessa), brl(soma(f.comissoes_remessa["comissao_brl"]))],
        ["**Total**", "", f"**{brl(total_com)}**"],
    ]), ""]
    ponte_nf = ""
    if total_nf != total_com:
        negativos = [f"{r.lojista} {brl(r.comissao_brl)}" for r in f.sem_nota.itertuples() if r.comissao_brl < 0]
        ponte_nf = (f" A diferença de {brl(total_nf - total_com)} para a comissão total é o saldo negativo sem nota "
                    f"({'; '.join(negativos)}).") if negativos else f" (difere da comissão total em {brl(total_nf - total_com)})."
    partes += [f"Notas a emitir: {t['notas']['quantidade']}, somando {brl(total_nf)}.{ponte_nf} "
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
        grupos = []
        for (linha, _cnpj), g in f.divergencias.groupby(["linha_negocio", "cnpj"], sort=False):
            grupos.append((soma(g["diferenca_brl"]), linha, g))
        grupos.sort(key=lambda x: -abs(x[0]))
        linhas = [[linha, g["lojista"].iloc[0], len(g),
                   f"{_fmt_pct(g['taxa_contratada_pct'])} × {_fmt_pct(g['taxa_aplicada_pct'])}", brl(total)]
                  for total, linha, g in grupos]
        partes.append(_tabela(["Linha", "Lojista", "Transações", "Contratada × aplicada", "Diferença"], linhas))
        partes.append("")
        partes.append("Cada transação está em `divergencias_taxa.csv`. Nada foi ajustado automaticamente: "
                      "cada caso é uma pendência para decisão.")
    for (cnpj, natureza), g in f.divergencias_fora_contrato.groupby(["cnpj", "natureza"], sort=False):
        partes.append("")
        partes.append(f"**Fora das divergências de contrato** ({natureza.lower().replace('_', ' ')}, regra "
                      f"{g['regra_id'].iloc[0]}): {len(g)} transações de {g['lojista'].iloc[0]} com condição especial "
                      f"contratada ({_fmt_pct(g['taxa_contratada_pct'])}) em que a adquirente aplicou "
                      f"{_fmt_pct(g['taxa_aplicada_pct'])}, {brl(soma(g['diferenca_brl']))} pela taxa. Não é cobrança da "
                      f"adquirente: ver pendência {g['tipo_pendencia'].iloc[0]}. As transações não estão em "
                      f"`divergencias_taxa.csv`; o rastro está na pendência.")
    partes.append("")

    partes += ["## Pendências por responsável", "",
               "\"Em jogo\" é a soma dos valores absolutos das pendências do responsável, sem as informativas "
               "(marcadas por regra, ex.: em trânsito e alertas) e sem as já incluídas em outra pendência: "
               "nenhuma linha de origem conta duas vezes.", ""]
    if f.pendencias.empty:
        partes.append("Nenhuma.")
    for quem, g in f.pendencias.groupby("quem_decide", sort=False):
        n_inf = int(g["informativa"].astype(bool).sum())
        partes += [f"### {quem} — {len(g)} pendência(s), {brl(valor_em_jogo(g))} em jogo"
                   + (f" ({n_inf} informativa{'s' if n_inf > 1 else ''})" if n_inf else ""), ""]
        for r in g.itertuples():
            valor = brl(r.valor_brl) if r.valor_brl is not None else "sem valor"
            marca = " (informativa)" if r.informativa else (f" (já incluída em {r.incluida_em})" if r.incluida_em else "")
            partes.append(f"- **{r.id_saida} · {r.tipo}{(' / ' + r.subtipo) if r.subtipo else ''}**{marca} "
                          f"({r.ref_origem}, {valor}): {r.motivo}")
        incl = g[g["incluida_em"].notna()]
        for r in incl.itertuples():
            partes.append(f"- Rodapé: {r.tipo} ({brl(r.valor_brl)}) já incluído em {r.incluida_em} de {r.lojista}: "
                          f"mostrado, mas fora da soma do \"em jogo\".")
        partes.append("")

    cj = res["carteira_pendente"]
    if cj["linhas"] or cj["faturadas_de_meses_anteriores"]:
        partes += ["## Carteira pendente (`carteira_pendente.csv`)", ""]
        if cj["linhas"]:
            partes.append(f"- {cj['linhas']} transações de checkout sem contrato, taxa ou cadastro ficam fora da comissão e "
                          f"guardadas para o próximo fechamento (valor bruto {brl(Decimal(cj['valor_bruto_brl']))}; "
                          f"{cj['de_meses_anteriores']} vieram de meses anteriores). Com a taxa confirmada (ex.: TAXA_EXCECAO "
                          f"retroativa), o próximo `fechar --anterior` fatura essas linhas junto com as do mês.")
        if cj["faturadas_de_meses_anteriores"]:
            partes.append(f"- {cj['faturadas_de_meses_anteriores']} transações de meses anteriores entraram na comissão e na "
                          f"nota deste mês (rastro aponta para o arquivo de origem).")
        partes.append("")

    lembretes = [r for r in config.lembretes(ref) if r.params.get("assunto") != ASSUNTO_CONCILIACAO_ADQUIRENTE]
    if lembretes:
        partes += ["## Lembretes do fechamento (regras em português, não executadas pelo sistema)", ""]
        for r in lembretes:
            partes.append(f"- **{r.id} · {r.situacao}** ({r.quem_decide}): {r.o_que_fazer}")
        partes.append("")

    c = f.conciliacao
    partes += ["## Conciliação entre fontes (informativa)", ""]
    ob = c["orbe_banco"]
    lembrete = config.lembrete_por_assunto(ASSUNTO_CONCILIACAO_ADQUIRENTE, ref)
    explicacao = (f"{lembrete.situacao}: {lembrete.o_que_fazer} (regra {lembrete.id}, {lembrete.quem_decide})."
                  if lembrete else "não conciliável com os arquivos do mês.")
    partes.append(f"- **Adquirente × banco:** {explicacao} Os totais do mês são só informativos e **não se comparam "
                  f"entre si**: recebido da adquirente {brl(ob['recebido_da_adquirente'])} ({ob['qtd_recebimentos']} "
                  f"créditos); repassado a lojistas {brl(ob['repassado_a_lojistas'])} ({ob['qtd_repasses']} lançamentos).")
    rb = c["remessa_banco"]
    obs = observacao_recursos(f, config)
    partes.append(f"- **Remessa × banco:** liquidado no parceiro {brl(rb['liquidado_na_ponte'])}; operações do relatório "
                  f"(Valor R$ + IOF) {brl(rb['operacoes_valor_mais_iof'])}; diferença {brl(rb['liquidado_menos_operacoes'])}. "
                  f"Recursos recebidos de lojistas {brl(rb['recursos_recebidos'])}: {brl(rb['recursos_menos_liquidado'])} "
                  f"acima do liquidado" + (f" ({obs})." if obs else "."))
    pc = c["ponte"]
    if pc["diferenca"] is not None:
        partes_dif = [f"{_assinado(d['efeito'])} ({d['qtd']} {destino.lower().replace('_', ' ')})"
                      for destino, d in pc["efeitos_por_destino"].items()]
        partes_dif.append(f"{_assinado(pc['residual'])} ("
                          + ("arredondamento por operação" if pc["residual_e_arredondamento"]
                             else "diferença NÃO explicada por arredondamento") + ")")
        partes.append(f"- **Parceiro de câmbio:** pelo total declarado ({brl(pc['spread_total_declarado'])}) o parceiro "
                      f"repassaria {brl(pc['repasse_pelo_total_declarado'])}; a nota é {brl(pc['comissao_calculada'])}. "
                      f"Diferença {brl(pc['diferenca'])} = " + " ".join(partes_dif)
                      + (" — ver pendência CONFERIR_REPASSE_PONTE." if pc["diferenca"] != ZERO else "."))
    partes.append("")

    if f.avisos:
        partes += ["## Avisos", ""] + [f"- {a}" for a in f.avisos] + [""]

    partes += ["## Checagens de integridade", ""]
    partes += [f"- {'✅' if ch.ok else '❌'} {ch.nome}: {ch.detalhe}" for ch in f.checagens]
    partes += ["", "Arquivos: " + ", ".join(f"`{v}`" for v in res["arquivos"].values()) + ".", ""]
    return "\n".join(partes)


def escrever_relatorio(texto: str, caminho: Path) -> Path:
    Path(caminho).write_text(texto, encoding="utf-8")
    return Path(caminho)
