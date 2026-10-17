"""Base de regras: cadastro (planilha + complemento), validação e classificação de extrato."""
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.regras import ErroConfig, alternativas, carregar_config, parse_parametros

RAIZ = Path(__file__).resolve().parents[1]
D = Decimal
SET = date(2026, 9, 15)
CASA, ROTA, KIWI = "00520815000100", "95927868000148", "07752116000126"


@pytest.fixture
def regras_tmp(tmp_path):
    """Cópia editável de regras/ para simular erros de edição."""
    destino = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", destino)
    return destino


def _carregar(pasta, dados, bancos):
    return carregar_config(pasta, dados["taxas"], dados["plano_contas"], bancos)


def _trocar(pasta, arquivo, antigo, novo):
    p = pasta / arquivo
    texto = p.read_text(encoding="utf-8")
    assert antigo in texto, antigo
    p.write_text(texto.replace(antigo, novo, 1), encoding="utf-8")


def _adicionar(pasta, arquivo, linha):
    p = pasta / arquivo
    p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + "\n" + linha + "\n", encoding="utf-8")


def _erros(pasta, dados, bancos) -> str:
    with pytest.raises(ErroConfig) as e:
        _carregar(pasta, dados, bancos)
    return str(e.value)


# ---------------------------------------------------------------- parse

def test_parse_parametros_aceita_espacos_em_volta_do_separador():
    assert parse_parametros("banco=AURORA | contem=PIX ENVIADO | conta=2.1.01.001 | prioridade=90") == {
        "banco": "AURORA", "contem": "PIX ENVIADO", "conta": "2.1.01.001", "prioridade": "90"}
    assert parse_parametros("") == {}


@pytest.mark.parametrize("texto", ["banco AURORA", "banco=A | banco=B", "=x"])
def test_parse_parametros_invalidos(texto):
    with pytest.raises(ValueError):
        parse_parametros(texto)


def test_alternativas_normaliza_e_separa_por_ou():
    assert alternativas("PONTE AEREA OU PONTE AÉREA") == ["PONTE AEREA"]
    assert alternativas("tar pacote ou TAR TED/PIX") == ["TAR PACOTE", "TAR TED/PIX"]


# ---------------------------------------------------------------- cadastro

def test_cadastro_planilha_mais_complemento(config):
    cad = config.cadastro.set_index("cnpj")
    assert len(cad) == 25
    assert cad["origem"].value_counts().to_dict() == {"planilha": 20, "planilha + complemento": 4, "complemento": 1}
    assert cad.loc["22348118000148", "status"] == "INATIVO"    # Globo Trotter: só o complemento diz isso
    assert cad.loc[KIWI, "ec_orbe"] == "1038867654" and cad.loc[KIWI, "nome"] == "Kiwi Experience"
    assert cad.loc["22224579000109", "ec_orbe"] == "1075624862"  # Bridge: 2 linhas, 1 EC
    assert cad.loc["22224579000109", "linhas_planilha"] == [6, 7]
    assert cad.loc["95739378000118", "ec_orbe"] is None            # Ponte Aérea: só remessa
    atlas = cad.loc["39566044000119"]
    assert (atlas.status, atlas.ec_orbe, atlas.nome) == ("SEM_CONTRATO", "1076801732", None)
    assert config.lojista_por_ec("1043300981").cnpj == "66564512000199"
    assert config.lojista_por_ec("9999999999") is None
    assert config.avisos == []


def test_complemento_redundante_gera_aviso(regras_tmp, dados, bancos):
    _adicionar(regras_tmp, "complemento_cadastro.csv", f"{ROTA};1074504011;ATIVO;teste;2026-10-16;")
    cfg = _carregar(regras_tmp, dados, bancos)
    assert any("linha redundante, pode ser removida" in a for a in cfg.avisos)


def test_complemento_com_ec_diferente_da_planilha_para(regras_tmp, dados, bancos):
    _adicionar(regras_tmp, "complemento_cadastro.csv", f"{ROTA};1000000000;ATIVO;teste;2026-10-16;")
    msg = _erros(regras_tmp, dados, bancos)
    assert ROTA in msg and "1074504011" in msg and "1000000000" in msg and "Como corrigir" in msg


