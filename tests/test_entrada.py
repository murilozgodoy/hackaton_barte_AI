"""Entrada flexível: zip com qualquer nome, pasta com o zip, arquivos soltos ou em subpastas.

A localização é pelos padrões de regras/fontes.csv (nunca por nome fixo de um mês); arquivo
ausente ou repetido para com mensagem em português dizendo qual. Sem --entrada, vale a pasta
entrada/ da raiz e, depois, o zip na raiz.
"""
import shutil
import zipfile
from decimal import Decimal
from pathlib import Path

import pytest

from src.cli import main
from src.fontes import carregar_config_fontes, localizar, preparar_entrada
from src.leitores.comum import ErroLeitura

RAIZ = Path(__file__).resolve().parents[1]
FONTES = carregar_config_fontes(RAIZ / "regras")
# nomes de outro mês, para provar que nada depende de "set2026"
NOMES = {
    "orbe": "01_orbe_relatorio_comissoes_out2026.csv",
    "taxas": "02_tabela_taxas_contratadas.xlsx",
    "ponte": "03_email_ponte_cambio_relatorio_out2026.eml",
    "plano_contas": "04_plano_de_contas_fenix_erp.csv",
    "aurora": "05a_extrato_banco_aurora_cc4471_out2026.csv",
    "meridiano": "05b_extrato_banco_meridiano_cc90233_out2026.ofx",
}


def _soltos(pasta: Path, fontes=NOMES, sub: str = "") -> Path:
    destino = pasta / sub if sub else pasta
    destino.mkdir(parents=True, exist_ok=True)
    for nome in fontes.values():
        (destino / nome).write_text("x", encoding="utf-8")
    (destino / "00_LEIA-ME.md").write_text("readme do pacote", encoding="utf-8")
    return pasta


def _zip(pasta: Path, nome: str, prefixo: str = "") -> Path:
    caminho = pasta / nome
    with zipfile.ZipFile(caminho, "w") as z:
        for fonte, arq in NOMES.items():
            z.writestr(prefixo + arq, "x")
        z.writestr(prefixo + "00_LEIA-ME.md", "readme")
    return caminho


ESPERADO = {**NOMES, "orbe": [NOMES["orbe"]], "ponte": [NOMES["ponte"]]}   # fontes multiplos=sim devolvem lista


def _nomes(arquivos: dict) -> dict:
    return {f: ([x.name for x in p] if isinstance(p, list) else p.name) for f, p in arquivos.items() if not f.startswith("_")}


def test_zip_com_qualquer_nome(tmp_path):
    z = _zip(tmp_path, "pacote_qualquer_nome.zip")
    pasta = preparar_entrada(z, tmp_path, FONTES)
    assert _nomes(localizar(pasta, FONTES)) == ESPERADO


def test_zip_com_subpasta_dentro(tmp_path):
    z = _zip(tmp_path, "dados.zip", prefixo="Tarvo_Data_Pack_out2026/")
    assert _nomes(localizar(preparar_entrada(z, tmp_path, FONTES), FONTES)) == ESPERADO


def test_pasta_com_o_zip_dentro(tmp_path):
    pasta = tmp_path / "recebido"
    pasta.mkdir()
    _zip(pasta, "Tarvo_Data_Pack_out2026.zip")
    assert _nomes(localizar(preparar_entrada(pasta, tmp_path, FONTES), FONTES)) == ESPERADO


def test_pasta_com_arquivos_soltos(tmp_path):
    pasta = _soltos(tmp_path / "soltos")
    assert _nomes(localizar(preparar_entrada(pasta, tmp_path, FONTES), FONTES)) == ESPERADO


def test_arquivos_em_subpastas(tmp_path):
    pasta = tmp_path / "mes"
    _soltos(pasta, {k: v for k, v in NOMES.items() if k in ("orbe", "taxas", "ponte")}, sub="adquirente e cambio")
    _soltos(pasta, {k: v for k, v in NOMES.items() if k not in ("orbe", "taxas", "ponte")}, sub="erp/bancos")
    assert _nomes(localizar(preparar_entrada(pasta, tmp_path, FONTES), FONTES)) == ESPERADO


