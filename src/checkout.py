"""Comissão de CHECKOUT (relatório da Orbe).

Comissão = valor_bruto x taxa CONTRATADA vigente na data da venda (estorno e
reversão usam a data da venda original), arredondada por linha e depois somada por
lojista. Cada linha da Orbe recebe exatamente um destino:

  COMISSAO          entra na comissão do lojista
  EXCLUIDO          regra EXCLUIR_E_PENDENCIA (ex.: lojista SEM_CONTRATO)
  SEM_CADASTRO      EC que não está na planilha de taxas nem no complemento
  SEM_TAXA          lojista sem taxa contratada para o produto, parcelas ou data
  FORA_COMPETENCIA  data de movimento fora do mês que está sendo fechado
  DADO_INSUFICIENTE estorno ou reversão sem data da venda original e cuja venda (id_referencia) não está
                    no arquivo: sem a data não há taxa contratada; fica fora da comissão, com pendência

Estorno e reversão usam a data da venda original (coluna do arquivo; sem ela, a data da venda
achada pelo id_referencia no próprio arquivo). Antecipação usa a data do movimento.
Nenhum nome de lojista, taxa, conta ou mês aqui: tudo vem dos dados e de regras/.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from .dinheiro import arredondar, pct, soma
from .regras import Config

LINHA_NEGOCIO = "CHECKOUT"
PREFIXO_ID = "COM-CHK-"
PRODUTO_ANTECIPACAO = "ANTECIPACAO"
PRODUTO_PARCELADO = "CREDITO PARCELADO"
TIPOS_ANTECIPACAO = {"ANTECIPACAO", "REVERSAO ANTECIPACAO"}
TIPOS_COM_ORIGINAL = {"ESTORNO", "REVERSAO ANTECIPACAO"}   # a taxa é a da venda/antecipação original (id_referencia)
SUBTIPO_FORA_FAIXA = "PARCELAS_FORA_FAIXA"   # parcelado com quantidade que nenhuma faixa da planilha cobre

COLUNAS_LINHAS = [
    "ref_origem", "arquivo_origem", "id_transacao", "data_movimento", "data_taxa", "cod_estabelecimento",
    "nome_orbe", "cnpj", "lojista", "status_cadastro", "tipo_lancamento", "produto", "qtd_parcelas",
    "id_referencia", "valor_bruto", "taxa_aplicada_pct", "valor_taxa_orbe", "taxa_contratada_pct",
    "regra_id", "comissao_brl", "destino", "destino_regra", "tipo_pendencia", "subtipo", "motivo",
    "data_venda_original", "competencia_origem",
]


@dataclass
class ResultadoCheckout:
    linhas: pd.DataFrame     # uma linha por transação da Orbe, com destino
    comissoes: pd.DataFrame  # uma linha por lojista com destino COMISSAO
    rastro: pd.DataFrame     # id_saida -> linhas da Orbe que compõem a comissão


class TabelaTaxas:
    """Taxa contratada por (CNPJ, produto, parcelas, data) a partir da planilha em formato longo."""

    def __init__(self, taxas: pd.DataFrame):
        self._grupos: dict = {}
        for r in taxas.itertuples(index=False):
            self._grupos.setdefault((r.cnpj, r.produto), []).append(r)

    def faixa_cobre(self, cnpj: str, parcelas: int) -> bool | None:
        """Alguma faixa de parcelado da planilha do lojista cobre essa quantidade? None se o lojista não tem faixas
        (aí não há como dizer qual é o máximo contratado)."""
        faixas = [(r.parcelas_de, r.parcelas_ate) for r in self._grupos.get((cnpj, PRODUTO_PARCELADO), [])
                  if pd.notna(r.parcelas_de) and pd.notna(r.parcelas_ate)]
        if not faixas:
            return None
        return any(de <= parcelas <= ate for de, ate in faixas)

    def contratada(self, cnpj: str, produto: str, parcelas: int | None, data) -> tuple[Decimal | None, str, str]:
        """-> (taxa em %, referência da célula, situação: OK | SEM_LINHA | SEM_PARCELAS | AMBIGUA | VAZIA)."""
        d = pd.Timestamp(data)
        if produto == PRODUTO_PARCELADO and parcelas is None:
            return None, "", "SEM_PARCELAS"
        candidatas, fora_da_faixa = [], False
        for r in self._grupos.get((cnpj, produto), []):
            if produto == PRODUTO_PARCELADO and not (
                    pd.notna(r.parcelas_de) and r.parcelas_de <= parcelas <= r.parcelas_ate):
                fora_da_faixa = True
                continue
            if pd.notna(r.vigencia_de) and d < r.vigencia_de:
                continue
            if pd.notna(r.vigencia_ate) and d > r.vigencia_ate:
                continue
            candidatas.append(r)
        if not candidatas:
            return None, "", ("FORA_FAIXA" if fora_da_faixa else "SEM_LINHA")
        if len(candidatas) > 1:
            return None, ", ".join(c.ref_origem for c in candidatas), "AMBIGUA"
        r = candidatas[0]
        if r.taxa_situacao != "VALOR":
            return None, r.ref_origem, "VAZIA"
        return r.taxa_pct, r.ref_origem, "OK"


def calcular(orbe: pd.DataFrame, taxas: pd.DataFrame, config: Config, competencia: str,
             carteira: pd.DataFrame | None = None) -> ResultadoCheckout:
    """`carteira`: linhas de meses anteriores (carteira_pendente.csv) que passam de novo pelo cálculo; a competência
    delas não é conferida (vieram de outro mês) e cada uma guarda competencia_origem."""
    tabela = TabelaTaxas(taxas)
    # data de movimento de cada transação do arquivo: estorno/reversão sem data da venda original procura a venda aqui
    datas = dict(zip(orbe["id_transacao"], orbe["data_movimento"]))
    registros = [_destino_da_linha(r, tabela, config, competencia, datas) for r in orbe.itertuples(index=False)]
    if carteira is not None and len(carteira):
        registros += [{**_destino_da_linha(r, tabela, config, None, datas), "competencia_origem": r.competencia_origem}
                      for r in carteira.itertuples(index=False)]
    linhas = pd.DataFrame(registros, columns=COLUNAS_LINHAS)
    comissoes, rastro = _agrupar_por_lojista(linhas)
    return ResultadoCheckout(linhas, comissoes, rastro)


def _destino_da_linha(r, tabela: TabelaTaxas, config: Config, competencia: str | None,
                      datas: dict | None = None) -> dict:
    data_mov = r.data_movimento.date()
    sem_original = None   # id da venda original que faltou (estorno/reversão sem data e sem a venda no arquivo)
    if pd.notna(r.data_venda_original):
        data_taxa = r.data_venda_original.date()
    elif r.tipo_lancamento in TIPOS_COM_ORIGINAL:
        original = (datas or {}).get(r.id_referencia) if r.id_referencia else None
        if original is not None and pd.notna(original):
            data_taxa = original.date()          # a venda está no arquivo: taxa pela data dela
        else:
            data_taxa, sem_original = data_mov, r.id_referencia or "(sem id_referencia)"
    else:
        data_taxa = data_mov                     # venda e antecipação: data do movimento
    parcelas = int(r.qtd_parcelas) if pd.notna(r.qtd_parcelas) else None
    produto = PRODUTO_ANTECIPACAO if r.tipo_lancamento in TIPOS_ANTECIPACAO else r.modalidade
    out = dict.fromkeys(COLUNAS_LINHAS)
    out.update(
        ref_origem=r.ref_origem, arquivo_origem=r.arquivo_origem, id_transacao=r.id_transacao,
        data_movimento=r.data_movimento, data_taxa=pd.Timestamp(data_taxa),
        cod_estabelecimento=r.cod_estabelecimento, nome_orbe=r.nome_estabelecimento,
        tipo_lancamento=r.tipo_lancamento, produto=produto, qtd_parcelas=parcelas,
        id_referencia=r.id_referencia, valor_bruto=r.valor_bruto, taxa_aplicada_pct=r.taxa_aplicada_pct,
        valor_taxa_orbe=r.valor_taxa, data_venda_original=r.data_venda_original,
    )

    if competencia is not None and r.data_movimento.strftime("%Y-%m") != competencia:
        return {**out, "destino": "FORA_COMPETENCIA", "tipo_pendencia": "FORA_COMPETENCIA",
                "motivo": f"data de movimento {data_mov} fora da competência {competencia}"}

    lojista = config.lojista_por_ec(r.cod_estabelecimento)
    if lojista is None:
        return {**out, "destino": "SEM_CADASTRO", "tipo_pendencia": "CADASTRO", "subtipo": "EC_ORBE",
                "motivo": f"EC {r.cod_estabelecimento} ({r.nome_estabelecimento}) não está na planilha "
                          "de taxas nem no complemento"}
    out.update(cnpj=lojista.cnpj, lojista=lojista.nome or r.nome_estabelecimento,
               status_cadastro=lojista.status)

    if sem_original is not None:
        return {**out, "destino": "DADO_INSUFICIENTE", "tipo_pendencia": "DADO_INSUFICIENTE",
                "motivo": f"{r.tipo_lancamento} sem data da venda original e a transação de origem {sem_original} "
                          f"não está no arquivo: sem a data da venda não há como saber a taxa contratada"}

    # uma TAXA_EXCECAO vigente para o lojista é a confirmação da taxa: destrava a exclusão por status do cadastro
    excecao = config.excecao_taxa(lojista.cnpj, LINHA_NEGOCIO, produto, data_taxa) if produto else None
    if excecao is None:
        for regra in config.regras_exclusao("orbe", data_mov):
            if regra.params["criterio"] == "status_cadastro" and lojista.status in regra.params["status"]:
                return {**out, "destino": "EXCLUIDO", "destino_regra": regra.id,
                        "tipo_pendencia": regra.tipo_pendencia, "subtipo": regra.subtipo, "motivo": regra.situacao}

    if not produto:
        return {**out, "destino": "SEM_TAXA", "tipo_pendencia": "CADASTRO", "subtipo": "TAXA_NAO_CADASTRADA",
                "motivo": f"linha {r.tipo_lancamento} sem modalidade: não dá para escolher a taxa"}

    # parcelado fora de toda faixa da planilha (ex.: acima do máximo vendido): fica fora da comissão e vira pendência,
    # mesmo com TAXA_EXCECAO vigente, porque nenhuma taxa foi contratada para essa quantidade de parcelas
    if produto == PRODUTO_PARCELADO and parcelas is not None and tabela.faixa_cobre(lojista.cnpj, parcelas) is False:
        return {**out, "destino": "SEM_TAXA", "tipo_pendencia": "CADASTRO", "subtipo": SUBTIPO_FORA_FAIXA,
                "motivo": _motivo_sem_taxa("FORA_FAIXA", produto, parcelas, data_taxa, "")}
    if excecao is not None:
        taxa, regra_id = excecao.params["taxa_pct"], excecao.id
    else:
        taxa, ref, situacao = tabela.contratada(lojista.cnpj, produto, parcelas, data_taxa)
        if taxa is None:
            return {**out, "destino": "SEM_TAXA", "tipo_pendencia": "CADASTRO",
                    "subtipo": SUBTIPO_FORA_FAIXA if situacao == "FORA_FAIXA" else "TAXA_NAO_CADASTRADA",
                    "regra_id": f"planilha:{ref}" if ref else None,
                    "motivo": _motivo_sem_taxa(situacao, produto, parcelas, data_taxa, ref)}
        regra_id = f"planilha:{ref}"

    comissao = arredondar(pct(taxa, r.valor_bruto), config.parametro("arredondamento", data_mov))
    return {**out, "taxa_contratada_pct": taxa, "regra_id": regra_id, "comissao_brl": comissao,
            "destino": "COMISSAO"}


def _motivo_sem_taxa(situacao: str, produto: str, parcelas, data, ref: str) -> str:
    alvo = f"{produto}{f' {parcelas}x' if parcelas else ''} em {data}"
    return {
        "SEM_LINHA": f"nenhuma taxa contratada vigente para {alvo} na planilha de taxas",
        "FORA_FAIXA": f"quantidade de parcelas fora das faixas da planilha de taxas ({alvo}): nenhuma taxa contratada para "
                      f"essa quantidade",
        "SEM_PARCELAS": f"linha parcelada sem quantidade de parcelas ({alvo})",
        "AMBIGUA": f"mais de uma taxa vigente para {alvo} na planilha ({ref})",
        "VAZIA": f"célula de taxa em branco para {alvo} na planilha ({ref})",
    }[situacao]


def _agrupar_por_lojista(linhas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    com = linhas[linhas["destino"] == "COMISSAO"]
    colunas_com = ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl", "ec_orbe",
                   "qtd_transacoes", "valor_bruto_total", "taxa_cobrada_orbe_brl"]
    colunas_rastro = ["id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"]
    if com.empty:
        return pd.DataFrame(columns=colunas_com), pd.DataFrame(columns=colunas_rastro)

    grupos = []
    for cnpj, g in com.groupby("cnpj", sort=False):
        grupos.append({
            "cnpj": cnpj, "lojista": g["lojista"].iloc[0], "linha_negocio": LINHA_NEGOCIO,
            "comissao_brl": soma(g["comissao_brl"]), "ec_orbe": g["cod_estabelecimento"].iloc[0],
            "qtd_transacoes": len(g), "valor_bruto_total": soma(g["valor_bruto"]),
            "taxa_cobrada_orbe_brl": soma(g["valor_taxa_orbe"]),
        })
    # ordem por CNPJ: o id_saida não muda se um lojista for renomeado na planilha
    comissoes = pd.DataFrame(grupos).sort_values("cnpj").reset_index(drop=True)
    comissoes.insert(0, "id_saida", [f"{PREFIXO_ID}{i:04d}" for i in range(1, len(comissoes) + 1)])
    comissoes = comissoes[colunas_com]

    ids = dict(zip(comissoes["cnpj"], comissoes["id_saida"]))
    rastro = pd.DataFrame({
        "id_saida": com["cnpj"].map(ids), "arquivo_origem": com["arquivo_origem"],
        "ref_origem": com["ref_origem"], "valor": com["comissao_brl"], "regra_id": com["regra_id"],
        "taxa_pct": com["taxa_contratada_pct"],
    }).sort_values("id_saida", kind="stable").reset_index(drop=True)
    return comissoes, rastro[colunas_rastro]
