"""Robustez para outubro: casos sintéticos que rodam sem o data pack, e caminhos de falha das checagens."""
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src import checkout, divergencias, remessa
from src.dinheiro import soma
from src.fechamento import executar
from src.validacao import checar_destinos, checar_lancamentos, checar_notas, checar_saldo_extratos
from tests.sintetico import (CASA, EC_A, EC_B, LOJA_A, LOJA_B, config_para, linha_orbe, operacao_ponte, orbe_df,
                             ponte_df, regras_copia, taxas_padrao)

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg(tmp_path):
    return config_para(regras_copia(tmp_path), taxas_padrao())


# ---------------------------------------------------------------- (a) taxa vigente por data

def test_taxa_vigente_pela_data_da_venda_inclusiva_nas_duas_pontas(cfg):
    orbe = orbe_df([
        linha_orbe(1, "2026-09-14", EC_A, "LOJA A", "1000.00", "2.59"),
        linha_orbe(2, "2026-09-15", EC_A, "LOJA A", "1000.00", "2.59"),   # Orbe ainda cobrou a taxa velha
        linha_orbe(3, "2026-09-20", EC_A, "LOJA A", "1000.00", "2.19"),
    ])
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    assert r.linhas.taxa_contratada_pct.tolist() == [D("2.59"), D("2.19"), D("2.19")]
    assert r.linhas.regra_id.tolist() == ["planilha:Taxas vigentes!E6", "planilha:Taxas vigentes!E7", "planilha:Taxas vigentes!E7"]
    assert r.linhas.comissao_brl.tolist() == [D("25.90"), D("21.90"), D("21.90")]
    div = divergencias.calcular(r.linhas, pd.DataFrame(columns=["destino", "diferenca_brl"]), cfg).divergencias
    assert div.ref_origem.tolist() == ["TX000002"] and div.diferenca_brl.tolist() == [D("4.00")]


def test_venda_antes_de_qualquer_vigencia_vira_cadastro(cfg):
    orbe = orbe_df([linha_orbe(1, "2026-09-02", EC_A, "LOJA A", "100.00", "2.59", tipo="ESTORNO",
                               data_venda="2025-12-31", ref="TXANTIGA")])
    orbe.loc[0, "valor_bruto"] = D("-100.00")
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    l = r.linhas.iloc[0]
    assert (l.destino, l.tipo_pendencia, l.subtipo) == ("SEM_TAXA", "CADASTRO", "TAXA_NAO_CADASTRADA")
    assert "nenhuma taxa contratada vigente" in l.motivo


# ---------------------------------------------------------------- (b) estorno de venda de mês anterior

def test_estorno_de_venda_do_mes_anterior_usa_taxa_da_venda_e_abate_no_mes(cfg):
    orbe = orbe_df([
        linha_orbe(1, "2026-09-03", EC_A, "LOJA A", "-500.00", "2.59", tipo="ESTORNO", ref="TXAGO", data_venda="2026-08-20"),
        linha_orbe(2, "2026-09-20", EC_A, "LOJA A", "-500.00", "2.19", tipo="ESTORNO", ref="TX000003", data_venda="2026-09-16"),
        linha_orbe(3, "2026-09-16", EC_A, "LOJA A", "500.00", "2.19"),
    ])
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    l = r.linhas.set_index("id_transacao")
    assert l.loc["TX000001", "taxa_contratada_pct"] == D("2.59") and l.loc["TX000001", "comissao_brl"] == D("-12.95")
    assert l.loc["TX000001", "data_taxa"] == pd.Timestamp("2026-08-20") and l.loc["TX000001", "destino"] == "COMISSAO"
    assert l.loc["TX000002", "taxa_contratada_pct"] == D("2.19")
    assert r.comissoes.iloc[0].comissao_brl == D("-12.95") + D("-10.95") + D("10.95")


def test_faixas_de_parcelas_e_fora_da_faixa(cfg):
    orbe = orbe_df([
        linha_orbe(1, "2026-09-01", EC_B, "LOJA B", "100.00", "3.00", modalidade="CREDITO PARCELADO", parcelas=6),
        linha_orbe(2, "2026-09-01", EC_B, "LOJA B", "100.00", "4.00", modalidade="CREDITO PARCELADO", parcelas=7),
        linha_orbe(3, "2026-09-01", EC_B, "LOJA B", "100.00", "4.00", modalidade="CREDITO PARCELADO", parcelas=13),
    ])
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    assert r.linhas.taxa_contratada_pct.tolist()[:2] == [D("3.00"), D("4.00")]
    fora = r.linhas.iloc[2]
    assert fora.destino == "SEM_TAXA" and "fora das faixas" in fora.motivo