def test_complemento_cnpj_sem_zero_a_esquerda_aceito_com_aviso(regras_tmp, dados, bancos):
    _trocar(regras_tmp, "complemento_cadastro.csv", f"\n{KIWI};", "\n7752116000126;")
    cfg = _carregar(regras_tmp, dados, bancos)
    assert cfg.lojista_por_cnpj(KIWI).ec_orbe == "1038867654"
    assert any("13 dígitos" in a for a in cfg.avisos)


def test_complemento_status_invalido_para(regras_tmp, dados, bancos):
    _trocar(regras_tmp, "complemento_cadastro.csv", ";SEM_CONTRATO;", ";PENDENTE;")
    assert "status 'PENDENTE' inválido" in _erros(regras_tmp, dados, bancos)


# ---------------------------------------------------------------- regras: carga

def test_parametros_carregados(config):
    assert config.parametro("participacao_spread", SET) == D("0.50")
    assert config.parametro("spread_padrao", SET) == D("0.015")
    assert config.parametro("tolerancia_spread_pp", SET) == D("0.01")
    assert config.parametro("tolerancia_taxa_checkout_pp", SET) == D("0")
    assert config.parametro("incluir_excesso_contestado", SET) is True
    assert config.parametro("arredondamento", SET) == "HALF_UP"
    assert config.parametro("nota_remessa_tomador_cnpj", SET) == "75374179000146"
    assert "{competencia}" in config.parametro("discriminacao_checkout", SET)


def test_excecao_casa_do_estudante_so_na_vigencia_e_no_checkout(config):
    x = config.excecao_taxa(CASA, "CHECKOUT", "CREDITO A VISTA", date(2026, 9, 1))
    assert x is not None and x.id == "X-01" and x.params["taxa_pct"] == D("0")
    assert x.tipo_pendencia == "TARIFA_ZERO_COBRADA" and "Comercial" in x.quem_decide
    assert config.excecao_taxa(CASA, "CHECKOUT", "ANTECIPACAO", date(2026, 12, 31)) is not None
    assert config.excecao_taxa(CASA, "CHECKOUT", "DEBITO", date(2026, 8, 21)) is None
    assert config.excecao_taxa(CASA, "CHECKOUT", "DEBITO", date(2027, 1, 1)) is None
    assert config.excecao_taxa(CASA, "REMESSA", "SPREAD REMESSA", SET) is None
    assert config.excecao_taxa(ROTA, "CHECKOUT", "CREDITO A VISTA", SET) is None


