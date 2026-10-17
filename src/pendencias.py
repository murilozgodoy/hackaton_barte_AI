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
from .regras import Config, Regra

PREFIXO_ID = "PEN-"
COLUNAS = ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide", "subtipo", "linha_negocio",
           "cnpj", "lojista", "qtd_itens", "regra_id", "o_que_fazer"]
COLUNAS_RASTRO = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]
# ordem de apresentação: o que mexe com dinheiro e nota primeiro, informativas depois
ORDEM_TIPOS = ["TARIFA_ZERO_COBRADA", "DIVERGENCIA_TAXA", "EXCESSO_SPREAD_CONTESTADO", "REPASSE_PONTE_DIVERGENTE",
               "SPREAD_NEGATIVO", "SEM_CONTRATO", "SALDO_NEGATIVO_LOJISTA", "CADASTRO", "RECURSO_SEM_OPERACAO",
               "EXTRATO_NAO_IDENTIFICADO", "DEVOLUCAO", "EM_TRANSITO", "REVISAR_IA", "FORA_COMPETENCIA",
               "COMPLIANCE", "DUPLICATA_DIVERGENTE", "MANUAL"]


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
            subtipo=None, linha_negocio=None, cnpj=None, lojista=None, qtd_itens=None):
        if rastro is not None and valor is not None and soma(rastro["valor"]) != valor:
            raise AssertionError(f"pendência {tipo} {ref_origem}: rastro soma {soma(rastro['valor'])}, valor {valor}")
        self.itens.append({
            "tipo": tipo, "ref_origem": ref_origem, "valor_brl": valor, "motivo": motivo,
            "quem_decide": regra.quem_decide, "subtipo": subtipo, "linha_negocio": linha_negocio, "cnpj": cnpj,
            "lojista": lojista, "qtd_itens": qtd_itens, "regra_id": regra.id, "o_que_fazer": regra.o_que_fazer,
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
             em_transito, conciliacao: dict, notas, config: Config) -> ResultadoPendencias:
    c = _Coletor(config, competencia_ref)
    _divergencias(c, divergencias, chk_linhas, rem_linhas)
    _excesso_contestado(c, rem_linhas)
    _exclusoes(c, chk_linhas, "CHECKOUT", "transações", "valor_taxa_orbe", "cod_estabelecimento")
    _exclusoes(c, rem_linhas, "REMESSA", "operações", "spread_brl", "cnpj")
    _cadastro(c, chk_linhas, rem_linhas)
    _fora_competencia(c, chk_linhas, "CHECKOUT", "valor_taxa_orbe")
    _fora_competencia(c, rem_linhas, "REMESSA", "spread_brl")
    _duplicatas_divergentes(c, rem_linhas)
    _saldo_negativo(c, sem_nota, chk_rastro)
    _extratos(c, lancamentos, em_transito)
    _recurso_sem_operacao(c, lancamentos, conciliacao)
    _repasse_parceiro(c, rem_linhas, conciliacao, notas)
    return _montar(c)


# --------------------------------------------------------------------------- origens

def _divergencias(c: _Coletor, div: pd.DataFrame, chk: pd.DataFrame, rem: pd.DataFrame) -> None:
    if div.empty:
        return
    chk_por_ref = chk.set_index("ref_origem")
    rem_por_ref = rem[rem["destino"] == "COMISSAO"].set_index("ref_origem")
    for (linha, cnpj, tipo), g in div.groupby(["linha_negocio", "cnpj", "tipo_pendencia"], sort=False):
        regra = c.config.regra(g["regra_id"].iloc[0]) if tipo != "DIVERGENCIA_TAXA" else None
        if regra is None or regra.tipo != "TAXA_EXCECAO":
            regra = c.dono("DIVERGENCIA_TAXA" if tipo == "DIVERGENCIA_TAXA" else tipo)
        total = soma(g["diferenca_brl"])
        if linha == "CHECKOUT":
            origem = chk_por_ref.loc[g["ref_origem"]]
            cobrado, contratado = soma(origem["valor_taxa_orbe"]), soma(origem["comissao_brl"])
            trunc = cobrado - contratado - total
            motivo = (f"{len(g)} transações de checkout com taxa aplicada pela adquirente "
                      f"({_pct(g['taxa_aplicada_pct'])}) diferente da contratada ({_pct(g['taxa_contratada_pct'])}). "
                      f"A adquirente cobrou {brl(cobrado)}; pela taxa contratada seria {brl(contratado)}; "
                      f"diferença {brl(total)}")
            if trunc != 0:
                motivo += f" ({brl(abs(trunc))} a menos no cobrado é truncamento da adquirente, não divergência)"
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
                  f"{'Entrou' if na_nota else 'Não entrou'} na nota do mês por decisão da regra {regra_param.id}. "
                  f"{regra.o_que_fazer}")
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
            else:
                detalhe += f"; spread {brl(soma(gg['spread_brl']))}"
                obs = _nomes(gg["observacao"])
                if obs:
                    detalhe += f" ({obs})"
            ref = valor_chave if agrupar in ("cnpj", "ec", "linha") else f"{len(gg)} {unidade}"
            c.add(regra.tipo_pendencia, ref, valor, f"{regra.situacao}: {detalhe}. {regra.o_que_fazer}", regra,
                  _rastro(gg, col_valor, col_regra=None, col_taxa="taxa_aplicada_pct" if linha_negocio == "CHECKOUT" else None),
                  subtipo=regra.subtipo, linha_negocio=linha_negocio,
                  cnpj=gg["cnpj"].iloc[0] if gg["cnpj"].notna().any() else None, lojista=lojista, qtd_itens=len(gg))


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
    sem = rem[rem["destino"] == "SEM_CADASTRO"]
    for cnpj, g in sem.groupby("cnpj", sort=False):
        bruto = soma(g["valor_brl"])
        motivo = (f"CNPJ {cnpj} aparece no parceiro de câmbio como {_nomes(g['cliente_ponte'])} ({len(g)} operações, "
                  f"{brl(bruto)}, spread {brl(soma(g['spread_brl']))}) e não está na planilha de taxas nem no complemento. "
                  f"{regra.o_que_fazer}")
        c.add("CADASTRO", cnpj, bruto, motivo, regra, _rastro(g, "valor_brl"), subtipo="CNPJ_PONTE",
              linha_negocio="REMESSA", cnpj=cnpj, lojista=_nomes(g["cliente_ponte"]), qtd_itens=len(g))
    sem = chk[chk["destino"] == "SEM_TAXA"]
    for cnpj, g in sem.groupby("cnpj", sort=False):
        valor = soma(g["valor_taxa_orbe"])
        motivo = (f"{len(g)} transações de {g['lojista'].iloc[0]} sem taxa contratada na planilha "
                  f"({_nomes(g['produto'])}): {_nomes(g['motivo'])}. A adquirente cobrou {brl(valor)}. {regra.o_que_fazer}")
        c.add("CADASTRO", cnpj, valor, motivo, regra, _rastro(g, "valor_taxa_orbe", col_taxa="taxa_aplicada_pct"),
              subtipo="TAXA_NAO_CADASTRADA", linha_negocio="CHECKOUT", cnpj=cnpj, lojista=g["lojista"].iloc[0],
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


def _fora_competencia(c: _Coletor, linhas: pd.DataFrame, linha_negocio: str, col_valor: str) -> None:
    fora = linhas[linhas["destino"] == "FORA_COMPETENCIA"]
    if fora.empty:
        return
    regra = c.dono("FORA_COMPETENCIA")
    valor = soma(fora[col_valor])
    motivo = f"{len(fora)} linhas de {linha_negocio} fora da competência fechada: {_nomes(fora['motivo'])}. {regra.o_que_fazer}"
    c.add("FORA_COMPETENCIA", f"{len(fora)} linhas", valor, motivo, regra, _rastro(fora, col_valor),
          linha_negocio=linha_negocio, qtd_itens=len(fora))


def _duplicatas_divergentes(c: _Coletor, rem: pd.DataFrame) -> None:
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


def _saldo_negativo(c: _Coletor, sem_nota: pd.DataFrame, chk_rastro: pd.DataFrame) -> None:
    if sem_nota.empty:
        return
    regra = c.dono("SALDO_NEGATIVO_LOJISTA")
    for r in sem_nota.itertuples(index=False):
        if r.comissao_brl >= ZERO:
            continue
        rastro = chk_rastro[chk_rastro["id_saida"] == r.id_saida][["arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]]
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
        motivo = (f"{r.banco} {r.data.date()}: \"{r.descricao}\" {brl(r.valor)}"
                  + (f", classificado em {r.conta_codigo} ({r.conta_descricao})" if r.conta_codigo else ", sem conta")
                  + f". {r.motivo or regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.valor,
                                "regra_id": r.regra_id, "taxa_pct": None}])
        c.add(r.tipo_pendencia, r.ref_origem, r.valor, motivo, regra, rastro, subtipo=r.subtipo, qtd_itens=1)
    if em_transito.empty:
        return
    regra = c.dono("EM_TRANSITO")
    por_id = lanc.set_index("id_saida")
    for r in em_transito.itertuples(index=False):
        l = por_id.loc[r.id_saida]
        motivo = (f"{r.banco} {r.data.date()}: \"{r.descricao}\" {brl(r.valor)} em {r.conta_codigo}: {r.motivo}. "
                  f"{regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": l.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.valor,
                                "regra_id": l.regra_id, "taxa_pct": None}])
        c.add("EM_TRANSITO", r.ref_origem, r.valor, motivo, regra, rastro, qtd_itens=1)


