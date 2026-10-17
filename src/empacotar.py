"""Empacota a skill (SKILL.md + references + scripts + base de regras inicial) num zip autocontido.

O zip contém a pasta `fechamento-tarvo/`, pronta para upload no Claude.ai/Cowork ou
cópia para a pasta de skills de qualquer agente compatível com SKILL.md. `scripts/`
leva uma cópia do motor (`src/`) e `assets/regras_iniciais/` a base de regras atual.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

NOME_SKILL = "fechamento-tarvo"
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".DS_Store")


def empacotar(raiz: Path, destino: Path) -> Path:
    raiz, destino = Path(raiz), Path(destino)
    origem_skill = raiz / "skills" / NOME_SKILL
    if not (origem_skill / "SKILL.md").exists():
        raise FileNotFoundError(f"{origem_skill / 'SKILL.md'} não existe")
    destino.mkdir(parents=True, exist_ok=True)
    pasta_tmp = destino / NOME_SKILL
    if pasta_tmp.exists():
        shutil.rmtree(pasta_tmp)
    shutil.copytree(origem_skill, pasta_tmp, ignore=IGNORAR)
    shutil.copytree(raiz / "src", pasta_tmp / "scripts" / "src", ignore=IGNORAR)
    shutil.copytree(raiz / "regras", pasta_tmp / "assets" / "regras_iniciais", ignore=IGNORAR)
    shutil.copy(raiz / "requirements.txt", pasta_tmp / "scripts" / "requirements.txt")
    # o roteiro sem IA (a skill manda ler quando não há execução de código) e as instruções para agentes
    for nome in ("COMO_FECHAR_O_MES.md", "AGENTS.md"):
        shutil.copy(raiz / nome, pasta_tmp / nome)
    zip_path = destino / f"{NOME_SKILL}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(pasta_tmp.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(destino).as_posix())
    shutil.rmtree(pasta_tmp)
    return zip_path