# ---------------------------------------------------------------- (c) HALF_UP com meio centavo, positivo e negativo

def test_half_up_meio_centavo_no_pipeline(cfg):
    orbe = orbe_df([
        linha_orbe(1, "2026-09-01", EC_B, "LOJA B", "0.50", "1.00", modalidade="DEBITO"),          # 0,005 -> 0,01
        linha_orbe(2, "2026-09-01", EC_B, "LOJA B", "-0.50", "1.00", tipo="ESTORNO", modalidade="DEBITO",
                   ref="TX000001", data_venda="2026-09-01"),                                       # -0,005 -> -0,01
        linha_orbe(3, "2026-09-01", EC_B, "LOJA B", "0.50", "2.00", modalidade="DEBITO"),          # divergência 0,005
    ])
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    assert r.linhas.comissao_brl.tolist() == [D("0.01"), D("-0.01"), D("0.01")]
    assert r.linhas.valor_taxa_orbe.tolist()[0] == D("0.00")   # a Orbe truncou; a Tarvo não
    div = divergencias.calcular(r.linhas, pd.DataFrame(columns=["destino", "diferenca_brl"]), cfg).divergencias
    assert div.diferenca_brl.tolist() == [D("0.01")]


# ---------------------------------------------------------------- (d) duplicata na Ponte

def test_duplicata_identica_conta_uma_vez_e_diferente_fica_fora(cfg):
    ops = [operacao_ponte("PC-1", "2026-09-10", LOJA_B, "LOJA B", "1000", "5.06", "5.0", 6),
           operacao_ponte("PC-1", "2026-09-10", LOJA_B, "LOJA B", "1000", "5.06", "5.0", 7, observacao="reprocessada"),
           operacao_ponte("PC-2", "2026-09-11", LOJA_B, "LOJA B", "1000", "5.06", "5.0", 8),
           operacao_ponte("PC-2", "2026-09-11", LOJA_B, "LOJA B", "1000", "5.07", "5.0", 9)]
    r = remessa.calcular(ponte_df(ops), taxas_padrao(), cfg, "2026-09")
    assert r.linhas.destino.tolist() == ["COMISSAO", "DUPLICATA_IGNORADA", "DUPLICATA_DIVERGENTE", "DUPLICATA_DIVERGENTE"]
    assert r.comissoes.comissao_brl.tolist() == [D("30.00")]   # 60,00 de spread x 50%, uma vez


def test_tolerancia_de_spread_na_borda(cfg):
    # contratado 1,2% (Loja B): 1,21% está na borda (0,01 p.p., não diverge); 1,2101% passa
    ops = [operacao_ponte("PC-1", "2026-09-10", LOJA_B, "LOJA B", "1000", "5.0605", "5.0", 6),
           operacao_ponte("PC-2", "2026-09-10", LOJA_B, "LOJA B", "1000", "5.060505", "5.0", 7)]
    r = remessa.calcular(ponte_df(ops), taxas_padrao(), cfg, "2026-09")
    l = r.linhas.set_index("num_operacao")
    assert l.loc["PC-1", "diferenca_pp"] == D("0.01") and l.loc["PC-1", "diferenca_brl"] is None
    assert l.loc["PC-2", "diferenca_pp"] > D("0.01") and l.loc["PC-2", "diferenca_brl"] is not None


def test_spread_negativo_e_compliance_excluidos_por_regra(cfg):
    ops = [operacao_ponte("PC-1", "2026-09-10", LOJA_B, "LOJA B", "1000", "4.95", "5.0", 6, observacao="Taxa travada"),
           operacao_ponte("PC-2", "2026-09-10", LOJA_B, "LOJA B", "1000", "5.06", "5.0", 7, status="REPROVADO"),
           operacao_ponte("PC-3", "2026-10-01", LOJA_B, "LOJA B", "1000", "5.06", "5.0", 8)]
    r = remessa.calcular(ponte_df(ops), taxas_padrao(), cfg, "2026-09")
    assert r.linhas.destino.tolist() == ["EXCLUIDO", "EXCLUIDO", "FORA_COMPETENCIA"]
    assert r.linhas.destino_regra.tolist()[:2] == ["E-03", "E-04"]
    assert r.linhas.tipo_pendencia.tolist() == ["SPREAD_NEGATIVO", "COMPLIANCE", "FORA_COMPETENCIA"]


