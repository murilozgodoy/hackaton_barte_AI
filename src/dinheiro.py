"""Aritmética monetária: só Decimal, nunca float nem round()."""
from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")
ZERO = Decimal("0")
# nomes usados no parâmetro `arredondamento` de regras/regras_negocio.csv
MODOS = {"HALF_UP": ROUND_HALF_UP, "TRUNCAR": ROUND_DOWN}


def arredondar(valor: Decimal, modo: str = "HALF_UP") -> Decimal:
    """Ao centavo. HALF_UP = meio centavo para cima, simétrico no negativo (-0,005 -> -0,01)."""
    if modo not in MODOS:
        raise ValueError(f"modo de arredondamento desconhecido: {modo!r} (use {', '.join(MODOS)})")
    return valor.quantize(CENTAVO, rounding=MODOS[modo])


def pct(taxa_pct: Decimal, base: Decimal) -> Decimal:
    """taxa em % (2.69) aplicada sobre a base, sem arredondar."""
    return base * taxa_pct / Decimal(100)


def soma(valores) -> Decimal:
    return sum((v for v in valores if v is not None), ZERO)


def brl(valor: Decimal) -> str:
    """Formato pt-BR para o terminal: R$ 1.234,56 / -R$ 5,50."""
    v = arredondar(valor)
    sinal = "-" if v < 0 else ""
    inteiro, dec = f"{abs(v):.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{dec}"
