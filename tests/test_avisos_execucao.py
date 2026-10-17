"""Avisos de execução são do motor: chegam ao resumo.json ("avisos") e ao topo do RELATORIO_FECHAMENTO.md, não só à
conversa com a IA (quem roda sem IA também precisa ver)."""
import json
import shutil
from pathlib import Path

from src import cli
from src.cli import main

RAIZ = Path(__file__).resolve().parents[1]


def _resumo_e_topo(saida: Path) -> tuple[dict, str]:
    res = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    rel = (saida / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    return res, rel.split("## Página 1")[0]


def test_base_inicial_apontada_vira_aviso(pasta_dados, tmp_path, capsys):
    regras = tmp_path / "assets" / "regras_iniciais"
    shutil.copytree(RAIZ / "regras", regras)
    assert main(["fechar", "--entrada", str(pasta_dados), "--regras", str(regras), "--saida", str(tmp_path / "s"),
                 "--sem-ia", "--json"]) == 0
    res, topo = _resumo_e_topo(tmp_path / "s")
    aviso = next(a for a in res["avisos"] if "base inicial da skill" in a)
    assert "--regras aponta para" in aviso and f"- {aviso}" in topo
    assert any(a.startswith("base de regras: última alteração registrada") for a in res["avisos"])


def test_sem_regras_na_skill_empacotada_usa_base_inicial_com_aviso(pasta_dados, tmp_path, monkeypatch, capsys):
    """Na skill empacotada não há regras/ ao lado de scripts/: sem --regras o motor usa assets/regras_iniciais/ e avisa."""
    scripts, iniciais = tmp_path / "scripts", tmp_path / "assets" / "regras_iniciais"
    scripts.mkdir()
    shutil.copytree(RAIZ / "regras", iniciais)
    monkeypatch.setattr(cli, "RAIZ", scripts)
    monkeypatch.setattr(cli, "REGRAS_INICIAIS", iniciais)
    assert main(["validar", "--entrada", str(pasta_dados), "--json"]) == 0
    v = json.loads(capsys.readouterr().out)
    assert any("--regras não foi informado: usei a base inicial" in a for a in v["regras"]["avisos"])
    assert main(["fechar", "--entrada", str(pasta_dados), "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    res, topo = _resumo_e_topo(tmp_path / "s")
    assert any("--regras não foi informado: usei a base inicial" in a and f"- {a}" in topo for a in res["avisos"])


def test_base_do_repositorio_nao_avisa_base_inicial(pasta_dados, tmp_path, capsys):
    assert main(["fechar", "--entrada", str(pasta_dados), "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    res, topo = _resumo_e_topo(tmp_path / "s")
    assert not any("base inicial" in a for a in res["avisos"])
    assert "## Avisos desta execução" in topo
