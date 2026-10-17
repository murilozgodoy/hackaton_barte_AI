"""Pendências: tudo o que precisa de uma pessoa, com motivo em português, quem decide e rastro.

Cada pendência vem de um fato do fechamento (divergência, exclusão por regra, cadastro
faltante, saldo negativo, lançamento sem regra, valor em trânsito, conciliação). Quem
decide e o que fazer vêm da regra que a originou ou da regra DONO_PENDENCIA do tipo;
o código só junta os números ao texto. Pendência com valor tem rastro que soma o valor.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from .dinheiro import ZERO, arredondar, brl, soma
from .textos import sem_repeticao
from .regras import NATUREZA_CONTRATO, Config, Regra
from .remessa import DESTINOS_COMISSAO

PREFIXO_ID = "PEN-"
COLUNAS = ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide", "subtipo", "linha_negocio",
           "cnpj", "lojista", "qtd_itens", "regra_id", "o_que_fazer", "informativa", "incluida_em",
           # só nas pendências de remessa com spread contratado conhecido (ex.: SPREAD_NEGATIVO): o que aconteceu
           # (spread do relatório) e o que se pede ao parceiro (spread contratado, diferença e a metade da Tarvo)
           "spread_relatorio_brl", "spread_contratado_brl", "diferenca_contrato_brl", "metade_tarvo_contrato_brl"]
COLUNAS_EXTRAS = COLUNAS[15:]
COLUNAS_RASTRO = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]
# ordem de apresentação: o que mexe com dinheiro e nota primeiro, informativas depois
ORDEM_TIPOS = ["TARIFA_ZERO_COBRADA", "DIVERGENCIA_TAXA", "EXCESSO_SPREAD_CONTESTADO",
               "CONFERIR_REPASSE_PONTE", "CONFERIR_AJUSTE_PONTE", "SPREAD_NEGATIVO", "SEM_CONTRATO", "ALERTA_ANTECIPACAO",
               "SALDO_NEGATIVO_LOJISTA", "CADASTRO", "DADO_INSUFICIENTE",
               "RECURSO_SEM_OPERACAO",
               "EXTRATO_NAO_IDENTIFICADO", "DEVOLUCAO", "EM_TRANSITO", "REVISAR_IA", "FORA_COMPETENCIA",
               "LINHA_NAO_INTERPRETADA", "COMPLIANCE", "DUPLICATA_DIVERGENTE", "MANUAL"]


@dataclass
class ResultadoPendencias:
    pendencias: pd.DataFrame
    rastro: pd.DataFrame


class _Coletor:
    def __init__(self, config: Config, referencia: date):
        self.config, self.ref = config, referencia
        self.itens: list[dict] = []

    def dono(self, tipo: str) -> Regra:
        return self.config.dono(tipo, self.ref)

    def add(self, tipo: str, ref_origem, valor, motivo: str, regra: Regra, rastro: pd.DataFrame | None,
            subtipo=None, linha_negocio=None, cnpj=None, lojista=None, qtd_itens=None, extras: dict | None = None):
        # rastro que não soma o valor não é escondido aqui: a checagem 1 acusa e o fechar sai com código 3
        motivo = motivo.replace(";", ",")   # ';' é o separador do CSV; evita quebrar leitores ingênuos
        motivo = sem_repeticao(motivo)        # fato + o que fazer da regra: cada informação uma vez
        self.itens.append({
            "tipo": tipo, "ref_origem": ref_origem, "valor_brl": valor, "motivo": motivo,
            "quem_decide": regra.quem_decide, "subtipo": subtipo, "linha_negocio": linha_negocio, "cnpj": cnpj,
            "lojista": lojista, "qtd_itens": qtd_itens, "regra_id": regra.id, "o_que_fazer": regra.o_que_fazer,
            "informativa": bool(regra.params.get("informativa", False)),   # fora do "em jogo" (regra diz)
            "incluida_em": regra.params.get("incluida_em"),                 # valor já dentro de outra pendência
            **{c: (extras or {}).get(c) for c in COLUNAS_EXTRAS},
            "_rastro": rastro,
        })


def _rastro(df: pd.DataFrame, col_valor: str, col_regra: str | None = None, col_taxa: str | None = None,
            col_ref: str = "ref_origem") -> pd.DataFrame:
    return pd.DataFrame({
        "arquivo_origem": df["arquivo_origem"].values, "ref_origem": df[col_ref].values,
        "valor": df[col_valor].values,
        "regra_id": df[col_regra].values if col_regra else None,
        "taxa_pct": df[col_taxa].values if col_taxa else None,
    })


def _pct(valores) -> str:
    vals = sorted({v for v in valores if v is not None})
    txt = [f"{v.normalize():f}%" for v in vals]
    return txt[0] if len(txt) == 1 else f"{txt[0]} a {txt[-1]}"


def _nomes(serie) -> str:
    return ", ".join(sorted({str(v) for v in serie if v}))


def calcular(competencia_ref: date, chk_linhas, rem_linhas, divergencias, sem_nota, chk_rastro, lancamentos,
             em_transito, conciliacao: dict, notas, config: Config,
             taxas: pd.DataFrame | None = None, contestacao_anterior: dict | None = None,
             rem_rastro: pd.DataFrame | None = None, so_pendencia: pd.DataFrame | None = None) -> ResultadoPendencias:
    c = _Coletor(config, competencia_ref)
    _divergencias(c, divergencias, chk_linhas, rem_linhas)
    _so_pendencia(c, so_pendencia, chk_linhas)
    _ajustes_parceiro(c, rem_linhas, contestacao_anterior or {})
    _nao_interpretadas(c, rem_linhas)
    _excesso_contestado(c, rem_linhas)
    _exclusoes(c, chk_linhas, "CHECKOUT", "transações", "valor_taxa_orbe", "cod_estabelecimento")
    _exclusoes(c, rem_linhas, "REMESSA", "operações", "spread_brl", "cnpj")
    _alertas(c, chk_linhas, taxas)
    _cadastro(c, chk_linhas, rem_linhas)
    _dado_insuficiente(c, chk_linhas)
    _fora_competencia(c, chk_linhas, "CHECKOUT", "valor_taxa_orbe")
    _fora_competencia(c, rem_linhas, "REMESSA", "spread_brl")
    _duplicatas_divergentes(c, rem_linhas, chk_linhas)
    _saldo_negativo(c, sem_nota, chk_rastro, rem_rastro)
    _extratos(c, lancamentos, em_transito)
    _recurso_sem_operacao(c, lancamentos, conciliacao)
    _repasse_parceiro(c, rem_linhas, conciliacao, notas)
    return _montar(c)


# --------------------------------------------------------------------------- origens

NATUREZAS_TEXTO = {"DEVOLUCAO_LOJISTA": "devolução ao lojista"}
_ROTULO_TIPOS = {"VENDA": "vendas", "ANTECIPACAO": "antecipações", "ESTORNO": "estornos",
                 "REVERSAO ANTECIPACAO": "reversões de antecipação"}


def _meses(competencia_origem: str, ref: date) -> int:
    a, m = (int(x) for x in competencia_origem.split("-"))
    return (ref.year - a) * 12 + (ref.month - m)


def _rotulo(tipos) -> str:
    nomes = [_ROTULO_TIPOS.get(t, str(t).lower()) for t in sorted(set(tipos))]
    return " e ".join(nomes) if nomes else "transações"


def _liquido(g: pd.DataFrame, origem: pd.DataFrame, total) -> str:
    """Venda e estorno se anulam: o que se cobra é a diferença líquida. Só aparece quando há sinal negativo."""
    neg = g["diferenca_brl"] < 0
    if not neg.any():
        return f": {brl(total)}"
    pos_v, neg_v = soma(g.loc[~neg, "diferenca_brl"]), soma(g.loc[neg, "diferenca_brl"])
    tipos = origem["tipo_lancamento"].values
    return (f", valor LÍQUIDO {brl(total)} = {brl(pos_v)} a maior em {int((~neg).sum())} {_rotulo(tipos[~neg.values])}"
            f" − {brl(-neg_v)} devolvidos em {int(neg.sum())} {_rotulo(tipos[neg.values])} (venda e estorno se anulam: "
            f"cobra-se da adquirente só a diferença líquida)")


def _divergencias(c: _Coletor, div: pd.DataFrame, chk: pd.DataFrame, rem: pd.DataFrame) -> None:
    """Uma pendência por (linha, lojista, tipo, natureza) de divergencias_taxa.csv; o rastro são as transações."""
    if div is None or not len(div):
        return
    todas = div
    chk_por_ref = chk.set_index("ref_origem")
    rem_por_ref = rem[rem["destino"] == "COMISSAO"].set_index("ref_origem")
    for (linha, cnpj, tipo, natureza), g in todas.groupby(["linha_negocio", "cnpj", "tipo_pendencia", "natureza"], sort=False):
        regra = c.config.regra(g["regra_id"].iloc[0]) if tipo != "DIVERGENCIA_TAXA" else None
        if regra is None or regra.tipo != "TAXA_EXCECAO":
            regra = c.dono("DIVERGENCIA_TAXA" if tipo == "DIVERGENCIA_TAXA" else tipo)
        total = soma(g["diferenca_brl"])
        if linha == "CHECKOUT":
            origem = chk_por_ref.loc[g["ref_origem"]]
            cobrado, contratado = soma(origem["valor_taxa_orbe"]), soma(origem["comissao_brl"])
            trunc = cobrado - contratado - total
            trunc_txt = (f", {brl(abs(trunc))} {'a menos' if trunc < 0 else 'a mais'} que a divergência calculada "
                         f"porque a adquirente trunca centavos, o que não é divergência") if trunc != 0 else ""
            taxas = f"{_pct(g['taxa_contratada_pct'])} contratada x {_pct(g['taxa_aplicada_pct'])} aplicada pela adquirente"
            if natureza == NATUREZA_CONTRATO:
                motivo = (f"Divergência calculada pela taxa ({taxas}) em {len(g)} transações de checkout"
                          f"{_liquido(g, origem, total)}. A adquirente cobrou efetivamente {brl(cobrado)} "
                          f"(pela taxa contratada seria {brl(contratado)}){trunc_txt}")
            else:
                obs = str(g["observacao"].iloc[0]) if "observacao" in g.columns and g["observacao"].notna().any() else ""
                motivo = (f"A adquirente cobrou efetivamente {brl(cobrado)} em {len(g)} transações de checkout com "
                          f"condição especial ({taxas}): {brl(total)} pela taxa{trunc_txt}. As transações estão em "
                          f"divergencias_taxa.csv com natureza {natureza}, fora da cobrança da adquirente, por regra "
                          f"({regra.id}): {NATUREZAS_TEXTO.get(natureza, natureza.lower().replace('_', ' '))}"
                          + (f" ({obs})" if obs else ""))
        else:
            origem = rem_por_ref.loc[g["ref_origem"]]
            metade = soma(origem["excesso_tarvo_brl"])
            na_nota = bool(c.config.parametro("incluir_excesso_contestado", c.ref))
            motivo = (f"{len(g)} operações de remessa com spread aplicado pelo parceiro "
                      f"({_pct(g['taxa_aplicada_pct'].map(lambda v: v.quantize(Decimal('0.01'))))}) acima do contratado "
                      f"({_pct(g['taxa_contratada_pct'])}). Excesso cobrado do lojista {brl(total)} (valor cheio). "
                      f"A metade da Tarvo, {brl(metade)}, {'entrou na nota do mês' if na_nota else 'ficou fora da nota'}")
        c.add(tipo, cnpj, total, f"{motivo}. {regra.o_que_fazer}", regra,
              _rastro(g, "diferenca_brl", "regra_id", "taxa_contratada_pct"),
              linha_negocio=linha, cnpj=cnpj, lojista=g["lojista"].iloc[0], qtd_itens=len(g))


def _so_pendencia(c: _Coletor, so_pend: pd.DataFrame | None, chk: pd.DataFrame) -> None:
    """Transações que a regra TAXA_EXCECAO manda só para a pendência (destino=PENDENCIA): fora de
    divergencias_taxa.csv. Uma pendência por (lojista, tipo), pelo que a adquirente cobrou DE FATO
    (`cobrado_brl`, rastro por transação), não pela fórmula bruto × taxa."""
    if so_pend is None or not len(so_pend):
        return
    for (cnpj, tipo), g in so_pend.groupby(["cnpj", "tipo_pendencia"], sort=False):
        regra = c.config.regra(g["regra_id"].iloc[0])
        cobrado, pela_taxa = soma(g["cobrado_brl"]), soma(g["diferenca_brl"])
        trunc = pela_taxa - cobrado
        taxas = f"{_pct(g['taxa_contratada_pct'])} contratada x {_pct(g['taxa_aplicada_pct'])} aplicada pela adquirente"
        natureza = str(g["natureza"].iloc[0])
        obs = str(g["observacao"].iloc[0]) if g["observacao"].notna().any() else ""
        formula = (f"a fórmula bruto × taxa daria {brl(pela_taxa)} ({brl(abs(trunc))} de truncamento da adquirente que o "
                   f"lojista {'não pagou' if trunc > 0 else 'pagou a mais'})") if trunc != 0 else f"a fórmula bruto × taxa dá o mesmo valor"
        motivo = (f"A adquirente cobrou efetivamente {brl(cobrado)} em {len(g)} transações de checkout com condição "
                  f"especial ({taxas}). {NATUREZAS_TEXTO.get(natureza, natureza.lower().replace('_', ' ')).capitalize()} "
                  f"do que foi efetivamente cobrado: {formula}. Detalhe por transação no rastro desta pendência "
                  f"(regra {regra.id})" + (f": {obs}" if obs and not regra.o_que_fazer else ""))
        c.add(tipo, cnpj, cobrado, f"{motivo}. {regra.o_que_fazer}", regra,
              _rastro(g, "cobrado_brl", "regra_id", "taxa_contratada_pct"),
              linha_negocio="CHECKOUT", cnpj=cnpj, lojista=g["lojista"].iloc[0], qtd_itens=len(g))


def _excesso_contestado(c: _Coletor, rem: pd.DataFrame) -> None:
    com = rem[(rem["destino"] == "COMISSAO") & rem["excesso_tarvo_brl"].notna()]
    for cnpj, g in com.groupby("cnpj", sort=False):
        metade = soma(g["excesso_tarvo_brl"])
        if metade <= ZERO:
            continue
        regra = c.dono("EXCESSO_SPREAD_CONTESTADO")
        regra_param = c.config.regra_parametro("incluir_excesso_contestado", c.ref)
        na_nota = bool(regra_param.valor)
        motivo = (f"Metade da Tarvo sobre o excesso de spread cobrado de {g['lojista'].iloc[0]} em {len(g)} operações: "
                  f"{brl(metade)} (excesso cheio {brl(soma(g['diferenca_brl']))}). "
                  f"{'Entrou' if na_nota else 'Não entrou'} na nota do mês pela regra {regra_param.id} "
                  f"({regra_param.situacao}). {regra.o_que_fazer}")
        rastro = _rastro(g, "excesso_tarvo_brl")
        rastro["regra_id"] = regra_param.id
        rastro["taxa_pct"] = g["participacao"].map(lambda p: p * 100).values
        c.add("EXCESSO_SPREAD_CONTESTADO", cnpj, metade, motivo, regra, rastro, linha_negocio="REMESSA",
              cnpj=cnpj, lojista=g["lojista"].iloc[0], qtd_itens=len(g))


def _exclusoes(c: _Coletor, linhas: pd.DataFrame, linha_negocio: str, unidade: str, col_padrao: str,
               col_ec: str) -> None:
    exc = linhas[linhas["destino"] == "EXCLUIDO"]
    if exc.empty:
        return
    col_fonte = {"valor_taxa": "valor_taxa_orbe", "valor_bruto": "valor_bruto", "spread_brl": "spread_brl",
                 "valor_brl": "valor_brl"}
    for regra_id, g in exc.groupby("destino_regra", sort=False):
        regra = c.config.regra(regra_id)
        p = regra.params
        col_valor = col_fonte.get(p.get("valor_pendencia"), col_padrao)
        agrupar = p.get("agrupar", "cnpj")
        chave = {"cnpj": "cnpj", "ec": col_ec, "linha": "ref_origem"}.get(agrupar)
        grupos = [(None, g)] if agrupar == "tudo" else list(g.groupby(chave, sort=False))
        for valor_chave, gg in grupos:
            valor = soma(gg[col_valor])
            bruto = soma(gg["valor_bruto"]) if "valor_bruto" in gg.columns else soma(gg["valor_brl"])
            lojista = gg["lojista"].iloc[0] if gg["lojista"].notna().any() else _nomes(
                gg["nome_orbe"] if "nome_orbe" in gg.columns else gg["cliente_ponte"])
            singular = {"transações": "transação", "operações": "operação"}[unidade]
            detalhe = (f"{len(gg)} {unidade} de {lojista}, valor bruto {brl(bruto)}" if len(gg) > 1
                       else f"{singular} {gg['ref_origem'].iloc[0]} de {lojista}, valor {brl(bruto)}")
            if linha_negocio == "CHECKOUT":
                detalhe += (f"; a adquirente cobrou {brl(soma(gg['valor_taxa_orbe']))} a taxas de "
                            f"{_pct(gg['taxa_aplicada_pct'])}")
                if "competencia_origem" in gg.columns and gg["competencia_origem"].notna().any():
                    antigas = gg[gg["competencia_origem"].notna()]
                    idades = sorted({_meses(o, c.ref) for o in antigas["competencia_origem"]})
                    texto_idades = ", ".join(f"{i} {'mês' if i == 1 else 'meses'}" for i in idades)
                    detalhe += f" (inclui {len(antigas)} transações de meses anteriores, idade {texto_idades})"
            else:
                detalhe += f"; spread {brl(soma(gg['spread_brl']))}"
                obs = _nomes(gg["observacao"])
                if obs:
                    detalhe += f" ({obs})"
            ref = valor_chave if agrupar in ("cnpj", "ec", "linha") else f"{len(gg)} {unidade}"
            extras, dois_valores = None, ""
            if linha_negocio == "REMESSA" and gg["spread_contratado_brl"].notna().all():
                extras = {"spread_relatorio_brl": soma(gg["spread_brl"]), "spread_contratado_brl": soma(gg["spread_contratado_brl"]),
                          "diferenca_contrato_brl": soma(gg["diferenca_contrato_brl"]),
                          "metade_tarvo_contrato_brl": soma(gg["metade_tarvo_contrato_brl"])}
                dois_valores = (f" O que aconteceu: spread {brl(extras['spread_relatorio_brl'])} no relatório. O que pedimos ao "
                                f"parceiro (a trava deveria ter sido honrada): spread contratado {brl(extras['spread_contratado_brl'])} "
                                f"({_pct(gg['spread_contratado_pct'])} x PTAX x Valor ME), ou seja, a diferença de "
                                f"{brl(abs(extras['diferenca_contrato_brl']))} até esse spread contratado, do qual a metade da Tarvo seria "
                                f"{brl(extras['metade_tarvo_contrato_brl'])}.")
            c.add(regra.tipo_pendencia, ref, valor, f"{regra.situacao}: {detalhe}.{dois_valores} {regra.o_que_fazer}", regra,
                  _rastro(gg, col_valor, col_regra=None, col_taxa="taxa_aplicada_pct" if linha_negocio == "CHECKOUT" else None),
                  subtipo=regra.subtipo, linha_negocio=linha_negocio,
                  cnpj=gg["cnpj"].iloc[0] if gg["cnpj"].notna().any() else None, lojista=lojista, qtd_itens=len(gg),
                  extras=extras)


TIPOS_VENDA, TIPOS_ANTECIPACAO, TIPOS_REVERSAO = {"VENDA"}, {"ANTECIPACAO"}, {"REVERSAO ANTECIPACAO"}
TEXTO_SO_PARA = {"SEM_CONTRATO": "lojista SEM_CONTRATO no cadastro", "INATIVO": "lojista INATIVO no cadastro",
                 "ATIVO": "lojista ATIVO no cadastro",
                 "PRIMEIRO_MES": "primeira transação e primeira taxa vigente dentro do mês (sem histórico anterior)"}


def _primeiro_mes(todas_do_lojista: pd.DataFrame, cnpj: str, taxas: pd.DataFrame | None, ref: date) -> bool:
    """Sem evidência de atividade antes do mês: nenhuma linha (venda, estorno, antecipação ou reversão) com data
    de venda anterior ao mês e nenhuma taxa vigente antes dele na planilha."""
    if (todas_do_lojista["data_taxa"].dt.date < ref).any():
        return False
    if taxas is not None and len(taxas):
        linhas = taxas[taxas["cnpj"] == cnpj]
        if len(linhas) and (linhas["vigencia_de"].isna() | (linhas["vigencia_de"].dt.date < ref)).any():
            return False
    return True


def alertas_antecipacao(chk: pd.DataFrame, taxas: pd.DataFrame | None, config: Config, ref: date) -> list[dict]:
    """Critério antecipacao_acima_das_vendas das regras ALERTA (fonte orbe): por lojista, no fim de cada dia com
    antecipação, a antecipação acumulada no mês supera as vendas acumuladas até a data. O filtro so_para da regra
    limita a lojistas sem histórico no arquivo (os demais antecipam vendas de meses anteriores).
    Devolve um item por (regra, lojista) com os números e as linhas de antecipação (rastro)."""
    out = []
    regras = [r for r in config.alertas("orbe", ref) if r.params["criterio"] == "antecipacao_acima_das_vendas"]
    if not regras or chk.empty:
        return out
    todas = chk[chk["cnpj"].notna()]
    base = todas[todas["tipo_lancamento"].isin(TIPOS_VENDA | TIPOS_ANTECIPACAO)]
    for cnpj, g in base.groupby("cnpj", sort=False):
        status = g["status_cadastro"].iloc[0]
        antecip = g[g["tipo_lancamento"].isin(TIPOS_ANTECIPACAO)]
        if antecip.empty:
            continue
        acc_v = acc_a = ZERO
        estouro = None
        for dia, gd in g.sort_values("data_movimento").groupby(g["data_movimento"].dt.date, sort=True):
            acc_v += soma(gd.loc[gd["tipo_lancamento"].isin(TIPOS_VENDA), "valor_bruto"])
            a = soma(gd.loc[gd["tipo_lancamento"].isin(TIPOS_ANTECIPACAO), "valor_bruto"])
            acc_a += a
            if a and acc_a > acc_v and estouro is None:
                estouro = (dia, acc_a, acc_v)
        if estouro is None:
            continue
        for regra in regras:
            so_para = regra.params["so_para"]
            motivo_lojista = None
            if not so_para or status in so_para:
                motivo_lojista = status if so_para else "TODOS"
            elif "PRIMEIRO_MES" in so_para and _primeiro_mes(todas[todas["cnpj"] == cnpj], cnpj, taxas, ref):
                motivo_lojista = "PRIMEIRO_MES"
            if motivo_lojista is None:
                continue
            ate_estouro = antecip[antecip["data_movimento"].dt.date <= estouro[0]]
            revertido = soma(todas.loc[(todas["cnpj"] == cnpj) & todas["tipo_lancamento"].isin(TIPOS_REVERSAO), "valor_bruto"])
            out.append({"regra": regra, "cnpj": cnpj, "lojista": g["lojista"].iloc[0], "motivo_lojista": motivo_lojista,
                        "antecipado": soma(antecip["valor_bruto"]), "revertido": -revertido,
                        "vendido": soma(g.loc[g["tipo_lancamento"].isin(TIPOS_VENDA), "valor_bruto"]),
                        "data_estouro": estouro[0], "acumulado_antecipado": estouro[1], "acumulado_vendido": estouro[2],
                        "linhas": ate_estouro})
    return out


def _alertas(c: _Coletor, chk: pd.DataFrame, taxas: pd.DataFrame | None) -> None:
    for a in alertas_antecipacao(chk, taxas, c.config, c.ref):
        regra, g = a["regra"], a["linhas"]
        motivo = (f"Em {a['data_estouro']}, {brl(a['acumulado_antecipado'])} antecipados contra {brl(a['acumulado_vendido'])} "
                  f"vendidos até a data. No mês, {brl(a['antecipado'])} antecipados e {brl(a['revertido'])} revertidos "
                  f"(líquido {brl(a['antecipado'] - a['revertido'])}) contra {brl(a['vendido'])} vendidos. "
                  f"{a['lojista']}: {TEXTO_SO_PARA.get(a['motivo_lojista'], a['motivo_lojista'])}. {regra.o_que_fazer}")
        # valor = antecipação acumulada no dia em que passou das vendas = soma das antecipações até esse dia (rastro)
        c.add(regra.tipo_pendencia, a["cnpj"], a["acumulado_antecipado"], motivo, regra,
              _rastro(g, "valor_bruto", col_taxa="taxa_aplicada_pct"), subtipo=regra.subtipo,
              linha_negocio="CHECKOUT", cnpj=a["cnpj"], lojista=a["lojista"], qtd_itens=len(g))


def _dado_insuficiente(c: _Coletor, chk: pd.DataFrame) -> None:
    """Estorno/reversão sem data da venda original cuja venda não está no arquivo: fora da comissão, uma pendência por
    lojista pelo que a adquirente lançou (valor_taxa, com sinal), rastro por linha."""
    sem = chk[chk["destino"] == "DADO_INSUFICIENTE"]
    if sem.empty:
        return
    regra = c.dono("DADO_INSUFICIENTE")
    for cnpj, g in sem.groupby("cnpj", sort=False):
        valor = soma(g["valor_taxa_orbe"])
        itens = "; ".join(f"{r.ref_origem} ({str(r.tipo_lancamento).lower()} de {r.data_movimento.date()}, "
                          f"{brl(r.valor_bruto)}, origem {r.id_referencia or 'sem id_referencia'})" for r in g.head(5).itertuples())
        motivo = (f"{len(g)} linha(s) de {g['lojista'].iloc[0]} sem data da venda original e cuja transação de origem não "
                  f"está no arquivo da adquirente: {itens}{'; ...' if len(g) > 5 else ''}. Sem a data da venda não há como "
                  f"saber a taxa contratada, então ficaram fora da comissão e da nota (a adquirente lançou {brl(valor)} de "
                  f"taxa nessas linhas). {regra.o_que_fazer}")
        c.add("DADO_INSUFICIENTE", cnpj, valor, motivo, regra, _rastro(g, "valor_taxa_orbe", col_taxa="taxa_aplicada_pct"),
              linha_negocio="CHECKOUT", cnpj=cnpj, lojista=g["lojista"].iloc[0], qtd_itens=len(g))


def _cadastro(c: _Coletor, chk: pd.DataFrame, rem: pd.DataFrame) -> None:
    regra = c.dono("CADASTRO")
    sem = chk[chk["destino"] == "SEM_CADASTRO"]
    for ec, g in sem.groupby("cod_estabelecimento", sort=False):
        bruto = soma(g["valor_bruto"])
        motivo = (f"EC {ec} aparece na adquirente como {_nomes(g['nome_orbe'])} ({len(g)} transações, valor bruto "
                  f"{brl(bruto)}, taxa cobrada {brl(soma(g['valor_taxa_orbe']))}) e não está na planilha de taxas nem no "
                  f"complemento. {regra.o_que_fazer}")
        c.add("CADASTRO", ec, bruto, motivo, regra, _rastro(g, "valor_bruto"), subtipo="EC_ORBE",
              linha_negocio="CHECKOUT", lojista=_nomes(g["nome_orbe"]), qtd_itens=len(g))
    regra_ponte = c.config.dono("CADASTRO", c.ref, subtipo="CNPJ_PONTE")
    sem = rem[rem["destino"] == "SEM_CADASTRO"]
    for cnpj, g in sem.groupby("cnpj", sort=False):
        bruto = soma(g["valor_brl"])
        motivo = (f"CNPJ {cnpj} aparece no parceiro de câmbio como {_nomes(g['cliente_ponte'])} ({len(g)} operações, "
                  f"{brl(bruto)}, spread {brl(soma(g['spread_brl']))}) e não está na planilha de taxas nem no complemento. "
                  f"As operações ficaram fora da comissão (parâmetro remessa_cnpj_sem_cadastro=EXCLUIR). {regra_ponte.o_que_fazer}")
        c.add("CADASTRO", cnpj, bruto, motivo, regra_ponte, _rastro(g, "valor_brl"), subtipo="CNPJ_PONTE",
              linha_negocio="REMESSA", cnpj=cnpj, lojista=_nomes(g["cliente_ponte"]), qtd_itens=len(g))
    # CNPJ sem cadastro que ENTROU na comissão (remessa_cnpj_sem_cadastro=COMISSAO): o parceiro paga, a nota bate
    com = rem[(rem["destino"] == "COMISSAO") & (rem["subtipo"] == "CNPJ_PONTE")]
    for cnpj, g in com.groupby("cnpj", sort=False):
        valor = soma(g["comissao_brl"])
        motivo = (f"CNPJ {cnpj} aparece no parceiro de câmbio como {_nomes(g['cliente_ponte'])} ({len(g)} operações, "
                  f"{brl(soma(g['valor_brl']))}, spread {brl(soma(g['spread_brl']))}) e não está na planilha de taxas nem no "
                  f"complemento. A comissão de {brl(valor)} entrou na comissão e na nota porque o parceiro paga a participação "
                  f"sobre o spread realizado; sem spread contratado, não há conferência de divergência. {regra_ponte.o_que_fazer}")
        c.add("CADASTRO", cnpj, valor, motivo, regra_ponte, _rastro(g, "comissao_brl", "regra_id"), subtipo="CNPJ_PONTE",
              linha_negocio="REMESSA", cnpj=cnpj, lojista=_nomes(g["cliente_ponte"]), qtd_itens=len(g))
    # spread contratado ambíguo (mais de uma linha vigente para o CNPJ na planilha): a comissão entrou pelo realizado,
    # a divergência de spread não pôde ser conferida; não some em silêncio
    com = rem[(rem["destino"] == "COMISSAO") & (rem["subtipo"] == "TAXA_AMBIGUA")]
    for cnpj, g in com.groupby("cnpj", sort=False):
        regra_amb = c.config.dono("CADASTRO", c.ref, subtipo="TAXA_AMBIGUA")
        valor = soma(g["comissao_brl"])
        motivo = (f"{g['lojista'].iloc[0]} (CNPJ {cnpj}) tem mais de uma linha de spread de remessa vigente na planilha "
                  f"de taxas para a data das operações: {_nomes(g['spread_contratado_origem'])}. {len(g)} operações "
                  f"({brl(soma(g['valor_brl']))}, spread {brl(soma(g['spread_brl']))}) entraram na comissão e na nota pelo "
                  f"spread realizado ({brl(valor)}), mas a divergência de spread (contratado x aplicado) NÃO pôde ser "
                  f"conferida. {regra_amb.o_que_fazer}")
        c.add("CADASTRO", cnpj, valor, motivo, regra_amb, _rastro(g, "comissao_brl", "regra_id"), subtipo="TAXA_AMBIGUA",
              linha_negocio="REMESSA", cnpj=cnpj, lojista=g["lojista"].iloc[0], qtd_itens=len(g))
    sem = chk[chk["destino"] == "SEM_TAXA"]
    for (cnpj, subtipo), g in sem.groupby(["cnpj", "subtipo"], sort=False):
        regra_sub = c.config.dono("CADASTRO", c.ref, subtipo=subtipo)   # ex.: PARCELAS_FORA_FAIXA tem dono próprio
        valor = soma(g["valor_taxa_orbe"])
        motivo = (f"{len(g)} transações de {g['lojista'].iloc[0]} sem taxa contratada na planilha "
                  f"({_nomes(g['produto'])}): {_nomes(g['motivo'])}. A adquirente cobrou {brl(valor)}. {regra_sub.o_que_fazer}")
        c.add("CADASTRO", cnpj, valor, motivo, regra_sub, _rastro(g, "valor_taxa_orbe", col_taxa="taxa_aplicada_pct"),
              subtipo=subtipo, linha_negocio="CHECKOUT", cnpj=cnpj, lojista=g["lojista"].iloc[0],
              qtd_itens=len(g))
    # remessa de lojista sem contrato/inativo: a comissão entra (o spread é pago pelo parceiro), mas avisa
    com = rem[(rem["destino"] == "COMISSAO") & rem["status_cadastro"].notna() & (rem["status_cadastro"] != "ATIVO")]
    for cnpj, g in com.groupby("cnpj", sort=False):
        valor = soma(g["comissao_brl"])
        motivo = (f"{g['lojista'].iloc[0]} está como {g['status_cadastro'].iloc[0]} no cadastro e fez {len(g)} operações "
                  f"de remessa ({brl(soma(g['valor_brl']))}). A comissão de {brl(valor)} entrou porque vem do spread pago "
                  f"pelo parceiro, mas o lojista não tem contrato vigente de checkout. Informativo. {regra.o_que_fazer}")
        c.add("CADASTRO", cnpj, valor, motivo, regra, _rastro(g, "comissao_brl", "regra_id"),
              subtipo="REMESSA_LOJISTA_SEM_CONTRATO", linha_negocio="REMESSA", cnpj=cnpj,
              lojista=g["lojista"].iloc[0], qtd_itens=len(g))


def _ajustes_parceiro(c: _Coletor, rem: pd.DataFrame, contestacao_anterior: dict) -> None:
    """Uma pendência (informativa, por regra) por linha de ajuste do parceiro: entrou na comissão do mês pelo valor;
    ligada ao pedido da contestação anterior quando --anterior trouxe a lista."""
    aj = rem[rem["destino"] == "AJUSTE_PONTE"]
    if aj.empty:
        return
    regra = c.dono("CONFERIR_AJUSTE_PONTE")
    for r in aj.itertuples(index=False):
        original = r.operacao_original
        ant = contestacao_anterior.get(original) if original else None
        if original and ant:
            ligacao = (f"Refere-se à operação {original}, pedido {ant.get('pedido') or '?'} ({ant.get('natureza') or 'sem natureza'}) "
                       f"da contestação do fechamento anterior" + (f" ({ant['competencia']})" if ant.get("competencia") else ""))
        elif original:
            ligacao = (f"Refere-se à operação {original}, que não está na contestação do fechamento anterior (sem --anterior "
                       f"ou operação não contestada): conferir a origem com o parceiro")
        else:
            ligacao = ("A observação não cita a operação original (regra de segurança por trecho): conferir com o parceiro "
                       "a que operação o ajuste se refere")
        sinal = "crédito" if r.spread_brl >= ZERO else "débito"
        motivo = (f"Ajuste do parceiro de câmbio no relatório do mês: linha {r.num_operacao} ({r.data_contratacao.date()}), "
                  f"{sinal} de {brl(r.spread_brl)} de spread para {r.lojista}"
                  + (f" (observação: \"{r.observacao}\")" if r.observacao else "")
                  + f". {'Abateu' if r.comissao_brl < ZERO else 'Entrou em'} {brl(r.comissao_brl)} na participação de remessa deste mês, "
                  f"dentro da nota única do parceiro ({_pct([r.participacao * 100])} do Spread R$ da linha), sem nota complementar. "
                  f"{ligacao}. {regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.comissao_brl,
                                "regra_id": r.regra_id, "taxa_pct": r.participacao * 100}])
        c.add("CONFERIR_AJUSTE_PONTE", r.ref_origem, r.comissao_brl, motivo, regra, rastro, subtipo=r.subtipo,
              linha_negocio="REMESSA", cnpj=r.cnpj, lojista=r.lojista, qtd_itens=1)


def _nao_interpretadas(c: _Coletor, rem: pd.DataFrame) -> None:
    """Linha do relatório do parceiro sem os números mínimos: fora de tudo, uma pendência por linha, sem valor."""
    ruins = rem[rem["destino"] == "NAO_INTERPRETADA"]
    if ruins.empty:
        return
    regra = c.dono("LINHA_NAO_INTERPRETADA")
    for r in ruins.itertuples(index=False):
        motivo = (f"Relatório do parceiro de câmbio, {r.motivo} (Nº Operação {r.num_operacao or 'em branco'}, cliente "
                  f"{r.cliente_ponte or 'em branco'}). {regra.o_que_fazer}")
        c.add("LINHA_NAO_INTERPRETADA", r.ref_origem or f"linha {r.linha_planilha}", None, motivo, regra, None,
              linha_negocio="REMESSA", cnpj=r.cnpj, lojista=r.cliente_ponte, qtd_itens=1)


def _fora_competencia(c: _Coletor, linhas: pd.DataFrame, linha_negocio: str, col_valor: str) -> None:
    fora = linhas[linhas["destino"] == "FORA_COMPETENCIA"]
    if fora.empty:
        return
    regra = c.dono("FORA_COMPETENCIA")
    valor = soma(fora[col_valor])
    motivo = f"{len(fora)} linhas de {linha_negocio} fora da competência fechada: {_nomes(fora['motivo'])}. {regra.o_que_fazer}"
    c.add("FORA_COMPETENCIA", f"{len(fora)} linhas", valor, motivo, regra, _rastro(fora, col_valor),
          linha_negocio=linha_negocio, qtd_itens=len(fora))


def _duplicatas_divergentes(c: _Coletor, rem: pd.DataFrame, chk: pd.DataFrame | None = None) -> None:
    dup_chk = chk[chk["destino"] == "DUPLICATA_DIVERGENTE"] if chk is not None and len(chk) else None
    if dup_chk is not None and len(dup_chk):
        regra = c.dono("DUPLICATA_DIVERGENTE")
        for tid, g in dup_chk.groupby("id_transacao", sort=False):
            motivo = (f"Transação {tid} aparece {len(g)} vezes nos arquivos da adquirente ("
                      f"{', '.join(str(a) for a in g['arquivo_origem'])}) com valores "
                      f"diferentes: valor bruto {', '.join(brl(v) for v in g['valor_bruto'])}; taxa cobrada "
                      f"{', '.join(brl(v) for v in g['valor_taxa_orbe'])}. Nenhuma das linhas entrou na comissão. {regra.o_que_fazer}")
            c.add("DUPLICATA_DIVERGENTE", tid, None, motivo, regra, None, linha_negocio="CHECKOUT",
                  cnpj=g["cnpj"].iloc[0], lojista=g["lojista"].iloc[0], qtd_itens=len(g))
    dup = rem[rem["destino"] == "DUPLICATA_DIVERGENTE"]
    if dup.empty:
        return
    regra = c.dono("DUPLICATA_DIVERGENTE")
    for num, g in dup.groupby("num_operacao", sort=False):
        motivo = (f"Operação {num} aparece {len(g)} vezes no relatório do parceiro (linhas "
                  f"{', '.join(str(l) for l in g['linha_planilha'])}) com valores diferentes: spreads "
                  f"{', '.join(brl(v) for v in g['spread_brl'])}. Nenhuma das linhas entrou na comissão. {regra.o_que_fazer}")
        c.add("DUPLICATA_DIVERGENTE", num, None, motivo, regra, None, linha_negocio="REMESSA",
              cnpj=g["cnpj"].iloc[0], lojista=_nomes(g["cliente_ponte"]), qtd_itens=len(g))


def _saldo_negativo(c: _Coletor, sem_nota: pd.DataFrame, chk_rastro: pd.DataFrame,
                    rem_rastro: pd.DataFrame | None = None) -> None:
    """Checkout: comissão do lojista negativa (zero não é pendência). Remessa: participação do mês zerada ou negativa
    (ajustes do parceiro maiores que o spread das operações): não há nota única para o parceiro, pendência."""
    if sem_nota.empty:
        return
    regra = c.dono("SALDO_NEGATIVO_LOJISTA")
    cols = ["arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]
    for r in sem_nota.itertuples(index=False):
        if r.linha_negocio == "REMESSA":
            if r.comissao_brl > ZERO:
                continue
            ids = [i.strip() for i in str(r.id_saida).split(",")]
            rastro = (rem_rastro[rem_rastro["id_saida"].isin(ids)][cols] if rem_rastro is not None and len(rem_rastro)
                      else pd.DataFrame(columns=cols))
            motivo = (f"A participação de remessa do mês ({r.qtd_transacoes} linhas do relatório do parceiro, ajustes incluídos) "
                      f"fechou em {brl(r.comissao_brl)}: os ajustes do parceiro superaram a participação sobre as operações do "
                      f"mês. Não há nota de remessa a emitir para {r.lojista} e nada carrega automaticamente. {regra.o_que_fazer}")
            c.add("SALDO_NEGATIVO_LOJISTA", r.cnpj, r.comissao_brl, motivo, regra, rastro.reset_index(drop=True),
                  subtipo="REMESSA_PARCEIRO", linha_negocio="REMESSA", cnpj=r.cnpj, lojista=r.lojista,
                  qtd_itens=int(r.qtd_transacoes))
            continue
        if r.comissao_brl >= ZERO:
            continue
        rastro = chk_rastro[chk_rastro["id_saida"] == r.id_saida][cols]
        motivo = (f"A comissão de checkout de {r.lojista} em {r.qtd_transacoes} transações fechou em {brl(r.comissao_brl)} "
                  f"(estornos ou reversões maiores que as vendas do mês). Não há nota a emitir. {regra.o_que_fazer}")
        c.add("SALDO_NEGATIVO_LOJISTA", r.cnpj, r.comissao_brl, motivo, regra, rastro.reset_index(drop=True),
              linha_negocio="CHECKOUT", cnpj=r.cnpj, lojista=r.lojista, qtd_itens=int(r.qtd_transacoes))


def _extratos(c: _Coletor, lanc: pd.DataFrame, em_transito: pd.DataFrame) -> None:
    pend = lanc[lanc["tipo_pendencia"].notna()]
    for r in pend.itertuples(index=False):
        regra = c.config.regra(r.regra_id) if r.regra_id else None
        if regra is None or not regra.params.get("gera_pendencia"):
            regra = c.dono(r.tipo_pendencia)
        detalhe = f"{r.motivo.rstrip('.')}. " if r.motivo and r.motivo != regra.o_que_fazer else ""
        motivo = (f"{r.banco} {r.data.date()}: \"{r.descricao}\" {brl(r.valor)}"
                  + (f", classificado em {r.conta_codigo} ({r.conta_descricao})" if r.conta_codigo else ", sem conta")
                  + f". {detalhe}{regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.valor,
                                "regra_id": r.regra_id, "taxa_pct": None}])
        c.add(r.tipo_pendencia, r.ref_origem, r.valor, motivo, regra, rastro, subtipo=r.subtipo, qtd_itens=1)
    if em_transito.empty:
        return
    regra = c.dono("EM_TRANSITO")
    por_id = lanc.set_index("id_saida")
    for r in em_transito.itertuples(index=False):
        l = por_id.loc[r.id_saida]
        motivo = (f"{r.banco} {r.data.date()}: \"{r.descricao}\" {brl(r.valor)}, em {r.conta_codigo} "
                  f"({l.conta_descricao}): {r.motivo}. {regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": l.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.valor,
                                "regra_id": l.regra_id, "taxa_pct": None}])
        c.add("EM_TRANSITO", r.ref_origem, r.valor, motivo, regra, rastro, qtd_itens=1)


def _recurso_sem_operacao(c: _Coletor, lanc: pd.DataFrame, conciliacao: dict) -> None:
    rb = conciliacao["remessa_banco"]
    diferenca = rb["recursos_menos_liquidado"]
    if diferenca == ZERO or rb["qtd_liquidacoes"] == 0:
        return
    regra = c.config.dono_se_houver("RECURSO_SEM_OPERACAO", c.ref)   # pendência opcional: sem dono, só lembrete MANUAL
    if regra is None:
        return
    recursos = lanc[lanc["papel"] == "recurso_remessa"]
    iguais = recursos[recursos["valor"] == diferenca]
    liquidado_txt = brl(rb["liquidado_na_ponte"])
    if rb["liquidado_menos_operacoes"] == ZERO:
        liquidado_txt += ", igual ao total das operações do relatório (Valor R$ + IOF)"
    if len(iguais) == 1:
        r = iguais.iloc[0]
        motivo = (f"Os recursos recebidos de lojistas para remessa ({brl(rb['recursos_recebidos'])}) superam o liquidado no "
                  f"parceiro ({liquidado_txt}) em {brl(diferenca)}. O valor coincide com o lançamento {r.ref_origem} de "
                  f"{r.data.date()}: \"{r.descricao}\"; confirmar com o lojista e o parceiro se é esse o recurso sem "
                  f"operação. {regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.valor,
                                "regra_id": r.regra_id, "taxa_pct": None}])
        c.add("RECURSO_SEM_OPERACAO", r.ref_origem, diferenca, motivo, regra, rastro, qtd_itens=1)
        return
    base = lanc[lanc["papel"].isin(["recurso_remessa", "liquidacao_remessa"])]
    motivo = (f"Os recursos recebidos de lojistas para remessa ({brl(rb['recursos_recebidos'])}) e o liquidado no parceiro "
              f"({liquidado_txt}) diferem em {brl(diferenca)}, sem um lançamento único que explique. "
              f"{regra.o_que_fazer}")
    c.add("RECURSO_SEM_OPERACAO", f"{len(base)} lançamentos", diferenca, motivo, regra,
          _rastro(base, "valor", "regra_id"), qtd_itens=len(base))


COLUNAS_CONTESTACAO = ["ref_origem", "cnpj", "lojista", "linha_negocio", "data", "produto", "taxa_contratada_pct",
                       "taxa_aplicada_pct", "valor_brl", "natureza", "pedido", "spread_relatorio_brl", "spread_contratado_brl",
                       "diferenca_contrato_brl", "metade_tarvo_contrato_brl", "motivo", "regra_id", "arquivo_origem"]


def lista_contestacao(rem: pd.DataFrame) -> pd.DataFrame:
    """Operações que vão na resposta ao relatório do parceiro (anexo de e-mail, não pendência): spread acima do
    contratado (excesso cheio, natureza EXCESSO_SPREAD), excluídas por regra (ex.: spread negativo, valor com sinal,
    natureza = tipo da pendência) e repetidas (valor 0, natureza REPETIDA: contada uma vez, só para corrigir o
    relatório). Cada natureza soma exatamente a pendência atômica correspondente.

    `pedido` (a, b, c...) agrupa o que é um pedido só para a contraparte: um por lojista com excesso, um por
    natureza de exclusão, um para as repetidas. Não há total único: cada pedido tem o seu valor e as suas operações."""
    excesso = rem[(rem["destino"] == "COMISSAO") & rem["diferenca_brl"].notna() & (rem["diferenca_brl"] > 0)]
    excluidas = rem[rem["destino"] == "EXCLUIDO"]
    repetidas = rem[rem["destino"].isin(["DUPLICATA_IGNORADA", "DUPLICATA_DIVERGENTE"])]
    partes = []
    for df, natureza, col_valor, motivo, chave in (
            (excesso, "EXCESSO_SPREAD", "diferenca_brl", "spread aplicado acima do contratado: excesso cheio a devolver ao lojista", "cnpj"),
            (excluidas, None, "spread_brl", None, "tipo_pendencia"),
            (repetidas, "REPETIDA", None, "operação repetida no relatório: contada uma vez, corrigir o relatório", None)):
        if df.empty:
            continue
        partes.append(pd.DataFrame({
            "ref_origem": df["ref_origem"], "cnpj": df["cnpj"], "lojista": df["lojista"], "linha_negocio": "REMESSA",
            "data": df["data_contratacao"], "produto": "spread " + df["moeda"].astype(str),
            "taxa_contratada_pct": df["spread_contratado_pct"], "taxa_aplicada_pct": df["spread_pct"],
            "valor_brl": df[col_valor] if col_valor else ZERO,
            "natureza": natureza if natureza else df["tipo_pendencia"],
            # os dois valores (relatório x contrato) só nas excluídas: nas de excesso o valor cheio já é a diferença
            "spread_relatorio_brl": df["spread_brl"] if natureza is None else None,
            "spread_contratado_brl": df["spread_contratado_brl"] if natureza is None else None,
            "diferenca_contrato_brl": df["diferenca_contrato_brl"] if natureza is None else None,
            "metade_tarvo_contrato_brl": df["metade_tarvo_contrato_brl"] if natureza is None else None,
            "_grupo": (natureza or "EXCLUIDO") + ":" + (df[chave].astype(str) if chave else ""),
            "motivo": motivo if motivo else df["motivo"], "regra_id": df["destino_regra"] if natureza is None else None,
            "arquivo_origem": df["arquivo_origem"],
        }))
    if not partes:
        return pd.DataFrame(columns=COLUNAS_CONTESTACAO)
    lc = pd.concat(partes, ignore_index=True)
    letras = {g: chr(ord("a") + i) for i, g in enumerate(dict.fromkeys(lc["_grupo"]))}
    lc["pedido"] = lc["_grupo"].map(letras)
    return lc[COLUNAS_CONTESTACAO]


def _repasse_parceiro(c: _Coletor, rem: pd.DataFrame, conciliacao: dict, notas: pd.DataFrame) -> None:
    p = conciliacao["ponte"]
    diferenca = p["diferenca"]
    if diferenca is None or diferenca == ZERO:
        return
    regra = c.dono("CONFERIR_REPASSE_PONTE")
    modo = c.config.parametro("arredondamento", c.ref)
    participacao = c.config.parametro("participacao_spread", c.ref)
    regra_arred = c.config.regra_parametro("arredondamento", c.ref)
    # cada linha do relatório que não entrou na comissão explica uma parte, HALF_UP por linha (= rastro)
    partes, descricao = [], []
    fora = rem[~rem["destino"].isin(DESTINOS_COMISSAO) & rem["spread_brl"].notna()]
    for destino, g in fora.groupby("destino", sort=False):
        efeito = ZERO
        for r in g.itertuples(index=False):
            v = arredondar(-r.spread_brl * participacao, modo)
            efeito += v
            partes.append({"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem, "valor": v,
                           "regra_id": r.destino_regra or destino, "taxa_pct": participacao * 100})
        regras_g = ", ".join(sorted({f"{c.config.regra(r).situacao}, regra {r}" for r in g["destino_regra"] if r}))
        descricao.append(f"{_assinado(efeito)} de {len(g)} {DESTINOS_PONTE.get(destino, destino.lower())}"
                         + (f" ({regras_g})" if regras_g and destino == "EXCLUIDO" else ""))
    rastro = pd.DataFrame(partes, columns=COLUNAS_RASTRO[1:])
    residual = diferenca - soma(rastro["valor"])
    if residual != ZERO:
        rastro = pd.concat([rastro, pd.DataFrame([{"arquivo_origem": rem["arquivo_origem"].iloc[0],
                                                   "ref_origem": p["total_declarado_ref"], "valor": residual,
                                                   "regra_id": regra_arred.id, "taxa_pct": None}])], ignore_index=True)
        if p["residual_e_arredondamento"]:
            descricao.append(f"{_assinado(residual)} de arredondamento por operação (dentro do limite de "
                             f"{brl(p['limite_arredondamento'])})")
        else:
            descricao.append(f"{_assinado(residual)} NÃO explicados por arredondamento (o máximo possível seria "
                             f"{brl(p['limite_arredondamento'])}): investigar antes de contestar")
    nf = notas[notas["linha_negocio"] == "REMESSA"]
    nf_txt = f"a nota {nf['id_saida'].iloc[0]} ({brl(nf['valor_brl'].iloc[0])})" if len(nf) else "a comissão calculada"
    quando = (f"previsto para {p['data_repasse']} (data do e-mail do parceiro)" if p.get("data_repasse")
              else "na data de repasse informada no e-mail do parceiro")
    motivo = (f"Conferir o TED do parceiro de câmbio {quando} contra {nf_txt}. Se o parceiro pagar {_pct([participacao * 100])} "
              f"do total que declarou ({brl(p['spread_total_declarado'])} -> {brl(p['repasse_pelo_total_declarado'])}), "
              f"a diferença possível é {brl(diferenca)} (= " + " ".join(descricao) + f"). {regra.o_que_fazer}")
    c.add("CONFERIR_REPASSE_PONTE", p["total_declarado_ref"], diferenca, motivo, regra, rastro,
          linha_negocio="REMESSA", qtd_itens=len(rastro))


DESTINOS_PONTE = {
    "EXCLUIDO": "operações excluídas",
    "DUPLICATA_IGNORADA": "operação repetida, contada uma vez",
    "DUPLICATA_DIVERGENTE": "linha repetida com valores diferentes, fora da comissão",
    "SEM_CADASTRO": "operação de CNPJ sem cadastro, fora da comissão",
    "FORA_COMPETENCIA": "operação fora da competência",
    "NAO_INTERPRETADA": "linha sem os números mínimos, fora da comissão",
}


def _assinado(v: Decimal) -> str:
    return ("+ " if v >= 0 else "- ") + brl(abs(v))


# --------------------------------------------------------------------------- montagem

def _montar(c: _Coletor) -> ResultadoPendencias:
    if not c.itens:
        return ResultadoPendencias(pd.DataFrame(columns=COLUNAS), pd.DataFrame(columns=COLUNAS_RASTRO))
    ordem = {t: i for i, t in enumerate(ORDEM_TIPOS)}
    itens = sorted(c.itens, key=lambda i: (ordem.get(i["tipo"], len(ordem)), str(i["linha_negocio"] or ""),
                                           str(i["cnpj"] or ""), str(i["ref_origem"])))
    partes = []
    for n, item in enumerate(itens, start=1):
        item["id_saida"] = f"{PREFIXO_ID}{n:04d}"
        rastro = item.pop("_rastro")
        if rastro is not None and len(rastro):
            partes.append(rastro.assign(id_saida=item["id_saida"]))
    pend = pd.DataFrame(itens)[COLUNAS]
    rastro = (pd.concat(partes, ignore_index=True)[COLUNAS_RASTRO] if partes
              else pd.DataFrame(columns=COLUNAS_RASTRO))
    return ResultadoPendencias(pend, rastro)
