"""Formato dos CSVs de saída e comportamento da CLI."""
import csv
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src.cli import main
from src.saida import escrever_csv, formatar_celula, formatar_pct

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("valor, coluna, esperado", [
    (D("3819.35"), "comissao_brl", "3819.35"), (D("-5.50"), "comissao_brl", "-5.50"),
    (D("0"), "valor", "0.00"), (D("-0.00"), "valor", "0.00"), (D("2.69"), "taxa_contratada_pct", "2.69"),
    (D("2.100"), "taxa_pct", "2.10"), (D("1.501"), "taxa_aplicada_pct", "1.501"), (D("0"), "taxa_pct", "0.00"),
    (D("50.00"), "taxa_pct", "50.00"), (D("0.3007"), "diferenca_pp", "0.3007"), (D("1"), "confianca", "1"),
    (D("0.80"), "confianca", "0.8"), (None, "x", ""), (pd.Timestamp("2026-09-01"), "data", "2026-09-01"),
    ("texto", "x", "texto"), (True, "flag", "true"),
])
def test_formatar_celula(valor, coluna, esperado):
    assert formatar_celula(valor, coluna) == esperado


def test_dinheiro_nao_arredondado_e_erro():
    with pytest.raises(ValueError, match="não está arredondado"):
        formatar_celula(D("1.005"), "comissao_brl")
    assert formatar_pct(D("1.4984")) == "1.4984"


def test_escrever_csv_formato(tmp_path):
    df = pd.DataFrame({"comissao_brl": [D("1.10")], "id_saida": ["X-1"], "cnpj": ["00520815000100"],
                       "lojista": ["Casa"], "linha_negocio": ["CHECKOUT"], "extra": [pd.Timestamp("2026-09-30")]})
    p = escrever_csv(df, tmp_path / "c.csv", "comissoes_por_lojista.csv")
    linhas = p.read_text(encoding="utf-8").split("\n")
    assert linhas[0] == "id_saida;cnpj;lojista;linha_negocio;comissao_brl;extra"   # obrigatórias primeiro
    assert linhas[1] == "X-1;00520815000100;Casa;CHECKOUT;1.10;2026-09-30" and linhas[2] == ""
    with pytest.raises(ValueError, match="obrigatórias ausentes"):
        escrever_csv(df.drop(columns=["cnpj"]), tmp_path / "d.csv", "comissoes_por_lojista.csv")


def test_cli_fechar_gera_saidas_e_json(dados, tmp_path, capsys):
    codigo = main(["fechar", "--saida", str(tmp_path), "--json", "--sem-ia"])
    assert codigo == 0
    j = json.loads(capsys.readouterr().out)
    assert j["ok"] is True and j["status_integridade"] == "OK" and j["competencia"] == "2026-09"
    assert j["totais"]["comissao_checkout_brl"] == "203735.34" and j["totais"]["comissao_remessa_brl"] == "39543.45"
    assert j["totais"]["notas"] == {"quantidade": 21, "valor_total_brl": "243284.29"}
    assert j["totais"]["divergencias"] == {"linhas": 115, "contrato": {"linhas": 115, "valor_brl": "2995.08"},
                                           "checkout": {"linhas": 92, "valor_brl": "1576.23"},
                                           "remessa": {"linhas": 23, "valor_brl": "1418.85"},
                                           "devolucao_lojista": {"linhas": 0, "valor_brl": "0.00"},
                                           "por_natureza": {"CONTRATO": {"linhas": 115, "valor_brl": "2995.08"}},
                                           "so_pendencia": {"linhas": 118, "valor_brl": "15396.77", "pela_taxa_brl": "15397.42"}}
    assert j["lancamentos"] == {"REGRA": 184, "IA": 0, "HUMANO": 0}
    assert all(isinstance(c["ok"], bool) for c in j["integridade"] + j["contexto"]["checagens"])
    assert all(c["ok"] for c in j["integridade"])
    assert j["totais"]["pendencias"]["quantidade"] == 16 and j["arquivos"]["resumo"] == "resumo.json"
    for nome in ["comissoes_por_lojista.csv", "divergencias_taxa.csv", "notas_a_emitir.csv",
                 "lancamentos_classificados.csv", "rastro.csv"]:
        with open(tmp_path / nome, encoding="utf-8", newline="") as f:
            linhas = list(csv.reader(f, delimiter=";"))
        assert len(linhas) > 1 and all(len(l) == len(linhas[0]) for l in linhas)
        assert not any("," in c and c.replace(",", "").replace(".", "").replace("-", "").isdigit() for l in linhas[1:] for c in l)