def test_exclusoes_duplicado_e_donos(config):
    assert {r.id for r in config.regras_exclusao("ponte", SET)} == {"E-03", "E-04"}
    assert {r.id for r in config.regras_exclusao("orbe", SET)} == {"E-01", "E-02"}
    e1 = next(r for r in config.regras_exclusao("orbe", SET) if r.id == "E-01")
    assert e1.params["status"] == {"SEM_CONTRATO"} and e1.tipo_pendencia == "SEM_CONTRATO"
    assert config.regra_duplicado("ponte", SET).params["chave"] == "num_operacao"
    assert config.regra_duplicado("orbe", SET) is None
    assert config.dono("CADASTRO", SET).quem_decide == "Financeiro/Comercial"
    assert config.dono("CADASTRO", SET, subtipo="CNPJ_PONTE").id == "DP-12" and config.dono("CADASTRO", SET, subtipo="CNPJ_PONTE").quem_decide == "Comercial"
    assert config.dono("CADASTRO", SET, subtipo="EC_ORBE").id == "DP-04"    # sem dono específico, vale o geral
    assert config.parametro("remessa_cnpj_sem_cadastro", SET) == "COMISSAO"
    assert config.dono("DIVERGENCIA_TAXA", SET).quem_decide == "Helena (Financeiro)"
    lembretes = config.lembretes(SET)
    assert [r.id for r in lembretes] == ["M-01", "M-02", "M-03", "M-04", "M-05"]
    alertas = config.por_tipo("ALERTA")
    assert [r.id for r in alertas] == ["A-01"] and alertas[0].params["criterio"] == "antecipacao_acima_das_vendas"
    assert alertas[0].params["so_para"] == {"SEM_CONTRATO", "PRIMEIRO_MES"} and alertas[0].tipo_pendencia == "ALERTA_ANTECIPACAO"
    assert alertas[0].quem_decide == "Helena (Financeiro) + Comercial" and alertas[0].params["informativa"] is True
    assert config.dono("EM_TRANSITO", SET).params["informativa"] is True and config.dono("DIVERGENCIA_TAXA", SET).params["informativa"] is False
    assert config.dono("CONFERIR_REPASSE_PONTE", SET).id == "DP-11" and config.regra("DP-13") is None
    assert config.dono("EXCESSO_SPREAD_CONTESTADO", SET).params["incluida_em"] == "DIVERGENCIA_TAXA"
    assert config.regra("DP-10").status == "INATIVA" and config.dono_se_houver("RECURSO_SEM_OPERACAO", SET) is None
    assert all(r.tipo == "MANUAL" and r.quem_decide for r in lembretes)
    assert lembretes[2].params == {"linha_negocio": "REMESSA", "cnpj": "17217888000111"}
    assert config.lembrete_por_assunto("conciliacao_adquirente", SET).id == "M-04"


@pytest.mark.parametrize("status", ["INATIVA", "PROPOSTA"])
def test_regra_nao_ativa_nao_executa(regras_tmp, dados, bancos, status):
    _trocar(regras_tmp, "regras_negocio.csv", "2026-09-01;2026-12-31;ATIVA;", f"2026-09-01;2026-12-31;{status};")
    cfg = _carregar(regras_tmp, dados, bancos)
    assert cfg.excecao_taxa(CASA, "CHECKOUT", "DEBITO", SET) is None
    assert "X-01" in {r.id for r in cfg.todas} and "X-01" not in {r.id for r in cfg.regras}


def test_data_ddmmaaaa_aceita_com_aviso(regras_tmp, dados, bancos):
    _trocar(regras_tmp, "regras_negocio.csv", ";2026-09-01;2026-12-31;ATIVA;", ";01/09/2026;2026-12-31;ATIVA;")
    cfg = _carregar(regras_tmp, dados, bancos)
    assert cfg.excecao_taxa(CASA, "CHECKOUT", "DEBITO", date(2026, 9, 1)) is not None
    assert any("dd/mm/aaaa" in a and "X-01" in a for a in cfg.avisos)


# ---------------------------------------------------------------- regras: erros de edição

@pytest.mark.parametrize("antigo, novo, trecho", [
    ("conta=1.1.03.001 | prioridade=50", "conta=1.1.03 | prioridade=50", "não aceita lançamento"),
    ("conta=1.1.03.001 | prioridade=50", "conta=9.9.99.999 | prioridade=50", "não existe no plano de contas"),
    (";CLASSIFICAR_CONTA;banco=AURORA | contem=ORBE", ";CLASSIFICAR;banco=AURORA | contem=ORBE", "tipo 'CLASSIFICAR' desconhecido"),
    ("participacao_spread=0.50", "participacao_spread=50", "fração entre 0 e 1"),
    ("arredondamento=HALF_UP", "arredondamento=BANCARIO", "não é opção válida"),
    ("conta=1.1.03.001 | prioridade=50", "conta=1.1.03.001 | prioridade=500", "prioridade '500' inválida"),
    ("conta=1.1.03.001 | prioridade=50", "conta=1.1.03.001 | prioridade=50 | cor=azul", "chaves desconhecidas ['cor']"),
    ("tipo_pendencia=SPREAD_NEGATIVO", "tipo_pendencia=SPREAD_RUIM", "tipo_pendencia 'SPREAD_RUIM' desconhecido"),
    (";2026-09-01;2026-12-31;ATIVA;", ";2026-09-01;2026-12-31;LIGADA;", "status 'LIGADA' inválido"),
    (";2026-09-01;2026-12-31;ATIVA;", ";2026-13-01;2026-12-31;ATIVA;", "não existe no calendário"),
])
def test_edicao_errada_para_com_mensagem(regras_tmp, dados, bancos, antigo, novo, trecho):
    _trocar(regras_tmp, "regras_negocio.csv", antigo, novo)
    msg = _erros(regras_tmp, dados, bancos)
    assert trecho in msg and "Como corrigir" in msg and "regras_negocio.csv linha" in msg


