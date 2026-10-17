"""resumo.json (para agentes, nada de recalcular) e RELATORIO_FECHAMENTO.md (para pessoas).

Os dois são escritos pelo motor, sem IA. Valores monetários no JSON vão como string
decimal já arredondada ao centavo (um valor não arredondado é erro, não é arredondado
em silêncio). O relatório é uma página: totais, notas, divergências, pendências por
responsável com o que fazer, lembretes das regras MANUAL, conciliação, avisos e
checagens. Sem data de geração, para o mesmo fechamento gerar sempre o mesmo arquivo.
"""
from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .dinheiro import CENTAVO, ZERO, brl, soma
from .notas import competencia_texto, primeiro_dia
from .saida import gravar_texto

# pendências cuja causa é a do lojista (regras/causas_divergencia.csv), não o tipo
TIPOS_POR_CAUSA = {"DIVERGENCIA_TAXA", "TARIFA_ZERO_COBRADA", "SEM_CONTRATO"}
# rótulos de apresentação dos tipos (texto, não regra de negócio)
ROTULOS_TIPO = {
    "CONFERIR_REPASSE_PONTE": "Repasse do parceiro de câmbio a conferir (TED x nota)",
    "SPREAD_NEGATIVO": "Spreads negativos no relatório do parceiro (trava vencida)",
    "SALDO_NEGATIVO_LOJISTA": "Comissão negativa no mês (sem nota)",
    "EXTRATO_NAO_IDENTIFICADO": "Lançamento de extrato sem identificação",
    "DEVOLUCAO": "Repasse devolvido pelo banco",
    "CADASTRO": "Cadastro faltante (EC, CNPJ, taxa ou faixa)",
    "DIVERGENCIA_TAXA": "Divergência de contrato", "TARIFA_ZERO_COBRADA": "Concessão comercial cobrada pela adquirente",
    "SEM_CONTRATO": "Lojista sem contrato", "CONFERIR_AJUSTE_PONTE": "Ajuste do parceiro de câmbio",
    "LINHA_NAO_INTERPRETADA": "Linha do relatório do parceiro não interpretada", "DUPLICATA_DIVERGENTE": "Operação repetida com valores diferentes",
    "FORA_COMPETENCIA": "Linhas fora da competência", "COMPLIANCE": "Operação reprovada no compliance",
    "RECURSO_SEM_OPERACAO": "Recurso de lojista sem operação", "REVISAR_IA": "Conta sugerida pela IA a revisar",
    "DADO_INSUFICIENTE": "Estorno ou reversão sem data da venda original (venda fora do arquivo)",
}

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


def resumo_divergencias(f) -> dict:
    """Totais de divergencias_taxa.csv: por linha de negócio (só natureza CONTRATO, o que se cobra da contraparte),
    por natureza e o total de transações do arquivo."""
    contrato, fora = f.divergencias_contrato, f.divergencias_fora_contrato
    div_chk = contrato[contrato["linha_negocio"] == "CHECKOUT"]
    div_rem = contrato[contrato["linha_negocio"] == "REMESSA"]
    por_nat = {}
    if len(f.divergencias):
        for nat, g in f.divergencias.groupby("natureza", sort=False):
            por_nat[str(nat)] = {"linhas": int(len(g)), "valor_brl": _s(soma(g["diferenca_brl"]))}
    so_pend = getattr(f, "so_pendencia", None)
    so_pend = so_pend if so_pend is not None else pd.DataFrame(columns=["cobrado_brl", "diferenca_brl"])
    return {
        "linhas": int(len(f.divergencias)),
        "contrato": {"linhas": int(len(contrato)), "valor_brl": _s(soma(contrato["diferenca_brl"]))},
        "checkout": {"linhas": int(len(div_chk)), "valor_brl": _s(soma(div_chk["diferenca_brl"]))},
        "remessa": {"linhas": int(len(div_rem)), "valor_brl": _s(soma(div_rem["diferenca_brl"]))},
        # outra natureza declarada pela regra TAXA_EXCECAO (ex.: isenção que não chegou à adquirente): no CSV, marcada,
        # fora da cobrança da contraparte
        "devolucao_lojista": {"linhas": int(len(fora)), "valor_brl": _s(soma(fora["diferenca_brl"]))},
        "por_natureza": por_nat,
        # transações que a regra TAXA_EXCECAO manda só para a pendência (destino=PENDENCIA): fora do CSV; o valor é o
        # que a adquirente cobrou de fato (= a pendência), e pela_taxa_brl o que a fórmula bruto × taxa daria
        "so_pendencia": {"linhas": int(len(so_pend)), "valor_brl": _s(soma(so_pend["cobrado_brl"])),
                         "pela_taxa_brl": _s(soma(so_pend["diferenca_brl"]))},
    }


