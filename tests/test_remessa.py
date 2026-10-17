"""Comissão de remessa de setembro/2026, conferida contra o relatório da Ponte."""
from decimal import Decimal

import pandas as pd
import pytest

from src.dinheiro import soma
from src.remessa import calcular

D = Decimal
MUNDO_ABERTO, MAPLE, CANGURU, PONTE_AEREA = "17217888000111", "34671260000100", "53857560000123", "95739378000118"


@pytest.fixture(scope="session")
def rem(dados, config):
    return calcular(dados["ponte"], dados["taxas"], config, "2026-09")


def _op(rem, num):
    sel = rem.linhas[(rem.linhas.num_operacao == num) & (rem.linhas.destino != "DUPLICATA_IGNORADA")]
    assert len(sel) == 1
    return sel.iloc[0]


def _com(rem, cnpj):
    sel = rem.comissoes[rem.comissoes.cnpj == cnpj]
    assert len(sel) == 1
    return sel.iloc[0]


def test_destinos_e_total(rem, dados):
    assert len(rem.linhas) == len(dados["ponte"]) == 233
    assert rem.linhas["destino"].value_counts().to_dict() == {"COMISSAO": 228, "EXCLUIDO": 4, "DUPLICATA_IGNORADA": 1}
    assert soma(rem.comissoes.comissao_brl) == D("39543.45")       # validado também pelo Lucca (21h56)
    assert len(rem.comissoes) == 14 and (rem.comissoes.linha_negocio == "REMESSA").all()
    assert rem.comissoes.id_saida.tolist() == [f"COM-REM-{i:04d}" for i in range(1, 15)]
    assert int(rem.comissoes.qtd_operacoes.sum()) == 228


def test_duplicata_conta_uma_vez(rem):
    dup = rem.linhas[rem.linhas.num_operacao == "PC-0926-0162"]
    assert len(dup) == 2 and dup.destino.tolist() == ["COMISSAO", "DUPLICATA_IGNORADA"]
    assert dup.iloc[1].destino_regra == "D-01" and "reprocessada" in str(dup.iloc[1].observacao)
    assert _op(rem, "PC-0926-0162").comissao_brl == D("410.94")   # 821,88 x 50%