def test_cli_fechar_e_deterministico(dados, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert main(["fechar", "--saida", str(a), "--sem-ia"]) == 0
    assert main(["fechar", "--saida", str(b), "--sem-ia"]) == 0
    arquivos = [p for p in a.rglob("*") if p.is_file()]
    assert len(arquivos) == 15
    for p in arquivos:
        assert p.read_bytes() == (b / p.relative_to(a)).read_bytes(), p.name


def test_cli_competencia_invalida_ou_vazia(dados, tmp_path, capsys):
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-9"]) == 1
    assert "AAAA-MM" in capsys.readouterr().err
    # competência de outro mês com os arquivos de setembro: os extratos são de outro mês -> erro de entrada (código 1)
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-10", "--sem-ia"]) == 1
    err = capsys.readouterr().err
    assert "é de outro mês" in err and "2026-10" in err and "--competencia" in err


def test_cli_regras_invalidas_codigo_2(dados, tmp_path, capsys):
    import shutil
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    p = regras / "regras_negocio.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("conta=1.1.03.001 | prioridade=50", "conta=1.1.03 | prioridade=50"),
                 encoding="utf-8")
    assert main(["validar", "--regras", str(regras)]) == 2
    assert "não aceita lançamento" in capsys.readouterr().err


def test_cli_entrada_inexistente_codigo_1(tmp_path, capsys):
    assert main(["validar", "--entrada", str(tmp_path / "nada.zip")]) == 1
    assert "Entrada com problema" in capsys.readouterr().err


def test_cli_fechar_imprime_resumo_final_em_portugues(dados, tmp_path, capsys):
    """Ao fim do `fechar` (sem --json) sai um resumo curto: totais, notas, divergências, pendências,
    checagens e onde estão os arquivos, com o caminho do relatório por último."""
    assert main(["fechar", "--saida", str(tmp_path), "--sem-ia"]) == 0
    out = capsys.readouterr().out
    bloco = out.split("RESUMO DO FECHAMENTO")[-1]
    linhas = [l for l in bloco.strip().splitlines() if l.strip()]
    assert 12 <= len(linhas) <= 22, linhas
    assert "Competência: 09/2026 (inferida dos dados)" in bloco
    assert "CHECKOUT" in bloco and "R$ 203.735,34" in bloco and "21 lojistas" in bloco
    assert "REMESSA" in bloco and "R$ 39.543,45" in bloco and "14 lojistas" in bloco
    assert "Notas a emitir: 21" in bloco and "R$ 243.284,29" in bloco
    assert ("Divergências: 115 transações, todas 115 de contrato (checkout R$ 1.576,23 + remessa R$ 1.418,85 = R$ 2.995,08); "
            "fora do arquivo, por regra, 118 transações de concessão comercial fora do contrato (R$ 15.396,77 cobrados de fato "
            "pela adquirente, devolução ao lojista por conta da Tarvo, só em pendência)") in bloco
    assert "Lançamentos classificados: 184" in bloco
    assert "Pendências: 16 (2 informativas), por responsável:" in bloco and "em jogo, por responsável" not in bloco and "Financeiro: 3 pendência(s), R$ 19.750,00 em jogo (1 informativa)" in bloco
    assert "Helena (Financeiro): 10 pendência(s), R$ 5.341,28 em jogo (1 já incluída em outra)" in bloco
    assert "Checagens de integridade: 7 de 7 ok" in bloco
    assert str(tmp_path) in bloco
    assert linhas[-1].strip().endswith("RELATORIO_FECHAMENTO.md")


# ---------------------------------------------------------------- competência dos extratos e avisos dos leitores

