"""Um leitor por fonte. Cada um devolve um DataFrame com colunas padronizadas,
ref_origem e arquivo_origem; metadados de conferência ficam em df.attrs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .aurora import ler_aurora
from .meridiano import ler_meridiano
from .orbe import ler_orbe
from .plano_contas import ler_plano_contas
from .ponte import ler_ponte
from .taxas import ler_taxas


def carregar_todas(arquivos: dict[str, Path], cfg: dict) -> dict[str, pd.DataFrame]:
    return {
        "orbe": ler_orbe(arquivos["orbe"]),
        "taxas": ler_taxas(arquivos["taxas"], aba=cfg["taxas"]["aba"]),
        "ponte": ler_ponte(arquivos["ponte"], aba=cfg["ponte"]["aba"]),
        "plano_contas": ler_plano_contas(arquivos["plano_contas"]),
        "aurora": ler_aurora(arquivos["aurora"], rotulo=cfg["aurora"]["rotulo"]),
        "meridiano": ler_meridiano(arquivos["meridiano"], rotulo=cfg["meridiano"]["rotulo"]),
    }
