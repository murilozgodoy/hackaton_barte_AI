"""Pendências de setembro/2026: cada uma com motivo, dono e rastro que soma o valor."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.cli import main
from src.dinheiro import brl, soma
from src.fechamento import executar

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]
CASA, ROTA, BRIDGE, MA, ATLAS_CNPJ = "00520815000100", "95927868000148", "22224579000109", "17217888000111", "39566044000119"


@pytest.fixture(scope="session")
def fech(dados, config):
    return executar(dados, config, "2026-09", usar_ia=False)


def _por(fech, tipo, subtipo=None):
    p = fech.pendencias
    sel = p[p.tipo == tipo] if subtipo is None else p[(p.tipo == tipo) & (p.subtipo == subtipo)]
    return sel


def test_lista_de_pendencias(fech):
    p = fech.pendencias
    assert p.id_saida.tolist() == [f"PEN-{i:04d}" for i in range(1, len(p) + 1)]
    assert p.tipo.value_counts().to_dict() == {
        "TARIFA_ZERO_COBRADA": 1, "DIVERGENCIA_TAXA": 3, "EXCESSO_SPREAD_CONTESTADO": 1,
        "CONFERIR_REPASSE_PONTE": 1, "SPREAD_NEGATIVO": 4, "SEM_CONTRATO": 1, "SALDO_NEGATIVO_LOJISTA": 1,
        "EXTRATO_NAO_IDENTIFICADO": 1, "DEVOLUCAO": 1, "EM_TRANSITO": 1, "ALERTA_ANTECIPACAO": 1}
    assert p.quem_decide.notna().all() and (p.motivo.str.len() > 40).all()
    assert p.quem_decide.value_counts().to_dict() == {"Helena (Financeiro)": 10, "Helena (Financeiro) + Comercial": 2,
                                                     "Comercial": 1, "Financeiro": 3}
    # a metade do excesso já está na divergência da Mundo Aberto: aparece, mas fora da soma do "em jogo"
    assert p[p.tipo == "EXCESSO_SPREAD_CONTESTADO"].incluida_em.iloc[0] == "DIVERGENCIA_TAXA"
    from src.relatorio import valor_em_jogo
    assert valor_em_jogo(p[p.quem_decide == "Helena (Financeiro)"]) == D("5341.28")
    # informativas (por regra, informativa=true): fora do "em jogo"
    assert set(p[p.informativa].tipo) == {"EM_TRANSITO", "ALERTA_ANTECIPACAO"} and p.informativa.dtype == bool


def test_alerta_antecipacao_so_para_a_atlas(fech):
    """Helena (17/10 09h44, ao Barteman; pergunta do Barteman 09h09): antecipação acima do que o lojista vendeu
    não deveria acontecer; alerta para ela e o Comercial. Por regra A-01, só lojista SEM_CONTRATO ou cuja
    primeira transação é no próprio mês (os outros antecipam vendas de meses anteriores, fora do arquivo)."""
    a = _por(fech, "ALERTA_ANTECIPACAO")
    assert len(a) == 1
    r = a.iloc[0]
    assert (r.cnpj, r.quem_decide, r.regra_id, r.linha_negocio) == (ATLAS_CNPJ, "Helena (Financeiro) + Comercial", "A-01", "CHECKOUT")
    # D1: valor = antecipação acumulada no dia em que passou das vendas (as 4 antecipações de 15/09); informativa
    assert r.valor_brl == D("179592.82") and r.qtd_itens == 4 and r.informativa
    assert r.motivo.startswith("Em 2026-09-15, R$ 179.592,82 antecipados contra R$ 55.357,50 vendidos até a data. "
                               "No mês, R$ 235.943,10 antecipados e R$ 108.712,14 revertidos (líquido R$ 127.230,96) "
                               "contra R$ 135.428,90 vendidos.")
    assert "Alerta de controle, não perda" in r.motivo and "SEM_CONTRATO" in r.motivo
    rastro = fech.rastro[fech.rastro.id_saida == r.id_saida]
    assert len(rastro) == 4 and rastro.ref_origem.str.startswith("AN").all() and soma(rastro.valor) == D("179592.82")


def test_rastro_fecha_para_toda_pendencia_com_valor(fech):
    por_id = fech.rastro.groupby("id_saida")["valor"].apply(soma)
    for r in fech.pendencias.itertuples():
        if r.valor_brl is not None:
            assert por_id[r.id_saida] == r.valor_brl, r.id_saida
    assert all(c.ok for c in fech.checagens), [c.detalhe for c in fech.checagens if not c.ok]


def test_casa_do_estudante_tarifa_zero(fech):
    r = _por(fech, "TARIFA_ZERO_COBRADA").iloc[0]
    assert (r.cnpj, r.valor_brl, r.qtd_itens, r.regra_id) == (CASA, D("15397.42"), 118, "X-01")
    assert r.quem_decide == "Helena (Financeiro) + Comercial"
    assert "cobrou efetivamente R$ 15.396,77" in r.motivo and "R$ 0,65 a menos" in r.motivo and "trunca centavos" in r.motivo
    assert "devolução ao lojista" in r.motivo and "não há o que cobrar da Orbe" in r.motivo
    assert "não chegou à Orbe nem à planilha" in r.motivo and "fora das divergências de contrato" in r.motivo
    assert len(fech.rastro[fech.rastro.id_saida == r.id_saida]) == 118
    assert CASA not in set(fech.divergencias.cnpj)


def test_divergencias_rota_bridge_mundo_aberto(fech):
    d = _por(fech, "DIVERGENCIA_TAXA").set_index("cnpj")
    assert d.loc[ROTA, "valor_brl"] == D("1546.28") and d.loc[ROTA, "qtd_itens"] == 87
    assert "2.49% a 3.59%" in d.loc[ROTA, "motivo"] and "2.99% a 4.09%" in d.loc[ROTA, "motivo"]
    # Helena (17/10 09h44): venda e estorno se anulam; cobra-se só a diferença LÍQUIDA
    rota = fech.divergencias[fech.divergencias.cnpj == ROTA]
    pos, neg = soma(rota.diferenca_brl[rota.diferenca_brl > 0]), soma(rota.diferenca_brl[rota.diferenca_brl < 0])
    assert "valor LÍQUIDO" in d.loc[ROTA, "motivo"] and f"{brl(pos)} a maior em 83 vendas" in d.loc[ROTA, "motivo"]
    assert f"{brl(-neg)} devolvidos em 4 estornos" in d.loc[ROTA, "motivo"] and "diferença líquida" in d.loc[ROTA, "motivo"]
    assert "LÍQUIDO" not in d.loc[BRIDGE, "motivo"]    # sem estorno, nada a explicar
    assert d.loc[BRIDGE, "valor_brl"] == D("29.95") and "2.19%" in d.loc[BRIDGE, "motivo"]
    assert d.loc[MA, "valor_brl"] == D("1418.85") and d.loc[MA, "linha_negocio"] == "REMESSA"
    assert "R$ 709,46" in d.loc[MA, "motivo"] and "entrou na nota" in d.loc[MA, "motivo"]
    assert (d.quem_decide == "Helena (Financeiro)").all()


def test_excesso_contestado(fech):
    r = _por(fech, "EXCESSO_SPREAD_CONTESTADO").iloc[0]
    assert (r.cnpj, r.valor_brl, r.qtd_itens) == (MA, D("709.46"), 23)
    assert "P-05" in r.motivo and "Entrou na nota" in r.motivo


def test_atlas_sem_contrato(fech):
    r = _por(fech, "SEM_CONTRATO").iloc[0]
    assert (r.cnpj, r.valor_brl, r.qtd_itens, r.quem_decide, r.regra_id) == (ATLAS_CNPJ, D("7876.05"), 57, "Comercial", "E-01")
    assert "NÃO é receita da Tarvo" in r.motivo and "0.99% a 4.49%" in r.motivo and "ATLAS IDIOMAS" in r.motivo
    assert "R$ 262.138,61" in r.motivo   # valor bruto das 57 transações


def test_spreads_negativos(fech):
    s = _por(fech, "SPREAD_NEGATIVO")
    assert set(s.ref_origem) == {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"}
    assert soma(s.valor_brl) == D("-1834.05") and (s.quem_decide == "Helena (Financeiro)").all()
    assert "Taxa travada no pedido (D-1)" in s.iloc[0].motivo


def test_saldo_negativo_casa(fech):
    r = _por(fech, "SALDO_NEGATIVO_LOJISTA").iloc[0]
    assert (r.cnpj, r.valor_brl, r.qtd_itens) == (CASA, D("-5.50"), 119)
    assert len(fech.rastro[fech.rastro.id_saida == r.id_saida]) == 119


def test_extrato(fech, config):
    e = _por(fech, "EXTRATO_NAO_IDENTIFICADO").iloc[0]
    assert (e.ref_origem, e.valor_brl, e.subtipo, e.quem_decide) == ("L50", D("7350.00"), "CREDITO_SEM_ORIGEM", "Financeiro")
    d = _por(fech, "DEVOLUCAO").iloc[0]
    assert (d.ref_origem, d.valor_brl, d.quem_decide) == ("L65", D("12400.00"), "Financeiro")
    # Helena (17/10 09h48): o repasse que voltou é o mesmo repasse devido, que precisa ser refeito (2.1.01.001);
    # 2.1.01.002 fica para créditos que a Tarvo deve ao lojista por outro motivo
    assert d.regra_id == "C-18" and d.motivo.endswith("Descobrir o motivo e repassar de novo")   # texto do lançamento não muda
    c18 = config.regra("C-18").situacao
    assert "2.1.01.001" in c18 and "mesmo repasse devido" in c18 and "2.1.01.002" in c18 and "outro motivo" in c18
    t = _por(fech, "EM_TRANSITO").iloc[0]
    assert (t.ref_origem, t.valor_brl, t.quem_decide) == ("L92", D("-300000.00"), "Financeiro")


def test_recurso_sem_operacao_nao_e_pendencia_e_sim_lembrete(fech, config):
    """Helena (17/10 09h44-09h45): o PIX de R$ 18.240 é recurso de remessa ainda não contratada (sai em outubro).
    DP-10 ficou INATIVA (sem dono, o motor não gera a pendência); a regra MANUAL M-05 lembra de conferir."""
    assert _por(fech, "RECURSO_SEM_OPERACAO").empty
    assert config.dono_se_houver("RECURSO_SEM_OPERACAO", date(2026, 9, 1)) is None
    m = config.lembrete_por_assunto("recurso_sem_operacao", date(2026, 9, 1))
    assert m is not None and m.id == "M-05" and "mês seguinte" in m.o_que_fazer and m.quem_decide == "Financeiro"
    assert fech.conciliacao["remessa_banco"]["recursos_menos_liquidado"] == D("18240.00")   # a conta 2.1.02.001 fica


def test_recurso_sem_operacao_volta_a_ser_pendencia_se_houver_dono(dados, tmp_path):
    """A decisão é dado: reativar DP-10 volta a gerar a pendência, sem mexer em código."""
    from src.regras import carregar_config
    from tests.sintetico import regras_copia
    regras = regras_copia(tmp_path)
    p = regras / "regras_negocio.csv"
    t = p.read_text(encoding="utf-8")
    assert ";INATIVA;" in t.split("\nDP-10;")[1].split("\n")[0]
    p.write_text(t.replace("\nDP-10;", "\nDP-10x;").replace(";INATIVA;Decisão do time MN AI na revisão da Fase 4", ";ATIVA;Decisão do time MN AI na revisão da Fase 4"), encoding="utf-8")
    cfg = carregar_config(regras, dados["taxas"], dados["plano_contas"], {"AURORA", "MERIDIANO"})
    f = executar(dados, cfg, "2026-09", usar_ia=False)
    r = f.pendencias[f.pendencias.tipo == "RECURSO_SEM_OPERACAO"]
    assert len(r) == 1 and r.iloc[0].ref_origem == "MRD2026090425" and r.iloc[0].valor_brl == D("18240.00") and f.integro


def test_conferir_repasse_ponte(fech):
    """A1 (Helena ao Lucca, 16/10 22h33): conferir o TED quando cair; não é perda, a contestação não foi aberta."""
    assert _por(fech, "REPASSE_PONTE_DIVERGENTE").empty
    r = _por(fech, "CONFERIR_REPASSE_PONTE").iloc[0]
    assert (r.valor_brl, r.quem_decide, r.regra_id) == (D("506.65"), "Helena (Financeiro)", "DP-11")
    assert r.motivo.startswith("Conferir o TED do parceiro de câmbio previsto para 2026-10-06 (data do e-mail do parceiro) contra a "
                               "nota NF-0021 (R$ 39.543,45). Se o parceiro pagar 50% do total que declarou (R$ 78.073,59 -> "
                               "R$ 39.036,80), a diferença possível é R$ 506,65 (= ")
    assert "+ R$ 917,03 de 4 operações excluídas (Spread negativo na remessa, regra E-03)" in r.motivo
    assert "- R$ 410,94 de 1 operação repetida, contada uma vez" in r.motivo and "+ R$ 0,56 de arredondamento" in r.motivo
    assert "Não é perda: a contestação ainda não foi aberta" in r.motivo and "previsto para 2026-10-06 (data do e-mail do parceiro)" in r.motivo
    assert "06/10" not in r.o_que_fazer      # nenhuma data fixa na regra: a data vem do e-mail
    assert "credita só 50%" not in r.motivo and "Contestar" not in r.motivo and ";" not in r.motivo and not r.informativa
    rastro = fech.rastro[fech.rastro.id_saida == r.id_saida]
    assert len(rastro) == 6 and soma(rastro.valor) == D("506.65")
    ref_total = "linha 241 do relatório (SPREAD TOTAL R$:)"
    assert set(rastro.ref_origem) == {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545", "PC-0926-0162", ref_total}
    assert rastro[rastro.ref_origem == ref_total].valor.iloc[0] == D("0.56") and r.ref_origem == ref_total


def test_lista_de_contestacao_da_ponte_nao_e_pendencia(fech):
    """A contestação (Helena ao Insper AI, 16/10 22h34) é anexo de e-mail (FASE D), não pendência: somaria de novo
    o que já está nas pendências atômicas. A lista tem as 23 da Mundo Aberto (excesso cheio), os 4 spreads
    negativos (com sinal) e a PC-0926-0162 repetida com valor 0; cada natureza soma a pendência correspondente."""
    from src.pendencias import lista_contestacao
    assert _por(fech, "CONTESTACAO_PONTE").empty and "CONTESTACAO_PONTE" not in set(fech.pendencias.tipo)
    lc = lista_contestacao(fech.ponte_linhas)
    assert len(lc) == 28 and lc.natureza.value_counts().to_dict() == {"EXCESSO_SPREAD": 23, "SPREAD_NEGATIVO": 4, "REPETIDA": 1}
    assert soma(lc[lc.natureza == "EXCESSO_SPREAD"].valor_brl) == D("1418.85") == _por(fech, "DIVERGENCIA_TAXA").set_index("cnpj").loc[MA, "valor_brl"]
    assert soma(lc[lc.natureza == "SPREAD_NEGATIVO"].valor_brl) == D("-1834.05") == soma(_por(fech, "SPREAD_NEGATIVO").valor_brl)
    assert lc[lc.natureza == "REPETIDA"].iloc[0].ref_origem == "PC-0926-0162" and lc[lc.natureza == "REPETIDA"].iloc[0].valor_brl == D("0")


def test_cnpj_da_ponte_sem_cadastro_entra_na_nota_com_pendencia_para_o_comercial(dados, config):
    """A0.9: a operação entra na comissão e na nota (a Ponte paga); pendência CADASTRO/CNPJ_PONTE do Comercial
    (DONO_PENDENCIA com subtipo), com rastro = a comissão de cada operação. A nota de remessa não muda."""
    ponte = dados["ponte"].copy()
    ponte.loc[ponte.num_operacao == "PC-0926-0002", "cnpj"] = "99999999999999"
    ponte.attrs = dict(dados["ponte"].attrs)
    f = executar({**dados, "ponte": ponte}, config, "2026-09", usar_ia=False)
    c = f.pendencias[(f.pendencias.tipo == "CADASTRO") & (f.pendencias.subtipo == "CNPJ_PONTE")]
    assert len(c) == 1 and c.iloc[0].quem_decide == "Comercial" and c.iloc[0].regra_id == "DP-12"
    assert c.iloc[0].valor_brl == D("131.01") and c.iloc[0].qtd_itens == 1 and "entrou na comissão" in c.iloc[0].motivo
    assert f.notas[f.notas.linha_negocio == "REMESSA"].valor_brl.iloc[0] == D("39543.45")
    r = f.pendencias[f.pendencias.tipo == "CONFERIR_REPASSE_PONTE"].iloc[0]
    assert r.valor_brl == D("506.65") and "sem cadastro" not in r.motivo and f.integro


def test_repasse_divergente_nao_chama_cadastro_de_arredondamento(dados, tmp_path):
    """Com remessa_cnpj_sem_cadastro=EXCLUIR (comportamento antigo), a operação fica fora da comissão e a
    diferença com a Ponte é dela, não arredondamento."""
    from src.regras import carregar_config
    from tests.sintetico import regras_copia
    regras = regras_copia(tmp_path, [("remessa_cnpj_sem_cadastro=COMISSAO", "remessa_cnpj_sem_cadastro=EXCLUIR")])
    cfg = carregar_config(regras, dados["taxas"], dados["plano_contas"], {"AURORA", "MERIDIANO"})
    ponte = dados["ponte"].copy()
    ponte.loc[ponte.num_operacao == "PC-0926-0002", "cnpj"] = "99999999999999"
    ponte.attrs = dict(dados["ponte"].attrs)
    f = executar({**dados, "ponte": ponte}, cfg, "2026-09", usar_ia=False)
    r = f.pendencias[f.pendencias.tipo == "CONFERIR_REPASSE_PONTE"].iloc[0]
    assert "- R$ 131,01 de 1 operação de CNPJ sem cadastro" in r.motivo
    assert "+ R$ 0,56 de arredondamento" in r.motivo or "+ R$ 0,55 de arredondamento" in r.motivo
    assert "NÃO explicados" not in r.motivo and f.integro


def test_textos_de_pendencia_sem_separador_e_com_acao(fech):
    assert not fech.pendencias.motivo.str.contains(";").any()
    for r in fech.pendencias.itertuples():
        assert r.o_que_fazer and r.o_que_fazer.split(".")[0][:30] in r.motivo, r.id_saida


def test_remessa_de_lojista_sem_contrato_vira_informativa(dados, config):
    ponte = dados["ponte"].copy()
    alvo = ponte.cnpj == "95739378000118"            # Ponte Aérea passa a ser a Atlas (SEM_CONTRATO)
    ponte.loc[alvo, "cnpj"] = ATLAS_CNPJ
    f = executar({**dados, "ponte": ponte}, config, "2026-09", usar_ia=False)
    r = f.pendencias[(f.pendencias.tipo == "CADASTRO") & (f.pendencias.subtipo == "REMESSA_LOJISTA_SEM_CONTRATO")]
    assert len(r) == 1 and r.iloc[0].cnpj == ATLAS_CNPJ and r.iloc[0].qtd_itens == 14
    assert soma(f.comissoes_remessa.comissao_brl) == D("39543.45")   # comissão mantida
    assert f.integro


def test_resumo_json_e_relatorio(dados, tmp_path):
    assert main(["fechar", "--saida", str(tmp_path), "--sem-ia"]) == 0
    res = json.loads((tmp_path / "resumo.json").read_text(encoding="utf-8"))
    assert res["status_integridade"] == "OK" and res["competencia"] == "2026-09"
    assert res["totais"]["comissao_checkout_brl"] == "207039.73" and res["totais"]["comissao_remessa_brl"] == "39543.45"
    assert res["totais"]["pendencias"]["quantidade"] == 16
    pr = res["totais"]["pendencias"]["por_responsavel"]
    assert pr["Comercial"] == {"quantidade": 1, "valor_brl": "7876.05", "informativas": 0, "incluidas_em_outra": 0}
    # informativas (EM_TRANSITO, ALERTA_ANTECIPACAO) e a metade do excesso (já na divergência) ficam fora do "em jogo"
    assert pr["Financeiro"] == {"quantidade": 3, "valor_brl": "19750.00", "informativas": 1, "incluidas_em_outra": 0}
    assert pr["Helena (Financeiro) + Comercial"] == {"quantidade": 2, "valor_brl": "15397.42", "informativas": 1, "incluidas_em_outra": 0}
    assert pr["Helena (Financeiro)"] == {"quantidade": 10, "valor_brl": "5341.28", "informativas": 0, "incluidas_em_outra": 1}
    assert res["totais"]["pendencias"]["informativas"] == 2 and res["totais"]["pendencias"]["em_jogo_brl"] == "48364.75"
    assert res["conciliacao"]["parceiro_cambio"]["data_repasse"] == "2026-10-06"
    assert "M-05" in res["conciliacao"]["remessa_x_banco"]["observacao"] and "18.240,00" in res["conciliacao"]["remessa_x_banco"]["observacao"]
    assert res["arquivos"]["pendencias"] == "pendencias.csv"
    assert res["conciliacao"]["parceiro_cambio"]["efeitos_por_destino"]["EXCLUIDO"]["efeito"] == "917.03"
    assert res["entrada"]["competencia_inferida"] is True and "orbe" in res["entrada"]["arquivos"]
    assert res["lancamentos"] == {"REGRA": 184, "IA": 0, "HUMANO": 0}
    assert res["conciliacao"]["adquirente_x_banco"]["conciliavel"] is False
    assert res["base_de_regras"]["ultima_alteracao_historico"] == "2026-10-17"
    assert [l["regra_id"] for l in res["lembretes"]] == ["M-01", "M-02", "M-03", "M-04", "M-05"]
    assert all(isinstance(c["ok"], bool) for c in res["integridade"])
    rel = (tmp_path / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert rel.startswith("# Fechamento Tarvo — competência 09/2026") and "Integridade: OK" in rel
    assert "R$ 207.039,73" in rel and "Ponte Câmbio S.A." in rel and "### Comercial" in rel
    assert "Fora das divergências de contrato" in rel and "118 transações" in rel and "R$ 15.397,42" in rel
    assert res["totais"]["divergencias"]["checkout"] == {"linhas": 92, "valor_brl": "1576.23"}
    assert res["totais"]["divergencias"]["devolucao_lojista"] == {"linhas": 118, "valor_brl": "15397.42"}
    assert "não se comparam" in rel and "agenda de recebíveis" in rel and "3.707" not in rel and "repassou" not in rel.lower()
    assert "M-01" in rel and "5 dias úteis" in rel
    assert "RECURSO_SEM_OPERACAO" not in rel and "M-05" in rel and "mês seguinte" in rel
    assert "pendencias.csv" in rel and "saldo negativo sem nota" in rel and "R$ 5,50" in rel
    assert "### Financeiro — 3 pendência(s), R$ 19.750,00 em jogo (1 informativa)" in rel and "REPASSE_PONTE_DIVERGENTE" not in rel
    assert "### Helena (Financeiro) — 10 pendência(s), R$ 5.341,28 em jogo" in rel
    assert "Rodapé: EXCESSO_SPREAD_CONTESTADO (R$ 709,46) já incluído em DIVERGENCIA_TAXA de Mundo Aberto" in rel
    assert "1.5%–1.5%" not in rel and "+ -R$" not in rel


def test_integridade_falha_nao_escreve_resumo(dados, tmp_path, capsys):
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "resumo.json").write_text("{}", encoding="utf-8")
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-10", "--sem-ia"]) == 3
    assert not (tmp_path / "resumo.json").exists()
    assert "RELATÓRIO INVÁLIDO" in (tmp_path / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