def texto_divergencias(t: dict) -> str:
    """'115 transações de contrato (checkout R$ x + remessa R$ y = R$ z); fora do arquivo, por regra, 118 transações
    de concessão comercial (...)'."""
    c, dc, dr, dl = t["contrato"], t["checkout"], t["remessa"], t["devolucao_lojista"]
    sp = t.get("so_pendencia") or {"linhas": 0}
    contrato = (f"{c['linhas']} de contrato (checkout {brl(Decimal(dc['valor_brl']))} + remessa "
                f"{brl(Decimal(dr['valor_brl']))} = {brl(Decimal(c['valor_brl']))})")
    if dl["linhas"]:
        txt = (f"{t['linhas']} transações = {contrato} + {dl['linhas']} de concessão comercial fora do contrato "
               f"({brl(Decimal(dl['valor_brl']))}, devolução ao lojista por conta da Tarvo)")
    else:
        txt = f"{t['linhas']} transações, todas {contrato}" if t["linhas"] else "nenhuma transação de contrato"
    if sp["linhas"]:
        txt += (f"; fora do arquivo, por regra, {sp['linhas']} transações de concessão comercial fora do contrato "
                f"({brl(Decimal(sp['valor_brl']))} cobrados de fato pela adquirente, devolução ao lojista por conta da Tarvo, "
                f"só em pendência)")
    return txt


def resumo(f, config, arquivos: dict[str, Path], entrada: dict | None = None) -> dict:
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
            "divergencias": resumo_divergencias(f),
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


def ler_causas(dir_regras: Path | None, internas: bool = False) -> dict:
    """{(cnpj, linha_negocio): causa} de regras/causas_divergencia.csv, na ordem do arquivo (vazio se não houver).
    `causa` cita só o contrato e pode ir para a contraparte; com `internas=True` entra também a coluna opcional
    `observacao_interna` (a causa de processo), que fica só no relatório e nos rascunhos internos."""
    if dir_regras is None or not (Path(dir_regras) / "causas_divergencia.csv").exists():
        return {}
    from .regras import ler_csv_regras
    out = {}
    for _, r in ler_csv_regras(Path(dir_regras) / "causas_divergencia.csv", ["cnpj", "linha_negocio", "causa"]):
        causa = r["causa"].strip()
        obs = (r.get("observacao_interna") or "").strip()
        if internas and obs:
            causa = f"{causa.rstrip('.')}. {obs}"
        out[(r["cnpj"].strip(), r["linha_negocio"].strip().upper())] = causa
    return out


def ler_historico(dir_regras: Path | None) -> list[dict]:
    """Linhas de regras/historico_alteracoes.csv (vazio se não houver)."""
    if dir_regras is None or not (Path(dir_regras) / "historico_alteracoes.csv").exists():
        return []
    from .regras import ler_csv_regras
    return [r for _, r in ler_csv_regras(Path(dir_regras) / "historico_alteracoes.csv", ["data", "quem", "id_regra", "acao"])]


