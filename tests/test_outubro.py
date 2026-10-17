"""Outubro sintético de ponta a ponta (T7 do prompt final, 17/10): o pacote gerado por tests/outubro_sintetico.py fecha
pela CLI com --anterior apontando para a saída de setembro, sem nada fixo para setembro no código.

Confere o que o roteiro do teste de férias (evals/teste_ferias.md) espera: competência inferida 10/2026; nota de remessa
com a competência certa; EC novo na Orbe vira CADASTRO (Comercial) e vai para a carteira; Bridge já na taxa nova (sem
divergência); Casa zerada (sem divergência, comissão 0, sem nota); parcelado em 13x vira CADASTRO/PARCELAS_FORA_FAIXA
(Helena); a carteira da Atlas de setembro entra e continua pendente enquanto não há taxa; os 2 ajustes da Ponte entram
na comissão do mês e viram pendência informativa ligada à contestação de setembro; o CNPJ novo na Ponte entra na
comissão com CADASTRO/CNPJ_PONTE (Comercial); folha e impostos do mês anterior classificados por regra genérica."""
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src.cli import main
from src.dinheiro import soma
from tests.outubro_sintetico import CNPJ_NOVO_PONTE, EC_NOVO, gerar

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]
CASA, BRIDGE, ATLAS, ROTA, MA = "00520815000100", "22224579000109", "39566044000119", "95927868000148", "17217888000111"


@pytest.fixture(scope="module")
def outubro(dados, tmp_path_factory):
    """(pasta de setembro fechada, pasta do pacote de outubro, pasta de saída de outubro, resumo de outubro)."""
    base = tmp_path_factory.mktemp("outubro")
    assert main(["fechar", "--saida", str(base / "set"), "--sem-ia"]) == 0
    pacote = gerar(base / "pacote_out")
    assert main(["fechar", "--entrada", str(pacote), "--anterior", str(base / "set"), "--saida", str(base / "out"), "--sem-ia"]) == 0
    res = json.loads((base / "out" / "resumo.json").read_text(encoding="utf-8"))
    return base / "set", pacote, base / "out", res


def _csv(p):
    return pd.read_csv(p, sep=";", dtype=str, keep_default_na=False)


def test_pacote_tem_os_seis_arquivos_e_valida(outubro):
    _set, pacote, _out, _res = outubro
    nomes = sorted(p.name for p in pacote.iterdir())
    assert [n[:3] for n in nomes] == ["01_", "02_", "03_", "04_", "05a", "05b"] and all("out2026" in n or n.startswith(("02_", "04_")) for n in nomes)
    assert main(["validar", "--entrada", str(pacote), "--json"]) == 0


def test_competencia_inferida_e_integridade(outubro):
    _set, _pacote, out, res = outubro
    assert res["competencia"] == "2026-10" and res["entrada"]["competencia_inferida"] is True and res["status_integridade"] == "OK"
    assert res["entrada"]["carteira_anterior"]["linhas"] == 57 and res["entrada"]["carteira_anterior"]["operacoes_contestadas"] == 28
    assert all(c["ok"] for c in res["integridade"]) and res["lancamentos"] == {"REGRA": 184, "IA": 0, "HUMANO": 0}
    notas = _csv(out / "notas_a_emitir.csv")
    assert (notas.discriminacao.str.contains("competência 10/2026")).all() and set(notas.competencia) == {"2026-10"}


def test_casa_zerada_bridge_na_taxa_nova_e_rota_continua_divergente(outubro):
    _set, _pacote, out, res = outubro
    com = _csv(out / "comissoes_por_lojista.csv").set_index(["cnpj", "linha_negocio"])
    assert com.loc[(CASA, "CHECKOUT"), "comissao_brl"] == "0.00"
    notas = _csv(out / "notas_a_emitir.csv")
    assert CASA not in set(notas[notas.linha_negocio == "CHECKOUT"].tomador_cnpj)
    div = _csv(out / "divergencias_taxa.csv")
    assert set(div.cnpj) == {ROTA, MA} and set(div.natureza) == {"CONTRATO"} and CASA not in set(div.cnpj) and BRIDGE not in set(div.cnpj)
    assert res["totais"]["divergencias"]["devolucao_lojista"] == {"linhas": 0, "valor_brl": "0.00"}
    pend = _csv(out / "pendencias.csv")
    assert "TARIFA_ZERO_COBRADA" not in set(pend.tipo) and "SALDO_NEGATIVO_LOJISTA" not in set(pend.tipo)


def test_ec_novo_e_parcelado_13x_sao_pendencias_e_vao_para_a_carteira(outubro):
    _set, _pacote, out, _res = outubro
    pend = _csv(out / "pendencias.csv")
    ec = pend[(pend.tipo == "CADASTRO") & (pend.subtipo == "EC_ORBE")].iloc[0]
    assert ec.ref_origem == EC_NOVO and ec.quem_decide == "Comercial" and ec.qtd_itens == "12" and "LOJA NOVA LTDA" in ec.motivo
    x13 = pend[(pend.tipo == "CADASTRO") & (pend.subtipo == "PARCELAS_FORA_FAIXA")].iloc[0]
    assert x13.quem_decide == "Helena (Financeiro)" and x13.regra_id == "DP-13" and "13x" in x13.motivo
    cart = _csv(out / "carteira_pendente.csv")
    rastro = _csv(out / "rastro.csv")
    assert set(cart[cart.ec == EC_NOVO].ref_origem) == set(rastro[rastro.id_saida == ec["id_saida"]].ref_origem)
    assert "TY99999913" in set(cart.ref_origem)


