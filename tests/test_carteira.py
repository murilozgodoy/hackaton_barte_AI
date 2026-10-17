"""A5 (Helena à MN AI, 17/10 09h47): a taxa da Atlas vale desde 10/09 e setembro é faturado junto com outubro.
`fechar` grava saida/carteira_pendente.csv (linhas excluídas por falta de contrato ou taxa) e
`fechar --anterior <saida anterior>` relê a carteira: com taxa vigente na data da venda, as linhas entram na
comissão e na nota do mês atual (rastro no arquivo do mês anterior); sem taxa, continuam na carteira com idade."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src import carteira, comandos
from src.cli import main
from src.dinheiro import soma
from src.fechamento import escrever, executar
from src.regras import carregar_config
from tests.sintetico import regras_copia

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]
ATLAS = "39566044000119"


@pytest.fixture(scope="module")
def setembro(dados, config):
    return executar(dados, config, "2026-09", usar_ia=False)


def test_carteira_de_setembro_tem_as_57_linhas_da_atlas(setembro):
    c = setembro.carteira
    assert len(c) == 57 and set(c.cnpj) == {ATLAS} and set(c.competencia_origem) == {"2026-09"} and set(c.idade_meses) == {0}
    assert list(c.columns[:9]) == ["arquivo_origem", "ref_origem", "cnpj", "ec", "data_venda", "produto", "valor_bruto",
                                   "motivo", "competencia_origem"]
    assert soma(c.valor_bruto) == D("262138.61") and set(c.ec) == {"1076801732"} and (c.motivo.str.len() > 10).all()
    assert setembro.integro and not any("carteira" in ch.nome for ch in setembro.checagens)   # sem --anterior, sem a checagem


def test_fechar_grava_carteira_pendente(dados, tmp_path, capsys):
    assert main(["fechar", "--saida", str(tmp_path), "--sem-ia", "--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["arquivos"]["carteira"] == "carteira_pendente.csv" and (tmp_path / "carteira_pendente.csv").exists()
    assert j["carteira_pendente"] == {"linhas": 57, "valor_bruto_brl": "262138.61", "de_meses_anteriores": 0,
                                      "faturadas_de_meses_anteriores": 0}
    lida = carteira.ler(tmp_path)
    assert len(lida) == 57 and set(lida.competencia_origem) == {"2026-09"}
    assert lida.arquivo_origem.iloc[0].startswith("01_orbe") and lida.valor_bruto.map(type).eq(Decimal).all()


def _outubro(dados):
    desl = dict(dados)
    for nome, colunas in (("orbe", ["data_movimento", "data_venda_original"]), ("ponte", ["data_contratacao", "data_liquidacao"]),
                          ("aurora", ["data"]), ("meridiano", ["data"])):
        df = dados[nome].copy()
        for c in colunas:
            df[c] = df[c] + pd.DateOffset(months=1)
        if nome == "orbe":   # ids novos: num mês real as transações têm outros ids
            df["id_transacao"] = df["id_transacao"] + "O"
            df["ref_origem"] = df["id_transacao"]
        df.attrs = dict(dados[nome].attrs)
        desl[nome] = df
    return desl


def test_sem_taxa_a_carteira_envelhece_e_a_pendencia_avisa(dados, config, setembro, tmp_path):
    escrever(setembro, tmp_path, config)
    f = executar(_outubro(dados), config, "2026-10", usar_ia=False, carteira=carteira.ler(tmp_path))
    assert f.integro
    c = f.carteira
    assert len(c) == 114 and c.idade_meses.value_counts().to_dict() == {0: 57, 1: 57}
    assert set(c[c.idade_meses == 1].competencia_origem) == {"2026-09"} and set(c[c.idade_meses == 0].competencia_origem) == {"2026-10"}
    p = f.pendencias[f.pendencias.tipo == "SEM_CONTRATO"].iloc[0]
    assert p.qtd_itens == 114 and "57 transações de meses anteriores" in p.motivo and "1 mês" in p.motivo
    assert ATLAS not in set(f.comissoes_checkout.cnpj)


def test_com_a_taxa_aprovada_outubro_fatura_setembro_junto(dados, config, setembro, tmp_path):
    """TAXA_EXCECAO da Atlas aprovada pelo Comercial e registrada pela Helena (aprovadores.csv), vigente desde 10/09."""
    escrever(setembro, tmp_path / "set", config)
    regras = regras_copia(tmp_path)
    hoje = date(2026, 10, 17)
    p = comandos.propor(regras, "TAXA_EXCECAO", {
        "situacao": "Taxa da Atlas confirmada pelo Comercial, retroativa a 10/09",
        "parametros": f"cnpj={ATLAS} | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=2.00",
        "o_que_fazer": "Faturar desde 10/09", "quem_decide": "Helena (Financeiro)", "informado_por": "teste",
        "vigencia_de": "2026-09-10"}, None, None, hoje)
    assert p.valida, p.erros
    with pytest.raises(comandos.ErroComando):
        comandos.aplicar(regras, p, "Helena", None, hoje)                      # taxa: só o Comercial aprova
    comandos.aplicar(regras, p, "Diego (Comercial)", None, hoje, "Helena (Financeiro)")
    cfg = carregar_config(regras, dados["taxas"], dados["plano_contas"], {"AURORA", "MERIDIANO"})
    out = _outubro(dados)
    f = executar(out, cfg, "2026-10", usar_ia=False, carteira=carteira.ler(tmp_path / "set"))
    assert f.integro and len(f.carteira) == 0
    com = f.comissoes_checkout.set_index("cnpj").loc[ATLAS]
    assert com.qtd_transacoes == 114
    esperado = soma((v * D("2") / 100).quantize(D("0.01"), rounding="ROUND_HALF_UP")
                    for v in out["orbe"][out["orbe"].cod_estabelecimento == "1076801732"].valor_bruto) * 2
    assert com.comissao_brl == esperado
    rastro = f.rastro[f.rastro.id_saida == com.id_saida]
    assert len(rastro) == 114 and (rastro.regra_id == "X-02").all()
    assert rastro.arquivo_origem.str.contains("01_orbe").all()       # setembro e outubro vêm do mesmo relatório (deslocado)
    assert (~rastro.ref_origem.str.endswith("O")).sum() == 57        # as 57 de setembro, com os ids originais
    assert any("carteira anterior" in ch.nome and ch.ok for ch in f.checagens)
    nf = f.notas[f.notas.tomador_cnpj == ATLAS]
    assert len(nf) == 1 and nf.iloc[0].valor_brl == esperado and nf.iloc[0].qtd_itens == 114
    assert f.pendencias[f.pendencias.tipo == "SEM_CONTRATO"].empty
    # os outros lojistas não mudam em relação a outubro sem carteira
    base = executar(out, config, "2026-10", usar_ia=False)
    a = f.comissoes_checkout[f.comissoes_checkout.cnpj != ATLAS].set_index("cnpj").comissao_brl
    assert a.equals(base.comissoes_checkout.set_index("cnpj").comissao_brl.loc[a.index])


def test_cli_anterior(dados, pasta_dados, tmp_path, capsys):
    from tests.test_saida_cli import _entrada_com_extratos_de_outubro
    assert main(["fechar", "--saida", str(tmp_path / "set"), "--sem-ia"]) == 0
    capsys.readouterr()
    # Orbe e Ponte de setembro com extratos de outubro e competência 2026-10: tudo de setembro fica fora da competência
    # (integridade falha, código 3), mas a carteira anterior é lida
    entrada = _entrada_com_extratos_de_outubro(pasta_dados, tmp_path)
    assert main(["fechar", "--entrada", str(entrada), "--saida", str(tmp_path / "out"), "--sem-ia", "--competencia", "2026-10",
                 "--anterior", str(tmp_path / "set"), "--json"]) == 3
    j = json.loads(capsys.readouterr().out)
    assert j["carteira_pendente"]["de_meses_anteriores"] == 57
    assert main(["fechar", "--saida", str(tmp_path / "x"), "--sem-ia", "--anterior", str(tmp_path / "nada")]) == 1
