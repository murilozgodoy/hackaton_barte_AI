"""Formato dos CSVs de saída e comportamento da CLI."""
import csv
import json
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
    assert j["totais"]["comissao_checkout_brl"] == "207039.73" and j["totais"]["comissao_remessa_brl"] == "39543.45"
    assert j["totais"]["notas"] == {"quantidade": 21, "valor_total_brl": "246588.68"}
    assert j["totais"]["divergencias"] == {"checkout": {"linhas": 92, "valor_brl": "1576.23"},
                                           "remessa": {"linhas": 23, "valor_brl": "1418.85"},
                                           "devolucao_lojista": {"linhas": 118, "valor_brl": "15397.42"}}
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
    for p in a.iterdir():
        assert p.read_bytes() == (b / p.name).read_bytes()


def test_cli_competencia_invalida_ou_vazia(dados, tmp_path, capsys):
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-9"]) == 1
    assert "AAAA-MM" in capsys.readouterr().err
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-10", "--sem-ia"]) == 3
    saida = capsys.readouterr()
    assert "nenhuma linha da Orbe entrou no mês" in saida.out and "INTEGRIDADE FALHOU" in saida.err


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
    assert "CHECKOUT" in bloco and "R$ 207.039,73" in bloco and "21 lojistas" in bloco
    assert "REMESSA" in bloco and "R$ 39.543,45" in bloco and "14 lojistas" in bloco
    assert "Notas a emitir: 21" in bloco and "R$ 246.588,68" in bloco
    assert "115 (R$ 2.995,08)" in bloco and "R$ 1.576,23" in bloco and "R$ 1.418,85" in bloco
    assert "fora delas" in bloco and "118" in bloco and "R$ 15.397,42" in bloco
    assert "Lançamentos classificados: 184" in bloco
    assert "Pendências: 16 (2 informativas), R$ 48.364,75 em jogo" in bloco and "Financeiro: 3 pendência(s), R$ 19.750,00 em jogo (1 informativa)" in bloco
    assert "Helena (Financeiro): 10 pendência(s), R$ 5.341,28 em jogo (1 já incluída em outra)" in bloco
    assert "Checagens de integridade: 6 de 6 ok" in bloco
    assert str(tmp_path) in bloco
    assert linhas[-1].strip().endswith("RELATORIO_FECHAMENTO.md")