def test_carteira_da_atlas_entra_e_continua_pendente_sem_taxa(outubro):
    _set, _pacote, out, res = outubro
    cart = _csv(out / "carteira_pendente.csv")
    atlas = cart[cart.cnpj == ATLAS]
    assert len(atlas) == 114 and atlas.idade_meses.value_counts().to_dict() == {"0": 57, "1": 57}
    assert set(atlas[atlas.idade_meses == "1"].competencia_origem) == {"2026-09"}
    assert res["carteira_pendente"]["de_meses_anteriores"] == 57 and res["carteira_pendente"]["faturadas_de_meses_anteriores"] == 0
    pend = _csv(out / "pendencias.csv")
    sc = pend[pend.tipo == "SEM_CONTRATO"].iloc[0]
    assert sc.qtd_itens == "114" and "57 transações de meses anteriores" in sc.motivo and sc.quem_decide == "Comercial"


def test_ajustes_da_ponte_entram_no_mes_e_apontam_para_a_contestacao_de_setembro(outubro, dados):
    set_, _pacote, out, res = outubro
    assert res["ponte_destinos"]["AJUSTE_PONTE"] == 2
    pend = _csv(out / "pendencias.csv")
    aj = pend[pend.tipo == "CONFERIR_AJUSTE_PONTE"].set_index("ref_origem")
    assert set(aj.index) == {"PC-0926-0210", "PC-0926-0011"} and set(aj.quem_decide) == {"Helena (Financeiro)"} and set(aj.informativa) == {"true"}
    assert aj.loc["PC-0926-0210", "subtipo"] == "CREDITO" and D(aj.loc["PC-0926-0210", "valor_brl"]) == D("343.76")
    assert aj.loc["PC-0926-0011", "subtipo"] == "DEBITO" and D(aj.loc["PC-0926-0011", "valor_brl"]) == D("-14.78")
    assert "pedido b (SPREAD_NEGATIVO) da contestação do fechamento anterior (2026-09)" in aj.loc["PC-0926-0210", "motivo"]
    assert "pedido a (EXCESSO_SPREAD) da contestação do fechamento anterior (2026-09)" in aj.loc["PC-0926-0011", "motivo"]
    # o ajuste está dentro da comissão e da nota de remessa do mês
    com = _csv(out / "comissoes_por_lojista.csv")
    rem = com[com.linha_negocio == "REMESSA"]
    nota = _csv(out / "notas_a_emitir.csv")
    assert soma(rem.comissao_brl.map(D)) == D(nota[nota.linha_negocio == "REMESSA"].valor_brl.iloc[0]) == D(res["totais"]["comissao_remessa_brl"])
    # as 2 operações do CNPJ novo já estavam no total de setembro (eram de outro lojista): só os ajustes mudam o total
    assert D(res["totais"]["comissao_remessa_brl"]) == D("39543.45") + D("343.76") - D("14.78")


def test_cnpj_novo_na_ponte_entra_na_comissao_com_cadastro_para_o_comercial(outubro):
    _set, _pacote, out, _res = outubro
    pend = _csv(out / "pendencias.csv")
    c = pend[(pend.tipo == "CADASTRO") & (pend.subtipo == "CNPJ_PONTE")].iloc[0]
    assert c.ref_origem == CNPJ_NOVO_PONTE and c.quem_decide == "Comercial" and c.qtd_itens == "2" and "entrou na comissão" in c.motivo
    com = _csv(out / "comissoes_por_lojista.csv")
    assert D(com[(com.cnpj == CNPJ_NOVO_PONTE)].comissao_brl.iloc[0]) == D(c.valor_brl)


def test_provisoes_e_textos_sem_mes_fixo(outubro):
    _set, _pacote, out, _res = outubro
    lanc = _csv(out / "lancamentos_classificados.csv")
    folha = lanc[lanc.descricao.str.contains("SALARIOS|GPS INSS|GRF FGTS|DARF|PAGTO ISS", regex=True)]
    assert len(folha) >= 6 and set(folha.metodo) == {"REGRA"} and (folha.conta_codigo != "").all()
    assert (folha.descricao.str.contains("09/2026")).any() and not (folha.descricao.str.contains("08/2026")).any()
    rel = (out / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert rel.startswith("# Fechamento Tarvo — competência 10/2026") and "09/2026" not in rel.split("## Pendências")[0]
    ponte_md = (out / "comunicacoes" / "ponte.md").read_text(encoding="utf-8")
    assert "competência 10/2026" in ponte_md and "2026-11-06" in (out / "pendencias.csv").read_text(encoding="utf-8")
