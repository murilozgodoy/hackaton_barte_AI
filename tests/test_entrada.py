"""Entrada flexível: zip com qualquer nome, pasta com o zip, arquivos soltos ou em subpastas.

A localização é pelos padrões de regras/fontes.csv (nunca por nome fixo de um mês); arquivo
ausente ou repetido para com mensagem em português dizendo qual. Sem --entrada, vale a pasta
entrada/ da raiz e, depois, o zip na raiz.
"""
import shutil
import zipfile
from pathlib import Path

import pytest

from src.cli import main
from src.fontes import carregar_config_fontes, localizar, preparar_entrada
from src.leitores.comum import ErroLeitura

RAIZ = Path(__file__).resolve().parents[1]
FONTES = carregar_config_fontes(RAIZ / "regras")
# nomes de outro mês, para provar que nada depende de "set2026"
NOMES = {
    "orbe": "01_orbe_relatorio_comissoes_out2026.csv",
    "taxas": "02_tabela_taxas_contratadas.xlsx",
    "ponte": "03_email_ponte_cambio_relatorio_out2026.eml",
    "plano_contas": "04_plano_de_contas_fenix_erp.csv",
    "aurora": "05a_extrato_banco_aurora_cc4471_out2026.csv",
    "meridiano": "05b_extrato_banco_meridiano_cc90233_out2026.ofx",
}


def _soltos(pasta: Path, fontes=NOMES, sub: str = "") -> Path:
    destino = pasta / sub if sub else pasta
    destino.mkdir(parents=True, exist_ok=True)
    for nome in fontes.values():
        (destino / nome).write_text("x", encoding="utf-8")
    (destino / "00_LEIA-ME.md").write_text("readme do pacote", encoding="utf-8")
    return pasta


def _zip(pasta: Path, nome: str, prefixo: str = "") -> Path:
    caminho = pasta / nome
    with zipfile.ZipFile(caminho, "w") as z:
        for fonte, arq in NOMES.items():
            z.writestr(prefixo + arq, "x")
        z.writestr(prefixo + "00_LEIA-ME.md", "readme")
    return caminho


def _nomes(arquivos: dict) -> dict:
    return {f: p.name for f, p in arquivos.items()}


def test_zip_com_qualquer_nome(tmp_path):
    z = _zip(tmp_path, "pacote_qualquer_nome.zip")
    pasta = preparar_entrada(z, tmp_path, FONTES)
    assert _nomes(localizar(pasta, FONTES)) == NOMES


def test_zip_com_subpasta_dentro(tmp_path):
    z = _zip(tmp_path, "dados.zip", prefixo="Tarvo_Data_Pack_out2026/")
    assert _nomes(localizar(preparar_entrada(z, tmp_path, FONTES), FONTES)) == NOMES


def test_pasta_com_o_zip_dentro(tmp_path):
    pasta = tmp_path / "recebido"
    pasta.mkdir()
    _zip(pasta, "Tarvo_Data_Pack_out2026.zip")
    assert _nomes(localizar(preparar_entrada(pasta, tmp_path, FONTES), FONTES)) == NOMES


def test_pasta_com_arquivos_soltos(tmp_path):
    pasta = _soltos(tmp_path / "soltos")
    assert _nomes(localizar(preparar_entrada(pasta, tmp_path, FONTES), FONTES)) == NOMES


def test_arquivos_em_subpastas(tmp_path):
    pasta = tmp_path / "mes"
    _soltos(pasta, {k: v for k, v in NOMES.items() if k in ("orbe", "taxas", "ponte")}, sub="adquirente e cambio")
    _soltos(pasta, {k: v for k, v in NOMES.items() if k not in ("orbe", "taxas", "ponte")}, sub="erp/bancos")
    assert _nomes(localizar(preparar_entrada(pasta, tmp_path, FONTES), FONTES)) == NOMES