def test_parametro_obrigatorio_ausente_e_duplicado_param(regras_tmp, dados, bancos):
    # P-01 passa a definir spread_padrao: falta participacao_spread e P-01/P-02 colidem
    _trocar(regras_tmp, "regras_negocio.csv", "participacao_spread=0.50", "spread_padrao=0.50")
    msg = _erros(regras_tmp, dados, bancos)
    assert "falta a regra PARAMETRO ativa 'participacao_spread'" in msg
    assert "P-01" in msg and "P-02" in msg and "ativas ao mesmo tempo" in msg


def test_dono_de_pendencia_ausente_para(regras_tmp, dados, bancos):
    _trocar(regras_tmp, "regras_negocio.csv", "estão cadastrados);;;ATIVA;", "estão cadastrados);;;INATIVA;")
    assert "falta a regra DONO_PENDENCIA ativa para 'CADASTRO'" in _erros(regras_tmp, dados, bancos)


def test_linha_com_coluna_a_mais_para_com_linha_indicada(regras_tmp, dados, bancos):
    _trocar(regras_tmp, "regras_negocio.csv", "participacao_spread=0.50;", "participacao_spread=0.50;X;")
    msg = _erros(regras_tmp, dados, bancos)
    assert "regras_negocio.csv linha 2" in msg and "colunas" in msg


def test_vigencias_sobrepostas_param(regras_tmp, dados, bancos):
    _adicionar(regras_tmp, "regras_negocio.csv",
               f"X-02;teste;teste;TAXA_EXCECAO;cnpj={CASA} | linha_negocio=CHECKOUT | produto=DEBITO | taxa_pct=1;"
               "teste;Comercial;;2026-10-01;;ATIVA;teste;2026-10-16")
    msg = _erros(regras_tmp, dados, bancos)
    assert "X-01" in msg and "X-02" in msg and "ativas ao mesmo tempo" in msg


def test_id_repetido_para(regras_tmp, dados, bancos):
    _trocar(regras_tmp, "regras_negocio.csv", "\nC-02;", "\nC-01;")
    assert "id repetido" in _erros(regras_tmp, dados, bancos)


# ---------------------------------------------------------------- classificação de extrato

@pytest.mark.parametrize("banco, descricao, valor, conta, regra", [
    ("AURORA", "TED RECEBIDA 99.876.669/0001-09 ORBE ADQUIRENCIA SA", "66026.00", "1.1.03.001", "C-01"),
    ("AURORA", "PIX ENVIADO ROTA GLOBAL INTERCAMBIO LT", "-77106.46", "2.1.01.001", "C-02"),
    ("AURORA", "PIX ENVIADO CONTABILIDADE EXATA LTDA", "-6800.00", "4.2.06", "C-03"),   # específica vence
    ("AURORA", "PIX ENVIADO ANDES EXPEDICÕES LTDA", "-51774.96", "2.1.01.001", "C-02"),  # acento
    ("AURORA", "TAR TED/PIX AVULSAS 09/2026", "-187.50", "4.2.01", "C-13"),             # alternativa OU
    ("AURORA", "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO", "7350.00", "1.1.09.002", "C-17"),
    ("MERIDIANO", "PIX RECEB PONTE AÉREA ESTUDANTIL L", "77595.09", "2.1.02.001", "C-19"),   # lojista
    ("MERIDIANO", "PIX RECEB PONTE AEREA ESTUDANTIL L", "18240.00", "2.1.02.001", "C-19"),
    ("MERIDIANO", "TED ENVIADA PONTE CAMBIO SA LIQ OPERACOES", "-240619.49", "2.1.02.001", "C-20"),  # parceiro
    ("MERIDIANO", "TED RECEB PONTE CAMBIO SA REPASSE COMISSAO 08/2026", "61884.12", "1.1.03.002", "C-21"),
    ("MERIDIANO", "APLICACAO AUTOMATICA CDB DI", "-161736.00", "1.1.02.001", "C-22"),
    ("MERIDIANO", "RESGATE AUTOMATICO CDB DI", "162128.00", "1.1.02.001", "C-22"),
    ("MERIDIANO", "IOF S/ OPERACAO CREDITO", "-48.21", "4.3.01", "C-24"),
])
def test_classificar(config, banco, descricao, valor, conta, regra):
    c = config.classificar(banco, descricao, D(valor), SET)
    assert c.regra is not None and (c.regra.id, c.regra.params["conta"]) == (regra, conta)