def test_arquivo_ausente_diz_qual(tmp_path):
    pasta = _soltos(tmp_path / "faltando", {k: v for k, v in NOMES.items() if k != "orbe"})
    with pytest.raises(ErroLeitura) as e:
        localizar(pasta, FONTES)
    msg = str(e.value)
    assert "falta: orbe" in msg and "01_orbe_*.csv" in msg and "Relatório de comissões" in msg
    assert "encontrei: " in msg and "02_tabela_taxas_contratadas.xlsx" in msg   # diz o que falta E o que achou
    assert not [l for l in msg.splitlines() if "falta:" in l and "taxas" in l]   # só o que falta na lista de faltas


def test_arquivo_repetido_diz_quais(tmp_path):
    pasta = _soltos(tmp_path / "repetido")
    (pasta / "02_tabela_taxas_contratadas (1).xlsx").write_text("x", encoding="utf-8")
    with pytest.raises(ErroLeitura) as e:
        localizar(pasta, FONTES)
    msg = str(e.value)
    assert "Mais de um" in msg and "taxas" in msg and "02_tabela_taxas_contratadas.xlsx" in msg
    assert "02_tabela_taxas_contratadas (1).xlsx" in msg and "deixe só um" in msg


def test_sem_entrada_usa_pasta_entrada_da_raiz(tmp_path):
    raiz = tmp_path / "projeto"
    _soltos(raiz / "entrada")
    _zip(raiz, "Tarvo_Data_Pack_set2026.zip")   # existe, mas entrada/ tem prioridade
    pasta = preparar_entrada(None, raiz, FONTES)
    assert pasta == raiz / "entrada"


def test_sem_entrada_e_pasta_entrada_so_com_readme_usa_o_zip_da_raiz(tmp_path):
    raiz = tmp_path / "projeto"
    (raiz / "entrada").mkdir(parents=True)
    (raiz / "entrada" / "README.md").write_text("coloque aqui os arquivos", encoding="utf-8")
    _zip(raiz, "Tarvo_Data_Pack_out2026.zip")
    pasta = preparar_entrada(None, raiz, FONTES)
    assert _nomes(localizar(pasta, FONTES)) == ESPERADO


def test_sem_entrada_e_sem_nada_explica_em_portugues(tmp_path):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    with pytest.raises(ErroLeitura) as e:
        preparar_entrada(None, raiz, FONTES)
    assert "entrada/" in str(e.value) and "--entrada" in str(e.value)


def test_sem_entrada_e_dois_zips_na_raiz_pede_para_escolher(tmp_path):
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    _zip(raiz, "Tarvo_Data_Pack_set2026.zip")
    _zip(raiz, "Tarvo_Data_Pack_out2026.zip")
    with pytest.raises(ErroLeitura, match="Mais de um pacote"):
        preparar_entrada(None, raiz, FONTES)


def test_entrada_inexistente(tmp_path):
    with pytest.raises(ErroLeitura, match="não existe"):
        preparar_entrada(tmp_path / "nada", tmp_path, FONTES)


# ---------------------------------------------------------------- com o data pack real: pasta solta == zip

def _csvs(pasta: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(pasta.glob("*.csv"))}


