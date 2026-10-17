"""FASE D: rascunhos por contraparte em saida/comunicacoes/ (Helena, 17/10 09h53: "um rascunho por contraparte,
com as operações anexadas, eu reviso e envio"). Nada é enviado; nenhum número novo; cada anexo soma as
pendências/divergências correspondentes; a Casa fica fora da contestação da Orbe (Helena ao Barteman 09h44)."""
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src.cli import main
from src.dinheiro import soma

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]
CASA, ROTA, BRIDGE, MA, ATLAS = "00520815000100", "95927868000148", "22224579000109", "17217888000111", "39566044000119"


@pytest.fixture(scope="module")
def saida(dados, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("saida")
    assert main(["fechar", "--saida", str(pasta), "--sem-ia", "--json"]) == 0
    return pasta


def _csv(p):
    return pd.read_csv(p, sep=";", dtype=str, keep_default_na=False)


def _pend(saida):
    return _csv(saida / "pendencias.csv")


def test_arquivos_gerados_e_topo_rascunho(saida):
    c = saida / "comunicacoes"
    nomes = sorted(p.name for p in c.iterdir())
    assert nomes == ["avisos_nova_condicao.md", "comercial.md", "orbe.md", "orbe_contestacao.csv", "ponte.md", "ponte_contestacao.csv"]
    for md in ("orbe.md", "ponte.md", "comercial.md", "avisos_nova_condicao.md"):
        texto = (c / md).read_text(encoding="utf-8")
        assert texto.startswith("RASCUNHO — envio só após aprovação de "), md
        assert "**Para:**" in texto and "**Assunto:**" in texto and "09/2026" in texto
    assert (c / "orbe.md").read_text(encoding="utf-8").startswith("RASCUNHO — envio só após aprovação de Helena (Financeiro)")


def test_orbe_rota_mais_bridge_sem_a_casa(saida):
    anexo = _csv(saida / "comunicacoes" / "orbe_contestacao.csv")
    pend = _pend(saida)
    assert set(anexo.cnpj) == {ROTA, BRIDGE} and CASA not in set(anexo.cnpj) and len(anexo) == 92
    por = anexo.assign(v=anexo.valor_brl.map(D)).groupby("cnpj").v.sum()
    div = pend[(pend.tipo == "DIVERGENCIA_TAXA") & (pend.linha_negocio == "CHECKOUT")].set_index("cnpj").valor_brl.map(D)
    assert por.to_dict() == div.to_dict() == {ROTA: D("1546.28"), BRIDGE: D("29.95")}
    md = (saida / "comunicacoes" / "orbe.md").read_text(encoding="utf-8")
    assert "valor LÍQUIDO R$ 1.546,28 (= R$ 1.644,72 a maior em 83 vendas − R$ 98,44 devolvidos em 4 estornos)" in md
    assert "R$ 29,95" in md and "Total a corrigir: R$ 1.576,23" in md and "Casa do Estudante" not in md
    assert "Erro da Orbe" in md and "avisada à Orbe alguns dias depois" in md


def test_ponte_mundo_aberto_negativos_e_repetida(saida):
    anexo = _csv(saida / "comunicacoes" / "ponte_contestacao.csv")
    pend = _pend(saida)
    assert anexo.natureza.value_counts().to_dict() == {"EXCESSO_SPREAD": 23, "SPREAD_NEGATIVO": 4, "REPETIDA": 1}
    v = anexo.valor_brl.map(D)
    assert soma(v[anexo.natureza == "EXCESSO_SPREAD"]) == D("1418.85") == D(pend[(pend.tipo == "DIVERGENCIA_TAXA") & (pend.cnpj == MA)].valor_brl.iloc[0])
    assert soma(v[anexo.natureza == "SPREAD_NEGATIVO"]) == D("-1834.05") == soma(pend[pend.tipo == "SPREAD_NEGATIVO"].valor_brl.map(D))
    rep = anexo[anexo.natureza == "REPETIDA"].iloc[0]
    assert rep.ref_origem == "PC-0926-0162" and D(rep.valor_brl) == 0 and "corrigir o relatório" in rep.motivo
    md = (saida / "comunicacoes" / "ponte.md").read_text(encoding="utf-8")
    assert "relatorios@pontecambio.com.br" in md and "R$ 1.418,85" in md and "-R$ 1.834,05" in md and "PC-0926-0162" in md
    assert "Total em disputa: R$ 3.252,90" in md and "M-01" in md and "5 dias úteis" in md and "2026-10-09" in md
    assert "nunca avisado à Ponte" in md


def test_comercial(saida):
    md = (saida / "comunicacoes" / "comercial.md").read_text(encoding="utf-8")
    assert "SEM_CONTRATO" in md and "R$ 7.876,05" in md and "NÃO é receita da Tarvo" in md
    assert "ALERTA_ANTECIPACAO" in md and "(informativa)" in md and "R$ 179.592,82" in md
    assert "TARIFA_ZERO_COBRADA" in md and "R$ 15.397,42" in md and "devolução ao lojista" in md
    assert md.count("- **PEN-") == 3


def test_avisos_nova_condicao(saida):
    md = (saida / "comunicacoes" / "avisos_nova_condicao.md").read_text(encoding="utf-8")
    assert "Casa do Estudante Viagens Ltda → Orbe" in md and "Escola Bridge de Idiomas Ltda → Orbe" in md and "Mundo Aberto → Ponte" in md
    assert md.count("### ") == 3 and "regra X-01" in md and "de 2026-09-01 até 2026-12-31" in md
    assert "de 2026-09-15 até sem fim" in md and "1.2%" in md and "nunca avisada à Orbe" in md
    assert "EC 1018325654" in md and "EC 1075624862" in md


def test_resumo_lista_os_rascunhos_e_lembrete_m06(saida):
    res = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    assert res["arquivos"]["comunicacoes/orbe_md"] == "comunicacoes/orbe.md"
    assert "M-06" in [l["regra_id"] for l in res["lembretes"]]
