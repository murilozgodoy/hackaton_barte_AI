"""Orquestra o fechamento: cálculo, pendências, checagens de integridade (1 a 6) e gravação de saida/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import checkout, conciliacao, divergencias, extratos, notas, pendencias, relatorio, remessa
from .dinheiro import soma
from .notas import primeiro_dia
from .saida import escrever_csv
from .validacao import (Checagem, checar_destinos, checar_lancamentos, checar_notas, checar_rastro,
                        checar_saldo_extratos)


@dataclass
class Fechamento:
    competencia: str
    orbe_linhas: pd.DataFrame
    ponte_linhas: pd.DataFrame
    comissoes: pd.DataFrame          # CHECKOUT + REMESSA, formato de saída
    divergencias: pd.DataFrame
    notas: pd.DataFrame
    sem_nota: pd.DataFrame           # comissões de checkout com saldo <= 0
    lancamentos: pd.DataFrame
    em_transito: pd.DataFrame
    pendencias: pd.DataFrame
    rastro: pd.DataFrame
    conciliacao: dict
    checagens: list[Checagem] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def integro(self) -> bool:
        return all(c.ok for c in self.checagens if c.nivel == "ERRO")

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


def executar(dados: dict[str, pd.DataFrame], config, competencia: str, usar_ia: bool = True) -> Fechamento:
    ref = primeiro_dia(competencia)
    chk = checkout.calcular(dados["orbe"], dados["taxas"], config, competencia)
    rem = remessa.calcular(dados["ponte"], dados["taxas"], config, competencia)
    div, rastro_div = divergencias.calcular(chk.linhas, rem.linhas, config)
    nf, rastro_nf, sem_nota = notas.calcular(chk.comissoes, rem.comissoes, chk.rastro, rem.rastro, config, competencia)
    bancos = extratos_de(dados)
    ext = extratos.classificar(bancos, config, dados["plano_contas"], usar_ia=usar_ia)
    conc = conciliacao.calcular(dados, rem.linhas, rem.comissoes, ext.lancamentos,
                                config.parametro("participacao_spread", ref), config.parametro("arredondamento", ref))
    pend = pendencias.calcular(ref, chk.linhas, rem.linhas, div, sem_nota, chk.rastro, ext.lancamentos,
                               ext.em_transito, conc, nf, config)

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
    checagens += checar_destinos(chk.linhas, len(dados["orbe"]), rem.linhas, len(dados["ponte"]))
    checagens += checar_lancamentos(ext.lancamentos, bancos)
    checagens += checar_saldo_extratos(bancos)

    return Fechamento(competencia, chk.linhas, rem.linhas, comissoes, div, nf, sem_nota, ext.lancamentos,
                      ext.em_transito, pend.pendencias, rastro, conc, checagens, list(config.avisos) + ext.avisos)


def escrever(f: Fechamento, pasta: Path, config) -> dict[str, Path]:
    """Grava os 6 CSVs, o RELATORIO_FECHAMENTO.md e, só se a integridade passou, o resumo.json."""
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
    }
    res = relatorio.resumo(f, config, arquivos, pasta)
    arquivos["relatorio"] = relatorio.escrever_relatorio(relatorio.markdown(f, config, res),
                                                         pasta / "RELATORIO_FECHAMENTO.md")
    resumo_path = pasta / "resumo.json"
    if f.integro:
        arquivos["resumo"] = relatorio.escrever_resumo(res, resumo_path)
    elif resumo_path.exists():
        resumo_path.unlink()   # um resumo antigo não pode passar por válido
    return arquivos


def totais(f: Fechamento) -> dict:
    """Totais em string decimal (sem float), para o JSON da CLI."""
    div_chk = f.divergencias[f.divergencias["linha_negocio"] == "CHECKOUT"]
    div_rem = f.divergencias[f.divergencias["linha_negocio"] == "REMESSA"]
    return {
        "comissao_checkout_brl": str(soma(f.comissoes_checkout["comissao_brl"])),
        "comissao_remessa_brl": str(soma(f.comissoes_remessa["comissao_brl"])),
        "notas": {"quantidade": int(len(f.notas)), "valor_total_brl": str(soma(f.notas["valor_brl"]))},
        "divergencias": {
            "checkout": {"linhas": int(len(div_chk)), "valor_brl": str(soma(div_chk["diferenca_brl"]))},
            "remessa": {"linhas": int(len(div_rem)), "valor_brl": str(soma(div_rem["diferenca_brl"]))},
        },
        "pendencias": {"quantidade": int(len(f.pendencias)),
                       "por_responsavel": {str(q): int(n) for q, n in f.pendencias["quem_decide"].value_counts().items()}},
        "lancamentos": {m: int(n) for m, n in f.lancamentos["metodo"].value_counts().items()},
    }
