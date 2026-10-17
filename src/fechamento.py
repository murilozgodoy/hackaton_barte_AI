"""Orquestra o fechamento: cálculo, checagens de integridade (1 a 6) e gravação de saida/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import checkout, conciliacao, divergencias, extratos, notas, remessa
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
    chk = checkout.calcular(dados["orbe"], dados["taxas"], config, competencia)
    rem = remessa.calcular(dados["ponte"], dados["taxas"], config, competencia)
    div, rastro_div = divergencias.calcular(chk.linhas, rem.linhas, config)
    nf, rastro_nf, sem_nota = notas.calcular(chk.comissoes, rem.comissoes, chk.rastro, rem.rastro, config, competencia)
    bancos = extratos_de(dados)
    ext = extratos.classificar(bancos, config, dados["plano_contas"], usar_ia=usar_ia)

    colunas_com = ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl"]
    comissoes = pd.concat([chk.comissoes, rem.comissoes], ignore_index=True)
    comissoes = comissoes[colunas_com + [c for c in comissoes.columns if c not in colunas_com]]
    rastro = pd.concat([chk.rastro, rem.rastro, rastro_div, rastro_nf, ext.rastro], ignore_index=True)

    checagens = checar_rastro({
        "comissoes_por_lojista.csv": (comissoes, "comissao_brl"),
        "divergencias_taxa.csv": (div, "diferenca_brl"),
        "notas_a_emitir.csv": (nf, "valor_brl"),
        "lancamentos_classificados.csv": (ext.lancamentos, "valor"),
    }, rastro)
    checagens += checar_notas(chk.comissoes, rem.comissoes, nf)
    checagens += checar_destinos(chk.linhas, len(dados["orbe"]), rem.linhas, len(dados["ponte"]))
    checagens += checar_lancamentos(ext.lancamentos, bancos)
    checagens += checar_saldo_extratos(bancos)

    ref = primeiro_dia(competencia)
    conc = conciliacao.calcular(dados, rem.comissoes, ext.lancamentos,
                                config.parametro("participacao_spread", ref), config.parametro("arredondamento", ref))
    return Fechamento(competencia, chk.linhas, rem.linhas, comissoes, div, nf, sem_nota, ext.lancamentos,
                      ext.em_transito, rastro, conc, checagens, list(config.avisos) + ext.avisos)


def escrever(f: Fechamento, pasta: Path) -> dict[str, Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    return {
        "comissoes": escrever_csv(f.comissoes, pasta / "comissoes_por_lojista.csv", "comissoes_por_lojista.csv"),
        "divergencias": escrever_csv(f.divergencias, pasta / "divergencias_taxa.csv", "divergencias_taxa.csv"),
        "notas": escrever_csv(f.notas, pasta / "notas_a_emitir.csv", "notas_a_emitir.csv"),
        "lancamentos": escrever_csv(f.lancamentos, pasta / "lancamentos_classificados.csv",
                                    "lancamentos_classificados.csv"),
        "rastro": escrever_csv(f.rastro, pasta / "rastro.csv", "rastro.csv"),
    }


def totais(f: Fechamento) -> dict:
    """Totais em string decimal (sem float), para o resumo e o JSON da CLI."""
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
        "lancamentos": {m: int(n) for m, n in f.lancamentos["metodo"].value_counts().items()},
    }