# ---------------------------------------------------------------- (e) EC desconhecido não quebra

def test_ec_desconhecido_vira_pendencia_e_os_demais_seguem(cfg):
    orbe = orbe_df([linha_orbe(1, "2026-09-01", "9999999999", "LOJA NOVA LTDA", "1000.00", "2.69"),
                    linha_orbe(2, "2026-09-01", "9999999999", "LOJA NOVA", "500.00", "2.69"),
                    linha_orbe(3, "2026-09-01", EC_B, "LOJA B", "100.00", "2.00")])
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    assert r.linhas.destino.tolist() == ["SEM_CADASTRO", "SEM_CADASTRO", "COMISSAO"]
    assert r.comissoes.cnpj.tolist() == [LOJA_B] and r.comissoes.comissao_brl.tolist() == [D("2.00")]


def test_ec_gravado_como_numero_no_excel_casa(tmp_path):
    taxas = taxas_padrao()
    taxas.loc[taxas.cnpj == LOJA_B, "ec_orbe"] = "2000000002.0"
    cfg = config_para(regras_copia(tmp_path), taxas)
    assert cfg.lojista_por_ec(EC_B).cnpj == LOJA_B


# ---------------------------------------------------------------- (f) datas deslocadas +1 mês e sem mês fixo

def test_fechamento_com_datas_deslocadas_um_mes(dados, config):
    """Outubro: as mesmas linhas, todas as datas +1 mês. Nada pode cair fora da competência por culpa do código."""
    desl = dict(dados)
    for nome, colunas in (("orbe", ["data_movimento", "data_venda_original"]),
                          ("ponte", ["data_contratacao", "data_liquidacao"]),
                          ("aurora", ["data"]), ("meridiano", ["data"])):
        df = dados[nome].copy()
        for c in colunas:
            df[c] = df[c] + pd.DateOffset(months=1)
        df.attrs = dict(dados[nome].attrs)
        desl[nome] = df
    f = executar(desl, config, "2026-10", usar_ia=False)
    assert f.integro and "FORA_COMPETENCIA" not in f.destinos_orbe and "FORA_COMPETENCIA" not in f.destinos_ponte
    assert f.destinos_ponte == {"COMISSAO": 228, "EXCLUIDO": 4, "DUPLICATA_IGNORADA": 1}
    assert soma(f.comissoes_remessa.comissao_brl) == D("39543.45")
    assert "competência 10/2026" in f.notas.discriminacao.iloc[0]
    # Casa do Estudante: isenção vale até dezembro, continua a zero; Bridge: tudo na vigência nova
    assert f.comissoes_checkout.set_index("cnpj").loc[CASA, "comissao_brl"] == D("0.00")


def test_nenhum_mes_nome_de_lojista_conta_ou_cnpj_fixo_no_codigo():
    """P3: regra é dado. Nenhum mês, lojista, conta contábil ou CNPJ pode estar em src/."""
    padrao = re.compile(r"set2026|setembro|2026-09|/09/|\b09\b|Casa do Estudante|Mundo Aberto|Bridge|Atlas|Rota Global|"
                        r"Kiwi|Horizonte|Globo Trotter|\b\d\.\d\.\d\d\.\d{3}\b|\b\d{14}\b", re.I)
    ofensas = []
    for p in (RAIZ / "src").rglob("*.py"):
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if padrao.search(linha):
                ofensas.append(f"{p.name}:{n}: {linha.strip()}")
    assert ofensas == [], ofensas


# ---------------------------------------------------------------- caminhos de falha das checagens 2 a 6