def test_spreads_negativos_excluidos(rem):
    neg = rem.linhas[rem.linhas.destino == "EXCLUIDO"]
    assert set(neg.num_operacao) == {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"}
    assert soma(neg.spread_brl) == D("-1834.05")
    assert set(neg.destino_regra) == {"E-03"} and set(neg.tipo_pendencia) == {"SPREAD_NEGATIVO"}
    assert neg.comissao_brl.isna().all() and neg.diferenca_brl.isna().all()


def test_half_up_por_operacao(rem):
    op = _op(rem, "PC-0926-0002")   # Maple: 262,01 x 50% = 131,005 -> 131,01
    assert op.spread_brl == D("262.01") and op.comissao_brl == D("131.01")
    assert op.data_contratacao == pd.Timestamp("2026-09-30") and op.data_liquidacao == pd.Timestamp("2026-10-01")
    assert op.destino == "COMISSAO"   # competência pela data de contratação
    assert op.regra_id == "P-01" and op.participacao == D("0.50")
    assert op.spread_contratado_pct == D("1.5") and op.spread_contratado_origem == "planilha:Taxas vigentes!J19"
    assert op.diferenca_brl is None   # 1,501% x 1,5%: dentro da tolerância


def test_spread_padrao_para_celula_em_branco_ou_padrao(rem):
    kiwi = rem.linhas[(rem.linhas.cnpj == "07752116000126") & (rem.linhas.destino == "COMISSAO")]
    assert set(kiwi.spread_contratado_pct) == {D("1.500")} or set(kiwi.spread_contratado_pct) == {D("1.5")}
    assert kiwi.spread_contratado_origem.iloc[0].startswith("P-02 (padrão")
    canguru = rem.linhas[(rem.linhas.cnpj == CANGURU) & (rem.linhas.destino == "COMISSAO")]
    assert "J29" in canguru.spread_contratado_origem.iloc[0]
    assert canguru.diferenca_brl.isna().all() and kiwi.diferenca_brl.isna().all()


def test_mundo_aberto_divergencia_valor_cheio_e_excesso(rem):
    ma = rem.linhas[(rem.linhas.cnpj == MUNDO_ABERTO) & (rem.linhas.destino == "COMISSAO")]
    assert len(ma) == 23 and set(ma.spread_contratado_pct) == {D("1.2")}
    assert ma.diferenca_brl.notna().all() and (ma.diferenca_brl > 0).all()
    assert soma(ma.diferenca_brl) == D("1418.85")         # coluna Spread % (decisão B); exato daria 1.418,88
    assert soma(ma.excesso_tarvo_brl) == D("709.46")
    c = _com(rem, MUNDO_ABERTO)
    assert c.comissao_brl == D("3547.69") and c.spread_realizado_brl == D("7095.25")   # fatura pelo realizado (P-05)
    assert c.excesso_contestado_brl == D("1418.85") and c.excesso_tarvo_brl == D("709.46")
    op = _op(rem, "PC-0926-0011")   # 2.438,46 CAD, PTAX 4,0315, spread 1,5007%
    assert op.diferenca_pp == D("0.3007") or abs(op.diferenca_pp - D("0.3007")) < D("0.00001")
    assert op.diferenca_brl == D("29.56")   # (0,015007 - 0,012) x 4,0315 x 2438,46


def test_outros_lojistas_sem_divergencia(rem):
    com = rem.linhas[rem.linhas.destino == "COMISSAO"]
    assert set(com[com.diferenca_brl.notna()].cnpj) == {MUNDO_ABERTO}
    outros = com[com.cnpj != MUNDO_ABERTO]
    assert (outros.diferenca_pp.map(abs) <= D("0.01")).all()


def test_ressalva_de_compliance_nao_muda_nada(rem):
    res = rem.linhas[rem.linhas.status_compliance == "APROVADO C/ RESSALVA"]
    assert len(res) == 16 and (res.destino == "COMISSAO").all()


def test_rastro_fecha(rem):
    por_id = rem.rastro.groupby("id_saida")["valor"].apply(soma)
    for r in rem.comissoes.itertuples():
        assert por_id[r.id_saida] == r.comissao_brl
    assert len(rem.rastro) == 228 and rem.rastro.ref_origem.is_unique
    assert set(rem.rastro.regra_id) == {"P-01"} and set(rem.rastro.taxa_pct) == {D("50.00")}


def test_excesso_fora_da_nota_quando_parametro_desligado(regras_tmp_remessa, dados, bancos):
    from src.regras import carregar_config
    cfg = carregar_config(regras_tmp_remessa, dados["taxas"], dados["plano_contas"], bancos)
    r = calcular(dados["ponte"], dados["taxas"], cfg, "2026-09")
    c = _com(r, MUNDO_ABERTO)
    assert c.comissao_brl == D("3547.69") - D("709.46")
    assert soma(r.comissoes.comissao_brl) == D("39543.45") - D("709.46")


@pytest.fixture
def regras_tmp_remessa(tmp_path):
    import shutil
    from pathlib import Path
    destino = tmp_path / "regras"
    shutil.copytree(Path(__file__).resolve().parents[1] / "regras", destino)
    p = destino / "regras_negocio.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("incluir_excesso_contestado=true", "incluir_excesso_contestado=false"),
                 encoding="utf-8")
    return destino


def test_duplicata_com_valores_diferentes_fica_fora(dados, config):
    ponte = dados["ponte"].copy()
    idx = ponte.index[ponte.num_operacao == "PC-0926-0162"][1]
    ponte.loc[idx, "spread_brl"] = ponte.loc[idx, "spread_brl"] + D("1.00")
    r = calcular(ponte, dados["taxas"], config, "2026-09")
    dup = r.linhas[r.linhas.num_operacao == "PC-0926-0162"]
    assert set(dup.destino) == {"DUPLICATA_DIVERGENTE"} and set(dup.tipo_pendencia) == {"DUPLICATA_DIVERGENTE"}
    assert soma(r.comissoes.comissao_brl) == D("39543.45") - D("410.94")


def test_cnpj_desconhecido_entra_na_comissao_e_vira_cadastro(dados, config):
    """Helena (17/10 09h45, à Desbravadores): a Ponte paga a metade do spread mesmo sem o CNPJ na planilha, e a
    nota precisa bater com o repasse: a operação ENTRA na comissão e na nota, com pendência CADASTRO/CNPJ_PONTE
    para o Comercial (parâmetro remessa_cnpj_sem_cadastro=COMISSAO). Sem spread contratado, não há divergência."""
    ponte = dados["ponte"].copy()
    alvo = ponte.cnpj == PONTE_AEREA
    ponte.loc[alvo, "cnpj"] = "99999999999999"
    r = calcular(ponte, dados["taxas"], config, "2026-09")
    sem = r.linhas[r.linhas.cnpj == "99999999999999"]
    assert len(sem) == 15 and sem.destino.value_counts().to_dict() == {"COMISSAO": 14, "EXCLUIDO": 1}   # spread negativo segue excluído
    com = sem[sem.destino == "COMISSAO"]
    assert set(com.tipo_pendencia) == {"CADASTRO"} and set(com.subtipo) == {"CNPJ_PONTE"} and com.status_cadastro.isna().all()
    assert com.spread_contratado_pct.isna().all() and com.diferenca_brl.isna().all() and "PONTE AÉREA" in com.lojista.iloc[0]
    assert soma(r.comissoes.comissao_brl) == D("39543.45") and len(r.comissoes) == 14   # nada muda no total
    assert "99999999999999" in set(r.comissoes.cnpj) and "não está na planilha" in com.motivo.iloc[0]
    assert com.spread_contratado_origem.iloc[0].startswith("sem cadastro")


