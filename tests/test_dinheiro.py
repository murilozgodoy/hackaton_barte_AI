from decimal import Decimal

import pytest

from src.dinheiro import arredondar, brl, pct, soma

D = Decimal


@pytest.mark.parametrize("valor, esperado", [
    ("0.005", "0.01"), ("-0.005", "-0.01"),       # meio centavo para cima, simétrico
    ("2.675", "2.68"), ("-2.675", "-2.68"),
    ("16.378872", "16.38"), ("83.120764", "83.12"),
    ("1.004999", "1.00"), ("0", "0.00"),
])
def test_half_up(valor, esperado):
    assert arredondar(D(valor)) == D(esperado)
    assert arredondar(D(valor), "HALF_UP") == D(esperado)


def test_truncar_e_modo_invalido():
    assert arredondar(D("16.378872"), "TRUNCAR") == D("16.37")
    assert arredondar(D("-5.5039"), "TRUNCAR") == D("-5.50")
    with pytest.raises(ValueError):
        arredondar(D("1"), "BANCARIO")


def test_pct_sem_arredondar():
    assert pct(D("2.69"), D("608.88")) == D("16.378872")
    assert pct(D("1.49"), D("-369.39")) == D("-5.503911")


def test_soma_ignora_none():
    assert soma([D("1.10"), None, D("2.20")]) == D("3.30")
    assert soma([]) == D("0")


def test_brl():
    assert brl(D("11916.02")) == "R$ 11.916,02"
    assert brl(D("-5.5")) == "-R$ 5,50"
    assert brl(D("1234567.891")) == "R$ 1.234.567,89"
