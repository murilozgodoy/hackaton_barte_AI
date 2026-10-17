"""Localiza os arquivos de entrada do mês (zip ou pasta) a partir de config/fontes.csv."""
from __future__ import annotations

import csv
import zipfile
from pathlib import Path, PurePosixPath

from .leitores.comum import ErroLeitura, ler_texto


def carregar_config_fontes(dir_config: Path) -> dict[str, dict]:
    caminho = Path(dir_config) / "fontes.csv"
    texto, _ = ler_texto(caminho, esperado=["fonte", "padrao_arquivo"])
    linhas = [l for l in texto.splitlines() if l.strip()]
    return {r["fonte"].strip(): {k: (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(linhas, delimiter=";")}


def _extrair_zip(zip_path: Path, destino: Path) -> Path:
    """Extrai para destino/<nome do zip>/ (uma vez). Recusa caminhos que saiam da pasta."""
    alvo = destino / zip_path.stem
    if alvo.is_dir() and any(alvo.iterdir()):
        return alvo
    alvo.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for membro in z.infolist():
            p = PurePosixPath(membro.filename)
            if p.is_absolute() or ".." in p.parts:
                raise ErroLeitura(f"{zip_path.name}: caminho suspeito no zip: {membro.filename}")
        z.extractall(alvo)
    return alvo


def preparar_entrada(entrada: Path | None, raiz: Path, dir_dados: Path, cfg: dict) -> Path:
    """Devolve a pasta com os arquivos do mês.

    entrada = zip -> extrai em data/<zip>/; entrada = pasta -> usa a pasta.
    Sem entrada: procura o pacote (padrão de config/fontes.csv) na raiz do projeto;
    exige que haja exatamente um, para não fechar o mês com o pacote errado.
    """
    if entrada is not None:
        entrada = Path(entrada)
        if entrada.is_file() and entrada.suffix.lower() == ".zip":
            return _extrair_zip(entrada, dir_dados)
        if entrada.is_dir():
            return entrada
        raise ErroLeitura(f"Entrada {entrada} não é um .zip nem uma pasta")
    padrao = cfg["pacote"]["padrao_arquivo"]
    pacotes = sorted(Path(raiz).glob(padrao))
    if len(pacotes) == 1:
        return _extrair_zip(pacotes[0], dir_dados)
    if not pacotes:
        raise ErroLeitura(f"Nenhum pacote {padrao} em {raiz}. Use --entrada <zip ou pasta>.")
    nomes = ", ".join(p.name for p in pacotes)
    raise ErroLeitura(f"Mais de um pacote encontrado ({nomes}). Use --entrada para escolher.")


def localizar(pasta: Path, cfg: dict) -> dict[str, Path]:
    """Acha cada fonte pelo padrão de nome. Exige exatamente um arquivo por fonte."""
    achados, erros = {}, []
    for fonte, linha in cfg.items():
        if fonte == "pacote":
            continue
        candidatos = sorted(p for p in Path(pasta).rglob(linha["padrao_arquivo"])
                            if p.is_file() and "__MACOSX" not in p.parts and not p.name.startswith("."))
        if len(candidatos) == 1:
            achados[fonte] = candidatos[0]
        elif not candidatos:
            erros.append(f"{fonte}: nenhum arquivo com o padrão {linha['padrao_arquivo']}")
        else:
            erros.append(f"{fonte}: mais de um arquivo com o padrão {linha['padrao_arquivo']}: "
                         + ", ".join(p.name for p in candidatos))
    if erros:
        raise ErroLeitura("Arquivos de entrada com problema em " + str(pasta) + ":\n  " + "\n  ".join(erros))
    return achados
