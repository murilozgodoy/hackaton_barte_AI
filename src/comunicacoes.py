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
from .saida import escrever_csv

COLUNAS_COMUNICACOES = ["contraparte", "destinatario", "assunto", "abertura", "fechamento", "quem_decide", "informado_por", "data"]
COLUNAS_CAUSAS = ["cnpj", "linha_negocio", "causa", "informado_por", "data"]
COLUNAS_ANEXO = ["ref_origem", "cnpj", "lojista", "linha_negocio", "data", "produto", "taxa_contratada_pct",
                 "taxa_aplicada_pct", "valor_brl", "natureza", "motivo", "arquivo_origem"]
CONTRAPARTE_POR_LINHA = {"CHECKOUT": "ORBE", "REMESSA": "PONTE"}


def _config_textos(dir_regras: Path) -> tuple[dict, dict]:
    textos = {r["contraparte"].strip().upper(): r for _, r in ler_csv_regras(Path(dir_regras) / "comunicacoes.csv", COLUNAS_COMUNICACOES)}
    caminho = Path(dir_regras) / "causas_divergencia.csv"
    causas = {}
    if caminho.exists():
        for _, r in ler_csv_regras(caminho, COLUNAS_CAUSAS):
            causas[(r["cnpj"].strip(), r["linha_negocio"].strip().upper())] = r["causa"]
    return textos, causas


def dias_uteis_depois(inicio: date, n: int) -> date:
    d = inicio
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


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
    textos, causas = _config_textos(dir_regras)
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
        causa = causas.get((r.cnpj, r.linha_negocio or ""), "")
        motivo = r.motivo if r.motivo.endswith(".") else r.motivo + "."
        linhas.append(f"- **{r.id_saida} · {r.tipo}**{' (informativa)' if r.informativa else ''} — {r.lojista or ''} "
                      f"({valor}): {motivo}" + (f" Causa: {causa}." if causa else ""))
    if pend.empty:
        linhas.append("Nenhuma pendência do Comercial neste mês.")
    linhas += ["", textos["COMERCIAL"]["fechamento"], ""]
    out["comercial_md"] = _gravar(pasta / "comercial.md", linhas)

    # ---------------- Avisos de condição nova: lojistas cuja taxa aplicada não bateu com a contratada
    linhas = _cabecalho(textos["AVISO"], competencia_txt, {})
    avisos = _avisos(f, config, causas)
    if not avisos:
        linhas.append("Nenhuma condição comercial sem aplicação neste mês.")
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
        linhas += [f"- Aplicado em {competencia_txt}: {a['aplicada']} em {a['n']} transações"
                   + (f" (causa informada: {a['causa']})" if a.get("causa") else ""), ""]
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
    regra = next((r for r in config.lembretes(ref) if "prazo" in (r.situacao or "").lower()), None)
    partes = []
    if regra is not None:
        partes.append(f"Prazo (regra {regra.id}): {regra.o_que_fazer.rstrip('.')}.")
    if meta.get("data_envio") and meta.get("prazo_dias_uteis"):
        limite = dias_uteis_depois(meta["data_envio"], int(meta["prazo_dias_uteis"]))
        partes.append(f"E-mail do parceiro de {meta['data_envio']}, {meta['prazo_dias_uteis']} dias úteis: responder até "
                      f"{limite} (sem contar feriados).")
    return " ".join(partes) if partes else "Prazo: ver o e-mail do parceiro."


