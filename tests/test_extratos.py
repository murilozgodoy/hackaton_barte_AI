"""Classificação dos extratos de setembro/2026 e detecção de transferência em trânsito."""
from decimal import Decimal

import pytest

from src.extratos import classificar
from src.fechamento import extratos_de

D = Decimal


@pytest.fixture(scope="session")
def ext(dados, config):
    return classificar(extratos_de(dados), config, dados["plano_contas"], usar_ia=False)


def test_todos_classificados_por_regra(ext, dados):
    lanc = ext.lancamentos
    assert len(lanc) == 84 + 100 and lanc.id_saida.tolist() == [f"LAN-{i:04d}" for i in range(1, 185)]
    assert set(lanc.metodo) == {"REGRA"} and set(lanc.confianca) == {D("1")}
    assert (lanc.conta_codigo != "").all() and lanc.conta_descricao.notna().all()
    assert lanc.banco.tolist()[:84] == ["AURORA"] * 84 and lanc.banco.tolist()[84:] == ["MERIDIANO"] * 100
    assert lanc.ref_origem.tolist()[:3] == ["L9", "L10", "L11"]


@pytest.mark.parametrize("ref, conta, regra", [
    ("L9", "1.1.03.001", "C-01"),              # TED Orbe -> recebíveis de adquirente
    ("L15", "2.1.04.001", "C-06"),             # folha 08/2026 provisionada
    ("L18", "2.1.01.001", "C-02"),             # repasse a lojista
    ("L50", "1.1.09.002", "C-17"),             # PIX sem identificação
    ("L53", "4.2.06", "C-03"),                 # contabilidade: não é repasse
    ("L65", "2.1.01.001", "C-18"),             # devolução PIX Mundo Aberto
    ("L92", "1.1.09.001", "C-04"),             # transferência de 300 mil em 30/09
    ("MRD2026090082", "2.1.02.001", "C-19"),   # PIX RECEB PONTE AÉREA (lojista)
    ("MRD2026090425", "2.1.02.001", "C-19"),   # PIX RECEB PONTE AEREA sem acento
    ("MRD2026090094", "2.1.02.001", "C-20"),   # TED PONTE CAMBIO LIQ OPERACOES (parceiro)
    ("MRD2026090132", "1.1.03.002", "C-21"),   # repasse comissão 08/2026
    ("MRD2026090586", "4.3.01", "C-24"),       # IOF
    ("MRD2026090680", "3.2.01", "C-23"),       # rendimento
])
def test_contas_conhecidas(ext, ref, conta, regra):
    r = ext.lancamentos.set_index("ref_origem").loc[ref]
    assert (r.conta_codigo, r.regra_id) == (conta, regra)


def test_pendencias_de_extrato(ext):
    pend = ext.lancamentos[ext.lancamentos.tipo_pendencia.notna()].set_index("ref_origem")
    assert set(pend.index) == {"L50", "L65"}
    assert (pend.loc["L50", "tipo_pendencia"], pend.loc["L50", "subtipo"]) == ("EXTRATO_NAO_IDENTIFICADO", "CREDITO_SEM_ORIGEM")
    assert pend.loc["L65", "tipo_pendencia"] == "DEVOLUCAO" and pend.loc["L65", "valor"] == D("12400.00")


def test_transferencia_em_transito(ext):
    t = ext.em_transito
    assert len(t) == 1
    r = t.iloc[0]
    assert (r.banco, r.ref_origem, r.valor, r.conta_codigo) == ("AURORA", "L92", D("-300000.00"), "1.1.09.001")
    assert "2026-09-30" in r.motivo


def test_rastro_e_avisos(ext):
    assert len(ext.rastro) == 184 and (ext.rastro.valor.values == ext.lancamentos.valor.values).all()
    assert ext.avisos == []


def test_sem_regra_vira_humano_sem_ia(dados, config):
    extratos = [df.copy() for df in extratos_de(dados)]
    extratos[0].loc[extratos[0].index[0], "descricao"] = "COMPRA DE CAFE PARA O ESCRITORIO"
    r = classificar(extratos, config, dados["plano_contas"], usar_ia=False)
    l = r.lancamentos.iloc[0]
    assert (l.metodo, l.conta_codigo, l.confianca) == ("HUMANO", "", D("0"))
    assert (l.tipo_pendencia, l.subtipo) == ("EXTRATO_NAO_IDENTIFICADO", "SEM_REGRA")
    assert r.lancamentos.metodo.value_counts().to_dict() == {"REGRA": 183, "HUMANO": 1}


def test_sem_chave_de_api_nao_chama_ia(dados, config, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    extratos = [df.copy() for df in extratos_de(dados)]
    extratos[0].loc[extratos[0].index[0], "descricao"] = "COMPRA DE CAFE"
    r = classificar(extratos, config, dados["plano_contas"], usar_ia=True)
    assert r.lancamentos.iloc[0].metodo == "HUMANO"
    assert any("sem ANTHROPIC_API_KEY" in a for a in r.avisos)