def _recurso_sem_operacao(c: _Coletor, lanc: pd.DataFrame, conciliacao: dict) -> None:
    rb = conciliacao["remessa_banco"]
    diferenca = rb["recursos_menos_liquidado"]
    if diferenca == ZERO or rb["qtd_liquidacoes"] == 0:
        return
    regra = c.dono("RECURSO_SEM_OPERACAO")
    recursos = lanc[lanc["papel"] == "recurso_remessa"]
    iguais = recursos[recursos["valor"] == diferenca]
    if len(iguais) == 1:
        r = iguais.iloc[0]
        motivo = (f"Os recursos recebidos de lojistas para remessa ({brl(rb['recursos_recebidos'])}) superam o liquidado no "
                  f"parceiro ({brl(rb['liquidado_na_ponte'])}, igual ao total das operações do relatório) em {brl(diferenca)}, "
                  f"exatamente o lançamento {r.ref_origem} de {r.data.date()}: \"{r.descricao}\". {regra.o_que_fazer}")
        rastro = pd.DataFrame([{"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem, "valor": r.valor,
                                "regra_id": r.regra_id, "taxa_pct": None}])
        c.add("RECURSO_SEM_OPERACAO", r.ref_origem, diferenca, motivo, regra, rastro, qtd_itens=1)
        return
    base = lanc[lanc["papel"].isin(["recurso_remessa", "liquidacao_remessa"])]
    motivo = (f"Os recursos recebidos de lojistas para remessa ({brl(rb['recursos_recebidos'])}) e o liquidado no parceiro "
              f"({brl(rb['liquidado_na_ponte'])}) diferem em {brl(diferenca)}, sem um lançamento único que explique. "
              f"{regra.o_que_fazer}")
    c.add("RECURSO_SEM_OPERACAO", f"{len(base)} lançamentos", diferenca, motivo, regra,
          _rastro(base, "valor", "regra_id"), qtd_itens=len(base))


