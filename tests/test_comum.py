from datetime import date
from decimal import Decimal

import pytest

from src.leitores.comum import (
    ErroLeitura, ler_texto, normalizar, normalizar_cnpj, numero_br, parse_vigencia,
    taxa_pct_de_celula,
)


@pytest.mark.parametrize("enc_arquivo, enc_esperado", [
    ("utf-8", "utf-8-sig"), ("utf-8-sig", "utf-8-sig"), ("cp1252", "cp1252"),
])
def test_ler_texto_detecta_encoding(tmp_path, enc_arquivo, enc_esperado):
    arq = tmp_path / "x.csv"
    arq.write_bytes("Data;Lançamento;Valor\n01/09/2026;PIX ENVIADO ANDES EXPEDIÇÕES;-1,00\n".encode(enc_arquivo))
    texto, enc = ler_texto(arq, esperado=["Lançamento"])
    assert enc == enc_esperado
    assert "EXPEDIÇÕES" in texto


def test_ler_texto_sem_trecho_esperado_para_com_mensagem(tmp_path):
    arq = tmp_path / "x.csv"
    arq.write_text("outra coisa", encoding="utf-8")
    with pytest.raises(ErroLeitura, match="não encontrei"):
        ler_texto(arq, esperado=["Lançamento"])


@pytest.mark.parametrize("entrada, esperado", [
    ("612.334,81", Decimal("612334.81")), ("-1.920.088,60", Decimal("-1920088.60")),
    ("608,88", Decimal("608.88")), ("-389,00", Decimal("-389.00")), ("", None), (None, None),
])
def test_numero_br(entrada, esperado):
    assert numero_br(entrada) == esperado


@pytest.mark.parametrize("entrada, esperado", [
    (3229837000103, "03229837000103"), ("22.224.579/0001-09", "22224579000109"),
    (8780784000120.0, "08780784000120"), ("00520815000100", "00520815000100"), (None, None),
])
def test_normalizar_cnpj(entrada, esperado):
    assert normalizar_cnpj(entrada) == esperado


@pytest.mark.parametrize("entrada, pct, situacao", [
    (0.0149, Decimal("1.49"), "VALOR"), ("1,49%", Decimal("1.49"), "VALOR"),
    ("padrão", None, "PADRAO"), (None, None, "VAZIO"), ("  ", None, "VAZIO"),
])
def test_taxa_pct_de_celula(entrada, pct, situacao):
    assert taxa_pct_de_celula(entrada) == (pct, situacao)


def test_taxa_texto_sem_percentual_e_ambigua():
    with pytest.raises(ErroLeitura):
        taxa_pct_de_celula("1,49")


@pytest.mark.parametrize("entrada, esperado", [
    ("01/01/2026", (date(2026, 1, 1), None)),
    ("até 14/09/2026", (None, date(2026, 9, 14))),
    ("a partir de 15/09/2026", (date(2026, 9, 15), None)),
    ("de 01/01/2026 a 31/12/2026", (date(2026, 1, 1), date(2026, 12, 31))),
    (None, (None, None)),
])
def test_parse_vigencia(entrada, esperado):
    assert parse_vigencia(entrada) == esperado


def test_normalizar_remove_acento_e_padroniza():
    assert normalizar("  Créd.  2-6x ") == "CRED. 2-6X"
    assert normalizar("Nº Operação") == "NO OPERACAO"


# ---------------------------------------------------------------- célula vazia (NaN/None/"") em qualquer leitor

import pandas as pd

from src.leitores.comum import data_br, decimal_de_celula, normalizar_ec, numero_ponto

VAZIOS = [None, "", "   ", float("nan"), pd.NA, pd.NaT]


@pytest.mark.parametrize("vazio", VAZIOS, ids=repr)
def test_celula_vazia_e_none_em_todos_os_conversores(vazio):
    """Com pandas 3 uma célula vazia chega como NaN (não como None): todo conversor trata igual."""
    assert normalizar_ec(vazio) is None
    assert normalizar_cnpj(vazio) is None
    assert data_br(vazio) is None
    assert numero_br(vazio) is None
    assert numero_ponto(vazio) is None
    assert decimal_de_celula(vazio) is None
    assert taxa_pct_de_celula(vazio) == (None, "VAZIO")
    assert parse_vigencia(vazio) == (None, None)


def test_src_desliga_inferencia_de_string_do_pandas_3():
    """pandas 2 e 3 têm que gerar o mesmo saida/: texto vazio é None (object), nunca NaN (dtype str)."""
    import src  # noqa: F401  (o pacote ajusta a opção ao ser importado)
    assert pd.get_option("future.infer_string") is False
    assert pd.DataFrame([{"a": "x"}, {"a": None}])["a"].tolist() == ["x", None]
