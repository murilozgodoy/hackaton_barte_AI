from pathlib import Path

import pytest

from src.fontes import carregar_config_fontes, localizar, preparar_entrada
from src.leitores import carregar_todas

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def cfg():
    return carregar_config_fontes(RAIZ / "config")


@pytest.fixture(scope="session")
def arquivos(cfg, tmp_path_factory):
    """Extrai o pacote da raiz numa pasta temporária (não depende de data/).

    O data pack não é versionado: sem o zip na raiz, os testes de dados são pulados.
    """
    if not list(RAIZ.glob(cfg["pacote"]["padrao_arquivo"])):
        pytest.skip(f"data pack ({cfg['pacote']['padrao_arquivo']}) não está na raiz do repositório")
    pasta = preparar_entrada(None, RAIZ, tmp_path_factory.mktemp("dados"), cfg)
    return localizar(pasta, cfg)


@pytest.fixture(scope="session")
def dados(arquivos, cfg):
    return carregar_todas(arquivos, cfg)
