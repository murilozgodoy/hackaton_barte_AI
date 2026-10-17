"""Pendências de setembro/2026: cada uma com motivo, dono e rastro que soma o valor."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.cli import main
from src.dinheiro import soma
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
        "REPASSE_PONTE_DIVERGENTE": 1, "SPREAD_NEGATIVO": 4, "SEM_CONTRATO": 1, "SALDO_NEGATIVO_LOJISTA": 1,
        "RECURSO_SEM_OPERACAO": 1, "EXTRATO_NAO_IDENTIFICADO": 1, "DEVOLUCAO": 1, "EM_TRANSITO": 1}
    assert p.quem_decide.notna().all() and (p.motivo.str.len() > 40).all()
    assert p.quem_decide.value_counts().to_dict() == {"Helena (Financeiro)": 10, "Helena (Financeiro) + Comercial": 1,
                                                     "Comercial": 1, "Financeiro": 4}


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
    assert len(fech.rastro[fech.rastro.id_saida == r.id_saida]) == 118


def test_divergencias_rota_bridge_mundo_aberto(fech):
    d = _por(fech, "DIVERGENCIA_TAXA").set_index("cnpj")
    assert d.loc[ROTA, "valor_brl"] == D("1546.28") and d.loc[ROTA, "qtd_itens"] == 87
    assert "2.49% a 3.59%" in d.loc[ROTA, "motivo"] and "2.99% a 4.09%" in d.loc[ROTA, "motivo"]
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


def test_extrato(fech):
    e = _por(fech, "EXTRATO_NAO_IDENTIFICADO").iloc[0]
    assert (e.ref_origem, e.valor_brl, e.subtipo, e.quem_decide) == ("L50", D("7350.00"), "CREDITO_SEM_ORIGEM", "Financeiro")
    d = _por(fech, "DEVOLUCAO").iloc[0]
    assert (d.ref_origem, d.valor_brl, d.quem_decide) == ("L65", D("12400.00"), "Financeiro")
    t = _por(fech, "EM_TRANSITO").iloc[0]
    assert (t.ref_origem, t.valor_brl, t.quem_decide) == ("L92", D("-300000.00"), "Financeiro")


def test_recurso_sem_operacao(fech):
    r = _por(fech, "RECURSO_SEM_OPERACAO").iloc[0]
    assert (r.ref_origem, r.valor_brl, r.quem_decide, r.regra_id) == ("MRD2026090425", D("18240.00"), "Financeiro", "DP-10")
    assert "PONTE AEREA" in r.motivo and "R$ 5.611.447,12" in r.motivo


def test_repasse_ponte_divergente(fech):
    r = _por(fech, "REPASSE_PONTE_DIVERGENTE").iloc[0]
    assert (r.valor_brl, r.quem_decide, r.regra_id) == (D("506.65"), "Helena (Financeiro)", "DP-11")
    assert "NF-0021" in r.motivo and "+ R$ 917,03" in r.motivo and "- R$ 410,94" in r.motivo and "M-01" in r.motivo
    assert "+ R$ 0,56 de arredondamento" in r.motivo and ";" not in r.motivo
    rastro = fech.rastro[fech.rastro.id_saida == r.id_saida]
    assert len(rastro) == 6 and soma(rastro.valor) == D("506.65")
    ref_total = "linha 241 do relatório (SPREAD TOTAL R$:)"
    assert set(rastro.ref_origem) == {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545", "PC-0926-0162", ref_total}
    assert rastro[rastro.ref_origem == ref_total].valor.iloc[0] == D("0.56") and r.ref_origem == ref_total


def test_repasse_divergente_nao_chama_cadastro_de_arredondamento(dados, config):
    """Operação de CNPJ sem cadastro fica fora da comissão: a diferença com a Ponte é dela, não arredondamento."""
    ponte = dados["ponte"].copy()
    ponte.loc[ponte.num_operacao == "PC-0926-0002", "cnpj"] = "99999999999999"
    ponte.attrs = dict(dados["ponte"].attrs)
    f = executar({**dados, "ponte": ponte}, config, "2026-09", usar_ia=False)
    r = f.pendencias[f.pendencias.tipo == "REPASSE_PONTE_DIVERGENTE"].iloc[0]
    assert "- R$ 131,01 de 1 operação(ões) de CNPJ sem cadastro" in r.motivo
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
    assert res["totais"]["pendencias"]["por_responsavel"]["Comercial"] == {"quantidade": 1, "valor_brl": "7876.05"}
    assert res["totais"]["pendencias"]["por_responsavel"]["Financeiro"]["valor_brl"] == "337990.00"
    assert res["arquivos"]["pendencias"] == "pendencias.csv"
    assert res["conciliacao"]["parceiro_cambio"]["efeitos_por_destino"]["EXCLUIDO"]["efeito"] == "917.03"
    assert res["entrada"]["competencia_inferida"] is True and "orbe" in res["entrada"]["arquivos"]
    assert res["lancamentos"] == {"REGRA": 184, "IA": 0, "HUMANO": 0}
    assert res["conciliacao"]["adquirente_x_banco"]["conciliavel"] is False
    assert res["base_de_regras"]["ultima_alteracao_historico"] == "2026-10-17"
    assert [l["regra_id"] for l in res["lembretes"]] == ["M-01", "M-02", "M-03", "M-04"]
    assert all(isinstance(c["ok"], bool) for c in res["integridade"])
    rel = (tmp_path / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert rel.startswith("# Fechamento Tarvo — competência 09/2026") and "Integridade: OK" in rel
    assert "R$ 207.039,73" in rel and "Ponte Câmbio S.A." in rel and "### Comercial" in rel
    assert "não se comparam" in rel and "agenda de recebíveis" in rel and "3.707" not in rel and "repassou" not in rel.lower()
    assert "M-01" in rel and "5 dias úteis" in rel
    assert "pendencias.csv" in rel and "saldo negativo sem nota" in rel and "R$ 5,50" in rel
    assert "1.5%–1.5%" not in rel and "+ -R$" not in rel


def test_integridade_falha_nao_escreve_resumo(dados, tmp_path, capsys):
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "resumo.json").write_text("{}", encoding="utf-8")
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-10", "--sem-ia"]) == 3
    assert not (tmp_path / "resumo.json").exists()
    assert "RELATÓRIO INVÁLIDO" in (tmp_path / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
