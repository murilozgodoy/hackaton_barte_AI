"""Totais conhecidos do pacote de setembro/2026, conferidos de forma independente na Fase 0."""
from decimal import ROUND_DOWN, Decimal

import pandas as pd

from src.validacao import validar_leitores

D = Decimal


def _soma(s):
    return sum(s, D("0"))


# ---------------------------------------------------------------- Orbe

def test_orbe_contagens(dados):
    o = dados["orbe"]
    assert len(o) == 1943
    assert o["tipo_lancamento"].value_counts().to_dict() == {
        "VENDA": 1840, "ESTORNO": 59, "ANTECIPACAO": 38, "REVERSAO ANTECIPACAO": 6}
    assert o["cod_estabelecimento"].nunique() == 22
    assert o["nome_estabelecimento"].nunique() == 31


def test_orbe_somas_por_tipo(dados):
    o = dados["orbe"]
    bruto = o.groupby("tipo_lancamento")["valor_bruto"].apply(_soma).to_dict()
    assert bruto == {"VENDA": D("6549199.22"), "ESTORNO": D("-216346.03"),
                     "ANTECIPACAO": D("1451981.71"), "REVERSAO ANTECIPACAO": D("-288606.34")}
    taxa = o.groupby("tipo_lancamento")["valor_taxa"].apply(_soma).to_dict()
    assert taxa == {"VENDA": D("214558.33"), "ESTORNO": D("-7108.69"),
                    "ANTECIPACAO": D("30491.41"), "REVERSAO ANTECIPACAO": D("-6060.69")}


def test_orbe_trunca_valor_taxa_em_todas_as_linhas(dados):
    o = dados["orbe"]
    trunc = [(b * t / 100).quantize(D("0.01"), rounding=ROUND_DOWN) for b, t in zip(o.valor_bruto, o.taxa_aplicada_pct)]
    assert all(a == b for a, b in zip(trunc, o.valor_taxa))


def test_orbe_campos_e_rastro(dados):
    o = dados["orbe"]
    primeira = o.iloc[0]
    assert (primeira.ref_origem, primeira.linha_arquivo) == ("TX88410932", 2)
    assert primeira.data_movimento == pd.Timestamp("2026-09-01")
    assert primeira.valor_bruto == D("608.88") and primeira.taxa_aplicada_pct == D("2.69")
    ant = o[o.tipo_lancamento == "ANTECIPACAO"]
    assert ant["modalidade"].isna().all() and ant["qtd_parcelas"].isna().all()
    est = o[o.tipo_lancamento == "ESTORNO"]
    assert est["id_referencia"].notna().all() and est["data_venda_original"].notna().all()
    assert (~est["id_referencia"].isin(o["id_transacao"])).sum() == 9  # vendas de agosto
    assert (est["data_venda_original"].dt.month == 8).sum() == 9


# ---------------------------------------------------------------- Taxas

def _taxa(t, cnpj, produto, parcelas=None, vig_de=None):
    sel = t[(t.cnpj == cnpj) & (t.produto == produto)]
    if parcelas is not None:
        sel = sel[(sel.parcelas_de <= parcelas) & (sel.parcelas_ate >= parcelas)]
    if vig_de is not None:
        sel = sel[sel.vigencia_de == pd.Timestamp(vig_de)]
    assert len(sel) == 1, sel
    return sel.iloc[0]


def test_taxas_estrutura(dados):
    t = dados["taxas"]
    assert t["linha_planilha"].nunique() == 25 and t["cnpj"].nunique() == 24
    assert t.attrs["linha_cabecalho"] == 5
    assert [i["linha"] for i in t.attrs["linhas_ignoradas"]] == [32]  # nota de rodapé
    assert set(t["produto"]) == {"DEBITO", "CREDITO A VISTA", "CREDITO PARCELADO", "PIX",
                                 "ANTECIPACAO", "SPREAD REMESSA"}
    parc = t[t.produto == "CREDITO PARCELADO"][["parcelas_de", "parcelas_ate"]].drop_duplicates()
    assert sorted(map(tuple, parc.to_numpy().tolist())) == [(2, 6), (7, 12)]


def test_taxas_aba_antiga_ignorada(dados):
    assert "39566044000119" not in set(dados["taxas"]["cnpj"])  # Atlas só existe na aba antiga


def test_taxas_bridge_duas_vigencias(dados):
    t = dados["taxas"]
    bridge = t[(t.cnpj == "22224579000109") & (t.produto == "CREDITO A VISTA")].sort_values("linha_planilha")
    assert bridge["taxa_pct"].tolist() == [D("2.59"), D("2.19")]
    assert pd.isna(bridge.iloc[0].vigencia_de) and bridge.iloc[0].vigencia_ate == pd.Timestamp("2026-09-14")
    assert bridge.iloc[1].vigencia_de == pd.Timestamp("2026-09-15") and pd.isna(bridge.iloc[1].vigencia_ate)


def test_taxas_formatos_mistos(dados):
    t = dados["taxas"]
    assert _taxa(t, "23109187000161", "CREDITO PARCELADO", 3).taxa_pct == D("3.09")  # texto "3,09%"
    assert _taxa(t, "03229837000103", "PIX").taxa_pct == D("0.79")                 # CNPJ int 13 dígitos
    assert _taxa(t, "08780784000120", "CREDITO PARCELADO", 4).taxa_pct == D("2.99")
    assert _taxa(t, "85694108000184", "DEBITO").taxa_pct == D("1.39")
    assert _taxa(t, "16181276000153", "CREDITO PARCELADO", 10).taxa_pct == D("3.49")
    canguru = _taxa(t, "53857560000123", "SPREAD REMESSA")
    assert (canguru.taxa_pct, canguru.taxa_situacao) == (None, "PADRAO")
    assert _taxa(t, "17217888000111", "SPREAD REMESSA").taxa_pct == D("1.2")
    assert _taxa(t, "68567965000102", "SPREAD REMESSA").taxa_situacao == "VALOR"
    assert _taxa(t, "34671260000100", "SPREAD REMESSA").taxa_pct == D("1.5")
    assert _taxa(t, "78576234000179", "PIX").taxa_situacao == "VALOR"


