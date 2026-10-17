"""Comissão de REMESSA (relatório mensal da Ponte Câmbio).

Comissão = participação da Tarvo (parâmetro) x Spread R$ realizado, por operação,
arredondada e somada por lojista (CNPJ do cliente). Cada linha do relatório recebe
exatamente um destino:

  COMISSAO             entra na comissão do lojista
  DUPLICATA_IGNORADA   repetição idêntica de uma operação já contada (regra IGNORAR_DUPLICADO)
  DUPLICATA_DIVERGENTE repetição com valores diferentes: nenhuma das linhas entra
  EXCLUIDO             regra EXCLUIR_E_PENDENCIA (ex.: spread negativo)
  SEM_CADASTRO         CNPJ que não está na planilha de taxas nem no complemento, quando o
                       parâmetro remessa_cnpj_sem_cadastro=EXCLUIR; com COMISSAO (padrão do
                       financeiro) a operação entra na comissão e na nota, sem spread contratado,
                       e vira pendência CADASTRO/CNPJ_PONTE
  FORA_COMPETENCIA     data de contratação fora do mês que está sendo fechado
  AJUSTE_PONTE         ajuste de mês anterior (regra AJUSTE_PARCEIRO: observação "AJUSTE REF <operação original>"
                       ou, como segurança, um trecho marcado): linha própria, Spread R$ com sinal (débito negativo).
                       Entra na comissão do mês pela participação sobre o Spread R$, dentro da nota única do
                       parceiro, e vira pendência informativa CONFERIR_AJUSTE_PONTE ligada à operação original.
                       Vem antes da exclusão por spread negativo pela `prioridade` das regras de destino
  NAO_INTERPRETADA     linha sem os números mínimos (valor, PTAX, spread): fora de tudo, pendência
                       LINHA_NAO_INTERPRETADA, nunca erro fatal

Spread contratado: coluna "Spread remessa" da planilha; vazio ou "padrão" usa o
parâmetro spread_padrao. Divergência quando |Spread % aplicado - contratado| passa
da tolerância: valor cheio = (aplicado - contratado) x PTAX x Valor ME.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

import re

from .dinheiro import arredondar, soma
from .leitores.comum import normalizar
from .regras import Config

LINHA_NEGOCIO = "REMESSA"
PREFIXO_ID = "COM-REM-"
PRODUTO_SPREAD = "SPREAD REMESSA"
DESTINOS_COMISSAO = {"COMISSAO", "AJUSTE_PONTE"}       # destinos que entram na comissão e na nota de remessa
_NUMERICAS_MINIMAS = ("valor_me", "taxa_cliente", "ptax", "valor_brl", "spread_brl", "spread_frac")
# colunas que precisam ser iguais para duas linhas com o mesmo Nº Operação serem a mesma operação
COLUNAS_DUPLICATA = ["cnpj", "data_contratacao", "moeda", "valor_me", "taxa_cliente", "ptax", "valor_brl",
                     "spread_brl", "spread_frac", "iof_brl"]
COLUNAS_LINHAS = [
    "ref_origem", "arquivo_origem", "num_operacao", "linha_planilha", "data_contratacao", "data_liquidacao",
    "cnpj", "cliente_ponte", "lojista", "status_cadastro", "moeda", "valor_me", "taxa_cliente", "ptax",
    "valor_brl", "spread_brl", "spread_pct", "spread_estimado_brl", "status_compliance", "observacao",
    "spread_contratado_pct", "spread_contratado_origem", "regra_id", "participacao",
    "comissao_realizado_brl", "diferenca_pp", "diferenca_brl", "excesso_tarvo_brl", "comissao_brl",
    # o spread que o contrato previa para a operação (contratado % x PTAX x Valor ME), a diferença do relatório para
    # ele e a metade da Tarvo sobre o contratado: é o que se pede ao parceiro quando a trava não foi honrada
    "spread_contratado_brl", "diferenca_contrato_brl", "metade_tarvo_contrato_brl",
    "destino", "destino_regra", "tipo_pendencia", "subtipo", "motivo", "operacao_original",
]


@dataclass
class ResultadoRemessa:
    linhas: pd.DataFrame     # uma linha por linha do relatório da Ponte, com destino
    comissoes: pd.DataFrame  # uma linha por lojista com destino COMISSAO
    rastro: pd.DataFrame     # id_saida -> operações que compõem a comissão


class TabelaSpread:
    """Spread contratado por (CNPJ, data) a partir da planilha em formato longo."""

    def __init__(self, taxas: pd.DataFrame):
        self._por_cnpj: dict = {}
        for r in taxas[taxas["produto"] == PRODUTO_SPREAD].itertuples(index=False):
            self._por_cnpj.setdefault(r.cnpj, []).append(r)

    def contratado(self, cnpj: str, data) -> tuple[Decimal | None, str, str]:
        """-> (spread em %, referência da célula, situação: OK | PADRAO | SEM_LINHA | AMBIGUA)."""
        d = pd.Timestamp(data)
        candidatas = [r for r in self._por_cnpj.get(cnpj, [])
                      if not (pd.notna(r.vigencia_de) and d < r.vigencia_de)
                      and not (pd.notna(r.vigencia_ate) and d > r.vigencia_ate)]
        if not candidatas:
            return None, "", "SEM_LINHA"
        if len(candidatas) > 1:
            return None, ", ".join(c.ref_origem for c in candidatas), "AMBIGUA"
        r = candidatas[0]
        if r.taxa_situacao == "VALOR":
            return r.taxa_pct, r.ref_origem, "OK"
        return None, r.ref_origem, "PADRAO"   # célula em branco ou "padrão"


def calcular(ponte: pd.DataFrame, taxas: pd.DataFrame, config: Config, competencia: str,
             contestacao_anterior: dict | None = None) -> ResultadoRemessa:
    """`contestacao_anterior`: {num_operacao: {...}} da ponte_contestacao.csv do fechamento anterior (--anterior):
    quando a observação de um ajuste cita essa operação, a pendência aponta para o pedido da contestação."""
    tabela = TabelaSpread(taxas)
    duplicatas = _mapear_duplicatas(ponte)
    registros = [_destino_da_linha(r, idx, duplicatas, tabela, config, competencia, contestacao_anterior or {})
                 for idx, r in zip(ponte.index, ponte.itertuples(index=False))]
    linhas = pd.DataFrame(registros, columns=COLUNAS_LINHAS)
    comissoes, rastro = _agrupar_por_lojista(linhas, config)
    return ResultadoRemessa(linhas, comissoes, rastro)


def _mapear_duplicatas(ponte: pd.DataFrame) -> dict:
    """num_operacao repetido -> ("IGUAIS", índice da linha que fica) ou ("DIFERENTES", None)."""
    out = {}
    for num, g in ponte.groupby("num_operacao", sort=False):
        if len(g) < 2:
            continue
        iguais = (g[COLUNAS_DUPLICATA].nunique() == 1).all()   # Decimal compara por valor (821.88 == 821.880)
        out[num] = ("IGUAIS", g.index[0]) if iguais else ("DIFERENTES", None)
    return out


def _casa_ajuste(regra, r) -> tuple[bool, str | None]:
    """A linha casa com a regra AJUSTE_PARCEIRO? -> (casou, Nº da operação original citada na observação, se houver)."""
    obs = normalizar(r.observacao or "")
    if not obs:
        return False, None
    alts = regra.params["contem_alternativas"]
    if regra.params["criterio"] == "observacao_ref":
        for alt in alts:
            m = re.search(re.escape(alt) + r"[\s:.-]*([A-Z0-9][A-Z0-9/.-]*\d[A-Z0-9/.-]*)", obs)
            if m:
                return True, m.group(1).rstrip(".,;:")
        return False, None
    return any(alt in obs for alt in alts), None


def _destino_da_linha(r, idx, duplicatas: dict, tabela: TabelaSpread, config: Config, competencia: str,
                      contestacao_anterior: dict | None = None) -> dict:
    data = r.data_contratacao.date()
    out = dict.fromkeys(COLUNAS_LINHAS)
    out.update(
        ref_origem=r.ref_origem, arquivo_origem=r.arquivo_origem, num_operacao=r.num_operacao,
        linha_planilha=r.linha_planilha, data_contratacao=r.data_contratacao, data_liquidacao=r.data_liquidacao,
        cnpj=r.cnpj, cliente_ponte=r.cliente, moeda=r.moeda, valor_me=r.valor_me, taxa_cliente=r.taxa_cliente,
        ptax=r.ptax, valor_brl=r.valor_brl, spread_brl=r.spread_brl, spread_pct=r.spread_pct,
        spread_estimado_brl=r.spread_estimado_brl, status_compliance=r.status_compliance, observacao=r.observacao,
    )

    faltam = [c for c in _NUMERICAS_MINIMAS if getattr(r, c) is None]
    if faltam or not r.num_operacao:
        return {**out, "destino": "NAO_INTERPRETADA", "tipo_pendencia": "LINHA_NAO_INTERPRETADA",
                "motivo": f"linha {r.linha_planilha} do relatório sem {', '.join(faltam) or 'Nº Operação'}: não dá para "
                          f"calcular a participação; nada entrou na comissão por ela"}


    if r.num_operacao in duplicatas:
        tipo_dup, fica = duplicatas[r.num_operacao]
        regra = config.regra_duplicado("ponte", data)
        if tipo_dup == "DIFERENTES" or regra is None:
            return {**out, "destino": "DUPLICATA_DIVERGENTE", "tipo_pendencia": "DUPLICATA_DIVERGENTE",
                    "motivo": (f"Nº Operação {r.num_operacao} aparece mais de uma vez com valores diferentes"
                               if tipo_dup == "DIFERENTES" else
                               f"Nº Operação {r.num_operacao} repetido e não há regra IGNORAR_DUPLICADO ativa")}
        if idx != fica:
            return {**out, "destino": "DUPLICATA_IGNORADA", "destino_regra": regra.id,
                    "motivo": f"repetição idêntica da operação {r.num_operacao} (linha {r.linha_planilha} do "
                              f"relatório); contada uma vez"}

    lojista = config.lojista_por_cnpj(r.cnpj)
    sem_cadastro = f"CNPJ {r.cnpj} ({r.cliente}) não está na planilha de taxas nem no complemento"
    if lojista is None:
        if config.parametro("remessa_cnpj_sem_cadastro", data) == "EXCLUIR":
            return {**out, "destino": "SEM_CADASTRO", "tipo_pendencia": "CADASTRO", "subtipo": "CNPJ_PONTE",
                    "motivo": sem_cadastro}
        # entra na comissão (o parceiro paga a participação sobre o spread realizado) e vira pendência de cadastro
        out.update(lojista=r.cliente, status_cadastro=None, tipo_pendencia="CADASTRO", subtipo="CNPJ_PONTE",
                   motivo=sem_cadastro)
    else:
        out.update(lojista=lojista.nome or r.cliente, status_cadastro=lojista.status)

    modo = config.parametro("arredondamento", data)
    regra_part = config.regra_parametro("participacao_spread", data)
    participacao = regra_part.valor

    # spread contratado da operação (também para as linhas excluídas: é o que se pede ao parceiro)
    excecao = config.excecao_taxa(r.cnpj, LINHA_NEGOCIO, PRODUTO_SPREAD, data)
    if lojista is None:
        contratado, origem = None, "sem cadastro (CNPJ fora da planilha e do complemento): sem spread contratado"
    elif excecao is not None:
        contratado, origem = excecao.params["taxa_pct"], excecao.id
    else:
        contratado, ref, situacao = tabela.contratado(r.cnpj, data)
        if situacao == "OK":
            origem = f"planilha:{ref}"
        elif situacao == "AMBIGUA":
            contratado, origem = None, f"ambígua na planilha ({ref})"
        else:
            regra_padrao = config.regra_parametro("spread_padrao", data)
            contratado = regra_padrao.valor * 100
            origem = f"{regra_padrao.id} (padrão" + (f", célula {ref} em branco/padrão)" if ref else ", sem linha na planilha)")
    out.update(spread_contratado_pct=contratado, spread_contratado_origem=origem)
    if contratado is not None:
        contratado_brl = arredondar(contratado / 100 * r.ptax * r.valor_me, modo)
        out.update(spread_contratado_brl=contratado_brl, diferenca_contrato_brl=r.spread_brl - contratado_brl,
                   metade_tarvo_contrato_brl=arredondar(contratado_brl * participacao, modo))

    # regras de destino em ordem de prioridade (menor vence). Os ajustes do parceiro (AJUSTE_PARCEIRO) são avaliados
    # antes do portão de competência, porque o ajuste entra no mês em que aparece qualquer que seja a data da linha;
    # as exclusões (EXCLUIR_E_PENDENCIA) só valem para linhas da competência.
    regras_destino = config.regras_destino("ponte", data)
    for regra in regras_destino:
        if regra.tipo == "AJUSTE_PARCEIRO":
            casou, original = _casa_ajuste(regra, r)
            if not casou:
                continue
            comissao = arredondar(r.spread_brl * participacao, modo)
            sinal = "crédito" if r.spread_brl >= 0 else "débito"
            ant = (contestacao_anterior or {}).get(original) if original else None
            return {**out, "lojista": (lojista.nome if lojista is not None and lojista.nome else r.cliente),
                    "status_cadastro": lojista.status if lojista is not None else None,
                    "spread_contratado_origem": "ajuste do parceiro: sem conferência de spread contratado",
                    "spread_contratado_pct": None, "spread_contratado_brl": None, "diferenca_contrato_brl": None,
                    "metade_tarvo_contrato_brl": None,
                    "regra_id": regra_part.id + (f" (ajuste ref {original})" if original else ""),
                    "participacao": participacao, "comissao_realizado_brl": comissao, "comissao_brl": comissao,
                    "destino": "AJUSTE_PONTE", "destino_regra": regra.id, "tipo_pendencia": regra.tipo_pendencia,
                    "subtipo": regra.subtipo or ("CREDITO" if r.spread_brl >= 0 else "DEBITO"),
                    "operacao_original": original,
                    "motivo": f"{sinal} de ajuste do parceiro de câmbio pela regra {regra.id} ({regra.situacao})"
                              + (f", referente à operação {original}" if original else "")
                              + (f", pedido {ant['pedido']} ({ant.get('natureza') or ''}) da contestação do fechamento anterior"
                                 if ant and ant.get("pedido") else "")}

    if r.data_contratacao.strftime("%Y-%m") != competencia:
        return {**out, "destino": "FORA_COMPETENCIA", "tipo_pendencia": "FORA_COMPETENCIA",
                "motivo": f"data de contratação {data} fora da competência {competencia}"}

    for regra in regras_destino:
        if regra.tipo != "EXCLUIR_E_PENDENCIA":
            continue
        crit = regra.params["criterio"]
        bate = ((crit == "spread_negativo" and r.spread_brl < 0)
                or (crit == "status_compliance_fora" and r.status_compliance not in regra.params["aceitos"])
                or (crit == "status_cadastro" and lojista is not None and lojista.status in regra.params["status"]))
        if bate:
            return {**out, "destino": "EXCLUIDO", "destino_regra": regra.id, "tipo_pendencia": regra.tipo_pendencia,
                    "subtipo": regra.subtipo, "motivo": regra.situacao}

    comissao_realizado = arredondar(r.spread_brl * participacao, modo)
    diferenca_pp = diferenca_brl = excesso_tarvo = None
    if contratado is not None:
        diferenca_pp = r.spread_pct - contratado
        if abs(diferenca_pp) > config.parametro("tolerancia_spread_pp", data):
            diferenca_brl = arredondar((r.spread_frac - contratado / 100) * r.ptax * r.valor_me, modo)
            if diferenca_brl > 0:
                excesso_tarvo = arredondar(diferenca_brl * participacao, modo)

    comissao = comissao_realizado
    if excesso_tarvo is not None and not config.parametro("incluir_excesso_contestado", data):
        comissao = comissao_realizado - excesso_tarvo

    return {**out, "regra_id": regra_part.id, "participacao": participacao,
            "comissao_realizado_brl": comissao_realizado, "diferenca_pp": diferenca_pp,
            "diferenca_brl": diferenca_brl, "excesso_tarvo_brl": excesso_tarvo, "comissao_brl": comissao,
            "destino": "COMISSAO"}


def _agrupar_por_lojista(linhas: pd.DataFrame, config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    com = linhas[linhas["destino"].isin(DESTINOS_COMISSAO)]
    colunas_com = ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl", "qtd_operacoes", "volume_brl",
                   "spread_realizado_brl", "excesso_contestado_brl", "excesso_tarvo_brl"]
    colunas_rastro = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]
    if com.empty:
        return pd.DataFrame(columns=colunas_com), pd.DataFrame(columns=colunas_rastro)

    grupos = []
    for cnpj, g in com.groupby("cnpj", sort=False):
        grupos.append({
            "cnpj": cnpj, "lojista": g["lojista"].iloc[0], "linha_negocio": LINHA_NEGOCIO,
            "comissao_brl": soma(g["comissao_brl"]), "qtd_operacoes": len(g), "volume_brl": soma(g["valor_brl"]),
            "spread_realizado_brl": soma(g["spread_brl"]),
            "excesso_contestado_brl": soma(v for v in g["diferenca_brl"] if v is not None and v > 0),
            "excesso_tarvo_brl": soma(g["excesso_tarvo_brl"]),
        })
    # ordem por CNPJ: o id_saida não muda se um lojista for renomeado na planilha
    comissoes = pd.DataFrame(grupos).sort_values("cnpj").reset_index(drop=True)
    comissoes.insert(0, "id_saida", [f"{PREFIXO_ID}{i:04d}" for i in range(1, len(comissoes) + 1)])
    comissoes = comissoes[colunas_com]

    ids = dict(zip(comissoes["cnpj"], comissoes["id_saida"]))
    rastro = pd.DataFrame({
        "id_saida": com["cnpj"].map(ids), "arquivo_origem": com["arquivo_origem"], "ref_origem": com["ref_origem"],
        "valor": com["comissao_brl"], "regra_id": com["regra_id"],
        "taxa_pct": com["participacao"].map(lambda p: p * 100),
    }).sort_values("id_saida", kind="stable").reset_index(drop=True)
    return comissoes, rastro[colunas_rastro]
