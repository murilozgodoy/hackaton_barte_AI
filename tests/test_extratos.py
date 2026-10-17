"""Classificação dos extratos de setembro/2026 e detecção de transferência em trânsito."""
from decimal import Decimal

import pandas as pd
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


# ---------------------------------------------------------------- A0.7: provisões de QUALQUER mês (Helena 17/10 09h48: "Sempre")

def test_nenhuma_regra_classificar_conta_depende_do_mes(config):
    """Folha, ISS, INSS, FGTS, DARFs e repasse da Ponte são provisionados todo mês e pagos no seguinte:
    nenhum `contem` pode ter mês, ano ou data, senão a regra só casaria o mês do exemplo."""
    import re
    padrao = re.compile(r"\d{2}/\d{4}|\b20\d{2}\b|\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[A-Z]*\b")
    ofensas = [(r.id, alt) for r in config.todas if r.tipo == "CLASSIFICAR_CONTA"
               for alt in r.params["contem_alternativas"] if padrao.search(alt)]
    assert ofensas == []


@pytest.mark.parametrize("de, para", [("08/2026", "09/2026"), ("08/2026", "10/2026"), ("08/2026", "01/2027"),
                                      ("09/2026", "12/2026")])
def test_lancamentos_provisionados_caem_na_mesma_conta_em_qualquer_mes(dados, config, de, para):
    extratos = [df.copy() for df in extratos_de(dados)]
    base = classificar(extratos, config, dados["plano_contas"], usar_ia=False).lancamentos.set_index("ref_origem")
    trocados = []
    for df in extratos:
        tem = df["descricao"].str.contains(de, regex=False)
        trocados += df.loc[tem, "ref_origem"].tolist()
        df["descricao"] = df["descricao"].str.replace(de, para, regex=False)
    assert trocados, f"nenhuma descrição com {de}"
    novo = classificar(extratos, config, dados["plano_contas"], usar_ia=False).lancamentos.set_index("ref_origem")
    for ref in trocados:
        assert (novo.loc[ref, "conta_codigo"], novo.loc[ref, "regra_id"]) == (base.loc[ref, "conta_codigo"], base.loc[ref, "regra_id"]), ref
        assert novo.loc[ref, "metodo"] == "REGRA"
    assert (novo.conta_codigo == base.conta_codigo).all() and (novo.regra_id == base.regra_id).all()


def test_provisoes_vao_para_a_conta_da_obrigacao_e_nao_para_despesa(ext):
    """O pagamento do mês seguinte baixa a provisão (conta 2.x), não vira despesa de novo (4.x)."""
    lanc = ext.lancamentos.set_index("ref_origem")
    for ref in ("L15", "L42", "L54", "L55", "L57", "L86", "L87"):     # folha, ISS, INSS, FGTS, IRRF, PIS, COFINS
        assert lanc.loc[ref, "conta_codigo"].startswith("2.1.0"), (ref, lanc.loc[ref, "conta_codigo"])
    assert lanc.loc["MRD2026090132", "conta_codigo"] == "1.1.03.002"   # repasse da Ponte: baixa do a receber provisionado


# ---------------------------------------------------------------- competência dos extratos (extrato de outro mês)

def _deslocar(df, meses: int, so_primeiras: int | None = None):
    novo = df.copy()
    sel = novo.index[:so_primeiras] if so_primeiras else novo.index
    novo.loc[sel, "data"] = novo.loc[sel, "data"] + pd.DateOffset(months=meses)
    novo.attrs = dict(df.attrs)
    return novo


def test_extrato_inteiro_de_outro_mes_e_erro(dados):
    """Os dois bancos em outubro com a competência de setembro: ERRO ("o extrato X é de outro mês"), nunca sucesso."""
    from src.validacao import checar_competencia_extratos
    c = checar_competencia_extratos([_deslocar(dados["aurora"], 1), _deslocar(dados["meridiano"], 1)], "2026-09")
    assert [(x.fonte, x.ok, x.nivel) for x in c] == [("AURORA", False, "ERRO"), ("MERIDIANO", False, "ERRO")]
    assert "é de outro mês" in c[0].detalhe and "05a_extrato_banco_aurora" in c[0].detalhe and "2026-10-01" in c[0].detalhe
    ok = checar_competencia_extratos(extratos_de(dados), "2026-09")
    assert all(x.ok for x in ok) and [x.detalhe for x in ok] == ["84 lançamentos em 2026-09", "100 lançamentos em 2026-09"]


def test_algumas_linhas_fora_da_competencia_e_aviso_persistido(dados):
    """Parte do extrato fora do mês: classifica normalmente, mais AVISO com banco, quantidade e período, que entra em
    Fechamento.avisos (resumo.json e seção Avisos do relatório) com a ação esperada."""
    from src.validacao import avisos_dos_leitores, checar_competencia_extratos
    c = checar_competencia_extratos([_deslocar(dados["aurora"], -1, so_primeiras=3), dados["meridiano"]], "2026-09")
    assert (c[0].fonte, c[0].ok, c[0].nivel) == ("AURORA", False, "AVISO") and c[1].ok
    assert c[0].detalhe.startswith("3 de 84 lançamentos do AURORA (05a_extrato_banco_aurora_cc4471_set2026.csv) fora de 2026-09, de 2026-08-01 a 2026-08-02")
    avisos = avisos_dos_leitores(c)
    assert len(avisos) == 1 and avisos[0].startswith("AURORA: lançamentos na competência (3 de 84") and "Ação: conferir se o extrato é do mês certo" in avisos[0]