def test_arquivo_ausente_diz_qual(tmp_path):
    pasta = _soltos(tmp_path / "faltando", {k: v for k, v in NOMES.items() if k != "orbe"})
    with pytest.raises(ErroLeitura) as e:
        localizar(pasta, FONTES)
    msg = str(e.value)
    assert "Falta" in msg and "orbe" in msg and "01_orbe_*.csv" in msg and "Relatório de comissões" in msg
    assert "taxas" not in msg   # só o que falta


def test_arquivo_repetido_diz_quais(tmp_path):
    pasta = _soltos(tmp_path / "repetido")
    (pasta / "02_tabela_taxas_contratadas (1).xlsx").write_text("x", encoding="utf-8")
    with pytest.raises(ErroLeitura) as e:
        localizar(pasta, FONTES)
    msg = str(e.value)
    assert "Mais de um" in msg and "taxas" in msg and "02_tabela_taxas_contratadas.xlsx" in msg
    assert "02_tabela_taxas_contratadas (1).xlsx" in msg and "Deixe só um" in msg


def test_sem_entrada_usa_pasta_entrada_da_raiz(tmp_path):
    raiz = tmp_path / "projeto"
    _soltos(raiz / "entrada")
    _zip(raiz, "Tarvo_Data_Pack_set2026.zip")   # existe, mas entrada/ tem prioridade
    pasta = preparar_entrada(None, raiz, FONTES)
    assert pasta == raiz / "entrada"


def test_sem_entrada_e_pasta_entrada_so_com_readme_usa_o_zip_da_raiz(tmp_path):
    raiz = tmp_path / "projeto"
    (raiz / "entrada").mkdir(parents=True)
    (raiz / "entrada" / "README.md").write_text("coloque aqui os arquivos", encoding="utf-8")
    _zip(raiz, "Tarvo_Data_Pack_out2026.zip")
    pasta = preparar_entrada(None, raiz, FONTES)
    assert _nomes(localizar(pasta, FONTES)) == NOMES


def test_sem_entrada_e_sem_nada_explica_em_portugues(tmp_path):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    with pytest.raises(ErroLeitura) as e:
        preparar_entrada(None, raiz, FONTES)
    assert "entrada/" in str(e.value) and "--entrada" in str(e.value)


def test_sem_entrada_e_dois_zips_na_raiz_pede_para_escolher(tmp_path):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    _zip(raiz, "Tarvo_Data_Pack_set2026.zip")
    _zip(raiz, "Tarvo_Data_Pack_out2026.zip")
    with pytest.raises(ErroLeitura, match="Mais de um pacote"):
        preparar_entrada(None, raiz, FONTES)


def test_entrada_inexistente(tmp_path):
    with pytest.raises(ErroLeitura, match="não existe"):
        preparar_entrada(tmp_path / "nada", tmp_path, FONTES)


# ---------------------------------------------------------------- com o data pack real: pasta solta == zip

def _csvs(pasta: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(pasta.glob("*.csv"))}


@pytest.mark.parametrize("modo", ["soltos", "subpasta", "pasta_com_zip"])
def test_cli_fechar_por_pasta_gera_o_mesmo_saida_que_o_zip(dados, tmp_path, modo):
    """A banca pode entregar os arquivos de qualquer jeito: o saida/ tem que ser o versionado."""
    zip_real = next(RAIZ.glob(FONTES["pacote"]["padrao_arquivo"]))
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    if modo == "pasta_com_zip":
        shutil.copy(zip_real, entrada / "arquivos_do_mes.zip")
    else:
        with zipfile.ZipFile(zip_real) as z:
            z.extractall(entrada / "Tarvo_Data_Pack_out2026" / "arquivos" if modo == "subpasta" else entrada)
    assert main(["fechar", "--entrada", str(entrada), "--saida", str(tmp_path / "saida"), "--sem-ia"]) == 0
    assert _csvs(tmp_path / "saida") == _csvs(RAIZ / "saida")
    assert (tmp_path / "saida" / "resumo.json").read_bytes() == (RAIZ / "saida" / "resumo.json").read_bytes()