def test_cnpj_desconhecido_fica_fora_se_o_parametro_mandar(dados, regras_tmp_excluir):
    from src.regras import carregar_config
    cfg = carregar_config(regras_tmp_excluir, dados["taxas"], dados["plano_contas"], {"AURORA", "MERIDIANO"})
    ponte = dados["ponte"].copy()
    ponte.loc[ponte.cnpj == PONTE_AEREA, "cnpj"] = "99999999999999"
    r = calcular(ponte, dados["taxas"], cfg, "2026-09")
    sem = r.linhas[r.linhas.destino == "SEM_CADASTRO"]
    assert len(sem) == 15 and set(sem.subtipo) == {"CNPJ_PONTE"} and len(r.comissoes) == 13


@pytest.fixture
def regras_tmp_excluir(tmp_path):
    import shutil
    from pathlib import Path
    destino = tmp_path / "regras"
    shutil.copytree(Path(__file__).resolve().parents[1] / "regras", destino)
    p = destino / "regras_negocio.csv"
    t = p.read_text(encoding="utf-8")
    assert "remessa_cnpj_sem_cadastro=COMISSAO" in t
    p.write_text(t.replace("remessa_cnpj_sem_cadastro=COMISSAO", "remessa_cnpj_sem_cadastro=EXCLUIR"), encoding="utf-8")
    return destino


def test_spread_ambiguo_na_planilha_vira_pendencia_e_nao_some(dados, config):
    """Duas linhas de spread vigentes para o mesmo CNPJ na planilha: o contratado não pode sumir em silêncio (sem
    divergência e sem pendência). A operação continua na comissão pelo realizado (a comissão de remessa não depende do
    contratado) e vira pendência CADASTRO/TAXA_AMBIGUA para o Comercial, com o CNPJ e as células conflitantes."""
    from src.fechamento import executar
    taxas = dados["taxas"]
    extra = taxas[(taxas.cnpj == MUNDO_ABERTO) & (taxas.produto == "SPREAD REMESSA")].copy()
    assert len(extra) == 1
    extra["taxa_pct"], extra["ref_origem"], extra["linha_planilha"] = D("1.5"), "Taxas vigentes!J99", 99
    f = executar({**dados, "taxas": pd.concat([taxas, extra], ignore_index=True)}, config, "2026-09", usar_ia=False)
    ops = f.ponte_linhas[f.ponte_linhas.cnpj == MUNDO_ABERTO]
    com = ops[ops.destino == "COMISSAO"]
    assert len(com) == 23 and com.spread_contratado_pct.isna().all() and com.diferenca_brl.isna().all()
    assert set(com.tipo_pendencia) == {"CADASTRO"} and set(com.subtipo) == {"TAXA_AMBIGUA"}
    assert com.spread_contratado_origem.iloc[0].startswith("ambígua na planilha (") and "J99" in com.spread_contratado_origem.iloc[0]
    assert soma(f.comissoes_remessa.comissao_brl) == D("39543.45")   # comissão pelo realizado: não muda
    assert MUNDO_ABERTO not in set(f.divergencias.cnpj)               # divergência não conferida, não inventada
    p = f.pendencias[(f.pendencias.tipo == "CADASTRO") & (f.pendencias.subtipo == "TAXA_AMBIGUA")]
    assert len(p) == 1
    r = p.iloc[0]
    assert (r.cnpj, r.quem_decide, r.qtd_itens, r.linha_negocio) == (MUNDO_ABERTO, "Comercial", 23, "REMESSA")
    assert "Taxas vigentes!J99" in r.motivo and "NÃO pôde ser conferida" in r.motivo and MUNDO_ABERTO in r.motivo
    assert r.valor_brl == soma(com.comissao_brl) and len(f.rastro[f.rastro.id_saida == r.id_saida]) == 23
    assert f.integro
