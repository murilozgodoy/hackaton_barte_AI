"""Montagem de texto sem repetição: cada informação aparece uma vez num motivo, num item de rascunho ou num aviso.

Uma frase repete outra quando as duas têm em comum uma sequência de N palavras (padrão 8), comparadas sem acento, sem
pontuação e em minúsculas. Só apresentação: nenhum número é calculado aqui.
"""
from __future__ import annotations

import re
import unicodedata

N_PALAVRAS = 8
_RE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú(\"“])")


def _palavras(texto: str) -> list[str]:
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+(?:[.,][0-9]+)*", s)


def _sequencias(texto: str, n: int = N_PALAVRAS) -> set[tuple[str, ...]]:
    p = _palavras(texto)
    return {tuple(p[i:i + n]) for i in range(len(p) - n + 1)}


def frases(texto: str) -> list[str]:
    return [f for f in _RE_FRASE.split(str(texto or "").strip()) if f.strip()]


def sem_repeticao(texto: str, ja_dito: str = "", n: int = N_PALAVRAS) -> str:
    """O texto sem as frases que repetem (N palavras em comum) algo já dito antes nele ou em `ja_dito`."""
    vistas = _sequencias(ja_dito, n)
    out = []
    for f in frases(texto):
        seq = _sequencias(f, n)
        if seq & vistas:
            continue
        out.append(f)
        vistas |= seq
    return " ".join(out)


def repeticoes(texto: str, n: int = N_PALAVRAS) -> list[str]:
    """Sequências de N palavras que aparecem mais de uma vez no texto (para os testes)."""
    p = _palavras(texto)
    vistas, rep = set(), []
    for i in range(len(p) - n + 1):
        s = tuple(p[i:i + n])
        if s in vistas:
            rep.append(" ".join(s))
        vistas.add(s)
    return rep
