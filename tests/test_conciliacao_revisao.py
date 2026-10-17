"""Conciliação entre fontes e correções da revisão da Fase 4 (em trânsito, inteiros no CSV, snapshot)."""
import csv
import re
from decimal import Decimal
from pathlib import Path

import pytest

from src.cli import main
from src.extratos import classificar
from src.fechamento import executar, extratos_de

D = Decimal
RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fech(dados, config):
    return executar(dados, config, "2026-09", usar_ia=False)


def test_conciliacao_ponte_decomposta(fech):
    p = fech.conciliacao["ponte"]
    assert p["repasse_pelo_total_declarado"] == D("39036.80") and p["comissao_calculada"] == D("39543.45")
    assert p["diferenca"] == D("506.65")
    # 50% dos 4 negativos (−1.834,05) tirados da base e 50% da repetição (821,88) tirada da base
    assert p["efeito_excluidas"] == D("917.025") and p["efeito_duplicatas"] == D("-410.94")
    assert p["qtd_excluidas"] == 4 and p["qtd_duplicatas"] == 1
    assert p["efeito_arredondamento"] == D("506.65") - D("917.025") + D("410.94")


def test_conciliacao_remessa_fecha_com_valor_mais_iof(fech):
    r = fech.conciliacao["remessa_banco"]
    assert r["liquidado_na_ponte"] == D("5611447.12") == r["operacoes_valor_mais_iof"]
    assert r["liquidado_menos_operacoes"] == D("0") and r["qtd_liquidacoes"] == 21
    assert r["recursos_recebidos"] == D("5629687.12") and r["recursos_menos_liquidado"] == D("18240.00")


def test_conciliacao_adquirente(fech):
    o = fech.conciliacao["orbe_banco"]
    assert o["liquido_orbe"] == D("7264348.20") and o["recebido_da_adquirente"] == D("3557246.29")
    assert o["qtd_recebimentos"] == 21 and o["qtd_repasses"] == 45
    assert o["repassado_a_lojistas"] == D("4230267.61") - D("12400.00")
    assert o["recebido_menos_repassado"] == D("3557246.29") - D("4217867.61")


def test_em_transito_quando_nada_cai_no_outro_banco(dados, config):
    extratos = [df.copy() for df in extratos_de(dados)]
    meridiano = extratos[1]
    extratos[1] = meridiano[~meridiano.descricao.str.contains("MESMA TITULARIDADE")]
    r = classificar(extratos, config, dados["plano_contas"], usar_ia=False)
    assert len(r.em_transito) == 4 and set(r.em_transito.banco) == {"AURORA"}
    assert set(r.em_transito.ref_origem) == {"L12", "L44", "L58", "L92"}


def test_credito_sem_debito_tambem_aparece(dados, config):
    extratos = [df.copy() for df in extratos_de(dados)]
    aurora = extratos[0]
    extratos[0] = aurora[aurora.ref_origem != "L12"]   # some a saída de 350 mil do Aurora
    r = classificar(extratos, config, dados["plano_contas"], usar_ia=False)
    assert set(r.em_transito.ref_origem) == {"L92", "MRD2026090107"}
    assert "mês anterior" in r.em_transito.set_index("ref_origem").loc["MRD2026090107", "motivo"]


def test_contagens_sao_inteiras_no_csv(dados, tmp_path):
    assert main(["fechar", "--saida", str(tmp_path), "--sem-ia"]) == 0
    for p in tmp_path.glob("*.csv"):
        with open(p, encoding="utf-8", newline="") as f:
            for linha in csv.reader(f, delimiter=";"):
                for celula in linha:
                    assert not re.fullmatch(r"-?\d+\.0", celula), (p.name, celula)


def test_saida_versionada_e_a_do_codigo_atual(dados, tmp_path):
    """saida/ é o que a banca vê: tem que ser exatamente o que o código gera hoje."""
    assert main(["fechar", "--saida", str(tmp_path), "--sem-ia"]) == 0
    for p in tmp_path.glob("*.csv"):
        versionado = RAIZ / "saida" / p.name
        assert versionado.exists(), f"saida/{p.name} não está versionado"
        assert p.read_bytes() == versionado.read_bytes(), f"saida/{p.name} está desatualizado: rode o fechar"
