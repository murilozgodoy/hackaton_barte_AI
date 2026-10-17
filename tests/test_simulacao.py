"""BLOCO 2 (17/10): `regra propor` mostra o efeito da regra no fechamento ANTES de gravar, fechando o mês duas vezes
numa pasta temporária (base x base + proposta). Nada é gravado na base real nem em saida/; a proposta muda só o
lojista-alvo; `regra aplicar` diz quem pode aprovar e recusa aprovador de outro papel (regras/aprovadores.csv)."""
import hashlib
import json
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src import comandos, simulacao
from src.cli import main
from src.fechamento import executar

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]
ATLAS = "39566044000119"
CAMPOS_ATLAS = ["situacao=Taxa da Atlas confirmada pelo Comercial, retroativa a 10/09",
                f"parametros=cnpj={ATLAS} | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=2.00",
                "o_que_fazer=Faturar desde 10/09", "quem_decide=Helena (Financeiro)", "informado_por=teste", "vigencia_de=2026-09-10"]


def _hash_dir(pasta: Path) -> dict:
    return {p.relative_to(pasta).as_posix(): hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(pasta.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def regras_copia(tmp_path_factory):
    destino = tmp_path_factory.mktemp("regras_sim") / "regras"
    shutil.copytree(RAIZ / "regras", destino)
    return destino


def test_simulacao_da_taxa_da_atlas_muda_so_a_atlas_e_nao_grava_nada(dados, config, regras_copia):
    antes = _hash_dir(regras_copia)
    p = comandos.propor(regras_copia, "TAXA_EXCECAO", {k: v for k, v in (c.split("=", 1) for c in CAMPOS_ATLAS)}, None, None, date(2026, 10, 17))
    assert p.valida, p.erros
    res = simulacao.simular(regras_copia, p, dados, "2026-09", {"AURORA", "MERIDIANO"})
    assert _hash_dir(regras_copia) == antes                          # a base real fica intacta
    assert res["integridade_depois"] == "OK" and not res["nada_muda"]
    com = res["comissoes_que_mudam"]
    assert [(c["cnpj"], c["linha_negocio"]) for c in com] == [(ATLAS, "CHECKOUT")]   # só o lojista-alvo
    assert com[0]["antes_brl"] is None and com[0]["qtd_depois"] == 57 and D(com[0]["depois_brl"]) > 0
    # o valor simulado é o que o motor dá ao fechar com a regra (nenhum número novo): 2% HALF_UP por linha, 57 linhas
    orbe = dados["orbe"]
    esperado = sum(((v * D("2") / 100).quantize(D("0.01"), rounding="ROUND_HALF_UP")
                    for v in orbe[orbe.cod_estabelecimento == "1076801732"].valor_bruto), D("0"))
    assert D(com[0]["depois_brl"]) == esperado
    notas = res["notas_que_mudam"]
    assert len(notas) == 1 and notas[0]["situacao"] == "nova" and notas[0]["tomador_cnpj"] == ATLAS
    assert notas[0]["id_depois"].startswith("NF-") and D(notas[0]["depois_brl"]) == esperado
    pend = {(x["tipo"], x["situacao"]) for x in res["pendencias_que_mudam"]}
    assert ("SEM_CONTRATO", "some") in pend                           # a Atlas deixa de ser SEM_CONTRATO
    assert ("DIVERGENCIA_TAXA", "aparece") in pend                    # 2% contratado x 0,99% a 4,49% aplicados: divergência de contrato
    assert all(x["lojista"] in ("ATLAS IDIOMAS", None) or ATLAS in str(x["cnpj_ou_ref"]) for x in res["pendencias_que_mudam"])
    assert res["lancamentos_que_mudam_de_conta"] == []
    assert res["carteira_que_entraria"] == {"linhas": 57, "valor_bruto_brl": "262138.61", "de_meses_anteriores": 0}   # as 57 de setembro saem da carteira
    t = res["totais"]
    assert D(t["comissao_checkout_brl"]["depois"]) == D("207039.73") + esperado and t["comissao_remessa_brl"]["antes"] == t["comissao_remessa_brl"]["depois"]
    assert t["notas"]["depois"]["quantidade"] == 22 and t["notas"]["antes"]["quantidade"] == 21
    txt = "\n".join(res["texto"])
    assert f"ATLAS IDIOMAS ({ATLAS}, CHECKOUT) passa a gerar" in txt and "em 57 transações" in txt
    assert "Nova nota NF-" in txt and "Pendência SEM_CONTRATO (ATLAS IDIOMAS" in txt and "some." in txt
    assert "Nenhum outro lojista muda." in txt and "Integridade do fechamento simulado: OK" in txt


def test_simulacao_com_anterior_fatura_a_carteira_de_setembro(dados, config, regras_copia, tmp_path):
    """Outubro com --anterior: a carteira da Atlas (57 linhas) entraria na comissão com a regra proposta."""
    from src import carteira
    from src.fechamento import escrever
    from tests.test_carteira import _outubro
    escrever(executar(dados, config, "2026-09", usar_ia=False), tmp_path / "set", config)
    p = comandos.propor(regras_copia, "TAXA_EXCECAO", {k: v for k, v in (c.split("=", 1) for c in CAMPOS_ATLAS)}, None, None, date(2026, 10, 17))
    res = simulacao.simular(regras_copia, p, _outubro(dados), "2026-10", {"AURORA", "MERIDIANO"}, carteira=carteira.ler(tmp_path / "set"))
    assert res["carteira_que_entraria"]["linhas"] == 114 and res["carteira_que_entraria"]["de_meses_anteriores"] == 57
    assert res["comissoes_que_mudam"][0]["qtd_depois"] == 114   # 57 de setembro + 57 de outubro
    assert any("114 linhas que hoje ficam na carteira pendente" in l and "57 vindas de meses anteriores" in l for l in res["texto"])


def test_cli_propor_mostra_o_efeito_simulado_e_nao_grava(pasta_dados, regras_copia, tmp_path, capsys):
    antes = _hash_dir(regras_copia)
    saida_antes = _hash_dir(RAIZ / "saida")
    proposta = tmp_path / "x.json"
    assert main(["regra", "propor", "--regras", str(regras_copia), "--saida", str(RAIZ / "saida"), "--entrada", str(pasta_dados),
                 "--tipo", "TAXA_EXCECAO", "--campos", *CAMPOS_ATLAS, "--proposta", str(proposta), "--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["ok"] and j["efeito_simulado"]["integridade_depois"] == "OK" and j["aviso_simulacao"] is None
    assert [c["cnpj"] for c in j["efeito_simulado"]["comissoes_que_mudam"]] == [ATLAS]
    assert _hash_dir(regras_copia) == antes and _hash_dir(RAIZ / "saida") == saida_antes   # nada gravado
    # em texto
    assert main(["regra", "propor", "--regras", str(regras_copia), "--saida", str(RAIZ / "saida"), "--entrada", str(pasta_dados),
                 "--tipo", "TAXA_EXCECAO", "--campos", *CAMPOS_ATLAS, "--proposta", str(proposta)]) == 0
    out = capsys.readouterr().out
    assert "Efeito simulado no fechamento de 09/2026" in out and "nada gravado" in out and "passa a gerar" in out
    assert "Nenhum outro lojista muda." in out and "Aprovação: Comercial (registro: Helena (Financeiro))" in out
    # sem --entrada: aviso, sem simulação
    assert main(["regra", "propor", "--regras", str(regras_copia), "--saida", str(RAIZ / "saida"),
                 "--tipo", "TAXA_EXCECAO", "--campos", *CAMPOS_ATLAS, "--proposta", str(proposta), "--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["efeito_simulado"] is None and "sem --entrada" in j["aviso_simulacao"]


def test_simulacao_de_regra_sem_efeito_diz_que_nada_muda(dados, regras_copia):
    p = comandos.propor(regras_copia, "MANUAL", {"situacao": "Conferir extrato", "o_que_fazer": "Conferir", "quem_decide": "Financeiro",
                                                 "informado_por": "teste"}, None, None, date(2026, 10, 17))
    res = simulacao.simular(regras_copia, p, dados, "2026-09", {"AURORA", "MERIDIANO"})
    assert res["nada_muda"] and res["texto"][0].startswith("Nenhum número do fechamento de 09/2026 muda")


def test_aplicar_diz_quem_aprova_e_recusa_aprovador_errado(regras_copia, tmp_path, capsys):
    """B2 / F9: TAXA_EXCECAO é aprovada pelo Comercial e registrada pela Helena; o comando mostra isso e recusa a Helena
    como aprovadora com mensagem clara, sem gravar nada."""
    proposta = tmp_path / "x.json"
    assert main(["regra", "propor", "--regras", str(regras_copia), "--saida", str(RAIZ / "saida"), "--tipo", "TAXA_EXCECAO",
                 "--campos", *CAMPOS_ATLAS, "--proposta", str(proposta)]) == 0
    capsys.readouterr()
    antes = _hash_dir(regras_copia)
    assert main(["regra", "aplicar", "--regras", str(regras_copia), "--proposta", str(proposta), "--aprovado-por", "Helena (Financeiro)"]) == 2
    saida = capsys.readouterr()
    assert "Regra do tipo TAXA_EXCECAO: quem aprova é Comercial, quem registra é Helena (Financeiro)" in saida.out
    assert "'Helena (Financeiro)' não pode aprovar" in saida.err and "--registrado-por" in saida.err
    assert _hash_dir(regras_copia) == antes
    assert main(["regra", "aplicar", "--regras", str(regras_copia), "--proposta", str(proposta), "--aprovado-por", "Diego (Comercial)",
                 "--registrado-por", "Helena (Financeiro)", "--json"]) == 0
    j = json.loads(capsys.readouterr().out)
    assert j["aprovacao"] == {"tipo": "TAXA_EXCECAO", "quem_aprova": "Comercial", "quem_registra": "Helena (Financeiro)"}
    assert "\nX-02;" in (regras_copia / "regras_negocio.csv").read_text(encoding="utf-8")
