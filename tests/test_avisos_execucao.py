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


# ---------------------------------------------------------------- Causa 4: cada informação aparece uma vez

def test_nenhum_texto_de_saida_repete_a_mesma_frase(tmp_path, capsys):
    """Nenhum motivo/o_que_fazer de pendencias.csv e nenhuma linha de comunicacoes/*.md repete uma sequência de 8 palavras."""
    import csv
    from src.textos import repeticoes
    assert main(["fechar", "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    capsys.readouterr()
    achados = []
    for r in csv.DictReader(open(tmp_path / "s" / "pendencias.csv", encoding="utf-8"), delimiter=";"):
        for col in ("motivo", "o_que_fazer"):
            if repeticoes(r[col]):
                achados.append((r["id_saida"], col, repeticoes(r[col])[:2]))
    for md in sorted((tmp_path / "s" / "comunicacoes").glob("*.md")):
        for n, linha in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if repeticoes(linha):
                achados.append((md.name, n, repeticoes(linha)[:2]))
    assert achados == []


def test_sem_repeticao_tira_a_frase_repetida():
    from src.textos import repeticoes, sem_repeticao
    a = "A Orbe cobrou o que estava contratado e não há o que cobrar dela."
    assert sem_repeticao(f"Concessão fora do contrato. {a} Fim.", ja_dito=a) == "Concessão fora do contrato. Fim."
    assert repeticoes(f"{a} {a}") and not repeticoes(a)


# ---------------------------------------------------------------- Causa 5: o motor agrupa por natureza, a skill só mostra

def test_por_natureza_bate_com_os_arquivos_e_nao_tem_total_geral(tmp_path, capsys):
    import csv
    from decimal import Decimal as D
    assert main(["fechar", "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    s = tmp_path / "s"
    t = json.loads((s / "resumo.json").read_text(encoding="utf-8"))["totais"]
    pn = t["por_natureza"]
    assert set(pn) == {"FATURAR", "COBRAR_ORBE", "CONTESTAR_PONTE", "DEVOLVER_LOJISTA", "NAO_FATURAR", "ACOMPANHAR"}
    assert not any(k.lower().startswith("total") for k in pn)
    linhas = {}
    for nome in ("notas_a_emitir.csv", "pendencias.csv"):
        linhas.update({r["id_saida"]: r for r in csv.DictReader(open(s / nome, encoding="utf-8"), delimiter=";")})
    for nat, d in pn.items():
        if nat == "CONTESTAR_PONTE":
            continue
        assert all(linhas[i]["natureza"] == nat for i in d["ids"] if i.startswith("PEN-"))
        assert [i for pt in d["por_tipo"].values() for i in pt["ids"]] == d["ids"] and len(d["ids"]) == d["quantidade"]
        for tipo, pt in d["por_tipo"].items():
            assert all(linhas[i].get("tipo", "NOTA_A_EMITIR") == tipo for i in pt["ids"]) and len(pt["ids"]) == pt["quantidade"]
            assert sum(abs(D(linhas[i]["valor_brl"])) for i in pt["ids"]) == D(pt["valor_brl"])
        # tipos diferentes não se somam: total da natureza só com um tipo
        if len(d["por_tipo"]) > 1:
            assert d["valor_brl"] is None and d["motivo_sem_total"] == "tipos diferentes não se somam"
        else:
            assert sum(abs(D(linhas[i]["valor_brl"])) for i in d["ids"]) == D(d["valor_brl"]) and "motivo_sem_total" not in d
    assert {n for n, d in pn.items() if d["valor_brl"] is None} == {"NAO_FATURAR", "ACOMPANHAR"}
    assert set(pn["ACOMPANHAR"]["por_tipo"]) == {"CONFERIR_REPASSE_PONTE", "EXTRATO_NAO_IDENTIFICADO", "DEVOLUCAO"}
    assert pn["FATURAR"]["valor_brl"] == t["notas"]["valor_total_brl"] and pn["FATURAR"]["arquivo_origem"] == "notas_a_emitir.csv"
    # CONTESTAR_PONTE = o que se PEDE à Ponte: soma dos pedidos do anexo (a: excesso; b: diferença até o contratado; c: 0)
    cp = pn["CONTESTAR_PONTE"]
    anexo = list(csv.DictReader(open(s / "comunicacoes" / "ponte_contestacao.csv", encoding="utf-8"), delimiter=";"))
    pedido = {p["pedido"]: p for p in cp["pedidos"]}
    assert set(pedido) == {r["pedido"] for r in anexo} and cp["quantidade"] == len(pedido)
    a = [r for r in anexo if r["pedido"] == "a"]
    b = [r for r in anexo if r["pedido"] == "b"]
    assert D(pedido["a"]["valor_brl"]) == sum(D(r["valor_brl"]) for r in a)
    assert D(pedido["b"]["valor_brl"]) == -sum(D(r["diferenca_contrato_brl"]) for r in b) and pedido["c"]["valor_brl"] == "0.00"
    assert D(cp["valor_brl"]) == sum(D(p["valor_brl"]) for p in cp["pedidos"])
    assert all(linhas[i]["natureza"] == "CONTESTAR_PONTE" for i in cp["pendencias"])
    # os valor_brl de pendencias.csv não mudam: o spread negativo segue o que aconteceu
    assert all(D(linhas[i]["valor_brl"]) < 0 for i in cp["pendencias"] if linhas[i]["tipo"] == "SPREAD_NEGATIVO")
    # demais naturezas de pendência: mesmas exclusões do por_responsavel
    assert sum(D(pt["valor_brl"]) for n, d in pn.items() if n not in ("FATURAR", "CONTESTAR_PONTE")
               for pt in d["por_tipo"].values()) + sum(
        abs(D(linhas[i]["valor_brl"])) for i in cp["pendencias"]) == D(t["pendencias"]["em_jogo_brl"])
    fora = [x for d in pn.values() for x in d.get("fora_da_soma", [])]
    assert any("informativa" in x for x in fora) and any("incluída em" in x for x in fora)


def test_tipo_sem_natureza_vira_aviso_e_natureza_fora_da_lista_e_erro(pasta_dados, tmp_path, capsys):
    regras = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", regras)
    p = regras / "regras_negocio.csv"
    t = p.read_text(encoding="utf-8-sig")
    p.write_text(t.replace("tipo_pendencia=EM_TRANSITO | informativa=true | natureza=ACOMPANHAR",
                           "tipo_pendencia=EM_TRANSITO | informativa=true"), encoding="utf-8")
    avisos = _avisos_validar(pasta_dados, regras, capsys)
    assert any("sem natureza" in a and "EM_TRANSITO (DP-06)" in a for a in avisos)
    p.write_text(t.replace("natureza=ACOMPANHAR", "natureza=GUARDAR", 1), encoding="utf-8")
    assert main(["validar", "--entrada", str(pasta_dados), "--regras", str(regras), "--json"]) == 2
    assert "natureza 'GUARDAR' desconhecida" in capsys.readouterr().out


# ---------------------------------------------------------------- integridade de entrega

def test_resumo_lista_o_relatorio_e_todo_arquivo_listado_existe(tmp_path, capsys):
    assert main(["fechar", "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    res = json.loads((tmp_path / "s" / "resumo.json").read_text(encoding="utf-8"))
    assert res["arquivos"]["relatorio"] == "RELATORIO_FECHAMENTO.md"
    assert all((tmp_path / "s" / v).exists() for v in res["arquivos"].values())
    assert any(c["nome"].startswith("8. todo arquivo listado") and c["ok"] for c in res["integridade"])


def test_arquivo_listado_que_nao_existe_falha_a_checagem(tmp_path):
    from src.fechamento import checar_arquivos
    (tmp_path / "a.csv").write_text("x")
    c = checar_arquivos({"a": tmp_path / "a.csv", "b": tmp_path / "sumiu.csv"})
    assert not c.ok and c.nivel == "ERRO" and "sumiu.csv" in c.detalhe


def test_checagem_7_falha_se_o_anexo_da_ponte_nao_bate(tmp_path, capsys):
    from src.fechamento import executar
    from src.relatorio import checar_por_natureza
    from src import cli
    assert main(["fechar", "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    capsys.readouterr()
    base = cli.resolver_regras(None)
    ctx = cli.carregar_contexto(type("A", (), {"entrada": None, "competencia": None})(), base)
    f = executar(ctx.dados, ctx.config, ctx.competencia, usar_ia=False)
    assert checar_por_natureza(f, tmp_path / "s").ok
    anexo = tmp_path / "s" / "comunicacoes" / "ponte_contestacao.csv"
    anexo.write_text(anexo.read_text(encoding="utf-8").replace(";-1351.87;", ";-1351.00;"), encoding="utf-8")
    c = checar_por_natureza(f, tmp_path / "s")
    assert not c.ok and "CONTESTAR_PONTE pedido b" in c.detalhe


def test_checagem_7_confere_por_tipo_quando_a_natureza_nao_tem_total(tmp_path, capsys):
    from src.fechamento import executar
    from src.relatorio import checar_por_natureza
    from src import cli
    assert main(["fechar", "--saida", str(tmp_path / "s"), "--sem-ia", "--json"]) == 0
    capsys.readouterr()
    ctx = cli.carregar_contexto(type("A", (), {"entrada": None, "competencia": None})(), cli.resolver_regras(None))
    f = executar(ctx.dados, ctx.config, ctx.competencia, usar_ia=False)
    pend = tmp_path / "s" / "pendencias.csv"
    pend.write_text(pend.read_text(encoding="utf-8").replace(";L50;7350.00;", ";L50;7300.00;"), encoding="utf-8")
    c = checar_por_natureza(f, tmp_path / "s")
    assert not c.ok and "ACOMPANHAR/EXTRATO_NAO_IDENTIFICADO" in c.detalhe