def test_checagens_acusam_saida_adulterada(dados, config):
    f = executar(dados, config, "2026-09", usar_ia=False)
    notas = f.notas.copy()
    notas.loc[notas.index[0], "valor_brl"] = notas.loc[notas.index[0], "valor_brl"] + D("0.01")
    c = checar_notas(f.comissoes_checkout, f.comissoes_remessa, notas)
    assert not c[0].ok and c[1].ok
    notas = f.notas.copy()
    notas.loc[notas.linha_negocio == "REMESSA", "valor_brl"] = D("1.00")
    assert not checar_notas(f.comissoes_checkout, f.comissoes_remessa, notas)[1].ok

    linhas = f.orbe_linhas.iloc[:-1]
    c = checar_destinos(linhas, len(dados["orbe"]), f.ponte_linhas, len(dados["ponte"]))
    assert not c[0].ok and c[2].ok
    ponte = f.ponte_linhas.copy()
    ponte.loc[ponte.index[1], "num_operacao"] = ponte.loc[ponte.index[0], "num_operacao"]
    ponte.loc[ponte.index[1], "destino"] = "EXCLUIDO"   # mesma operação com dois destinos diferentes
    assert not checar_destinos(f.orbe_linhas, len(dados["orbe"]), ponte, len(dados["ponte"]))[2].ok

    lanc = f.lancamentos.iloc[1:]
    c = checar_lancamentos(lanc, [dados["aurora"], dados["meridiano"]])
    assert not c[0].ok and c[1].ok
    aurora = dados["aurora"].copy()
    aurora.attrs = dict(dados["aurora"].attrs)
    aurora.loc[aurora.index[5], "valor"] = aurora.loc[aurora.index[5], "valor"] + D("1.00")
    assert not checar_saldo_extratos([aurora])[0].ok


def test_excesso_contestado_desligado_ponta_a_ponta(dados, tmp_path):
    from tests.sintetico import plano_contas_para  # noqa: F401
    from src.regras import carregar_config
    regras = regras_copia(tmp_path, [("incluir_excesso_contestado=true", "incluir_excesso_contestado=false")])
    cfg = carregar_config(regras, dados["taxas"], dados["plano_contas"], {"AURORA", "MERIDIANO"})
    f = executar(dados, cfg, "2026-09", usar_ia=False)
    assert f.integro
    nf = f.notas[f.notas.linha_negocio == "REMESSA"].iloc[0]
    assert nf.valor_brl == D("39543.45") - D("709.46") == soma(f.comissoes_remessa.comissao_brl)
    exc = f.pendencias[f.pendencias.tipo == "EXCESSO_SPREAD_CONTESTADO"].iloc[0]
    assert "Não entrou na nota" in exc.motivo


def test_tolerancia_de_checkout_editavel(dados, tmp_path):
    from src.regras import carregar_config
    regras = regras_copia(tmp_path, [("tolerancia_taxa_checkout_pp=0;", "tolerancia_taxa_checkout_pp=0.5;")])
    cfg = carregar_config(regras, dados["taxas"], dados["plano_contas"], {"AURORA", "MERIDIANO"})
    f = executar(dados, cfg, "2026-09", usar_ia=False)
    chk = f.divergencias_contrato[f.divergencias_contrato.linha_negocio == "CHECKOUT"]
    # Rota (+0,50 p.p., na borda) e Bridge (+0,40) somem; Casa (2,69 x 0) fica, com natureza DEVOLUCAO_LOJISTA
    # (X-01 divergencia=DEVOLUCAO_LOJISTA): no CSV, marcada, fora da cobrança; pendência com as 118 transações no rastro
    assert chk.empty and set(f.divergencias_fora_contrato.cnpj) == {CASA} and len(f.divergencias_fora_contrato) == 118
    assert set(f.divergencias.cnpj) == {CASA, "17217888000111"}   # só a Casa e a remessa da Mundo Aberto
    assert f.integro


# ---------------------------------------------------------------- A0.5: alerta de antecipação acima das vendas (regra A-01)

