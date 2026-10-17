from pathlib import Path

import pytest

from src.fontes import carregar_config_fontes, localizar, preparar_entrada
from src.leitores import carregar_todas
from src.regras import carregar_config

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fontes():
    return carregar_config_fontes(RAIZ / "regras")


@pytest.fixture(scope="session")
def bancos(fontes):
    return {f["rotulo"] for f in fontes.values() if f.get("rotulo")}


@pytest.fixture(scope="session")
def arquivos(fontes):
    """Extrai o pacote da raiz numa pasta temporária.

    O data pack não é versionado: sem o zip na raiz, os testes de dados são pulados.
    """
    if not list(RAIZ.glob(fontes["pacote"]["padrao_arquivo"])):
        pytest.skip(f"data pack ({fontes['pacote']['padrao_arquivo']}) não está na raiz do repositório")
    pasta = preparar_entrada(None, RAIZ, fontes)
    return localizar(pasta, fontes)


@pytest.fixture(scope="session")
def pasta_dados(arquivos) -> Path:
    """Pasta com os 6 arquivos do mês (extraídos do zip da raiz), para comandos que recebem --entrada."""
    return arquivos["orbe"][0].parent


@pytest.fixture(scope="session")
def dados(arquivos, fontes):
    return carregar_todas(arquivos, fontes)


@pytest.fixture(scope="session")
def config(dados, bancos):
    """Base de regras do repositório (regras/) carregada com os dados do mês."""
    return carregar_config(RAIZ / "regras", dados["taxas"], dados["plano_contas"], bancos)