def ler_pendencias_anteriores(pasta_anterior: Path | None) -> set | None:
    """Chaves (tipo, subtipo, cnpj ou ref_origem) das pendências da saída do mês anterior, para marcar nova x recorrente."""
    if pasta_anterior is None or not (Path(pasta_anterior) / "pendencias.csv").exists():
        return None
    df = pd.read_csv(Path(pasta_anterior) / "pendencias.csv", sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    return {(r.tipo, r.subtipo, r.cnpj or r.ref_origem) for r in df.itertuples(index=False)}


def _chave_pendencia(r) -> tuple:
    return (r.tipo, r.subtipo or "", r.cnpj or str(r.ref_origem))


# apresentação (não é regra de negócio): o que se faz com o dinheiro de cada tipo de pendência. DIVERGENCIA_TAXA
# depende da linha de negócio (checkout = adquirente, remessa = parceiro de câmbio); tipos fora da lista = só acompanhar
NATUREZA_POR_TIPO = {
    "SPREAD_NEGATIVO": "PARCEIRO", "DUPLICATA_DIVERGENTE": "PARCEIRO", "LINHA_NAO_INTERPRETADA": "PARCEIRO",
    "COMPLIANCE": "PARCEIRO", "CONFERIR_AJUSTE_PONTE": "PARCEIRO",
    "TARIFA_ZERO_COBRADA": "DEVOLVER",
    "SEM_CONTRATO": "NAO_FATURAR", "ALERTA_ANTECIPACAO": "NAO_FATURAR", "CADASTRO": "NAO_FATURAR",
    "SALDO_NEGATIVO_LOJISTA": "NAO_FATURAR", "DADO_INSUFICIENTE": "NAO_FATURAR", "FORA_COMPETENCIA": "NAO_FATURAR",
}
NATUREZAS = [("ADQUIRENTE", "Cobrar da adquirente"), ("PARCEIRO", "Contestar com o parceiro de câmbio"),
             ("DEVOLVER", "Devolver ao lojista por conta da Tarvo"), ("NAO_FATURAR", "Não faturar até decidir"),
             ("ACOMPANHAR", "Só acompanhar")]


def _primeira_frase(texto, limite: int = 160) -> str:
    s = str(texto or "").split(". ")[0].strip()
    return s if len(s) <= limite else s[:limite].rstrip() + "…"


def dinheiro_por_natureza(f, causas: dict, config=None) -> list[dict]:
    """Uma linha por natureza do dinheiro e tipo de pendência: faturar, cobrar da adquirente, contestar com o parceiro,
    devolver ao lojista, não faturar até decidir, só acompanhar. Naturezas diferentes NUNCA são somadas; dentro de uma
    linha só se somam pendências do mesmo tipo. Pendência já incluída em outra fica fora; informativa aparece marcada."""
    from .pendencias import lista_contestacao
    nf_chk, nf_rem = f.notas[f.notas["linha_negocio"] == "CHECKOUT"], f.notas[f.notas["linha_negocio"] == "REMESSA"]
    out = [{"natureza": "Faturar", "o_que": f"{len(f.notas)} notas a emitir ({len(nf_chk)} de checkout + {len(nf_rem)} de remessa)",
            "valor": brl(soma(f.notas["valor_brl"])), "quem": "Financeiro (emite)"}]
    pend = f.pendencias
    ativas = pend[pend["incluida_em"].isna() | (pend["incluida_em"] == "")] if len(pend) else pend
    grupos: dict = {}
    for r in ativas.itertuples(index=False):
        if r.tipo == "DIVERGENCIA_TAXA":
            nat = "ADQUIRENTE" if r.linha_negocio == "CHECKOUT" else "PARCEIRO"
        else:
            nat = NATUREZA_POR_TIPO.get(r.tipo, "ACOMPANHAR")
        grupos.setdefault((nat, r.tipo, r.linha_negocio or ""), []).append(r)
    lc = lista_contestacao(f.ponte_linhas) if len(f.ponte_linhas) else pd.DataFrame(columns=["natureza", "ref_origem"])
    repetidas = lc[lc["natureza"] == "REPETIDA"] if len(lc) else lc
    for nat_key, rotulo in NATUREZAS:
        primeira = True
        for (nat, tipo, linha), rs in grupos.items():
            if nat != nat_key:
                continue
            informativa = all(bool(r.informativa) for r in rs)
            quem = " / ".join(dict.fromkeys(r.quem_decide for r in rs))
            total = soma(abs(r.valor_brl) for r in rs if r.valor_brl is not None)
            valor = brl(total) + (" (informativa)" if informativa else "")
            if tipo == "DIVERGENCIA_TAXA":
                itens = "; ".join(f"{r.lojista}: {causas.get((r.cnpj, linha), 'divergência de contrato').rstrip('.')} "
                                  f"({int(r.qtd_itens)} transações, {brl(r.valor_brl)})" for r in rs)
                o_que = (f"a: excesso de spread cobrado do lojista, volta ao lojista. {itens}" if linha == "REMESSA"
                         else f"{itens}. Rascunho: comunicacoes/orbe.md")
            elif tipo == "SPREAD_NEGATIVO":
                rel = soma(r.spread_relatorio_brl for r in rs if r.spread_relatorio_brl is not None and not pd.isna(r.spread_relatorio_brl))
                dif = soma(r.diferenca_contrato_brl for r in rs if r.diferenca_contrato_brl is not None and not pd.isna(r.diferenca_contrato_brl))
                o_que = (f"b: {len(rs)} operações com spread negativo (trava vencida), fora da comissão e da nota. "
                         f"O que aconteceu: {brl(rel)} de spread no relatório; o que se pede ao parceiro: a diferença até o "
                         f"spread contratado, {brl(abs(dif))}. Os dois valores, nunca somados")
                valor = f"{brl(rel)} aconteceu / {brl(abs(dif))} pedido"
            elif tipo == "SEM_CONTRATO":
                partes = []
                for r in rs:
                    cart = f.carteira[f.carteira["cnpj"] == r.cnpj] if len(f.carteira) else f.carteira
                    partes.append(f"{r.lojista}: {causas.get((r.cnpj, linha), _primeira_frase(r.motivo)).rstrip('.')}; "
                                  f"{brl(r.valor_brl)} cobrados pela adquirente em {int(r.qtd_itens)} transações"
                                  + (f", {brl(soma(cart['valor_bruto']))} brutos na carteira pendente" if len(cart) else ""))
                o_que = "; ".join(partes)
            elif tipo == "TARIFA_ZERO_COBRADA":
                o_que = "; ".join(f"{r.lojista}: {causas.get((r.cnpj, linha), _primeira_frase(r.motivo)).rstrip('.')} "
                                  f"({int(r.qtd_itens)} transações, o que a adquirente cobrou de fato)" for r in rs)
            elif tipo == "CONFERIR_REPASSE_PONTE":
                o_que = "TED do parceiro de câmbio a conferir contra a nota de remessa: " + "; ".join(_primeira_frase(r.motivo) for r in rs)
                valor = "até " + valor
            else:
                o_que = ROTULOS_TIPO.get(tipo, tipo.replace("_", " ").capitalize()) + ": " + "; ".join(
                    f"{r.lojista + ': ' if r.lojista else ''}{_primeira_frase(r.motivo)}" for r in rs[:3]) + ("; …" if len(rs) > 3 else "")
            out.append({"natureza": rotulo if primeira else "", "o_que": o_que, "valor": valor, "quem": quem})
            primeira = False
        if nat_key == "PARCEIRO" and len(repetidas):
            # quem decide vem da regra que mandou contar a repetida uma vez (IGNORAR_DUPLICADO), nunca do código
            regra_dup = config.regra_duplicado("ponte", primeiro_dia(f.competencia)) if config is not None else None
            out.append({"natureza": rotulo if primeira else "",
                        "o_que": f"c: corrigir o relatório: {', '.join(repetidas['ref_origem'])} aparece mais de uma vez "
                                 f"(contada uma vez no fechamento). Rascunho: comunicacoes/ponte.md",
                        "valor": brl(ZERO), "quem": regra_dup.quem_decide if regra_dup is not None else ""})
    return out


def escrever_resumo(res: dict, caminho: Path) -> Path:
    gravar_texto(caminho, json.dumps(res, ensure_ascii=False, indent=2, default=str) + "\n")
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


def _pagina_cfo(f, config, res: dict, causas: dict, historico: list[dict], pend_anteriores: set | None,
                arquivos: dict) -> list[str]:
    comp = competencia_texto(f.competencia)
    ref = primeiro_dia(f.competencia)
    t = res["totais"]
    total_com, total_nf = soma(f.comissoes["comissao_brl"]), soma(f.notas["valor_brl"])
    nf_chk, nf_rem = f.notas[f.notas["linha_negocio"] == "CHECKOUT"], f.notas[f.notas["linha_negocio"] == "REMESSA"]
    sem = "; ".join(f"{r.lojista} sem nota ({brl(r.comissao_brl)})" for r in f.sem_nota.itertuples())
    partes = ["## Página 1 — o que o CFO precisa saber", "",
              "### Totais do mês", "",
              _tabela(["Linha", "Lojistas", "Comissão (receita da Tarvo)", "Notas a emitir"], [
                  ["CHECKOUT", len(f.comissoes_checkout), brl(soma(f.comissoes_checkout["comissao_brl"])),
                   f"{len(nf_chk)} notas, {brl(soma(nf_chk['valor_brl']))}" + (f" ({sem})" if sem else "")],
                  ["REMESSA", len(f.comissoes_remessa), brl(soma(f.comissoes_remessa["comissao_brl"])),
                   f"{len(nf_rem)} nota, {brl(soma(nf_rem['valor_brl']))}" if len(nf_rem) else "sem nota (ver pendências)"],
                  ["**Total**", "", f"**{brl(total_com)}**", f"**{len(f.notas)} notas, {brl(total_nf)}**"]]), "",
              f"Divergências: {texto_divergencias(t['divergencias'])}.", ""]
    n_orbe = (int(f.orbe_linhas["competencia_origem"].isna().sum()) if "competencia_origem" in f.orbe_linhas.columns
              else len(f.orbe_linhas))
    n_ponte, n_ext = len(f.ponte_linhas), len(f.lancamentos)
    milhar = lambda n: f"{n:,}".replace(",", ".")
    partes += [f"**{milhar(n_orbe + n_ponte + n_ext)} linhas de origem conferidas** ({milhar(n_orbe)} da adquirente + "
               f"{milhar(n_ponte)} do parceiro de câmbio + {milhar(n_ext)} dos extratos) → **{len(f.pendencias)} decisões para "
               f"pessoas** (pendências com dono). O motor não mede tempo de espera nem de decisão.", ""]
    partes += ["### Dinheiro em jogo, por natureza", "",
               "O que fazer com cada dinheiro. Naturezas diferentes nunca são somadas (faturar, cobrar, contestar, devolver e "
               "acompanhar são coisas distintas); dentro de uma linha só há pendências do mesmo tipo. Pendência já incluída em "
               "outra fica fora; informativa aparece marcada.", ""]
    partes.append(_tabela(["Natureza", "O quê", "Valor", "Quem decide"],
                          [[l["natureza"], l["o_que"], l["valor"], l["quem"]] for l in dinheiro_por_natureza(f, causas, config)]))
    partes += ["", "### Pendências por responsável", ""]
    for quem, g in f.pendencias.groupby("quem_decide", sort=False):
        n_inf = int(g["informativa"].astype(bool).sum())
        n_inc = int(g["incluida_em"].notna().sum())
        notas_g = [f"{n_inf} informativa{'s' if n_inf > 1 else ''}"] * bool(n_inf) + [f"{n_inc} já incluída{'s' if n_inc > 1 else ''} em outra"] * bool(n_inc)
        tipos = ", ".join(dict.fromkeys(g["tipo"]))
        partes.append(f"- **{quem}**: {len(g)} pendência(s), {brl(valor_em_jogo(g))} em jogo"
                      + (f" ({', '.join(notas_g)})" if notas_g else "") + f": {tipos}.")
    if f.pendencias.empty:
        partes.append("Nenhuma.")
    rascunhos = {k: v for k, v in arquivos.items() if k.startswith("comunicacoes/")}
    if rascunhos:
        partes += ["", "### Rascunhos prontos para revisão (nada foi enviado)", ""]
        descr = {"orbe_md": "contestação à adquirente (divergências de contrato do checkout)",
                 "ponte_md": "contestação ao parceiro de câmbio, um pedido por assunto",
                 "comercial_md": "o que depende do Comercial", "avisos_md": "avisos de condição comercial nova às contrapartes",
                 "orbe_contestacao": "anexo da contestação à adquirente", "ponte_contestacao": "anexo da contestação ao parceiro"}
        for k, v in rascunhos.items():
            nome = k.split("/", 1)[1]
            partes.append(f"- `{Path(v).parent.name}/{Path(v).name}`: {descr.get(nome, nome)}.")
    # conhecimento capturado
    partes += ["", "### Conhecimento capturado", ""]
    recentes = [h for h in historico if h.get("data", "") >= ref.isoformat()]
    if recentes:
        por_acao = {}
        for h in recentes:
            por_acao[h["acao"]] = por_acao.get(h["acao"], 0) + 1
        partes.append(f"- Base de regras: {len(recentes)} alterações registradas em `historico_alteracoes.csv` desde {ref} "
                      f"({', '.join(f'{v} {k.lower()}' for k, v in por_acao.items())}), em "
                      f"{len({h['id_regra'] for h in recentes})} regras/arquivos. Cada linha traz quem aprovou, quem registrou e a fonte "
                      f"(pessoa, canal, hora). Últimas:")
        for h in recentes[-8:]:
            partes.append(f"  - {h['data']} · {h['id_regra']} · {h['acao']} · aprovado por {h.get('aprovado_por') or '—'}, registrado por "
                          f"{h.get('registrado_por') or h.get('quem') or '—'} · fonte: {(h.get('fonte') or '')[:110]}")
    else:
        partes.append("- Base de regras: nenhuma alteração registrada desde o início da competência.")
    if pend_anteriores is not None and len(f.pendencias):
        chaves = [_chave_pendencia(r) for r in f.pendencias.itertuples(index=False)]
        rec = sum(1 for c in chaves if c in pend_anteriores)
        partes.append(f"- Pendências: {len(chaves) - rec} novas e {rec} recorrentes em relação à saída anterior (`--anterior`); "
                      f"as recorrentes estão marcadas no anexo.")
    else:
        partes.append("- Pendências: sem `--anterior`, não dá para dizer quais são novas e quais são recorrentes.")
    partes += ["", "---", "", "## Anexo — detalhe do fechamento", ""]
    return partes


def markdown(f, config, res: dict, causas: dict | None = None, historico: list[dict] | None = None,
             pend_anteriores: set | None = None, arquivos: dict | None = None) -> str:
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
    if f.avisos:
        # no topo: quem roda sem IA lê aqui o que a execução teve de diferente (base inicial, regra sem aprovador...)
        partes += ["## Avisos desta execução", ""] + [f"- {a}" for a in f.avisos] + [""]
    partes += _pagina_cfo(f, config, res, causas or {}, historico or [], pend_anteriores, arquivos or {})

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
               f"Divergências: {texto_divergencias(t['divergencias'])}. "
               f"Pendências: {t['pendencias']['quantidade']}.", ""]

    partes += ["## Notas a emitir", "", _tabela(["Nota", "Linha", "Tomador", "CNPJ", "Valor"], [
        [r.id_saida, r.linha_negocio, r.tomador, r.tomador_cnpj, brl(r.valor_brl)] for r in f.notas.itertuples()]), ""]
    for r in f.sem_nota.itertuples():
        partes.append(f"Sem nota: {r.lojista} ({r.cnpj}) fechou em {brl(r.comissao_brl)} "
                      f"({'zero' if r.comissao_brl == ZERO else 'negativo, vira pendência'}).")
    partes.append("")

    partes += ["## Divergências de taxa (contratada × aplicada)", ""]
    if f.divergencias.empty:
        partes.append("Nenhuma em `divergencias_taxa.csv`." if len(f.so_pendencia) else "Nenhuma.")
    else:
        partes += [f"{texto_divergencias(t['divergencias'])}. A coluna `natureza` de `divergencias_taxa.csv` separa as "
                   "duas: CONTRATO é cobrança da contraparte (anexos em `comunicacoes/`); outra natureza é marcada pela "
                   "regra TAXA_EXCECAO e fica fora de qualquer total a cobrar.", ""]
        grupos = []
        for (natureza, linha, _cnpj), g in f.divergencias.groupby(["natureza", "linha_negocio", "cnpj"], sort=False):
            grupos.append((soma(g["diferenca_brl"]), natureza, linha, g))
        grupos.sort(key=lambda x: (x[1] != "CONTRATO", -abs(x[0])))
        linhas = [[natureza, linha, g["lojista"].iloc[0], len(g),
                   f"{_fmt_pct(g['taxa_contratada_pct'])} × {_fmt_pct(g['taxa_aplicada_pct'])}", brl(total)]
                  for total, natureza, linha, g in grupos]
        partes.append(_tabela(["Natureza", "Linha", "Lojista", "Transações", "Contratada × aplicada", "Diferença"], linhas))
        partes.append("")
        partes.append("Cada transação está em `divergencias_taxa.csv`. Nada foi ajustado automaticamente: "
                      "cada caso é uma pendência para decisão.")
    for (cnpj, natureza), g in f.divergencias_fora_contrato.groupby(["cnpj", "natureza"], sort=False):
        obs = str(g["observacao"].iloc[0]) if g["observacao"].notna().any() else ""
        partes.append("")
        partes.append(f"**Fora da cobrança da contraparte** (natureza {natureza}, regra {g['regra_id'].iloc[0]}): "
                      f"{len(g)} transações de {g['lojista'].iloc[0]} com condição especial contratada "
                      f"({_fmt_pct(g['taxa_contratada_pct'])}) em que a adquirente aplicou "
                      f"{_fmt_pct(g['taxa_aplicada_pct'])}, {brl(soma(g['diferenca_brl']))} pela taxa. "
                      + (f"Observação da regra: {obs}. " if obs else "")
                      + f"Ver pendência {g['tipo_pendencia'].iloc[0]}; as transações estão em `divergencias_taxa.csv` "
                      f"marcadas com essa natureza e não entram em `orbe_contestacao.csv`.")
    for (cnpj, tipo), g in f.so_pendencia.groupby(["cnpj", "tipo_pendencia"], sort=False):
        obs = str(g["observacao"].iloc[0]) if g["observacao"].notna().any() else ""
        cobrado, pela_taxa = soma(g["cobrado_brl"]), soma(g["diferenca_brl"])
        partes.append("")
        partes.append(f"**Fora de `divergencias_taxa.csv`, por regra** ({g['regra_id'].iloc[0]}): {len(g)} transações de "
                      f"{g['lojista'].iloc[0]} com condição especial contratada ({_fmt_pct(g['taxa_contratada_pct'])}) em que a "
                      f"adquirente aplicou {_fmt_pct(g['taxa_aplicada_pct'])}: {brl(cobrado)} cobrados de fato"
                      + (f" (a fórmula bruto × taxa daria {brl(pela_taxa)}; {brl(abs(pela_taxa - cobrado))} de truncamento da "
                         f"adquirente que o lojista não pagou)" if pela_taxa != cobrado else "") + ". "
                      + (f"Observação da regra: {obs}. " if obs else "")
                      + f"Não é divergência de contrato: fica fora deste arquivo, de `orbe_contestacao.csv` e de qualquer "
                      f"cobrança da adquirente. O total e o detalhe por transação estão na pendência {tipo} (rastro).")
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
            if pend_anteriores is not None:
                marca += " (recorrente)" if _chave_pendencia(r) in pend_anteriores else " (nova)"
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

    partes += ["## Checagens de integridade", ""]
    partes += [f"- {'✅' if ch.ok else '❌'} {ch.nome}: {ch.detalhe}" for ch in f.checagens]
    partes += ["", "Arquivos: " + ", ".join(f"`{v}`" for v in res["arquivos"].values()) + ".", ""]
    return "\n".join(partes)


def escrever_relatorio(texto: str, caminho: Path) -> Path:
    gravar_texto(caminho, texto)
    return Path(caminho)