def test_alerta_antecipacao_so_para_lojista_sem_historico(tmp_path):
    """Loja B (contrato desde 01/01, ATIVO) antecipa mais do que vendeu: sem alerta, porque antecipa vendas de meses
    anteriores que não estão no arquivo. Loja C (primeira vigência e primeira transação no mês) e a Atlas
    (SEM_CONTRATO) disparam. Rastro = as linhas de antecipação."""
    from datetime import date
    from src import pendencias
    from tests.sintetico import lojista_taxas, taxas_df
    LOJA_C, EC_C, ATLAS, EC_ATLAS = "33333333000153", "2000000003", "39566044000119", "1076801732"
    taxas = taxas_df(*[l for l in [
        lojista_taxas(6, "Loja B", LOJA_B, EC_B, ["1.00", "2.00", "3.00", "4.00", "0.50", "2.00"], vig_de="2026-01-01"),
        lojista_taxas(7, "Loja C", LOJA_C, EC_C, ["1.00", "2.00", "3.00", "4.00", "0.50", "2.00"], vig_de="2026-09-10"),
        lojista_taxas(9, "Casa", CASA, "1018325654", ["1.49", "2.69", "3.19", "3.79", "0.89", "2.10"], vig_de="2026-01-01"),
    ]])
    orbe = orbe_df([
        linha_orbe(1, "2026-09-01", EC_B, "LOJA B", "100.00", "2.00"),
        linha_orbe(2, "2026-09-02", EC_B, "LOJA B", "500.00", "2.00", tipo="ANTECIPACAO"),
        linha_orbe(3, "2026-09-10", EC_C, "LOJA C", "100.00", "2.00"),
        linha_orbe(4, "2026-09-12", EC_C, "LOJA C", "300.00", "2.00", tipo="ANTECIPACAO"),
        linha_orbe(5, "2026-09-13", EC_C, "LOJA C", "250.00", "2.00", tipo="ANTECIPACAO"),
        linha_orbe(6, "2026-09-11", EC_ATLAS, "ATLAS", "50.00", "3.49"),
        linha_orbe(7, "2026-09-15", EC_ATLAS, "ATLAS", "900.00", "2.10", tipo="ANTECIPACAO"),
    ])
    cfg = config_para(regras_copia(tmp_path), taxas)    # cadastro com a Loja C (planilha) e a Atlas (complemento)
    chk = checkout.calcular(orbe, taxas, cfg, "2026-09")
    alertas = pendencias.alertas_antecipacao(chk.linhas, taxas, cfg, date(2026, 9, 1))
    por_cnpj = {a["cnpj"]: a for a in alertas}
    assert set(por_cnpj) == {LOJA_C, ATLAS}
    assert por_cnpj[LOJA_C]["antecipado"] == D("550.00") and por_cnpj[LOJA_C]["vendido"] == D("100.00")
    assert por_cnpj[LOJA_C]["data_estouro"] == date(2026, 9, 12) and por_cnpj[LOJA_C]["motivo_lojista"] == "PRIMEIRO_MES"
    assert por_cnpj[ATLAS]["motivo_lojista"] == "SEM_CONTRATO" and len(por_cnpj[ATLAS]["linhas"]) == 1


# ---------------------------------------------------------------- T3 (Helena à Casa Barton 17/10 11h01): "A gente não vende acima de 12x. Se aparecer, é pendência."

def _pendencias_so_checkout(chk, cfg, ref):
    """Pendências a partir só do checkout (sem Ponte, extratos e conciliação), para testes sintéticos."""
    from src import pendencias, remessa
    vazio_rem = pd.DataFrame(columns=remessa.COLUNAS_LINHAS)
    lanc = pd.DataFrame(columns=["id_saida", "banco", "ref_origem", "data", "descricao", "valor", "conta_codigo", "metodo",
                                 "tipo_pendencia", "subtipo", "motivo", "regra_id", "papel", "arquivo_origem", "conta_descricao"])
    conc = {"remessa_banco": {"recursos_menos_liquidado": D("0"), "qtd_liquidacoes": 0}, "ponte": {"diferenca": None}}
    return pendencias.calcular(ref, chk.linhas, vazio_rem, pd.DataFrame(columns=divergencias.COLUNAS), pd.DataFrame(),
                               chk.rastro, lanc, pd.DataFrame(), conc, pd.DataFrame(columns=["linha_negocio"]), cfg)


