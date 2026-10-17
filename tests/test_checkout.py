"""Comissão de checkout de setembro/2026, conferida contra a origem."""
from decimal import Decimal

import pandas as pd
import pytest

from src.checkout import calcular
from src.dinheiro import soma
from src.validacao import checar_rastro

D = Decimal
BRIDGE, CASA, OXFORD, ATLAS_EC = "22224579000109", "00520815000100", "23109187000161", "1076801732"


@pytest.fixture(scope="session")
def chk(dados, config):
    return calcular(dados["orbe"], dados["taxas"], config, "2026-09")


def _linha(chk, id_transacao):
    sel = chk.linhas[chk.linhas.id_transacao == id_transacao]
    assert len(sel) == 1
    return sel.iloc[0]


def _comissao(chk, cnpj):
    sel = chk.comissoes[chk.comissoes.cnpj == cnpj]
    assert len(sel) == 1
    return sel.iloc[0]


def test_toda_linha_tem_um_destino(chk, dados):
    assert len(chk.linhas) == len(dados["orbe"]) == 1943
    assert chk.linhas["destino"].value_counts().to_dict() == {"COMISSAO": 1886, "EXCLUIDO": 57}
    excluidas = chk.linhas[chk.linhas.destino == "EXCLUIDO"]
    assert set(excluidas.cod_estabelecimento) == {ATLAS_EC}
    assert set(excluidas.destino_regra) == {"E-01"} and set(excluidas.tipo_pendencia) == {"SEM_CONTRATO"}


def test_total_e_lojistas(chk):
    assert len(chk.comissoes) == 21            # 22 ECs na Orbe, menos a Atlas
    assert soma(chk.comissoes.comissao_brl) == D("207039.73")
    assert chk.comissoes.id_saida.tolist() == [f"COM-CHK-{i:04d}" for i in range(1, 22)]
    assert (chk.comissoes.linha_negocio == "CHECKOUT").all()
    assert chk.comissoes.cnpj.str.fullmatch(r"\d{14}").all()


def test_bridge_duas_vigencias(chk):
    assert _comissao(chk, BRIDGE).comissao_brl == D("11916.02")
    avista = chk.linhas[(chk.linhas.cnpj == BRIDGE) & (chk.linhas.produto == "CREDITO A VISTA")
                        & (chk.linhas.tipo_lancamento == "VENDA")]
    antes = avista[avista.data_taxa <= "2026-09-14"]
    depois = avista[avista.data_taxa >= "2026-09-15"]
    assert len(antes) == 8 and set(antes.taxa_contratada_pct) == {D("2.59")}
    assert set(antes.regra_id) == {"planilha:Taxas vigentes!E6"}
    assert len(depois) == 14 and set(depois.taxa_contratada_pct) == {D("2.19")}
    assert set(depois.regra_id) == {"planilha:Taxas vigentes!E7"}
    # a Orbe só passou a aplicar 2,19% em 19/09: antes disso cobrou 2,59% (divergência, Fase 4)
    assert (depois.taxa_aplicada_pct == D("2.59")).sum() == 5
    # as outras faixas não mudaram e usam a linha nova depois de 15/09
    deb = chk.linhas[(chk.linhas.cnpj == BRIDGE) & (chk.linhas.produto == "DEBITO") & (chk.linhas.data_taxa >= "2026-09-15")]
    assert set(deb.regra_id) == {"planilha:Taxas vigentes!D7"} and set(deb.taxa_contratada_pct) == {D("1.49")}


def test_casa_do_estudante_isencao_e_estorno_de_agosto(chk):
    casa = chk.linhas[chk.linhas.cnpj == CASA]
    assert len(casa) == 119 and (casa.destino == "COMISSAO").all()
    set_ = casa[casa.data_taxa >= "2026-09-01"]
    assert (set_.comissao_brl == 0).all() and set(set_.regra_id) == {"X-01"}
    assert set(set_.taxa_contratada_pct) == {D("0")}
    estorno = _linha(chk, "TX88445133")
    assert estorno.tipo_lancamento == "ESTORNO" and estorno.produto == "DEBITO"
    assert estorno.data_movimento == pd.Timestamp("2026-09-07") and estorno.data_taxa == pd.Timestamp("2026-08-21")
    assert estorno.regra_id == "planilha:Taxas vigentes!D13" and estorno.taxa_contratada_pct == D("1.49")
    assert estorno.comissao_brl == D("-5.50")          # -369,39 x 1,49% = -5,5039
    assert _comissao(chk, CASA).comissao_brl == D("-5.50")
    # o que a Orbe cobrou: 15.396,77 nas linhas de setembro menos 5,50 do estorno da venda de agosto
    assert _comissao(chk, CASA).taxa_cobrada_orbe_brl == D("15391.27")
    assert soma(set_.valor_taxa_orbe) == D("15396.77")


def test_oxford_com_estorno_de_venda_de_agosto(chk):
    est = _linha(chk, "TX88444848")
    assert est.tipo_lancamento == "ESTORNO" and est.produto == "CREDITO PARCELADO" and est.qtd_parcelas == 10
    assert est.data_movimento == pd.Timestamp("2026-09-01") and est.data_taxa == pd.Timestamp("2026-08-22")
    assert est.id_referencia == "TX87651902"            # venda que não está no arquivo de setembro
    assert est.taxa_contratada_pct == D("3.79") and est.regra_id == "planilha:Taxas vigentes!G20"
    assert est.comissao_brl == D("-83.12")              # -2193,16 x 3,79% = -83,1208
    assert est.destino == "COMISSAO"                    # abate em setembro
    assert _comissao(chk, OXFORD).comissao_brl == D("16077.90")
    assert _comissao(chk, OXFORD).qtd_transacoes == 98


