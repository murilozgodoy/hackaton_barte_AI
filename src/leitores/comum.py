"""Funções comuns aos leitores: encoding, números pt-BR, CNPJ, datas e taxas.

Nenhuma regra de negócio mora aqui; só a interpretação do formato dos arquivos.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

# Ordem de tentativa. "utf-8-sig" aceita arquivo com ou sem BOM.
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


class ErroLeitura(Exception):
    """Arquivo de entrada fora do formato esperado (mensagem em português)."""


def celula_vazia(valor) -> bool:
    """None, texto em branco, NaN, pd.NA ou NaT: célula vazia, venha de onde vier.

    Com pandas 3 uma célula vazia chega aos conversores como NaN (dtype str) e não como
    None (dtype object); os dois têm que significar a mesma coisa em todos os leitores.
    """
    if valor is None:
        return True
    if isinstance(valor, str):
        return valor.strip() == ""
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- texto

def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def normalizar(texto) -> str:
    """Maiúsculas, sem acento e com espaços simples. Usado para casar cabeçalhos e padrões."""
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", sem_acento(str(texto)).upper()).strip()


def ler_texto(caminho: Path, esperado: list[str]) -> tuple[str, str]:
    """Lê o arquivo testando encodings em ordem e valida o resultado.

    Um encoding só é aceito se a decodificação for estrita (sem erro), não gerar
    caractere de substituição e todos os trechos de `esperado` aparecerem no texto.
    Use trechos com acento em `esperado` sempre que possível: é o que denuncia
    um arquivo UTF-8 lido como cp1252 (e vice-versa).
    """
    dados = Path(caminho).read_bytes()
    falhas = []
    for enc in ENCODINGS:
        try:
            texto = dados.decode(enc)
        except UnicodeDecodeError as e:
            falhas.append(f"{enc}: byte inválido na posição {e.start}")
            continue
        if "�" in texto:
            falhas.append(f"{enc}: caractere de substituição no texto")
            continue
        faltando = [t for t in esperado if t not in texto]
        if faltando:
            falhas.append(f"{enc}: não encontrei {faltando}")
            continue
        return texto, enc
    raise ErroLeitura(
        f"Não consegui ler {Path(caminho).name} em nenhum encoding conhecido. "
        f"Tentativas: {'; '.join(falhas)}"
    )


def linhas_fisicas(texto: str) -> list[str]:
    """Divide em linhas físicas (só '\\n' conta como quebra; '\\r' final é removido)."""
    return [linha.rstrip("\r") for linha in texto.split("\n")]


# --------------------------------------------------------------------------- números

def numero_br(valor) -> Decimal | None:
    """'612.334,81' -> Decimal('612334.81'). Ponto é milhar, vírgula é decimal."""
    if celula_vazia(valor):
        return None
    s = str(valor).strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ErroLeitura(f"Valor numérico inválido: {valor!r}") from None


def numero_ponto(valor) -> Decimal | None:
    """'207215.87' -> Decimal. Para formatos com ponto decimal (OFX)."""
    if celula_vazia(valor):
        return None
    try:
        return Decimal(str(valor).strip())
    except InvalidOperation:
        raise ErroLeitura(f"Valor numérico inválido: {valor!r}") from None


def decimal_de_celula(valor) -> Decimal | None:
    """Célula do Excel -> Decimal sem ruído de ponto flutuante (0.0149 continua 0.0149)."""
    if celula_vazia(valor):
        return None
    if isinstance(valor, bool):
        raise ErroLeitura(f"Valor booleano onde se esperava número: {valor!r}")
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, float):
        return Decimal(repr(valor))
    s = str(valor).strip()
    return numero_br(s) if s else None


def taxa_pct_de_celula(valor) -> tuple[Decimal | None, str]:
    """Célula de taxa -> (taxa em %, situação).

    situação: VALOR, PADRAO (texto "padrão") ou VAZIO.
    Número no Excel é fração (0.0149 = 1,49%), como o Excel guarda percentuais.
    Texto precisa trazer '%' ("1,49%"); texto numérico sem '%' é ambíguo e para a leitura.
    """
    if celula_vazia(valor):
        return None, "VAZIO"
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return decimal_de_celula(valor) * 100, "VALOR"
    texto = normalizar(valor)
    if texto == "PADRAO":
        return None, "PADRAO"
    if texto.endswith("%"):
        return numero_br(texto[:-1]), "VALOR"
    raise ErroLeitura(
        f"Taxa {valor!r} sem '%': não dá para saber se é fração ou percentual. "
        "Escreva como 1,49% ou como número formatado em %."
    )


# --------------------------------------------------------------------------- CNPJ e datas

def normalizar_cnpj(valor) -> str | None:
    """Qualquer formato (com máscara, int sem zero à esquerda) -> 14 dígitos."""
    if celula_vazia(valor):
        return None
    if isinstance(valor, float):
        if not valor.is_integer():
            raise ErroLeitura(f"CNPJ inválido: {valor!r}")
        valor = int(valor)
    digitos = re.sub(r"\D", "", str(valor))
    if not digitos:
        return None
    if len(digitos) > 14:
        raise ErroLeitura(f"CNPJ com mais de 14 dígitos: {valor!r}")
    return digitos.zfill(14)


def normalizar_ec(valor) -> str | None:
    """Código de estabelecimento como texto só de dígitos (o Excel pode gravar 1086291869.0)."""
    if celula_vazia(valor):
        return None
    if isinstance(valor, float):
        if not valor.is_integer():
            raise ErroLeitura(f"EC inválido: {valor!r}")
        valor = int(valor)
    s = re.sub(r"\.0+$", "", str(valor).strip())
    if not s:
        return None
    if not s.isdigit():
        raise ErroLeitura(f"EC deve ter só dígitos: {valor!r}")
    return s


_RE_DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def data_br(valor) -> date | None:
    """'15/03/2027' -> date(2027, 3, 15). Aceita também datetime/date do Excel."""
    if celula_vazia(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    if not s:
        return None
    m = _RE_DATA_BR.fullmatch(s)
    if not m:
        raise ErroLeitura(f"Data fora do formato dd/mm/aaaa: {valor!r}")
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


def parse_vigencia(valor) -> tuple[date | None, date | None]:
    """Texto livre da planilha -> (início, fim). Datas inclusivas.

    "dd/mm/aaaa" (data simples) = a partir dessa data; "até dd/mm/aaaa" = até essa
    data; "a partir de 15/03/2027" ou "desde ..." = a partir; "de X a Y" = intervalo.
    """
    if celula_vazia(valor):
        return None, None
    if isinstance(valor, (datetime, date)):
        return data_br(valor), None
    texto = normalizar(valor)
    datas = [data_br(m.group(0)) for m in _RE_DATA_BR.finditer(texto)]
    if len(datas) == 2:
        return datas[0], datas[1]
    if len(datas) == 1:
        if texto.startswith("ATE"):
            return None, datas[0]
        if texto.startswith(("A PARTIR", "DESDE")) or _RE_DATA_BR.fullmatch(texto):
            return datas[0], None
    raise ErroLeitura(f"Vigência que não sei interpretar: {valor!r}")