def _entrada_com_extratos_de_outubro(pasta_dados, tmp_path):
    """Pasta com os arquivos de setembro, mas os dois extratos bancários deslocados para outubro."""
    from tests.outubro_sintetico import gerar
    entrada = tmp_path / "entrada"
    shutil.copytree(pasta_dados, entrada)
    for p in entrada.glob("05*"):
        p.unlink()
    for p in gerar(tmp_path / "out_sint", pasta_dados).glob("05*"):
        shutil.copy(p, entrada / p.name)
    return entrada


def test_extrato_de_outro_mes_para_com_codigo_1(pasta_dados, tmp_path, capsys):
    """Bancos de outubro com Orbe e Ponte de setembro: erro de entrada, nunca um número "íntegro"."""
    entrada = _entrada_com_extratos_de_outubro(pasta_dados, tmp_path)
    assert main(["validar", "--entrada", str(entrada)]) == 1
    err = capsys.readouterr().err
    assert "é de outro mês" in err and "AURORA" in err and "MERIDIANO" in err and "2026-09" in err
    assert main(["fechar", "--entrada", str(entrada), "--saida", str(tmp_path / "saida"), "--sem-ia"]) == 1
    assert not (tmp_path / "saida" / "resumo.json").exists()


def test_integridade_falha_nao_escreve_resumo(pasta_dados, tmp_path, capsys):
    """Orbe e Ponte de setembro com --competencia 2026-10 (extratos de outubro): nenhuma linha da Orbe no mês -> 3."""
    entrada = _entrada_com_extratos_de_outubro(pasta_dados, tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()
    (saida / "resumo.json").write_text("{}", encoding="utf-8")
    assert main(["fechar", "--entrada", str(entrada), "--saida", str(saida), "--competencia", "2026-10", "--sem-ia"]) == 3
    out = capsys.readouterr()
    assert "nenhuma linha da Orbe entrou no mês" in out.out and "INTEGRIDADE FALHOU" in out.err
    assert not (saida / "resumo.json").exists()
    assert "RELATÓRIO INVÁLIDO" in (saida / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")


def test_aviso_dos_leitores_chega_ao_resumo_e_ao_relatorio(pasta_dados, tmp_path, capsys):
    """3 lançamentos do Aurora datados de agosto: fecha (código 0), classifica normalmente, e o aviso fica em
    resumo.json["avisos"] e na seção Avisos do relatório, com fonte e ação esperada (não só na tela)."""
    entrada = tmp_path / "entrada"
    shutil.copytree(pasta_dados, entrada)
    p = next(entrada.glob("05a_extrato_banco_aurora*.csv"))
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    import re
    texto, n = re.subn(r"\n(\d{2})/09/2026;", r"\n\1/08/2026;", texto, count=3)   # as 3 primeiras linhas viram agosto
    assert n == 3
    p.write_text(texto, encoding=enc)
    assert main(["fechar", "--entrada", str(entrada), "--saida", str(tmp_path / "saida"), "--json", "--sem-ia"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["lancamentos"] == {"REGRA": 184, "IA": 0, "HUMANO": 0}
    assert any(a.startswith("AURORA: lançamentos na competência (3 de 84") and "Ação: conferir" in a for a in j["avisos"])
    res = json.loads((tmp_path / "saida" / "resumo.json").read_text(encoding="utf-8"))
    assert res["avisos"] == j["avisos"]
    rel = (tmp_path / "saida" / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert "## Avisos" in rel and "- AURORA: lançamentos na competência (3 de 84" in rel


# ---------------------------------------------------------------- finais de linha: saida/ idêntico em macOS, Linux e Windows

def test_saida_so_com_lf_e_gitattributes(dados, tmp_path):
    """Todo arquivo de saída é gravado com newline fixo em LF (open(..., newline="\\n")); no git, .gitattributes fixa LF
    para texto e marca zip/xlsx como binário. Assim o teste "saida/ versionado = gerado" passa também no Windows."""
    assert main(["fechar", "--saida", str(tmp_path / "saida"), "--sem-ia"]) == 0
    arquivos = [p for p in (tmp_path / "saida").rglob("*") if p.is_file()]
    assert len(arquivos) == 15
    for p in arquivos:
        assert b"\r" not in p.read_bytes(), p.name
    attrs = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    assert "* text=auto eol=lf" in attrs and "*.zip binary" in attrs and "*.xlsx binary" in attrs
