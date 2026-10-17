"""Comandos de apoio: explicar, pendencias, regra propor/aplicar, base de regras em zip, empacotar-skill."""
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from src.cli import main

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def saida(dados, tmp_path_factory):
    pasta = tmp_path_factory.mktemp("saida")
    assert main(["fechar", "--saida", str(pasta), "--sem-ia"]) == 0
    return pasta


def test_explicar_comissao_com_rastro_e_regra(saida, capsys):
    assert main(["explicar", "COM-CHK-0002", "--saida", str(saida), "--json"]) == 0   # Fluente: só planilha
    e = json.loads(capsys.readouterr().out)
    assert e["arquivo"] == "comissoes_por_lojista.csv" and e["bate"] is True
    assert e["rastro_linhas"] == int(e["linha"]["qtd_transacoes"]) and e["rastro_soma"] == e["linha"]["comissao_brl"]
    assert all(l["regra_id"].startswith("planilha:") for l in e["rastro"])
    assert main(["explicar", "COM-CHK-0001", "--saida", str(saida), "--json"]) == 0   # Casa: regra X-01
    e = json.loads(capsys.readouterr().out)
    assert "X-01" in e["regras"] and e["regras"]["X-01"]["tipo"] == "TAXA_EXCECAO"


def test_explicar_pendencia_mostra_origem_e_regra(saida, pasta_dados, capsys):
    assert main(["explicar", "PEN-0001", "--saida", str(saida), "--entrada", str(pasta_dados)]) == 0
    txt = capsys.readouterr().out
    assert "TARIFA_ZERO_COBRADA" in txt and "X-01" in txt and "Regras envolvidas" in txt
    assert "valor_bruto=" in txt and "bate" in txt


def test_explicar_id_inexistente_codigo_4(saida, capsys):
    assert main(["explicar", "COM-CHK-9999", "--saida", str(saida)]) == 4
    assert "não existe" in capsys.readouterr().err


def test_pendencias_filtros(saida, capsys):
    assert main(["pendencias", "--saida", str(saida), "--json"]) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["total"] == 16 and {g["quem_decide"] for g in res["por_responsavel"]} == {
        "Helena (Financeiro)", "Helena (Financeiro) + Comercial", "Comercial", "Financeiro"}
    assert main(["pendencias", "--saida", str(saida), "--quem", "comercial", "--json"]) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["total"] == 3    # Atlas SEM_CONTRATO (Comercial), Casa TARIFA_ZERO e alerta da Atlas (Helena + Comercial)
    assert main(["pendencias", "--saida", str(saida), "--tipo", "SPREAD_NEGATIVO"]) == 0
    assert "4 pendência(s)" in capsys.readouterr().out


def test_regra_propor_e_aplicar_classificar_conta(saida, pasta_dados, tmp_path, capsys):
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    proposta = tmp_path / "p.json"
    assert main(["regra", "propor", "--regras", str(regras), "--saida", str(saida), "--tipo", "CLASSIFICAR_CONTA",
                 "--campos", "situacao=Café do escritório", "como_identificar=compra de café no cartão",
                 "parametros=banco=AURORA | contem=CAFE | sinal=debito | conta=4.2.04 | prioridade=50",
                 "o_que_fazer=Despesa do mês", "quem_decide=Financeiro", "informado_por=teste",
                 "--entrada", str(pasta_dados), "--proposta", str(proposta), "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["ok"] and p["linha"]["id"] == "C-27" and p["linha"]["status"] == "ATIVA"
    assert any("casaria 0 lançamento" in e for e in p["efeito"])
    antes = (regras / "regras_negocio.csv").read_text(encoding="utf-8")
    assert "C-27" not in antes   # propor não grava
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Helena",
                 "--entrada", str(pasta_dados)]) == 0
    depois = (regras / "regras_negocio.csv").read_text(encoding="utf-8")
    assert depois.count("\nC-27;") == 1 and depois.startswith("﻿")
    hist = (regras / "historico_alteracoes.csv").read_text(encoding="utf-8")
    assert ";Helena;C-27;CRIOU;;CLASSIFICAR_CONTA: banco=AURORA" in hist
    assert hist.splitlines()[-1].endswith(";Helena;Helena")      # aprovado_por;registrado_por (registro = aprovador se omitido)
    assert hist.splitlines()[0] == "\ufeffdata;quem;id_regra;acao;antes;depois;motivo;fonte;aprovado_por;registrado_por"
    # a base alterada continua válida e fecha o mês
    assert main(["validar", "--regras", str(regras)]) == 0