def test_taxas_lojistas_so_remessa_e_inativo(dados):
    t = dados["taxas"]
    ponte_aerea = t[t.cnpj == "95739378000118"]
    assert (ponte_aerea[ponte_aerea.produto != "SPREAD REMESSA"].taxa_situacao == "VAZIO").all()
    assert _taxa(t, "14760206000124", "SPREAD REMESSA").taxa_pct == D("1.25")
    globo = t[t.cnpj == "22348118000148"].iloc[0]
    assert pd.isna(globo.vigencia_de) and globo.obs == "INATIVO desde jul/26"
    sem_ec = set(t[t.ec_orbe.isna()].cnpj)
    assert {"78576234000179", "07752116000126", "66564512000199"} <= sem_ec


# ---------------------------------------------------------------- Ponte

def test_ponte_totais(dados):
    p = dados["ponte"]
    assert len(p) == 233 and p["num_operacao"].nunique() == 232
    assert _soma(p.spread_brl) == D("78073.59")
    assert p.attrs["totais_declarados"] == {"TOTAL DE OPERACOES:": D(233), "SPREAD TOTAL R$:": D("78073.59")}
    neg = p[p.spread_brl < 0]
    assert len(neg) == 4 and _soma(neg.spread_brl) == D("-1834.05")
    assert (neg.observacao == "Taxa travada no pedido (D-1)").all()


def test_ponte_campos(dados):
    p = dados["ponte"]
    assert p["cnpj"].str.fullmatch(r"\d{14}").all()
    assert p["cnpj_original"].astype(str).str.contains("/").sum() == 70
    dup = p[p.num_operacao == "PC-0926-0162"]
    assert dup["observacao"].tolist() == [None, "reprocessada"]
    op = p[p.num_operacao == "PC-0926-0002"].iloc[0]
    assert (op.spread_brl, op.spread_frac, op.spread_pct) == (D("262.01"), D("0.01501"), D("1.501"))
    assert (op.ptax, op.valor_me) == (D("3.2311"), D("5402.22"))
    assert (p.data_contratacao.dt.month == 9).all()
    assert (p.data_liquidacao.dt.month == 10).sum() == 6
    assert set(p.status_compliance) == {"APROVADO", "APROVADO C/ RESSALVA"}
    # corpo do e-mail: data de repasse e prazo de contestação (nunca ficam fixos em regra)
    from datetime import date
    assert p.attrs["data_repasse"] == date(2026, 10, 6) and p.attrs["prazo_dias_uteis"] == 5
    assert p.attrs["data_envio"] == date(2026, 10, 2) and "pontecambio" in p.attrs["remetente"]


# ---------------------------------------------------------------- Plano de contas

def test_plano_contas(dados):
    pc = dados["plano_contas"].set_index("cod_conta")
    assert len(pc) == 52 and pc["aceita_lancto"].sum() == 32
    assert pc.loc["1.1.01.002", "descricao"] == "Banco Meridiano C/C 90233-5 (Câmbio)"
    assert pc.loc["3.1.02", "descricao"] == "Receita de antecipação"
    assert not pc.loc["1.1.03", "aceita_lancto"] and pc.loc["1.1.03.001", "aceita_lancto"]


# ---------------------------------------------------------------- Extratos

def test_aurora(dados):
    a = dados["aurora"].set_index("ref_origem")
    assert len(a) == 84 and a.index[0] == "L9" and a.index[-1] == "L92"
    assert dados["aurora"].attrs["saldo_anterior"] == {"valor": D("612334.81"), "linha": 8,
                                                      "data": pd.Timestamp("2026-08-31").date()}
    assert dados["aurora"].attrs["saldo_final"] == {"valor": D("-1920088.60"), "linha": 94}
    assert _soma(a.valor) == D("-2532423.41")
    assert a.loc["L50", "valor"] == D("7350.00") and "SEM IDENTIFICACAO" in a.loc["L50", "descricao"]
    assert a.loc["L65", "valor"] == D("12400.00")
    assert a.loc["L92", "valor"] == D("-300000.00")
    assert a.loc["L53", "descricao"] == "PIX ENVIADO CONTABILIDADE EXATA LTDA"
    assert a.loc["L21", "descricao"] == "PIX ENVIADO ANDES EXPEDICÕES LTDA"  # grafia do próprio banco


def test_meridiano(dados):
    m = dados["meridiano"].set_index("ref_origem")
    assert len(m) == 100 and _soma(m.valor) == D("1116335.23")
    assert dados["meridiano"].attrs["saldo_final"] == D("1320453.26")
    assert m.loc["MRD2026090132", "valor"] == D("61884.12")
    assert m.loc["MRD2026090586", "descricao"] == "IOF S/ OPERACAO CREDITO"
    assert m.loc["MRD2026090008", "descricao"] == "PIX RECEB MUNDO ABERTO INTERCÂMBIO"
    assert m.loc["MRD2026090425", "descricao"] == "PIX RECEB PONTE AEREA ESTUDANTIL L"
    assert m.loc["MRD2026090082", "descricao"] == "PIX RECEB PONTE AÉREA ESTUDANTIL L"


# ---------------------------------------------------------------- Checagens de toda execução

def test_validacao_dos_leitores_sem_erro(dados):
    falhas = [c for c in validar_leitores(dados) if c.nivel == "ERRO" and not c.ok]
    assert falhas == []