@pytest.mark.parametrize("modo", ["soltos", "subpasta", "pasta_com_zip"])
def test_cli_fechar_por_pasta_gera_o_mesmo_saida_que_o_zip(dados, tmp_path, modo):
    """A banca pode entregar os arquivos de qualquer jeito: o saida/ tem que ser o versionado."""
    zip_real = next(RAIZ.glob(FONTES["pacote"]["padrao_arquivo"]))
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    if modo == "pasta_com_zip":
        shutil.copy(zip_real, entrada / "arquivos_do_mes.zip")
    else:
        with zipfile.ZipFile(zip_real) as z:
            z.extractall(entrada / "Tarvo_Data_Pack_out2026" / "arquivos" if modo == "subpasta" else entrada)
    assert main(["fechar", "--entrada", str(entrada), "--saida", str(tmp_path / "saida"), "--sem-ia"]) == 0
    assert _csvs(tmp_path / "saida") == _csvs(RAIZ / "saida")
    assert (tmp_path / "saida" / "resumo.json").read_bytes() == (RAIZ / "saida" / "resumo.json").read_bytes()


# ---------------------------------------------------------------- reconhecimento por conteúdo, fontes múltiplas e avisos
# (a partir do pacote real de setembro, que traz o 01 e os 14 ajustes tardios do 06)

import csv
import json

from src.cli import main as _main


def _pasta_mes(pasta_dados: Path, tmp_path: Path, excluir=(), renomear=None, extras=None) -> Path:
    """Cópia dos arquivos do mês numa pasta nova, sem alguns, com outros renomeados e com arquivos extras."""
    destino = tmp_path / "mes"
    destino.mkdir()
    for p in pasta_dados.iterdir():
        if not p.is_file() or any(p.name.startswith(e) for e in excluir):
            continue
        nome = next((v for k, v in (renomear or {}).items() if p.name.startswith(k)), p.name)
        shutil.copy(p, destino / nome)
    for nome, conteudo in (extras or {}).items():
        (destino / nome).write_bytes(conteudo if isinstance(conteudo, bytes) else conteudo.encode("utf-8"))
    return destino


def _fechar(pasta: Path, saida: Path, capsys):
    codigo = _main(["fechar", "--entrada", str(pasta), "--saida", str(saida), "--sem-ia", "--json"])
    out = capsys.readouterr()
    return codigo, (json.loads(out.out) if codigo in (0, 3) and out.out.strip().startswith("{") else None), out.err


def _iguais_ao_versionado(saida: Path, nomes=("comissoes_por_lojista.csv", "notas_a_emitir.csv", "divergencias_taxa.csv",
                                             "lancamentos_classificados.csv", "pendencias.csv")) -> list[str]:
    return [n for n in nomes if (saida / n).read_bytes() != (RAIZ / "saida" / n).read_bytes()]


def test_ajuste_tardio_e_reconhecido_pelo_conteudo_com_qualquer_nome(pasta_dados, tmp_path, capsys):
    """R1/R5a: o 06 renomeado para um nome que não casa com padrão nenhum entra pela assinatura (cabeçalho da Orbe):
    mesmo resultado que com o nome original."""
    pasta = _pasta_mes(pasta_dados, tmp_path, renomear={"06_orbe": "orbe_ajustes_qualquer.csv"})
    codigo, j, _ = _fechar(pasta, tmp_path / "saida", capsys)
    assert codigo == 0 and j["avisos"] == [] and _iguais_ao_versionado(tmp_path / "saida") == []
    assert j["entrada"]["arquivos"]["orbe"] == "01_orbe_relatorio_comissoes_set2026.csv, orbe_ajustes_qualquer.csv"
    assert j["totais"]["comissao_checkout_brl"] == "203735.34" and j["contexto"]["fontes"]["orbe"]["linhas"] == 1957
    rastro = list(csv.DictReader(open(tmp_path / "saida" / "rastro.csv", encoding="utf-8"), delimiter=";"))
    assert sum(1 for r in rastro if r["arquivo_origem"] == "orbe_ajustes_qualquer.csv" and r["id_saida"].startswith("COM-CHK")) == 14


