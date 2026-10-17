"""Orquestra o fechamento: cálculo, checagens de integridade e gravação de saida/."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import checkout
from .saida import escrever_csv
from .validacao import Checagem, checar_rastro


@dataclass
class Fechamento:
    competencia: str
    orbe_linhas: pd.DataFrame
    comissoes: pd.DataFrame
    rastro: pd.DataFrame
    checagens: list[Checagem] = field(default_factory=list)

    @property
    def integro(self) -> bool:
        return all(c.ok for c in self.checagens if c.nivel == "ERRO")

    @property
    def destinos_orbe(self) -> dict[str, int]:
        return self.orbe_linhas["destino"].value_counts().to_dict()


def executar(dados: dict[str, pd.DataFrame], config, competencia: str) -> Fechamento:
    chk = checkout.calcular(dados["orbe"], dados["taxas"], config, competencia)
    saidas_com_valor = {"comissoes_por_lojista.csv": (chk.comissoes, "comissao_brl")}
    checagens = checar_rastro(saidas_com_valor, chk.rastro)
    return Fechamento(competencia, chk.linhas, chk.comissoes, chk.rastro, checagens)


def escrever(f: Fechamento, pasta: Path) -> dict[str, Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos = {
        "comissoes": escrever_csv(f.comissoes, pasta / "comissoes_por_lojista.csv", "comissoes_por_lojista.csv"),
        "rastro": escrever_csv(f.rastro, pasta / "rastro.csv", "rastro.csv"),
    }
    return arquivos
