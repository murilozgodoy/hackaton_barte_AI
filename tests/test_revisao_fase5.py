"""Achados da revisão da Fase 5: cobertura de vigência, strings decimais estritas, relatório inválido."""
import json
from decimal import Decimal

import pytest

from src.cli import main
from src.relatorio import _s
from tests.sintetico import regras_copia


def test_resumo_recusa_valor_nao_arredondado():
    assert _s(Decimal("917.03")) == "917.03" and _s(Decimal("0")) == "0.00" and _s(None) is None
    with pytest.raises(ValueError, match="não está arredondado"):
        _s(Decimal("917.025"))


def test_dono_de_pendencia_vencido_para_no_validar_com_codigo_2(dados, tmp_path, capsys):
    regras = regras_copia(tmp_path, [("tipo_pendencia=CONFERIR_REPASSE_PONTE;", "tipo_pendencia=CONFERIR_REPASSE_PONTE;")])
    p = regras / "regras_negocio.csv"
    t = p.read_text(encoding="utf-8")
    linha = next(l for l in t.splitlines() if l.startswith("DP-11;"))
    nova = linha.replace(";;;ATIVA;", ";;2026-08-31;ATIVA;")
    assert nova != linha
    p.write_text(t.replace(linha, nova), encoding="utf-8")
    assert main(["validar", "--regras", str(regras), "--json"]) == 2
    j = json.loads(capsys.readouterr().out)
    assert j["ok"] is False and "CONFERIR_REPASSE_PONTE" in j["erro"] and "não cobre a competência" in j["erro"]
    assert main(["fechar", "--regras", str(regras), "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 2
    j = json.loads(capsys.readouterr().out)
    assert j["ok"] is False


def test_parametro_com_vigencia_que_acaba_no_meio_do_mes_para(dados, tmp_path, capsys):
    regras = regras_copia(tmp_path, [("participacao_spread=0.50;Comissão de remessa", "participacao_spread=0.50;Comissão de remessa")])
    p = regras / "regras_negocio.csv"
    t = p.read_text(encoding="utf-8")
    linha = next(l for l in t.splitlines() if l.startswith("P-01;"))
    p.write_text(t.replace(linha, linha.replace(";;;ATIVA;", ";;2026-09-15;ATIVA;")), encoding="utf-8")
    assert main(["validar", "--regras", str(regras)]) == 2
    assert "participacao_spread" in capsys.readouterr().err


def test_relatorio_invalido_nao_diz_ok(dados, tmp_path):
    assert main(["fechar", "--saida", str(tmp_path), "--competencia", "2026-11", "--sem-ia"]) == 3
    rel = (tmp_path / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert "RELATÓRIO INVÁLIDO" in rel and "Integridade: OK" not in rel
    assert not (tmp_path / "resumo.json").exists()
