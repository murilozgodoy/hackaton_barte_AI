"""Um leitor por fonte. Cada um devolve um DataFrame com colunas padronizadas,
ref_origem e arquivo_origem; metadados de conferência ficam em df.attrs.
Fontes com vários arquivos (multiplos=sim em fontes.csv) são lidas arquivo a arquivo e
concatenadas, cada linha guardando o arquivo de onde veio."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .aurora import ler_aurora
from .meridiano import ler_meridiano
from .orbe import ler_orbe, ler_orbe_varios
from .plano_contas import ler_plano_contas
from .ponte import ler_ponte, ler_ponte_varios
from .taxas import ler_taxas


def _lista(valor) -> list[Path]:
    return [Path(v) for v in valor] if isinstance(valor, (list, tuple)) else [Path(valor)]


def _um(valor, fonte: str) -> Path:
    lista = _lista(valor)
    if len(lista) != 1:
        raise ValueError(f"fonte {fonte} aceita um arquivo só, recebi {len(lista)}")
    return lista[0]


def carregar_todas(arquivos: dict, cfg: dict) -> dict[str, pd.DataFrame]:
    return {
        "orbe": ler_orbe_varios(_lista(arquivos["orbe"])),
        "taxas": ler_taxas(_um(arquivos["taxas"], "taxas"), aba=cfg["taxas"]["aba"]),
        "ponte": ler_ponte_varios(_lista(arquivos["ponte"]), aba=cfg["ponte"]["aba"]),
        "plano_contas": ler_plano_contas(_um(arquivos["plano_contas"], "plano_contas")),
        "aurora": ler_aurora(_um(arquivos["aurora"], "aurora"), rotulo=cfg["aurora"]["rotulo"]),
        "meridiano": ler_meridiano(_um(arquivos["meridiano"], "meridiano"), rotulo=cfg["meridiano"]["rotulo"]),
    }
