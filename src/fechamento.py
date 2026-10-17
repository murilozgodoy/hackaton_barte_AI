"""Orquestra o fechamento: cálculo, pendências, checagens de integridade (1 a 6) e gravação de saida/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import carteira as carteira_mod
from . import checkout, comunicacoes, conciliacao, divergencias, extratos, notas, pendencias, relatorio, remessa
from .notas import primeiro_dia  # noqa: F401  (usado em executar)
from .saida import escrever_csv
from .validacao import (Checagem, checar_destinos, checar_lancamentos, checar_notas, checar_rastro,
                        checar_saldo_extratos)


@dataclass
class Fechamento:
    competencia: str
    orbe_linhas: pd.DataFrame
    ponte_linhas: pd.DataFrame
    comissoes: pd.DataFrame          # CHECKOUT + REMESSA, formato de saída
    divergencias: pd.DataFrame           # divergencias_taxa.csv: todas as naturezas (coluna natureza)
    notas: pd.DataFrame
    sem_nota: pd.DataFrame           # comissões de checkout com saldo <= 0
    lancamentos: pd.DataFrame
    em_transito: pd.DataFrame
    pendencias: pd.DataFrame
    rastro: pd.DataFrame
    conciliacao: dict
    carteira: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=carteira_mod.COLUNAS))
    carteira_anterior: int = 0           # linhas lidas de --anterior
    taxas: pd.DataFrame | None = None    # planilha de taxas (vigências, para os avisos)
    meta_ponte: dict = field(default_factory=dict)   # remetente, data do e-mail, data de repasse, prazo
    checagens: list[Checagem] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    # transações com diferença de taxa que a regra TAXA_EXCECAO manda só para a pendência (destino=PENDENCIA):
    # fora de divergencias_taxa.csv e de qualquer cobrança; o detalhe por transação está no rastro da pendência
    so_pendencia: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=divergencias.COLUNAS_SO_PENDENCIA))

    @property
    def integro(self) -> bool:
        return all(c.ok for c in self.checagens if c.nivel == "ERRO")

    @property
    def divergencias_contrato(self) -> pd.DataFrame:
        """Natureza CONTRATO: o que se cobra da contraparte."""
        return divergencias.contrato(self.divergencias)

    @property
    def divergencias_fora_contrato(self) -> pd.DataFrame:
        """Outras naturezas (ex.: DEVOLUCAO_LOJISTA, regra TAXA_EXCECAO): marcadas no CSV, fora da cobrança."""
        return divergencias.fora_contrato(self.divergencias)

    @property
    def comissoes_checkout(self) -> pd.DataFrame:
        return self.comissoes[self.comissoes["linha_negocio"] == "CHECKOUT"]

    @property
    def comissoes_remessa(self) -> pd.DataFrame:
        return self.comissoes[self.comissoes["linha_negocio"] == "REMESSA"]

    @property
    def destinos_orbe(self) -> dict[str, int]:
        return self.orbe_linhas["destino"].value_counts().to_dict()

    @property
    def destinos_ponte(self) -> dict[str, int]:
        return self.ponte_linhas["destino"].value_counts().to_dict()


def extratos_de(dados: dict[str, pd.DataFrame]) -> list[pd.DataFrame]:
    """Os DataFrames de extrato bancário (os que têm coluna `banco`), na ordem de regras/fontes.csv."""
    return [df for df in dados.values() if "banco" in df.columns]


def executar(dados: dict[str, pd.DataFrame], config, competencia: str, usar_ia: bool = True,
             carteira: pd.DataFrame | None = None, contestacao_anterior: dict | None = None) -> Fechamento:
    """`carteira` e `contestacao_anterior` vêm da saída do mês anterior (--anterior): linhas de checkout guardadas e a
    lista de operações contestadas com o parceiro de câmbio (para reconhecer os ajustes dele neste mês)."""
    ref = primeiro_dia(competencia)
    n_cart = int(len(carteira)) if carteira is not None else 0
    chk = checkout.calcular(dados["orbe"], dados["taxas"], config, competencia, carteira=carteira)
    cart = carteira_mod.montar(chk.linhas, competencia)
    rem = remessa.calcular(dados["ponte"], dados["taxas"], config, competencia, contestacao_anterior=contestacao_anterior)
    dv = divergencias.calcular(chk.linhas, rem.linhas, config)
    div, rastro_div = dv.divergencias, dv.rastro
    nf, rastro_nf, sem_nota = notas.calcular(chk.comissoes, rem.comissoes, chk.rastro, rem.rastro, config, competencia)
    bancos = extratos_de(dados)
    ext = extratos.classificar(bancos, config, dados["plano_contas"], usar_ia=usar_ia)
    conc = conciliacao.calcular(dados, rem.linhas, rem.comissoes, ext.lancamentos,
                                config.parametro("participacao_spread", ref), config.parametro("arredondamento", ref))
    pend = pendencias.calcular(ref, chk.linhas, rem.linhas, div, sem_nota, chk.rastro, ext.lancamentos,
                               ext.em_transito, conc, nf, config, taxas=dados["taxas"], contestacao_anterior=contestacao_anterior,
                               rem_rastro=rem.rastro, so_pendencia=dv.so_pendencia)

    colunas_com = ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl"]
    comissoes = pd.concat([chk.comissoes, rem.comissoes], ignore_index=True)
    comissoes = comissoes[colunas_com + [c for c in comissoes.columns if c not in colunas_com]]
    for col in ("qtd_transacoes", "qtd_operacoes"):   # o concat promove inteiros a float por causa dos vazios
        comissoes[col] = comissoes[col].astype("Int64")
    rastro = pd.concat([chk.rastro, rem.rastro, rastro_div, rastro_nf, ext.rastro, pend.rastro], ignore_index=True)

    refs_com = set(chk.linhas.loc[chk.linhas["destino"] == "COMISSAO", "ref_origem"])
    refs_rastro = set(rastro.loc[rastro["id_saida"].str.startswith(checkout.PREFIXO_ID), "ref_origem"])
    checagens = [Checagem("integridade", "4. transações em comissão de checkout = transações no rastro COM-CHK",
                          refs_com == refs_rastro, f"{len(refs_com)} transações" if refs_com == refs_rastro else
                          f"diferem em {len(refs_com ^ refs_rastro)} transações")]
    checagens += checar_rastro({
        "comissoes_por_lojista.csv": (comissoes, "comissao_brl"),
        "divergencias_taxa.csv": (div, "diferenca_brl"),
        "notas_a_emitir.csv": (nf, "valor_brl"),
        "lancamentos_classificados.csv": (ext.lancamentos, "valor"),
        "pendencias.csv": (pend.pendencias, "valor_brl"),
    }, rastro)
    checagens += checar_notas(chk.comissoes, rem.comissoes, nf)
    checagens += checar_destinos(chk.linhas, len(dados["orbe"]) + n_cart, rem.linhas, len(dados["ponte"]))
    if n_cart:
        de_antes = chk.linhas[chk.linhas["competencia_origem"].notna()]
        faturadas = int((de_antes["destino"] == "COMISSAO").sum())
        continuam = int((cart["idade_meses"] > 0).sum())
        checagens.append(Checagem("integridade", "4. toda linha da carteira anterior entrou na comissão ou continua na carteira",
                                  n_cart == faturadas + continuam,
                                  f"{n_cart} linhas -> {faturadas} faturadas + {continuam} na carteira"))
    checagens += checar_lancamentos(ext.lancamentos, bancos)
    checagens += checar_saldo_extratos(bancos)
    avisos_extra = []
    for ign in dados["ponte"].attrs.get("linhas_ignoradas", []) or []:
        avisos_extra.append(f"relatório do parceiro de câmbio, linha {ign['linha']} ignorada (sem Nº Operação ou data de "
                            f"contratação válida): {ign['conteudo']}")

    meta_ponte = {k: dados["ponte"].attrs.get(k) for k in ("remetente", "assunto", "data_envio", "data_repasse", "prazo_dias_uteis")}
    f = Fechamento(competencia, chk.linhas, rem.linhas, comissoes, div, nf, sem_nota,
                   ext.lancamentos, ext.em_transito, pend.pendencias, rastro, conc, cart, n_cart, dados["taxas"],
                   meta_ponte, checagens, list(config.avisos) + ext.avisos + avisos_extra, dv.so_pendencia)
    f.checagens += [relatorio.checar_diferenca_notas(f), relatorio.checar_por_natureza(f)]
    return f


def escrever(f: Fechamento, pasta: Path, config, entrada: dict | None = None,
             dir_regras: Path | None = None, pasta_anterior: Path | None = None) -> tuple[dict[str, Path], dict]:
    """Grava os 6 CSVs, a carteira, os rascunhos de comunicação, o RELATORIO_FECHAMENTO.md e, só se a
    integridade passou, o resumo.json. Devolve (arquivos gravados, dicionário do resumo)."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = {
        "comissoes": escrever_csv(f.comissoes, pasta / "comissoes_por_lojista.csv", "comissoes_por_lojista.csv"),
        "divergencias": escrever_csv(f.divergencias, pasta / "divergencias_taxa.csv", "divergencias_taxa.csv"),
        "notas": escrever_csv(f.notas, pasta / "notas_a_emitir.csv", "notas_a_emitir.csv"),
        "lancamentos": escrever_csv(f.lancamentos, pasta / "lancamentos_classificados.csv",
                                    "lancamentos_classificados.csv"),
        "pendencias": escrever_csv(f.pendencias, pasta / "pendencias.csv", "pendencias.csv"),
        "rastro": escrever_csv(f.rastro, pasta / "rastro.csv", "rastro.csv"),
        "carteira": escrever_csv(f.carteira, pasta / "carteira_pendente.csv", "carteira_pendente.csv"),
    }
    if dir_regras is not None and (Path(dir_regras) / "comunicacoes.csv").exists():
        from .notas import competencia_texto
        gerados = comunicacoes.gerar(f, config, dir_regras, pasta, competencia_texto(f.competencia), f.meta_ponte)
        arquivos["comunicacoes"] = pasta / "comunicacoes"
        arquivos.update({f"comunicacoes/{k}": v for k, v in gerados.items()})
    res = relatorio.resumo(f, config, arquivos, entrada)
    pend_ant = relatorio.ler_pendencias_anteriores(pasta_anterior)
    if pend_ant is not None and len(f.pendencias):
        chaves = [relatorio._chave_pendencia(r) for r in f.pendencias.itertuples(index=False)]
        rec = sum(1 for c in chaves if c in pend_ant)
        res["totais"]["pendencias"]["recorrentes"], res["totais"]["pendencias"]["novas"] = rec, len(chaves) - rec
    md = relatorio.markdown(f, config, res, relatorio.ler_causas(dir_regras, internas=True), relatorio.ler_historico(dir_regras), pend_ant, arquivos)
    arquivos["relatorio"] = relatorio.escrever_relatorio(md, pasta / "RELATORIO_FECHAMENTO.md")
    resumo_path = pasta / "resumo.json"
    if f.integro:
        arquivos["resumo"] = relatorio.escrever_resumo(res, resumo_path)
    elif resumo_path.exists():
        resumo_path.unlink()   # um resumo antigo não pode passar por válido
    res["arquivos"] = {k: Path(v).name for k, v in arquivos.items()}
    return arquivos, res