def test_classificar_sem_regra_ou_sinal_errado(config):
    assert config.classificar("AURORA", "COMPRA DE CAFE", D("-10"), SET).regra is None
    assert config.classificar("AURORA", "PIX ENVIADO ROTA GLOBAL", D("10"), SET).regra is None  # C-02 é débito
    assert config.classificar("MERIDIANO", "PIX ENVIADO ROTA GLOBAL", D("-10"), SET).regra is None  # banco errado


def test_classificar_pendencia_do_credito_sem_origem(config):
    r = config.classificar("AURORA", "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO", D("7350"), SET).regra
    assert r.params["gera_pendencia"] is True
    assert (r.tipo_pendencia, r.subtipo) == ("EXTRATO_NAO_IDENTIFICADO", "CREDITO_SEM_ORIGEM")


def test_empate_de_prioridade_com_contas_diferentes_vira_conflito(regras_tmp, dados, bancos):
    # texto diferente de C-02, mesma prioridade (90), conta diferente: empate real no lançamento da Rota
    _adicionar(regras_tmp, "regras_negocio.csv",
               "C-99;teste;teste;CLASSIFICAR_CONTA;banco=AURORA | contem=ROTA GLOBAL | sinal=debito | conta=4.2.01 | prioridade=90;"
               "teste;Financeiro;;;;ATIVA;teste;2026-10-16")
    cfg = _carregar(regras_tmp, dados, bancos)
    c = cfg.classificar("AURORA", "PIX ENVIADO ROTA GLOBAL INTERCAMBIO LT", D("-10"), SET)
    assert c.regra is None and {r.id for r in c.conflito} == {"C-02", "C-99"}
    # a específica (prioridade 10) continua vencendo as genéricas
    assert cfg.classificar("AURORA", "PIX ENVIADO CONTABILIDADE EXATA", D("-10"), SET).regra.id == "C-03"
    assert cfg.classificar("AURORA", "PIX ENVIADO ANDES", D("-10"), SET).regra.id == "C-02"


def test_mesmo_texto_banco_e_sinal_duas_vezes_para_na_carga(regras_tmp, dados, bancos):
    _adicionar(regras_tmp, "regras_negocio.csv",
               "C-99;teste;teste;CLASSIFICAR_CONTA;banco=AURORA | contem=PIX ENVIADO | sinal=debito | conta=4.2.01 | prioridade=90;"
               "teste;Financeiro;;;;ATIVA;teste;2026-10-16")
    msg = _erros(regras_tmp, dados, bancos)
    assert "C-02" in msg and "C-99" in msg and "ativas ao mesmo tempo" in msg


def test_todos_os_lancamentos_do_mes_tem_regra(config, dados):
    for banco in ("aurora", "meridiano"):
        df = dados[banco]
        sem_regra = [(r.ref_origem, r.descricao) for r in df.itertuples()
                     if config.classificar(r.banco, r.descricao, r.valor, r.data.date()).regra is None]
        assert sem_regra == [], sem_regra