def test_regra_propor_invalida_codigo_2(tmp_path, saida, pasta_dados, capsys):
    assert main(["regra", "propor", "--regras", str(RAIZ / "regras"), "--saida", str(saida), "--tipo", "CLASSIFICAR_CONTA",
                 "--campos", "situacao=x", "parametros=banco=AURORA | contem=PIX ENVIADO | sinal=debito | conta=4.2.04 | prioridade=90",
                 "quem_decide=Financeiro", "informado_por=teste", "--json"]) == 2
    p = json.loads(capsys.readouterr().out)
    assert not p["ok"] and any("ativas ao mesmo tempo" in e for e in p["erros"])
    assert main(["regra", "propor", "--regras", str(RAIZ / "regras"), "--saida", str(saida), "--tipo", "CLASSIFICAR_CONTA",
                 "--campos", "situacao=x", "parametros=banco=AURORA | contem=CAFE | conta=9.9.99 | prioridade=50",
                 "quem_decide=Financeiro", "informado_por=teste", "--entrada", str(pasta_dados)]) == 2
    assert "não existe no plano de contas" in capsys.readouterr().out


def test_regra_propor_complemento_para_ec_novo(tmp_path, saida, capsys):
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    proposta = tmp_path / "c.json"
    assert main(["regra", "propor", "--regras", str(regras), "--saida", str(saida), "--tipo", "COMPLEMENTO",
                 "--campos", "cnpj=11.111.111/0001-91", "ec_orbe=9999999999", "status=ATIVO",
                 "informado_por=Helena, Slack 17/10", "observacao=Loja nova", "--proposta", str(proposta), "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["alvo"] == "complemento_cadastro.csv" and p["linha"]["cnpj"] == "11111111000191"
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Helena"]) == 0
    assert "11111111000191;9999999999;ATIVO" in (regras / "complemento_cadastro.csv").read_text(encoding="utf-8")
    assert "complemento:11111111000191" in (regras / "historico_alteracoes.csv").read_text(encoding="utf-8")


def test_aplicar_sem_aprovador_ou_proposta_invalida(tmp_path, saida, capsys):
    proposta = tmp_path / "ruim.json"
    proposta.write_text(json.dumps({"alvo": "regras_negocio.csv", "linha": {"id": "C-01", "tipo": "CLASSIFICAR_CONTA",
                                    "parametros": "banco=AURORA | contem=X | conta=4.2.04 | prioridade=50",
                                    "situacao": "x", "quem_decide": "F", "informado_por": "t"}}), encoding="utf-8")
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "X"]) == 2
    assert "já existe" in capsys.readouterr().err
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", " "]) == 2


def test_base_de_regras_em_zip(tmp_path, dados, capsys):
    zip_path = tmp_path / "regras_tarvo.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        for p in (RAIZ / "regras").iterdir():
            z.write(p, f"regras/{p.name}")
    assert main(["validar", "--regras", str(zip_path)]) == 0
    saida = tmp_path / "s"
    assert main(["fechar", "--regras", str(zip_path), "--saida", str(saida), "--sem-ia"]) == 0
    proposta = tmp_path / "p.json"
    assert main(["regra", "propor", "--regras", str(zip_path), "--saida", str(saida), "--tipo", "MANUAL",
                 "--campos", "situacao=Conferir extrato", "o_que_fazer=Conferir", "quem_decide=Financeiro",
                 "informado_por=teste", "--proposta", str(proposta)]) == 0
    assert main(["regra", "aplicar", "--regras", str(zip_path), "--proposta", str(proposta), "--aprovado-por", "Helena"]) == 0
    out = capsys.readouterr().out
    novos = list(tmp_path.glob("regras_tarvo_*.zip"))
    assert len(novos) == 1 and "substitui o anterior" in out
    with zipfile.ZipFile(novos[0]) as z:
        assert "\nM-07;" in z.read("regras/regras_negocio.csv").decode("utf-8")
    assert "M-07" not in zipfile.ZipFile(zip_path).read("regras/regras_negocio.csv").decode("utf-8")  # original intacto


def test_empacotar_skill(tmp_path, capsys):
    assert main(["empacotar-skill", "--destino", str(tmp_path / "dist")]) == 0
    zip_path = tmp_path / "dist" / "fechamento-tarvo.zip"
    assert zip_path.exists()
    nomes = zipfile.ZipFile(zip_path).namelist()
    assert "fechamento-tarvo/SKILL.md" in nomes
    assert "fechamento-tarvo/scripts/src/__main__.py" in nomes
    assert "fechamento-tarvo/assets/regras_iniciais/regras_negocio.csv" in nomes
    assert not any("__pycache__" in n for n in nomes)


# ---------------------------------------------------------------- A0.10: quem aprova cada tipo de regra (regras/aprovadores.csv)