def test_parcelado_acima_do_maximo_da_planilha_vira_pendencia_da_helena(cfg):
    from datetime import date
    from src import carteira
    orbe = orbe_df([
        linha_orbe(1, "2026-09-01", EC_B, "LOJA B", "1200.00", "4.00", modalidade="CREDITO PARCELADO", parcelas=12),
        linha_orbe(2, "2026-09-02", EC_B, "LOJA B", "1300.00", "4.50", modalidade="CREDITO PARCELADO", parcelas=13),
        linha_orbe(3, "2026-09-03", "1018325654", "CASA", "1800.00", "3.79", modalidade="CREDITO PARCELADO", parcelas=18),  # X-01 TODOS
        linha_orbe(4, "2026-09-03", EC_B, "LOJA B", "100.00", "2.00"),
    ])
    r = checkout.calcular(orbe, taxas_padrao(), cfg, "2026-09")
    l = r.linhas.set_index("id_transacao")
    assert l.loc["TX000001", "destino"] == "COMISSAO" and l.loc["TX000001", "taxa_contratada_pct"] == D("4.00")
    for tx in ("TX000002", "TX000003"):   # 13x e 18x: nenhuma faixa cobre, nem com TAXA_EXCECAO vigente
        assert l.loc[tx, "destino"] == "SEM_TAXA" and l.loc[tx, "subtipo"] == "PARCELAS_FORA_FAIXA"
        assert "nenhuma taxa contratada para essa quantidade" in l.loc[tx, "motivo"] and l.loc[tx, "comissao_brl"] is None
    assert r.comissoes.set_index("cnpj").loc[LOJA_B, "comissao_brl"] == D("48.00") + D("2.00")
    assert CASA not in set(r.comissoes.cnpj)
    pend = _pendencias_so_checkout(r, cfg, date(2026, 9, 1)).pendencias
    fora = pend[(pend.tipo == "CADASTRO") & (pend.subtipo == "PARCELAS_FORA_FAIXA")]
    assert len(fora) == 2 and set(fora.quem_decide) == {"Helena (Financeiro)"} and set(fora.regra_id) == {"DP-13"}
    assert set(fora.cnpj) == {LOJA_B, CASA} and "não vende acima do máximo" in fora.iloc[0].o_que_fazer
    assert fora.set_index("cnpj").loc[LOJA_B, "valor_brl"] == D("58.50")    # o que a Orbe cobrou (1300 x 4,5%, truncado)
    cart = carteira.montar(r.linhas, "2026-09")
    assert set(cart.ref_origem) == {"TX000002", "TX000003"}   # guardadas para o próximo mês


# ---------------------------------------------------------------- T6 (Helena à Turma do Barulho 17/10 10h44): ajuste da Ponte no relatório do mês seguinte

def _com_ajustes(dados):
    """Setembro mais 1 crédito e 1 débito de ajuste do parceiro (datas de agosto): o crédito pela observação (P-12),
    o débito pelo Nº Operação da contestação anterior (--anterior)."""
    from tests.sintetico import operacao_ponte
    ponte = dados["ponte"].copy()
    base = ponte.iloc[0].to_dict()
    credito = {**base, "num_operacao": "PC-0826-0901", "ref_origem": "PC-0826-0901", "linha_planilha": 900,
               "data_contratacao": pd.Timestamp("2026-08-20"), "data_liquidacao": pd.Timestamp("2026-08-21"),
               "observacao": "AJUSTE - spread negativo revisto (contestação do mês anterior)", "spread_brl": D("687.52"),
               "spread_frac": D("0.01"), "spread_pct": D("1.00"), "cnpj": "95739378000118", "cliente": "PONTE AÉREA ESTUDANTIL"}
    debito = {**base, "num_operacao": "PC-0826-0902", "ref_origem": "PC-0826-0902", "linha_planilha": 901,
              "data_contratacao": pd.Timestamp("2026-08-25"), "data_liquidacao": pd.Timestamp("2026-08-26"),
              "observacao": None, "spread_brl": D("-29.56"), "spread_frac": D("-0.001"), "spread_pct": D("-0.10"),
              "cnpj": "17217888000111", "cliente": "MUNDO ABERTO INTERCÂ"}
    novo = pd.concat([ponte, pd.DataFrame([credito, debito])], ignore_index=True)
    novo.attrs = dict(dados["ponte"].attrs)
    total = dict(novo.attrs["spread_total_declarado"])
    total["valor"] = total["valor"] + D("687.52") - D("29.56")
    novo.attrs["spread_total_declarado"] = total
    anterior = {"PC-0826-0902": {"natureza": "EXCESSO_SPREAD", "pedido": "a", "competencia": "2026-08"}}
    return {**dados, "ponte": novo}, anterior