def _repasse_parceiro(c: _Coletor, rem: pd.DataFrame, conciliacao: dict, notas: pd.DataFrame) -> None:
    p = conciliacao["ponte"]
    diferenca = p["diferenca"]
    if diferenca is None or diferenca == ZERO:
        return
    regra = c.dono("REPASSE_PONTE_DIVERGENTE")
    modo = c.config.parametro("arredondamento", c.ref)
    participacao = c.config.parametro("participacao_spread", c.ref)
    regra_arred = c.config.regra_parametro("arredondamento", c.ref)
    partes = []
    for destino in ("EXCLUIDO", "DUPLICATA_IGNORADA"):
        g = rem[rem["destino"] == destino]
        for r in g.itertuples(index=False):
            partes.append({"arquivo_origem": r.arquivo_origem, "ref_origem": r.ref_origem,
                           "valor": arredondar(-r.spread_brl * participacao, modo), "regra_id": r.destino_regra,
                           "taxa_pct": participacao * 100})
    rastro = pd.DataFrame(partes, columns=COLUNAS_RASTRO[1:])
    residual = diferenca - soma(rastro["valor"])
    if residual != ZERO:
        eml = rem["arquivo_origem"].iloc[0]
        rastro = pd.concat([rastro, pd.DataFrame([{"arquivo_origem": eml, "ref_origem": "SPREAD TOTAL R$:",
                                                   "valor": residual, "regra_id": regra_arred.id, "taxa_pct": None}])],
                           ignore_index=True)
    nf = notas[notas["linha_negocio"] == "REMESSA"]
    nf_txt = f"a nota {nf['id_saida'].iloc[0]} ({brl(nf['valor_brl'].iloc[0])})" if len(nf) else "a comissão calculada"
    motivo = (f"Diferença entre {nf_txt} e {_pct([participacao * 100])} do spread total declarado pelo parceiro "
              f"({brl(p['spread_total_declarado'])} -> {brl(p['repasse_pelo_total_declarado'])}): {brl(diferenca)} = "
              f"{brl(p['efeito_excluidas'])} de {p['qtd_excluidas']} operações com spread negativo excluídas "
              f"+ {brl(p['efeito_duplicatas'])} de {p['qtd_duplicatas']} repetição(ões) + "
              f"{brl(p['efeito_arredondamento'])} de arredondamento por operação. {regra.o_que_fazer}")
    c.add("REPASSE_PONTE_DIVERGENTE", "SPREAD TOTAL R$:", diferenca, motivo, regra, rastro, linha_negocio="REMESSA",
          qtd_itens=len(rastro))


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