def test_arquivo_estranho_nao_para_e_vira_aviso_persistido(pasta_dados, tmp_path, capsys):
    """R3/R5b: arquivo que não bate com assinatura nem padrão: fecha igual, com aviso no resumo e no relatório."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "Qualquer"
    wb.active["A1"] = "nada a ver"
    xlsx = tmp_path / "planilha_qualquer.xlsx"
    wb.save(xlsx)
    pasta = _pasta_mes(pasta_dados, tmp_path, extras={"notas.txt": "lembrete da analista", "planilha_qualquer.xlsx": xlsx.read_bytes()})
    codigo, j, _ = _fechar(pasta, tmp_path / "saida", capsys)
    assert codigo == 0 and _iguais_ao_versionado(tmp_path / "saida") == []
    avisos = [a for a in j["avisos"] if "não reconhecido; não foi usado" in a]
    assert len(avisos) == 2 and any("notas.txt" in a for a in avisos) and any("planilha_qualquer.xlsx" in a for a in avisos)
    rel = (tmp_path / "saida" / "RELATORIO_FECHAMENTO.md").read_text(encoding="utf-8")
    assert "## Avisos" in rel and "arquivo notas.txt não reconhecido; não foi usado" in rel
    res = json.loads((tmp_path / "saida" / "resumo.json").read_text(encoding="utf-8"))
    assert res["avisos"] == j["avisos"]


def test_sem_o_ajuste_tardio_da_os_valores_antigos(pasta_dados, tmp_path, capsys):
    """R5c: o ajuste tardio é só somado. Sem o 06, setembro fecha com os valores de antes."""
    pasta = _pasta_mes(pasta_dados, tmp_path, excluir=("06_orbe",))
    codigo, j, _ = _fechar(pasta, tmp_path / "saida", capsys)
    assert codigo == 0 and j["avisos"] == []
    assert j["totais"]["comissao_checkout_brl"] == "207039.73" and j["totais"]["comissao_remessa_brl"] == "39543.45"
    assert j["totais"]["notas"] == {"quantidade": 21, "valor_total_brl": "246588.68"}
    assert j["contexto"]["fontes"]["orbe"]["linhas"] == 1943 and j["entrada"]["arquivos"]["orbe"] == "01_orbe_relatorio_comissoes_set2026.csv"
    com = list(csv.DictReader(open(tmp_path / "saida" / "comissoes_por_lojista.csv", encoding="utf-8"), delimiter=";"))
    assert sum(int(r["qtd_transacoes"]) for r in com if r["linha_negocio"] == "CHECKOUT") == 1886
    assert j["totais"]["divergencias"]["linhas"] == 115 and j["totais"]["pendencias"]["quantidade"] == 16


def test_fonte_obrigatoria_ausente_para_e_diz_o_que_achou(pasta_dados, tmp_path, capsys):
    """R4/R5d: sem o extrato do Meridiano, código 1 com o que falta E o que foi encontrado. Nada de fechamento parcial."""
    pasta = _pasta_mes(pasta_dados, tmp_path, excluir=("05b_",))
    assert _main(["validar", "--entrada", str(pasta)]) == 1
    err = capsys.readouterr().err
    assert "falta: meridiano" in err and "Extrato OFX" in err and "05b_extrato_banco_meridiano*.ofx" in err
    assert "encontrei: 01_orbe_relatorio_comissoes_set2026.csv" in err and "06_orbe_ajustes_tardios_set2026.csv" in err
    assert not (tmp_path / "saida").exists()


def test_dois_arquivos_para_fonte_de_um_so_e_erro_claro(pasta_dados, tmp_path, capsys):
    """R2/R5e: duas planilhas de taxas (mesmo conteúdo, nomes diferentes): erro que diz os dois nomes."""
    pasta = _pasta_mes(pasta_dados, tmp_path)
    shutil.copy(pasta / "02_tabela_taxas_contratadas.xlsx", pasta / "taxas_reenviadas.xlsx")
    assert _main(["validar", "--entrada", str(pasta)]) == 1
    err = capsys.readouterr().err
    assert "Mais de um arquivo para a fonte taxas" in err and "02_tabela_taxas_contratadas.xlsx" in err
    assert "taxas_reenviadas.xlsx" in err and "deixe só um" in err


def test_lixo_de_sistema_no_zip_e_ignorado_sem_aviso(pasta_dados, tmp_path, capsys):
    """R3/R5f: .DS_Store, __MACOSX, ~$ e Thumbs.db no zip não são dados nem viram aviso."""
    z = tmp_path / "pacote.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in pasta_dados.iterdir():
            if p.is_file():
                zf.write(p, f"Pacote/{p.name}")
        zf.writestr("Pacote/.DS_Store", b"\x00\x01lixo")
        zf.writestr("__MACOSX/Pacote/._01_orbe_relatorio_comissoes_set2026.csv", b"\x00Mac OS X")
        zf.writestr("Pacote/~$02_tabela_taxas_contratadas.xlsx", b"lock do Excel")
        zf.writestr("Pacote/Thumbs.db", b"thumbs")
    codigo, j, _ = _fechar(z, tmp_path / "saida", capsys)
    assert codigo == 0 and j["avisos"] == [] and _iguais_ao_versionado(tmp_path / "saida") == []


def test_id_transacao_repetido_entre_arquivos_da_orbe(pasta_dados, tmp_path, capsys):
    """Bug do 06, item 2: id repetido entre arquivos. Linha idêntica conta uma vez (aviso); linha com valores
    diferentes tira TODAS as ocorrências da comissão, com pendência DUPLICATA_DIVERGENTE para a Helena."""
    orbe = next(pasta_dados.glob("01_orbe_*.csv")).read_text(encoding="utf-8").splitlines()
    cab, igual, diferente = orbe[0], orbe[5], orbe[6].split(";")
    id_dif = diferente[0]
    bruto = Decimal(diferente[8].replace(".", "").replace(",", ".")) + Decimal("1000")
    taxa = Decimal(diferente[10].replace(".", "").replace(",", "."))
    diferente[8], diferente[11] = f"{bruto:.2f}".replace(".", ","), f"{bruto - taxa:.2f}".replace(".", ",")
    extra = "\n".join([cab, igual, ";".join(diferente)]) + "\n"
    pasta = _pasta_mes(pasta_dados, tmp_path, extras={"07_orbe_reenvio_set2026.csv": extra})
    codigo, j, _ = _fechar(pasta, tmp_path / "saida", capsys)
    assert codigo == 0 and j["status_integridade"] == "OK"
    assert any("contado(s) uma vez" in a and igual.split(";")[0] in a for a in j["avisos"])
    assert any("valores diferentes" in a and id_dif in a for a in j["avisos"])
    assert j["contexto"]["fontes"]["orbe"]["linhas"] == 1957 + 1   # a idêntica sumiu; a divergente ficou com as 2 linhas
    pend = list(csv.DictReader(open(tmp_path / "saida" / "pendencias.csv", encoding="utf-8"), delimiter=";"))
    dup = [p for p in pend if p["tipo"] == "DUPLICATA_DIVERGENTE"]
    assert len(dup) == 1 and dup[0]["ref_origem"] == id_dif and dup[0]["linha_negocio"] == "CHECKOUT"
    assert dup[0]["quem_decide"] == "Helena (Financeiro)" and "07_orbe_reenvio_set2026.csv" in dup[0]["motivo"] and dup[0]["qtd_itens"] == "2"
    rastro_base = list(csv.DictReader(open(RAIZ / "saida" / "rastro.csv", encoding="utf-8"), delimiter=";"))
    comissao_linha = sum(Decimal(r["valor"]) for r in rastro_base if r["id_saida"].startswith("COM-CHK") and r["ref_origem"] == id_dif)
    assert Decimal(j["totais"]["comissao_checkout_brl"]) == Decimal("203735.34") - comissao_linha
    assert j["totais"]["pendencias"]["quantidade"] == 17
