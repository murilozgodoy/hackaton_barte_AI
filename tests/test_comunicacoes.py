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
    assert "Erro da Orbe" in md and "aditivo assinado com 2,19% a partir de 15/09" in md and "não o aviso" not in md   # externo: só o contrato


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
    # T4 (Helena ao Insper AI 16/10 22h34: "com o valor e as operações"): 3 pedidos, cada um com valor e operações, sem total único
    assert "Total em disputa" not in md and "São 3 pedidos" in md and "M-01" in md and "5 dias úteis" in md and "2026-10-09" in md
    assert "Pedido a — devolver a Mundo Aberto (CNPJ 17217888000111) o excesso de spread: R$ 1.418,85 em 23 operações." in md
    assert "1.5% aplicado contra 1.2% contratado" in md and "negociado e registrado desde julho" in md and "ressarcir o lojista" in md
    assert "Pedido b — 4 operações com spread negativo, fora da nossa comissão e da nota." in md and "Taxa travada no pedido (D-1)" in md
    assert ("o que aconteceu: -R$ 1.834,05 de spread no relatório; o que pedimos à Ponte (a trava deveria ter sido honrada): "
            "R$ 3.565,98, a diferença até o spread contratado de R$ 1.731,93") in md and "do qual a metade da Tarvo seria R$ 865,98" in md
    b = anexo[anexo.pedido == "b"].set_index("ref_origem")
    assert b.loc["PC-0926-0210", ["spread_relatorio_brl", "spread_contratado_brl", "diferenca_contrato_brl", "metade_tarvo_contrato_brl"]].tolist() == ["-687.52", "664.35", "-1351.87", "332.18"]
    assert b.loc["PC-0926-0545", "spread_contratado_brl"] == "292.88" and (anexo[anexo.pedido != "b"].spread_contratado_brl == "").all()
    assert "Pedido c — corrigir o relatório: PC-0926-0162 aparece mais de uma vez." in md and "valor 0" in md
    assert anexo.groupby("pedido").natureza.agg(lambda s: set(s)).to_dict() == {"a": {"EXCESSO_SPREAD"}, "b": {"SPREAD_NEGATIVO"}, "c": {"REPETIDA"}}
    assert set(anexo[anexo.pedido == "b"].regra_id) == {"E-03"} and set(anexo[anexo.pedido == "a"].regra_id) == {""}


def test_rascunhos_externos_citam_so_o_contrato(saida):
    """Helena (17/10 11h37): o que decide é o contrato, não o aviso. Para a Orbe e a Ponte, os rascunhos citam só o
    contrato (aditivo da Bridge 2,19% desde 15/09; Mundo Aberto 1,20%); a causa de processo ("avisada dias depois",
    "nunca avisada", "falha de processo nossa") fica só no relatório e em comercial.md (internos)."""
    for nome in ("orbe.md", "ponte.md", "avisos_nova_condicao.md"):
        md = (saida / "comunicacoes" / nome).read_text(encoding="utf-8")
        assert "falha de processo" not in md and "avisad" not in md.lower().replace("aviso", ""), nome
    orbe = (saida / "comunicacoes" / "orbe.md").read_text(encoding="utf-8")
    assert "aditivo assinado com 2,19% a partir de 15/09" in orbe
    ponte = (saida / "comunicacoes" / "ponte.md").read_text(encoding="utf-8")
    assert "spread de 1,20% negociado e registrado desde julho" in ponte
    rel = (saida / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert "falha de processo nossa" in rel


def test_comercial(saida):
    md = (saida / "comunicacoes" / "comercial.md").read_text(encoding="utf-8")
    assert "SEM_CONTRATO" in md and "R$ 7.876,05" in md and "NÃO é receita da Tarvo" in md
    assert "ALERTA_ANTECIPACAO" in md and "(informativa)" in md and "R$ 179.592,82" in md
    assert "TARIFA_ZERO_COBRADA" in md and "R$ 15.396,77" in md and "devolução ao lojista" in md   # o que foi cobrado, devolve-se
    assert md.count("- **PEN-") == 3


def test_avisos_nova_condicao(saida):
    """Aviso só para condição com vigência depois da competência, ou no mês sem divergência (regra P-13). Bridge (vigência
    15/09, com divergência) e Mundo Aberto (vigência jan/26) já estão em contestação: sem aviso atrasado e duplicado. A Casa
    (X-01) é concessão absorvida pela Tarvo: a linha diz por que não há aviso."""
    md = (saida / "comunicacoes" / "avisos_nova_condicao.md").read_text(encoding="utf-8")
    assert md.count("### ") == 0 and "Nenhuma condição comercial nova a avisar na competência 09/2026." in md
    assert "- TAXA_EXCECAO X-01 não gera aviso à Orbe: concessão absorvida pela Tarvo" in md
    contestacao = next(l for l in md.splitlines() if "seguem pela contestação, não por aviso (regra P-13)" in l)
    assert "Escola Bridge de Idiomas Ltda (Orbe, comunicacoes/orbe.md)" in contestacao
    assert "Mundo Aberto (Ponte, comunicacoes/ponte.md)" in contestacao
    assert "O aviso é controle de processo: quem deve é definido pelo contrato" in md and "não o aviso" not in md   # externo


def test_aviso_sai_para_condicao_futura_ou_no_mes_sem_divergencia(dados, config):
    """Condição com vigência no mês seguinte gera aviso; com aviso_condicao_nova_com_divergencia=true, a Bridge (no mês,
    com divergência) também gera."""
    import copy
    from src import comunicacoes
    from src.fechamento import executar
    fech = executar(dados, config, "2026-09", usar_ia=False)
    f2 = copy.copy(fech)
    tx = fech.taxas.copy()
    nova = tx[tx["linha_planilha"] == 7].copy()
    nova["linha_planilha"], nova["vigencia_de"], nova["taxa_pct"] = 99, pd.Timestamp("2026-10-05"), nova["taxa_pct"] - 1
    f2.taxas = pd.concat([tx, nova], ignore_index=True)
    avisos, _ = comunicacoes._avisos(f2, config, {})
    assert {(a["lojista"], a["contraparte"], a["origem"]) for a in avisos} == {
        ("Escola Bridge de Idiomas Ltda", "ORBE", "planilha de taxas, linha 99"),
        ("Escola Bridge de Idiomas Ltda", "PONTE", "planilha de taxas, linha 99")}
    assert "depois da competência" in avisos[0]["situacao"]
    regra = config.regra_parametro("aviso_condicao_nova_com_divergencia", __import__("datetime").date(2026, 9, 1))
    antes, regra.valor = regra.valor, True
    try:
        avisos, notas = comunicacoes._avisos(fech, config, {})
    finally:
        regra.valor = antes
    assert [a["origem"] for a in avisos] == ["planilha de taxas, linha 7"] and "já com divergência" in avisos[0]["situacao"]
    assert avisos[0]["produtos"] == "CREDITO A VISTA"     # só o que mudou em relação à linha anterior (L6)


def test_resumo_lista_os_rascunhos_e_lembrete_m06(saida):
    res = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    assert res["arquivos"]["comunicacoes/orbe_md"] == "comunicacoes/orbe.md"
    assert "M-06" in [l["regra_id"] for l in res["lembretes"]]