def _avisos(f, config, causas: dict) -> list[dict]:
    """Uma entrada por (lojista, linha de negócio) com divergência (de contrato ou fora dele): a condição contratada
    não foi aplicada desde o primeiro dia. Vigência: da TAXA_EXCECAO ou da linha da planilha de taxas."""
    # só divergências de contrato: uma concessão fora do contrato (natureza DEVOLUCAO_LOJISTA) não é condição que a
    # contraparte devesse aplicar, então não gera aviso (fonte: regras/causas_divergencia.csv e HIPOTESES.md)
    todas = f.divergencias_contrato
    out = []
    for (cnpj, linha), g in todas.groupby(["cnpj", "linha_negocio"], sort=False):
        origem = str(g["regra_id"].iloc[0])
        if not _nao_bateu_desde_o_primeiro_dia(f, cnpj, linha, origem, set(g["ref_origem"])):
            continue   # condição antiga que a contraparte aplicava e passou a errar no meio do mês: não é aviso
        regra = config.regra(origem)
        if regra is not None:
            vig = f"de {regra.vigencia_de or 'início'} até {regra.vigencia_ate or 'sem fim'}"
            origem_txt = f"regra {regra.id} ({regra.situacao})"
        else:
            vig_de, vig_ate, vig_celula, obs, obs_celula = _vigencia_planilha(f, cnpj, origem)
            vig = f"de {vig_de or 'início'} até {vig_ate or 'sem fim'}" + (f" (planilha de taxas, célula {vig_celula})" if vig_celula else "")
            origem_txt = origem.replace("planilha:", "planilha de taxas, célula ")
        ec = ""
        if linha == "CHECKOUT" and "cod_estabelecimento" in f.orbe_linhas.columns:
            ecs = f.orbe_linhas.loc[f.orbe_linhas["cnpj"] == cnpj, "cod_estabelecimento"].dropna().unique()
            ec = ", ".join(sorted(ecs))
        out.append({"contraparte": CONTRAPARTE_POR_LINHA[linha], "lojista": g["lojista"].iloc[0], "cnpj": cnpj, "ec": ec,
                    "produtos": ", ".join(sorted({str(p) for p in g["produto"]})), "taxa": _faixa(g["taxa_contratada_pct"]),
                    "origem": origem_txt, "vigencia": vig, "aplicada": _faixa(g["taxa_aplicada_pct"]), "n": len(g),
                    "causa": causas.get((cnpj, linha), ""), "obs": obs if regra is None else "",
                    "obs_celula": obs_celula if regra is None else ""})
    return out


def _nao_bateu_desde_o_primeiro_dia(f, cnpj: str, linha: str, origem: str, refs_divergentes: set) -> bool:
    """A primeira transação do mês sob essa condição (mesma origem da taxa contratada) já divergiu: a contraparte
    nunca aplicou a condição. Se a primeira bateu, a condição era conhecida (erro no meio do mês, não aviso)."""
    if linha == "CHECKOUT":
        base = f.orbe_linhas[(f.orbe_linhas["cnpj"] == cnpj) & (f.orbe_linhas["destino"] == "COMISSAO")
                             & (f.orbe_linhas["regra_id"] == origem)].sort_values(["data_taxa", "ref_origem"])
    else:
        base = f.ponte_linhas[(f.ponte_linhas["cnpj"] == cnpj) & (f.ponte_linhas["destino"] == "COMISSAO")
                              & (f.ponte_linhas["spread_contratado_origem"] == origem)].sort_values(["data_contratacao", "ref_origem"])
    return (not base.empty) and base["ref_origem"].iloc[0] in refs_divergentes


def _vigencia_planilha(f, cnpj: str, origem: str):
    """(vigência de, até, célula da vigência, observação da linha, célula da observação) da linha da planilha de onde
    veio a taxa; tudo None/"" quando a taxa não veio da planilha."""
    vazio = (None, None, "", "", "")
    taxas = getattr(f, "taxas", None)
    if taxas is None or not origem.startswith("planilha:"):
        return vazio
    ref = origem.split(":", 1)[1]
    sel = taxas[(taxas["cnpj"] == cnpj) & (taxas["ref_origem"] == ref)]
    if sel.empty:
        return vazio
    r = sel.iloc[0]
    de = r["vigencia_de"].date() if pd.notna(r["vigencia_de"]) else None
    ate = r["vigencia_ate"].date() if pd.notna(r["vigencia_ate"]) else None
    def texto(col):
        v = r[col] if col in sel.columns else None
        return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v).strip()
    return de, ate, texto("vigencia_celula"), texto("obs"), texto("obs_celula")


def _gravar(caminho: Path, linhas: list[str]) -> Path:
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    return caminho