def test_ajuste_do_parceiro_entra_na_comissao_do_mes_e_vira_pendencia_informativa(dados, config):
    base = executar(dados, config, "2026-09", usar_ia=False)
    com_aj, anterior = _com_ajustes(dados)
    f = executar(com_aj, config, "2026-09", usar_ia=False, contestacao_anterior=anterior)
    assert f.integro and f.destinos_ponte == {"COMISSAO": 228, "EXCLUIDO": 4, "DUPLICATA_IGNORADA": 1, "AJUSTE_PONTE": 2}
    aj = f.ponte_linhas[f.ponte_linhas.destino == "AJUSTE_PONTE"].set_index("num_operacao")
    assert aj.loc["PC-0826-0901", "comissao_brl"] == D("343.76") and aj.loc["PC-0826-0901", "subtipo"] == "CREDITO"
    assert aj.loc["PC-0826-0902", "comissao_brl"] == D("-14.78") and aj.loc["PC-0826-0902", "subtipo"] == "DEBITO"
    assert "FORA_COMPETENCIA" not in set(f.ponte_linhas.destino) and "SPREAD_NEGATIVO" not in set(aj.tipo_pendencia)
    # entra na comissão do lojista e na nota de remessa do mês pelo valor; nada mais muda
    assert soma(f.comissoes_remessa.comissao_brl) == D("39543.45") + D("343.76") - D("14.78")
    assert f.notas[f.notas.linha_negocio == "REMESSA"].valor_brl.iloc[0] == soma(f.comissoes_remessa.comissao_brl)
    assert f.comissoes_remessa.set_index("cnpj").loc["17217888000111", "comissao_brl"] == base.comissoes_remessa.set_index("cnpj").loc["17217888000111", "comissao_brl"] - D("14.78")
    assert f.comissoes_checkout.equals(base.comissoes_checkout)
    p = f.pendencias[f.pendencias.tipo == "CONFERIR_AJUSTE_PONTE"].set_index("ref_origem")
    assert len(p) == 2 and set(p.quem_decide) == {"Helena (Financeiro)"} and p.informativa.all() and set(p.regra_id) == {"DP-14"}
    assert p.loc["PC-0826-0901", "valor_brl"] == D("343.76") and "crédito de R$ 687,52" in p.loc["PC-0826-0901", "motivo"]
    assert "Não consta na contestação do fechamento anterior" in p.loc["PC-0826-0901", "motivo"]
    assert "Corresponde ao pedido a (EXCESSO_SPREAD) da contestação do fechamento anterior (2026-08)" in p.loc["PC-0826-0902", "motivo"]
    assert "débito de -R$ 29,56" in p.loc["PC-0826-0902", "motivo"] and "no mês em que o ajuste apareceu" in p.loc["PC-0826-0902", "motivo"]
    assert soma(f.rastro[f.rastro.id_saida == p.loc["PC-0826-0901", "id_saida"]].valor) == D("343.76")
    # o repasse a conferir não muda: o ajuste está dentro da comissão e do total declarado
    r = f.pendencias[f.pendencias.tipo == "CONFERIR_REPASSE_PONTE"].iloc[0]
    assert r.valor_brl == D("506.65")
    # as demais pendências são as mesmas de setembro
    assert f.pendencias.tipo.value_counts().to_dict() == {**base.pendencias.tipo.value_counts().to_dict(), "CONFERIR_AJUSTE_PONTE": 2}


def test_linha_do_parceiro_sem_numeros_vira_pendencia_e_nao_erro(dados, config):
    ponte = dados["ponte"].copy()
    ruim = {**ponte.iloc[0].to_dict(), "num_operacao": "PC-0926-0999", "ref_origem": "PC-0926-0999", "linha_planilha": 999,
            "valor_me": None, "ptax": None, "spread_brl": None, "spread_frac": None, "spread_pct": None}
    novo = pd.concat([ponte, pd.DataFrame([ruim])], ignore_index=True)
    novo.attrs = dict(dados["ponte"].attrs)
    f = executar({**dados, "ponte": novo}, config, "2026-09", usar_ia=False)
    assert f.integro and f.destinos_ponte["NAO_INTERPRETADA"] == 1
    assert soma(f.comissoes_remessa.comissao_brl) == D("39543.45")
    p = f.pendencias[f.pendencias.tipo == "LINHA_NAO_INTERPRETADA"]
    assert len(p) == 1 and p.iloc[0].quem_decide == "Helena (Financeiro)" and p.iloc[0].valor_brl is None
    assert "sem valor_me, ptax, spread_brl, spread_frac" in p.iloc[0].motivo and "PC-0926-0999" in p.iloc[0].motivo
