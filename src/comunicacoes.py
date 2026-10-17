"""Rascunhos de e-mail por contraparte (Orbe, Ponte, Comercial) e avisos de condição comercial nova.

Tudo é RASCUNHO: nada é enviado; quem decide revisa e envia. Destinatários, assuntos e textos vêm de
regras/comunicacoes.csv; a causa de cada divergência vem de regras/causas_divergencia.csv; os números
vêm das saídas do fechamento (nenhum número novo). Os anexos CSV somam exatamente as pendências e
divergências correspondentes (há teste).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .dinheiro import ZERO, arredondar, brl, soma
from .pendencias import COLUNAS_CONTESTACAO, lista_contestacao
from .regras import ErroConfig, ler_csv_regras
from .textos import sem_repeticao
from .saida import escrever_csv, gravar_texto

COLUNAS_COMUNICACOES = ["contraparte", "destinatario", "assunto", "abertura", "fechamento", "quem_decide", "informado_por", "data"]
COLUNAS_CAUSAS = ["cnpj", "linha_negocio", "causa", "informado_por", "data"]
COLUNAS_ANEXO = ["ref_origem", "cnpj", "lojista", "linha_negocio", "data", "produto", "taxa_contratada_pct",
                 "taxa_aplicada_pct", "valor_brl", "natureza", "motivo", "arquivo_origem"]
CONTRAPARTE_POR_LINHA = {"CHECKOUT": "ORBE", "REMESSA": "PONTE"}


def _config_textos(dir_regras: Path) -> tuple[dict, dict, dict]:
    textos = {r["contraparte"].strip().upper(): r for _, r in ler_csv_regras(Path(dir_regras) / "comunicacoes.csv", COLUNAS_COMUNICACOES)}
    # causa de contrato (vai para a contraparte) e, à parte, a versão interna com a observação de processo
    from .relatorio import ler_causas
    return textos, ler_causas(dir_regras), ler_causas(dir_regras, internas=True)


def dias_uteis_depois(inicio: date, n: int) -> date:
    d = inicio
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def prazo_lembrete(regra, meta: dict) -> dict | None:
    """Campos do prazo de um lembrete MANUAL com `prazo=`: data_base, data_limite e base_da_data, tirados do e-mail do
    parceiro (data de envio, dias úteis, data de repasse). Nunca compara com a data de hoje: dizer se venceu não é do
    motor (o fechamento pode ser simulado depois do mês)."""
    tipo = (regra.params or {}).get("prazo")
    if not tipo:
        return None
    envio, dias, repasse = meta.get("data_envio"), meta.get("prazo_dias_uteis"), meta.get("data_repasse")
    if tipo == "contestacao_parceiro":
        if not (envio and dias):
            return {"data_base": None, "data_limite": None,
                    "base_da_data": "o e-mail do parceiro não traz a data de envio ou os dias úteis do prazo"}
        return {"data_base": str(envio), "data_limite": str(dias_uteis_depois(envio, int(dias))),
                "base_da_data": f"data de envio do e-mail do parceiro ({envio}) + {dias} dias úteis informados no e-mail "
                                "(sem contar feriados)"}
    if not repasse:
        return {"data_base": str(envio) if envio else None, "data_limite": None,
                "base_da_data": "o e-mail do parceiro não traz a data de repasse"}
    return {"data_base": str(envio) if envio else None, "data_limite": str(repasse),
            "base_da_data": f"data de repasse informada no corpo do e-mail do parceiro de {envio}; a nota sai antes dela"}


def _pct(v) -> str:
    return "" if v is None or pd.isna(v) else f"{Decimal(v).quantize(Decimal('0.01')).normalize():f}%"


def _cabecalho(t: dict, competencia_txt: str, subst: dict) -> list[str]:
    def s(x):
        for k, v in subst.items():
            x = x.replace("{" + k + "}", str(v))
        return x.replace("{competencia}", competencia_txt)
    return [f"RASCUNHO — envio só após aprovação de {t['quem_decide']}", "",
            f"**Para:** {s(t['destinatario'])}", f"**Assunto:** {s(t['assunto'])}", "", s(t["abertura"]), ""]


def gerar(f, config, dir_regras: Path, pasta_saida: Path, competencia_txt: str, meta_ponte: dict | None = None) -> dict[str, Path]:
    """Grava saida/comunicacoes/: orbe_contestacao.csv + orbe.md, ponte_contestacao.csv + ponte.md, comercial.md,
    avisos_nova_condicao.md. Devolve {nome: caminho}."""
    textos, causas, causas_internas = _config_textos(dir_regras)
    for chave in ("ORBE", "PONTE", "COMERCIAL", "AVISO"):
        if chave not in textos:
            raise ErroConfig([f"comunicacoes.csv: falta a linha {chave}. Como corrigir: acrescente contraparte={chave}"])
    pasta = Path(pasta_saida) / "comunicacoes"
    pasta.mkdir(parents=True, exist_ok=True)
    meta = meta_ponte or {}
    out: dict[str, Path] = {}

    # ---------------- Orbe: divergências de contrato do checkout (natureza CONTRATO; a devolução ao lojista fica fora)
    contrato = f.divergencias_contrato
    div = contrato[contrato["linha_negocio"] == "CHECKOUT"]
    anexo = pd.DataFrame({
        "ref_origem": div["ref_origem"], "cnpj": div["cnpj"], "lojista": div["lojista"], "linha_negocio": "CHECKOUT",
        "data": div["data"], "produto": div["produto"], "taxa_contratada_pct": div["taxa_contratada_pct"],
        "taxa_aplicada_pct": div["taxa_aplicada_pct"], "valor_brl": div["diferenca_brl"], "natureza": "DIVERGENCIA_TAXA",
        "motivo": div["regra_id"].map(lambda r: f"taxa contratada em {r}"), "arquivo_origem": div["arquivo_origem"],
    }) if len(div) else pd.DataFrame(columns=COLUNAS_ANEXO)
    out["orbe_contestacao"] = escrever_csv(anexo[COLUNAS_ANEXO], pasta / "orbe_contestacao.csv", "orbe_contestacao.csv")
    linhas = _cabecalho(textos["ORBE"], competencia_txt, {})
    if div.empty:
        linhas.append("Nenhuma divergência de contrato neste mês.")
    for cnpj, g in div.groupby("cnpj", sort=False):
        pos, neg = g[g["diferenca_brl"] > 0], g[g["diferenca_brl"] < 0]
        liquido = soma(g["diferenca_brl"])
        decomp = (f" (= {brl(soma(pos['diferenca_brl']))} a maior em {len(pos)} vendas − {brl(-soma(neg['diferenca_brl']))} "
                  f"devolvidos em {len(neg)} estornos)") if len(neg) else ""
        linhas.append(f"- **{g['lojista'].iloc[0]}** (CNPJ {cnpj}): {len(g)} transações, taxa contratada "
                      f"{_faixa(g['taxa_contratada_pct'])} × aplicada {_faixa(g['taxa_aplicada_pct'])}, valor LÍQUIDO "
                      f"{brl(liquido)}{decomp}. Causa: {causas.get((cnpj, 'CHECKOUT'), 'a apurar')}.")
    linhas += ["", f"**Total a corrigir: {brl(soma(div['diferenca_brl']))}** ({len(div)} transações, anexo `orbe_contestacao.csv`).",
               "", textos["ORBE"]["fechamento"], ""]
    out["orbe_md"] = _gravar(pasta / "orbe.md", linhas)

    # ---------------- Ponte: um pedido por assunto (excesso por lojista, exclusões por natureza, repetidas), sem total único
    lc = lista_contestacao(f.ponte_linhas)
    out["ponte_contestacao"] = escrever_csv(lc if len(lc) else pd.DataFrame(columns=COLUNAS_CONTESTACAO),
                                            pasta / "ponte_contestacao.csv", "ponte_contestacao.csv")
    linhas = _cabecalho(textos["PONTE"], competencia_txt, {"remetente": meta.get("remetente") or "e-mail do relatório mensal"})
    if lc.empty:
        linhas.append("Nenhuma operação a contestar neste mês.")
    else:
        n_pedidos = lc["pedido"].nunique()
        linhas += [f"São {n_pedidos} pedido{'s' if n_pedidos > 1 else ''}, cada um com o seu valor e as suas operações "
                   f"(coluna `pedido` do anexo `ponte_contestacao.csv`, {len(lc)} operações):", ""]
    from .notas import primeiro_dia
    ref = primeiro_dia(f.competencia)
    participacao, modo = config.parametro("participacao_spread", ref), config.parametro("arredondamento", ref)
    for pedido, g in lc.groupby("pedido", sort=True):
        natureza = g["natureza"].iloc[0]
        ops = ", ".join(g["ref_origem"])
        if natureza == "EXCESSO_SPREAD":
            cnpj = g["cnpj"].iloc[0]
            linhas.append(f"- **Pedido {pedido} — devolver a {g['lojista'].iloc[0]} (CNPJ {cnpj}) o excesso de spread: "
                          f"{brl(soma(g['valor_brl']))} em {len(g)} operações.** {_faixa(g['taxa_aplicada_pct'])} aplicado contra "
                          f"{_faixa(g['taxa_contratada_pct'])} contratado (excesso cheio cobrado do lojista). "
                          f"Causa: {causas.get((cnpj, 'REMESSA'), 'a apurar')}. Operações: {ops}.")
        elif natureza == "REPETIDA":
            linhas.append(f"- **Pedido {pedido} — corrigir o relatório: {ops} aparece{'m' if len(g) > 1 else ''} mais de uma vez.** "
                          f"Contada{'s' if len(g) > 1 else ''} uma vez no nosso fechamento (valor 0 neste pedido).")
        else:
            obs = ", ".join(sorted({str(o) for o in f.ponte_linhas.loc[f.ponte_linhas["ref_origem"].isin(g["ref_origem"]), "observacao"] if o}))
            cabeca = (f"- **Pedido {pedido} — {len(g)} operações com {natureza.replace('_', ' ').lower()}, fora da nossa comissão e "
                      f"da nota.** {g['motivo'].iloc[0]}" + (f" ({obs})" if obs else "") + ": não aceitas; ")
            if g["spread_contratado_brl"].notna().all():
                rel, contr = soma(g["spread_relatorio_brl"]), soma(g["spread_contratado_brl"])
                dif, metade = soma(g["diferenca_contrato_brl"]), soma(g["metade_tarvo_contrato_brl"])
                linhas.append(cabeca + f"o que aconteceu: {brl(rel)} de spread no relatório; o que pedimos à Ponte (a trava deveria "
                              f"ter sido honrada): {brl(abs(dif))}, a diferença até o spread contratado de {brl(contr)} "
                              f"({_faixa(g['taxa_contratada_pct'])} x PTAX x Valor ME), do qual a metade da Tarvo seria {brl(metade)}. "
                              f"As colunas spread_relatorio_brl e spread_contratado_brl do anexo trazem os dois valores por operação. "
                              f"Operações: {ops}.")
            else:
                impacto = soma(arredondar(-v * participacao, modo) for v in g["valor_brl"])
                linhas.append(cabeca + f"{brl(soma(g['valor_brl']))} no relatório, impacto de {brl(impacto)} na metade da Tarvo. "
                              f"Operações: {ops}.")
    prazo = _prazo(config, meta, f)
    linhas += ["", prazo, "", textos["PONTE"]["fechamento"], ""]
    out["ponte_md"] = _gravar(pasta / "ponte.md", linhas)

    # ---------------- Comercial: tudo o que depende do Comercial nas pendências
    linhas = _cabecalho(textos["COMERCIAL"], competencia_txt, {})
    pend = f.pendencias[f.pendencias["quem_decide"].str.contains("Comercial", case=False, na=False)]
    for r in pend.itertuples():
        valor = brl(r.valor_brl) if r.valor_brl is not None else "sem valor"
        motivo = r.motivo if r.motivo.endswith(".") else r.motivo + "."
        # o motivo tem até 3 frases: o rascunho leva também o resto do o_que_fazer da regra, sem repetir o que o motivo diz
        resto = sem_repeticao(r.o_que_fazer or "", ja_dito=motivo).rstrip(".")
        texto = f"{motivo} {resto}." if resto else motivo
        # rascunho interno: leva a causa de processo, sem repetir o que o texto já diz
        causa = sem_repeticao(causas_internas.get((r.cnpj, r.linha_negocio or ""), ""), ja_dito=texto).rstrip(".")
        linhas.append(f"- **{r.id_saida} · {r.tipo}**{' (informativa)' if r.informativa else ''} — {r.lojista or ''} "
                      f"({valor}): {texto}" + (f" Causa: {causa}." if causa else ""))
    if pend.empty:
        linhas.append("Nenhuma pendência do Comercial neste mês.")
    linhas += ["", textos["COMERCIAL"]["fechamento"], ""]
    out["comercial_md"] = _gravar(pasta / "comercial.md", linhas)

    # ---------------- Avisos de condição nova: lojistas cuja taxa aplicada não bateu com a contratada
    linhas = _cabecalho(textos["AVISO"], competencia_txt, {})
    avisos, notas_aviso = _avisos(f, config, causas)
    if not avisos:
        linhas.append(f"Nenhuma condição comercial nova a avisar na competência {competencia_txt}.")
    for a in avisos:
        dest = textos[a["contraparte"]]["destinatario"].replace("{remetente}", meta.get("remetente") or "")
        linhas += [f"### {a['lojista']} → {a['contraparte'].title()} ({dest})", "",
                   f"- Lojista: {a['lojista']} — CNPJ {a['cnpj']}" + (f", EC {a['ec']}" if a.get("ec") else ""),
                   f"- Produtos: {a['produtos']}", f"- Taxa contratada: {a['taxa']} (origem: {a['origem']})",
                   f"- Vigência: {a['vigencia']}"]
        if a.get("obs"):
            linhas.append(f"- Observação na mesma linha da planilha ({a['obs_celula'] or 'coluna Obs'}): “{a['obs']}”. "
                          f"Se a observação indicar outra data ou condição que a coluna de vigência, {textos['PONTE']['quem_decide']} "
                          f"confirma qual vale antes do envio. O fechamento usou a vigência da coluna; nada foi decidido aqui.")
        linhas += [f"- Situação: {a['situacao']}", ""]
    if notas_aviso:
        linhas += [""] + [f"- {n}" for n in notas_aviso] + [""]
    linhas += [textos["AVISO"]["fechamento"], ""]
    out["avisos_md"] = _gravar(pasta / "avisos_nova_condicao.md", linhas)
    return out


def _faixa(serie) -> str:
    vals = sorted({Decimal(v).quantize(Decimal("0.01")) for v in serie if v is not None and not pd.isna(v)})
    if not vals:
        return "n/d"
    txt = [f"{v.normalize():f}%" for v in vals]
    return txt[0] if len(txt) == 1 else f"{txt[0]} a {txt[-1]}"


def _prazo(config, meta: dict, f) -> str:
    from .notas import primeiro_dia
    ref = primeiro_dia(f.competencia)
    regra = next((r for r in config.lembretes(ref) if r.params.get("prazo") == "contestacao_parceiro"), None)
    partes = []
    if regra is not None:
        partes.append(f"Prazo (regra {regra.id}): {regra.o_que_fazer.rstrip('.')}.")
        pz = prazo_lembrete(regra, meta)
        if pz["data_limite"]:
            partes.append(f"E-mail do parceiro de {pz['data_base']}, {meta['prazo_dias_uteis']} dias úteis: responder até "
                          f"{pz['data_limite']} (sem contar feriados).")
    return " ".join(partes) if partes else "Prazo: ver o e-mail do parceiro."


def _avisos(f, config, causas: dict) -> tuple[list[dict], list[str]]:
    """Condições comerciais novas a avisar à contraparte, e as linhas que explicam por que uma condição NÃO gera aviso.

    Sai aviso para condição (linha da planilha de taxas ou TAXA_EXCECAO) com vigência a partir do primeiro dia da
    competência seguinte, ou com vigência dentro da competência e sem divergência no mês. Com divergência no mês o canal
    é a contestação (orbe.md, ponte.md), salvo se a regra PARAMETRO aviso_condicao_nova_com_divergencia=true. Condição
    com vigência anterior à competência já devia estar aplicada: se não está, é divergência, não aviso. TAXA_EXCECAO com
    divergencia diferente de CONTRATO é concessão absorvida pela Tarvo: a contraparte cobra o contratado e não age."""
    from .notas import primeiro_dia
    from .regras import NATUREZA_CONTRATO
    ref = primeiro_dia(f.competencia)
    proximo = (pd.Timestamp(ref) + pd.offsets.MonthBegin(1)).date()
    regra_crit = config.regra_parametro("aviso_condicao_nova_com_divergencia", ref)
    com_div = set(zip(f.divergencias_contrato["cnpj"], f.divergencias_contrato["linha_negocio"]))

    def situacao(de, cnpj, linha) -> str | None:
        if de is None:
            return None
        if de >= proximo:
            return f"vigência a partir de {de}, depois da competência: avisar antes da data de início"
        if ref <= de < proximo and ((cnpj, linha) not in com_div or regra_crit.valor):
            return (f"vigência dentro da competência ({de}) e sem divergência no mês: confirmar a aplicação"
                    if (cnpj, linha) not in com_div else f"vigência dentro da competência ({de}), já com divergência no mês")
        return None

    out, notas = [], []
    for r in config.por_tipo("TAXA_EXCECAO"):
        p, cnpj, linha = r.params, r.params["cnpj"], r.params["linha_negocio"]
        contraparte = CONTRAPARTE_POR_LINHA[linha].title()
        if p.get("divergencia", NATUREZA_CONTRATO) != NATUREZA_CONTRATO:
            notas.append(f"TAXA_EXCECAO {r.id} não gera aviso à {contraparte}: concessão absorvida pela Tarvo "
                         f"(divergencia={p['divergencia']} na regra: a {contraparte} cobra o contratado e não precisa agir).")
            continue
        sit = situacao(r.vigencia_de, cnpj, linha)
        if sit is None:
            continue
        loj = config.lojista_por_cnpj(cnpj)
        out.append({"contraparte": CONTRAPARTE_POR_LINHA[linha], "lojista": _nome(f, loj, cnpj), "cnpj": cnpj,
                    "ec": getattr(loj, "ec_orbe", "") if linha == "CHECKOUT" else "",
                    "produtos": ", ".join(sorted(p["produto"])), "taxa": _pct(p["taxa_pct"]),
                    "origem": f"regra {r.id} ({r.situacao})",
                    "vigencia": f"de {r.vigencia_de} até {r.vigencia_ate or 'sem fim'}", "situacao": sit, "obs": "", "obs_celula": ""})
    taxas = getattr(f, "taxas", None)
    if taxas is not None and len(taxas):
        tx = taxas.assign(_linha=taxas["produto"].map(lambda x: "REMESSA" if str(x).upper().startswith("SPREAD") else "CHECKOUT"))
        for (linha_pl, cnpj, linha), g in tx.groupby(["linha_planilha", "cnpj", "_linha"], sort=False):
            de = g["vigencia_de"].iloc[0]
            de = de.date() if pd.notna(de) else None
            sit = situacao(de, cnpj, linha)
            if sit is None:
                continue
            # o que mudou em relação à linha anterior do mesmo lojista (a que termina antes desta vigência)
            ant = tx[(tx["cnpj"] == cnpj) & (tx["_linha"] == linha) & tx["vigencia_ate"].notna() & (tx["vigencia_ate"] < pd.Timestamp(de))]
            if len(ant):
                ant = ant[ant["vigencia_ate"] == ant["vigencia_ate"].max()]
                antes = {(r.produto, r.parcelas_de, r.parcelas_ate): r.taxa_pct for r in ant.itertuples()}
                g = g[[antes.get((r.produto, r.parcelas_de, r.parcelas_ate)) != r.taxa_pct for r in g.itertuples()]]
            if g.empty:
                continue
            ate = g["vigencia_ate"].iloc[0]
            loj = config.lojista_por_cnpj(cnpj)
            out.append({"contraparte": CONTRAPARTE_POR_LINHA[linha], "lojista": _nome(f, loj, cnpj, g["lojista_planilha"].iloc[0]),
                        "cnpj": cnpj, "ec": (getattr(loj, "ec_orbe", "") or "") if linha == "CHECKOUT" else "",
                        "produtos": ", ".join(sorted({str(x) for x in g["produto"]})), "taxa": _faixa(g["taxa_pct"]),
                        "origem": f"planilha de taxas, linha {linha_pl}",
                        "vigencia": f"de {de} até {ate.date() if pd.notna(ate) else 'sem fim'}"
                                    + (f" (planilha de taxas, célula {g['vigencia_celula'].iloc[0]})" if g["vigencia_celula"].iloc[0] else ""),
                        "situacao": sit, "obs": str(g["obs"].iloc[0] or "") if pd.notna(g["obs"].iloc[0]) else "",
                        "obs_celula": str(g["obs_celula"].iloc[0] or "") if pd.notna(g["obs_celula"].iloc[0]) else ""})
    def condicao_no_mes(cnpj, linha) -> bool:
        """Há condição registrada (linha da planilha de taxas ou TAXA_EXCECAO) com vigência começando na competência."""
        if any(r.params["cnpj"] == cnpj and r.params["linha_negocio"] == linha and r.vigencia_de
               and ref <= r.vigencia_de < proximo for r in config.por_tipo("TAXA_EXCECAO")):
            return True
        if taxas is None or not len(taxas):
            return False
        de = tx.loc[(tx["cnpj"] == cnpj) & (tx["_linha"] == linha), "vigencia_de"].dropna()
        return bool(((de >= pd.Timestamp(ref)) & (de < pd.Timestamp(proximo))).any())

    # só entra na frase quem teve condição nova no mês; divergência sem condição nova (erro da contraparte) não é caso de aviso
    contestadas = []
    for (cnpj, linha), g in f.divergencias_contrato.groupby(["cnpj", "linha_negocio"], sort=False):
        if not condicao_no_mes(cnpj, linha):
            continue
        contestadas.append(f"{g['lojista'].iloc[0]} ({CONTRAPARTE_POR_LINHA[linha].title()}, "
                           f"comunicacoes/{CONTRAPARTE_POR_LINHA[linha].lower()}.md)")
    if contestadas and not regra_crit.valor:
        notas.append(f"Condições com vigência no mês e já com divergência seguem pela contestação, não por aviso (regra {regra_crit.id}): "
                     + "; ".join(contestadas) + ".")
    return out, notas


def _nome(f, loj, cnpj: str, padrao: str = "") -> str:
    """Nome do lojista como sai nas comissões do mês; sem comissão, o do cadastro (nunca usado para identificar)."""
    com = f.comissoes.loc[f.comissoes["cnpj"] == cnpj, "lojista"]
    return str(com.iloc[0]) if len(com) else (getattr(loj, "nome", "") or padrao or cnpj)


def _gravar(caminho: Path, linhas: list[str]) -> Path:
    gravar_texto(caminho, "\n".join(linhas))
    return caminho
