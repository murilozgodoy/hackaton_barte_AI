"""Localiza os arquivos de entrada do mês a partir de regras/fontes.csv.

Aceita o zip do pacote (com qualquer nome), uma pasta com o zip dentro, uma pasta com os
arquivos soltos ou em subpastas. Cada fonte é achada pelo padrão de nome de fontes.csv,
nunca por nome fixo de um mês. Zips são extraídos numa pasta temporária, apagada ao fim.
"""
from __future__ import annotations

import csv
import fnmatch
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .leitores.comum import ErroLeitura, ler_texto

PASTA_ENTRADA = "entrada"          # pasta da raiz usada quando não se passa --entrada
_IGNORAR_PARTES = {"__MACOSX"}
_TEMPORARIOS: list[tempfile.TemporaryDirectory] = []   # mantidos vivos até o fim do processo


def carregar_config_fontes(dir_config: Path) -> dict[str, dict]:
    caminho = Path(dir_config) / "fontes.csv"
    texto, _ = ler_texto(caminho, esperado=["fonte", "padrao_arquivo"])
    linhas = [l for l in texto.splitlines() if l.strip()]
    return {r["fonte"].strip(): {k: (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(linhas, delimiter=";")}


def _extrair_zip(zip_path: Path) -> Path:
    """Extrai o zip numa pasta temporária nova (nunca reaproveita extração antiga). Recusa caminhos que saiam dela."""
    tmp = tempfile.TemporaryDirectory(prefix=f"{zip_path.stem}_")
    _TEMPORARIOS.append(tmp)
    alvo = Path(tmp.name)
    try:
        with zipfile.ZipFile(zip_path) as z:
            for membro in z.infolist():
                p = PurePosixPath(membro.filename)
                if p.is_absolute() or ".." in p.parts:
                    raise ErroLeitura(f"{zip_path.name}: caminho suspeito no zip: {membro.filename}")
            z.extractall(alvo)
    except zipfile.BadZipFile:
        raise ErroLeitura(f"{zip_path.name} não é um zip válido") from None
    return alvo


def _arquivos_de_dados(pasta: Path) -> list[Path]:
    """Arquivos sob a pasta (recursivo), fora lixo de sistema e READMEs."""
    return sorted(p for p in Path(pasta).rglob("*") if p.is_file()
                  and not (_IGNORAR_PARTES & set(p.parts)) and not any(parte.startswith(".") for parte in p.parts)
                  and not p.name.upper().startswith(("README", "LEIA-ME", "00_LEIA-ME")))


def preparar_entrada(entrada: Path | None, raiz: Path, cfg: dict) -> Path:
    """Devolve a pasta onde procurar os arquivos do mês.

    entrada = zip -> extraído em pasta temporária; entrada = pasta -> a própria (zips dentro dela
    são abertos por `localizar`). Sem entrada: a pasta entrada/ da raiz, se tiver algum arquivo
    de dados; senão o único zip de pacote na raiz (padrão `pacote` de fontes.csv).
    """
    raiz = Path(raiz)
    if entrada is not None:
        entrada = Path(entrada)
        if entrada.is_file() and entrada.suffix.lower() == ".zip":
            return _extrair_zip(entrada)
        if entrada.is_dir():
            return entrada
        if entrada.exists():
            raise ErroLeitura(f"Entrada {entrada} não é um .zip nem uma pasta")
        raise ErroLeitura(f"Entrada {entrada} não existe")
    pasta = raiz / PASTA_ENTRADA
    if pasta.is_dir() and _arquivos_de_dados(pasta):
        return pasta
    padrao = cfg["pacote"]["padrao_arquivo"]
    pacotes = sorted(p for p in raiz.glob(padrao) if p.is_file())
    if len(pacotes) == 1:
        return _extrair_zip(pacotes[0])
    if not pacotes:
        raise ErroLeitura(f"Nenhum arquivo do mês: coloque o zip ou os arquivos em {PASTA_ENTRADA}/ "
                          f"(ou um pacote {padrao} na raiz), ou use --entrada <zip ou pasta>.")
    nomes = ", ".join(p.name for p in pacotes)
    raise ErroLeitura(f"Mais de um pacote encontrado na raiz ({nomes}). Use --entrada para escolher.")


def localizar(pasta: Path, cfg: dict) -> dict[str, Path]:
    """Acha cada fonte pelo padrão de nome, na pasta, em subpastas e dentro de zips. Exige exatamente um arquivo por fonte."""
    pasta = Path(pasta)
    arquivos = _arquivos_de_dados(pasta)
    for z in [p for p in arquivos if p.suffix.lower() == ".zip"]:
        arquivos += _arquivos_de_dados(_extrair_zip(z))
    achados, faltam, repetidos = {}, [], []
    for fonte, linha in cfg.items():
        if fonte == "pacote":
            continue
        padrao = linha["padrao_arquivo"]
        candidatos = [p for p in arquivos if fnmatch.fnmatchcase(p.name.lower(), padrao.lower())]
        descricao = f" ({linha['descricao']})" if linha.get("descricao") else ""
        if len(candidatos) == 1:
            achados[fonte] = candidatos[0]
        elif not candidatos:
            faltam.append(f"Falta o arquivo da fonte {fonte}{descricao}: nenhum arquivo com o padrão {padrao}")
        else:
            repetidos.append(f"Mais de um arquivo para a fonte {fonte}{descricao}: "
                             + ", ".join(p.name for p in candidatos) + ". Deixe só um")
    if faltam or repetidos:
        raise ErroLeitura(f"Arquivos de entrada com problema em {pasta}:\n  " + "\n  ".join(faltam + repetidos))
    return achados
