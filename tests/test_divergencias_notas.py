"""Divergências de taxa e notas a emitir de setembro/2026."""
from decimal import Decimal

import pandas as pd
import pytest

from src import checkout, divergencias, notas, remessa
from src.dinheiro import soma

D = Decimal
CASA, ROTA, BRIDGE, MUNDO_ABERTO = "00520815000100", "95927868000148", "22224579000109", "17217888000111"


@pytest.fixture(scope="session")
def partes(dados, config):
    chk = checkout.calcular(dados["orbe"], dados["taxas"], config, "2026-09")
    rem = remessa.calcular(dados["ponte"], dados["taxas"], config, "2026-09")
    div, rastro_div = divergencias.calcular(chk.linhas, rem.linhas, config)
    nf, rastro_nf, sem_nota = notas.calcular(chk.comissoes, rem.comissoes, chk.rastro, rem.rastro, config, "2026-09")
    return dict(chk=chk, rem=rem, div=div, rastro_div=rastro_div, nf=nf, rastro_nf=rastro_nf, sem_nota=sem_nota)


def test_divergencias_por_lojista(partes):
    div = partes["div"]
    por = div.groupby(["linha_negocio", "cnpj"]).agg(n=("id_saida", "size"), valor=("diferenca_brl", soma))
    assert por.loc[("CHECKOUT", CASA)].tolist() == [118, D("15397.42")]
    assert por.loc[("CHECKOUT", ROTA)].tolist() == [87, D("1546.28")]
    assert por.loc[("CHECKOUT", BRIDGE)].tolist() == [5, D("29.95")]
    assert por.loc[("REMESSA", MUNDO_ABERTO)].tolist() == [23, D("1418.85")]
    assert len(div) == 233 and len(por) == 4
    assert div.id_saida.tolist() == [f"DIV-{i:04d}" for i in range(1, 234)]
    assert (div[div.linha_negocio == "CHECKOUT"].index < div[div.linha_negocio == "REMESSA"].index.min()).all()


def test_divergencia_casa_do_estudante_e_tarifa_zero(partes):
    div = partes["div"]
    casa = div[div.cnpj == CASA]
    assert set(casa.taxa_contratada_pct) == {D("0")} and set(casa.tipo_pendencia) == {"TARIFA_ZERO_COBRADA"}
    assert set(casa.regra_id) == {"X-01"}
    assert "TX88445133" not in set(casa.ref_origem)     # estorno de agosto: 1,49% contratado = 1,49% aplicado
    # a Orbe cobrou 15.396,77 (truncado); a divergência por linha HALF_UP soma 15.397,42: 0,65 de truncamento
    assert soma(casa.diferenca_brl) - D("15396.77") == D("0.65")


def test_divergencia_rota_e_bridge(partes):
    div = partes["div"]
    rota = div[div.cnpj == ROTA]
    assert set(rota.tipo_pendencia) == {"DIVERGENCIA_TAXA"}
    assert set((rota.taxa_aplicada_pct - rota.taxa_contratada_pct)) == {D("0.50")}
    assert rota.data.min() == pd.Timestamp("2026-09-12") and set(rota.produto) == {"CREDITO A VISTA", "CREDITO PARCELADO"}
    assert (rota.diferenca_brl < 0).sum() == 4 and (rota.diferenca_brl > 0).sum() == 83  # 4 estornos, sinal negativo
    bridge = div[div.cnpj == BRIDGE]
    assert bridge.data.min() == pd.Timestamp("2026-09-15") and bridge.data.max() == pd.Timestamp("2026-09-18")
    assert set(bridge.taxa_contratada_pct) == {D("2.19")} and set(bridge.taxa_aplicada_pct) == {D("2.59")}


def test_divergencia_remessa_usa_coluna_spread_pct(partes):
    ma = partes["div"][partes["div"].cnpj == MUNDO_ABERTO]
    assert set(ma.taxa_contratada_pct) == {D("1.2")}
    assert (ma.taxa_aplicada_pct > D("1.49")).all() and (ma.taxa_aplicada_pct < D("1.51")).all()
    assert (ma.ref_origem.str.startswith("PC-")).all()


def test_rastro_das_divergencias(partes):
    div, rastro = partes["div"], partes["rastro_div"]
    assert len(rastro) == len(div) and (rastro.valor.values == div.diferenca_brl.values).all()
    assert set(rastro.id_saida) == set(div.id_saida)


def test_notas(partes):
    nf, sem_nota = partes["nf"], partes["sem_nota"]
    chk = nf[nf.linha_negocio == "CHECKOUT"]
    rem = nf[nf.linha_negocio == "REMESSA"]
    assert len(chk) == 20 and len(rem) == 1 and nf.id_saida.tolist() == [f"NF-{i:04d}" for i in range(1, 22)]
    assert soma(chk.valor_brl) == D("207039.73") + D("5.50")   # todos menos a Casa (-5,50)
    assert CASA not in set(chk.tomador_cnpj)
    assert len(sem_nota) == 1 and sem_nota.iloc[0].cnpj == CASA and sem_nota.iloc[0].comissao_brl == D("-5.50")
    r = rem.iloc[0]
    assert (r.tomador_cnpj, r.tomador, r.valor_brl) == ("75374179000146", "Ponte Câmbio S.A.", D("39543.45"))
    assert r.discriminacao == "Intermediação de câmbio - participação no spread - competência 09/2026"
    assert chk.iloc[0].discriminacao == "Intermediação de pagamentos - MDR e antecipação - competência 09/2026"
    assert nf.tomador_cnpj.str.fullmatch(r"\d{14}").all()


def test_rastro_das_notas_sao_as_transacoes(partes):
    nf, rastro = partes["nf"], partes["rastro_nf"]
    por_id = rastro.groupby("id_saida")["valor"].apply(soma)
    for r in nf.itertuples():
        assert por_id[r.id_saida] == r.valor_brl
    rem_id = nf[nf.linha_negocio == "REMESSA"].id_saida.iloc[0]
    assert (rastro[rastro.id_saida == rem_id].ref_origem.str.startswith("PC-")).all()
    assert len(rastro[rastro.id_saida == rem_id]) == 228
    assert len(rastro) == 228 + (1886 - 119)   # Casa (119 linhas) não tem nota
