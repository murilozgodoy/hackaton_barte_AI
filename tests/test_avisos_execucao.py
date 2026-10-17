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


def _base_com_historico(tmp_path: Path, aprovador_por_id: dict[str, str]) -> Path:
    """Cópia de regras/ com o histórico reescrito: uma linha CRIOU por regra ativa, com o aprovador dado (padrão: Helena)."""
    import csv
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    ids = [r["id"] for r in csv.DictReader(open(regras / "regras_negocio.csv", encoding="utf-8-sig"), delimiter=";")
           if r["status"] == "ATIVA"]
    cab = "data;quem;id_regra;acao;antes;depois;motivo;fonte;aprovado_por;registrado_por"
    linhas = [f"2026-10-17;teste;{i};CRIOU;;;;;{aprovador_por_id.get(i, 'Helena (Financeiro), Slack 17/10 09h49')};"
              for i in ids]
    (regras / "historico_alteracoes.csv").write_text("\n".join([cab] + linhas) + "\n", encoding="utf-8")
    return regras


def _avisos_validar(pasta_dados, regras: Path, capsys) -> list[str]:
    assert main(["validar", "--entrada", str(pasta_dados), "--regras", str(regras), "--json"]) == 0
    return json.loads(capsys.readouterr().out)["regras"]["avisos"]


def test_regra_ativa_sem_aprovador_vira_aviso_e_com_aprovador_nao(pasta_dados, tmp_path, capsys):
    regras = _base_com_historico(tmp_path, {"J-01": "—", "E-03": "", "J-02": "PREMISSA MN AI (sem aprovação do financeiro)"})
    avisos = _avisos_validar(pasta_dados, regras, capsys)
    sem = next(a for a in avisos if "sem aprovador" in a)
    assert "2 item(ns)" in sem and "J-01" in sem and "E-03" in sem and "X-01" not in sem and "J-02" not in sem
    prem = next(a for a in avisos if "premissas em uso" in a)
    assert "J-02" in prem and "J-01" not in prem


def test_base_toda_aprovada_nao_avisa(pasta_dados, tmp_path, capsys):
    avisos = _avisos_validar(pasta_dados, _base_com_historico(tmp_path, {}), capsys)
    assert not any("sem aprovador" in a or "premissas em uso" in a for a in avisos)


def test_ultima_linha_do_historico_decide_e_vale_para_varios_ids(pasta_dados, tmp_path, capsys):
    """Premissa depois confirmada pela Helena deixa de ser premissa; linha com "C-01, C-02" vale para os dois ids."""
    regras = _base_com_historico(tmp_path, {"P-05": "PREMISSA MN AI (sem aprovação do financeiro)"})
    with open(regras / "historico_alteracoes.csv", "a", encoding="utf-8") as f:
        f.write("2026-10-17;teste;P-05;ALTEROU;;;;;Helena (Financeiro), Slack ~22h;\n")
        f.write("2026-10-17;teste;C-01, C-02;ALTEROU;;;;;—;\n")
    avisos = _avisos_validar(pasta_dados, regras, capsys)
    assert not any("premissas em uso" in a for a in avisos)
    sem = next(a for a in avisos if "sem aprovador" in a)
    assert "C-01, C-02" in sem and "P-05" not in sem


# ---------------------------------------------------------------- Causa 1: o motor publica o que a IA somava ou comparava

def test_resumo_publica_total_e_diferenca_notas_com_motivo(pasta_dados, tmp_path, capsys):
    assert main(["fechar", "--entrada", str(pasta_dados), "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    t = json.loads((tmp_path / "s" / "resumo.json").read_text(encoding="utf-8"))["totais"]
    from decimal import Decimal as D
    assert D(t["comissao_total_brl"]) == D(t["comissao_checkout_brl"]) + D(t["comissao_remessa_brl"])
    assert D(t["diferenca_notas_x_comissao_brl"]) == D(t["notas"]["valor_total_brl"]) - D(t["comissao_total_brl"])
    com = {r["id_saida"]: D(r["comissao_brl"]) for r in __import__("csv").DictReader(
        open(tmp_path / "s" / "comissoes_por_lojista.csv", encoding="utf-8"), delimiter=";")}
    ids = t["diferenca_notas_x_comissao"]["ids_sem_nota"]
    assert ids and all(com[i] <= 0 for i in ids) and -sum(com[i] for i in ids) == D(t["diferenca_notas_x_comissao_brl"])
    assert all(i in t["diferenca_notas_x_comissao"]["motivo"] for i in ids)


def test_lembretes_com_prazo_tem_datas_das_fontes_e_nao_de_hoje(pasta_dados, tmp_path, capsys):
    assert main(["fechar", "--entrada", str(pasta_dados), "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    lemb = {l["regra_id"]: l for l in json.loads((tmp_path / "s" / "resumo.json").read_text(encoding="utf-8"))["lembretes"]}
    con = next(l for l in lemb.values() if "dias úteis" in (l.get("base_da_data") or ""))
    rep = next(l for l in lemb.values() if "data de repasse" in (l.get("base_da_data") or ""))
    assert con["data_base"] == rep["data_base"] == "2026-10-02"    # data de envio do e-mail do parceiro
    assert con["data_limite"] == "2026-10-09" and rep["data_limite"] == "2026-10-06"
    assert not any(k in l for l in lemb.values() for k in ("vencido", "dias_restantes", "hoje"))
    sem_prazo = [l for l in lemb.values() if "data_limite" not in l]
    assert sem_prazo, "lembrete sem prazo= não ganha campos de data"


def test_prazo_desconhecido_e_erro_de_regra(pasta_dados, tmp_path, capsys):
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    p = regras / "regras_negocio.csv"
    p.write_text(p.read_text(encoding="utf-8-sig").replace("prazo=repasse_parceiro", "prazo=amanha"), encoding="utf-8")
    assert main(["validar", "--entrada", str(pasta_dados), "--regras", str(regras), "--json"]) == 2
    assert "prazo 'amanha' desconhecido" in capsys.readouterr().out