def test_quem_aprova_por_tipo():
    from src.comandos import quem_aprova
    assert quem_aprova(RAIZ / "regras", "TAXA_EXCECAO") == ("Comercial", "Helena (Financeiro)")
    assert quem_aprova(RAIZ / "regras", "PARAMETRO") == ("Helena (Financeiro)", "Helena (Financeiro)")
    assert quem_aprova(RAIZ / "regras", "COMPLEMENTO") == ("Helena (Financeiro)", "Helena (Financeiro)")


def test_taxa_excecao_so_o_comercial_aprova_e_a_helena_registra(saida, pasta_dados, tmp_path, capsys):
    """Helena (17/10 09h49): "Taxa e condição comercial, quem aprova é o comercial, e eu registro"."""
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    proposta = tmp_path / "x.json"
    campos = ["situacao=Condição especial de teste", "parametros=cnpj=95927868000148 | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=2.0",
              "o_que_fazer=Taxa especial", "quem_decide=Helena (Financeiro)", "informado_por=teste", "vigencia_de=2026-11-01"]
    assert main(["regra", "propor", "--regras", str(regras), "--saida", str(saida), "--tipo", "TAXA_EXCECAO", "--campos", *campos,
                 "--entrada", str(pasta_dados), "--proposta", str(proposta), "--json"]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p["ok"] and p["aprovacao"] == {"quem_aprova": "Comercial", "quem_registra": "Helena (Financeiro)"}
    # a Helena não pode aprovar taxa
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Helena",
                 "--entrada", str(pasta_dados)]) == 2
    err = capsys.readouterr().err
    assert "TAXA_EXCECAO" in err and "Comercial" in err and "não pode aprovar" in err and "--registrado-por" in err
    assert "X-02" not in (regras / "regras_negocio.csv").read_text(encoding="utf-8")   # nada gravado
    # o Comercial aprova, mas só a Helena registra
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Diego (Comercial)",
                 "--entrada", str(pasta_dados)]) == 2
    assert "não pode registrar" in capsys.readouterr().err
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Diego (Comercial)",
                 "--registrado-por", "Helena (Financeiro)", "--entrada", str(pasta_dados)]) == 0
    assert "\nX-02;" in (regras / "regras_negocio.csv").read_text(encoding="utf-8")
    ultima = (regras / "historico_alteracoes.csv").read_text(encoding="utf-8").splitlines()[-1]
    assert ultima.startswith("2026-") and ";Diego (Comercial);X-02;CRIOU;" in ultima and ultima.endswith(";Diego (Comercial);Helena (Financeiro)")


def test_regra_de_fechamento_so_a_helena_aprova(saida, tmp_path, capsys):
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    proposta = tmp_path / "m.json"
    assert main(["regra", "propor", "--regras", str(regras), "--saida", str(saida), "--tipo", "MANUAL",
                 "--campos", "situacao=Conferir extrato", "o_que_fazer=Conferir", "quem_decide=Financeiro",
                 "informado_por=teste", "--proposta", str(proposta)]) == 0
    assert "Aprovação: Helena (Financeiro)" in capsys.readouterr().out
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Diego (Comercial)"]) == 2
    assert "não pode aprovar" in capsys.readouterr().err
    assert main(["regra", "aplicar", "--regras", str(regras), "--proposta", str(proposta), "--aprovado-por", "Helena (Financeiro)"]) == 0


def test_empacotar_skill_inclui_roteiro_sem_ia_e_agents(tmp_path, capsys):
    """A skill manda ler COMO_FECHAR_O_MES.md quando não há execução de código: o zip precisa trazê-lo (e o AGENTS.md).
    O zip extraído numa pasta qualquer roda o motor com a base de regras inicial."""
    import subprocess
    import sys
    assert main(["empacotar-skill", "--destino", str(tmp_path / "dist")]) == 0
    zip_path = tmp_path / "dist" / "fechamento-tarvo.zip"
    with zipfile.ZipFile(zip_path) as z:
        nomes = z.namelist()
        assert "fechamento-tarvo/COMO_FECHAR_O_MES.md" in nomes and "fechamento-tarvo/AGENTS.md" in nomes
        z.extractall(tmp_path / "extraido")
    raiz = tmp_path / "extraido" / "fechamento-tarvo"
    assert (raiz / "COMO_FECHAR_O_MES.md").read_bytes() == (RAIZ / "COMO_FECHAR_O_MES.md").read_bytes()
    zip_mes = next(RAIZ.glob("Tarvo_Data_Pack_*.zip"))
    r = subprocess.run([sys.executable, "-m", "src", "validar", "--entrada", str(zip_mes), "--regras",
                        str(raiz / "assets" / "regras_iniciais"), "--json"], cwd=raiz / "scripts", capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["ok"] is True