def test_antecipacao_e_reversao(chk):
    ant = _linha(chk, "AN88445076")   # Kiwi, antecipação de 04/09
    rev = _linha(chk, "AN88445093")   # reversão de 05/09 da mesma antecipação
    assert ant.produto == rev.produto == "ANTECIPACAO"
    assert ant.taxa_contratada_pct == rev.taxa_contratada_pct == D("2.1")
    assert rev.data_taxa == pd.Timestamp("2026-09-04") and rev.id_referencia == "AN88445076"
    assert ant.comissao_brl == D("1098.60") and rev.comissao_brl == D("-1098.60")  # 52314,21 x 2,10% = 1098,598
    assert ant.valor_taxa_orbe == D("1098.59")  # a Orbe truncou; a Tarvo arredonda


def test_half_up_por_linha_difere_da_orbe(chk):
    """Nas linhas em que a taxa contratada é a mesma que a aplicada, a diferença para o
    valor_taxa da Orbe só pode ser o centavo de truncamento, nunca mais que isso."""
    iguais = chk.linhas[(chk.linhas.destino == "COMISSAO")
                        & (chk.linhas.taxa_contratada_pct == chk.linhas.taxa_aplicada_pct)]
    dif = (iguais.comissao_brl - iguais.valor_taxa_orbe).map(abs)
    assert len(iguais) > 1500 and (dif <= D("0.01")).all() and (dif == D("0.01")).sum() > 400


def test_rastro_fecha_com_a_comissao(chk):
    assert len(chk.rastro) == 1886
    checagens = checar_rastro({"comissoes_por_lojista.csv": (chk.comissoes, "comissao_brl")}, chk.rastro)
    assert all(c.ok for c in checagens), [c.detalhe for c in checagens if not c.ok]
    por_id = chk.rastro.groupby("id_saida")["valor"].apply(soma)
    for r in chk.comissoes.itertuples():
        assert por_id[r.id_saida] == r.comissao_brl
    assert set(chk.rastro.columns) >= {"id_saida", "arquivo_origem", "ref_origem", "valor", "regra_id", "taxa_pct"}
    assert chk.rastro.regra_id.notna().all() and chk.rastro.taxa_pct.notna().all()
    assert (chk.rastro.arquivo_origem == "01_orbe_relatorio_comissoes_set2026.csv").all()


def test_checagem_1_detecta_rastro_adulterado(chk):
    rastro = chk.rastro.copy()
    rastro.loc[rastro.index[0], "valor"] = rastro.loc[rastro.index[0], "valor"] + D("0.01")
    checagens = checar_rastro({"comissoes_por_lojista.csv": (chk.comissoes, "comissao_brl")}, rastro)
    falhas = [c for c in checagens if not c.ok]
    assert len(falhas) == 1 and "não batem" in falhas[0].detalhe


def test_ec_desconhecido_vira_cadastro_e_nao_quebra(dados, config):
    orbe = dados["orbe"].copy()
    alvo = orbe.cod_estabelecimento == "1074504011"       # troca o EC da Rota por um desconhecido
    orbe.loc[alvo, "cod_estabelecimento"] = "9999999999"
    r = calcular(orbe, dados["taxas"], config, "2026-09")
    sem = r.linhas[r.linhas.destino == "SEM_CADASTRO"]
    assert len(sem) == alvo.sum() == 159
    assert set(sem.tipo_pendencia) == {"CADASTRO"} and set(sem.subtipo) == {"EC_ORBE"}
    assert "9999999999" in sem.motivo.iloc[0] and "ROTA GLOBAL" in sem.motivo.iloc[0]
    assert len(r.comissoes) == 20 and "95927868000148" not in set(r.comissoes.cnpj)
    assert soma(r.comissoes.comissao_brl) == D("207039.73") - D("15621.27")


def test_linha_fora_da_competencia(dados, config):
    orbe = dados["orbe"].copy()
    orbe.loc[orbe.index[0], "data_movimento"] = pd.Timestamp("2026-10-01")
    r = calcular(orbe, dados["taxas"], config, "2026-09")
    assert r.linhas.iloc[0].destino == "FORA_COMPETENCIA" and r.linhas.iloc[0].tipo_pendencia == "FORA_COMPETENCIA"
    assert (r.linhas.destino == "COMISSAO").sum() == 1885


def test_sem_taxa_contratada_vira_cadastro(dados, config):
    taxas = dados["taxas"]
    taxas2 = taxas[~((taxas.cnpj == OXFORD) & (taxas.produto == "PIX"))]   # some a taxa Pix da Oxford
    r = calcular(dados["orbe"], taxas2, config, "2026-09")
    sem = r.linhas[r.linhas.destino == "SEM_TAXA"]
    assert len(sem) > 0 and set(sem.cnpj) == {OXFORD} and set(sem.produto) == {"PIX"}
    assert set(sem.tipo_pendencia) == {"CADASTRO"} and set(sem.subtipo) == {"TAXA_NAO_CADASTRADA"}
    assert "nenhuma taxa contratada vigente" in sem.motivo.iloc[0]
