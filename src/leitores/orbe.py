"""Leitor do relatório de comissões da Orbe (CSV ';', vírgula decimal, datas dd/mm/aaaa)."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .comum import ErroLeitura, data_br, ler_texto, linhas_fisicas, normalizar, numero_br

COLUNAS_ESPERADAS = [
    "id_transacao", "data_movimento", "cod_estabelecimento", "nome_estabelecimento",
    "tipo_lancamento", "modalidade", "qtd_parcelas", "bandeira", "valor_bruto",
    "taxa_aplicada_pct", "valor_taxa", "valor_liquido", "id_referencia", "data_venda_original",
]


def ler_orbe(caminho: Path) -> pd.DataFrame:
    caminho = Path(caminho)
    texto, encoding = ler_texto(caminho, esperado=["id_transacao", "tipo_lancamento", "valor_bruto"])

    cabecalho = None
    registros = []
    for n, linha in enumerate(linhas_fisicas(texto), start=1):
        if not linha.strip():
            continue
        campos = next(csv.reader([linha], delimiter=";"))
        if cabecalho is None:
            cabecalho = [c.strip() for c in campos]
            faltando = [c for c in COLUNAS_ESPERADAS if c not in cabecalho]
            if faltando:
                raise ErroLeitura(f"{caminho.name}: colunas ausentes no cabeçalho: {faltando}")
            continue
        if len(campos) != len(cabecalho):
            raise ErroLeitura(
                f"{caminho.name} L{n}: {len(campos)} campos, esperado {len(cabecalho)}"
            )
        bruto = dict(zip(cabecalho, (c.strip() for c in campos)))
        registros.append(_converter(bruto, n, caminho.name))

    if cabecalho is None:
        raise ErroLeitura(f"{caminho.name}: arquivo vazio")

    df = pd.DataFrame(registros)
    df["data_movimento"] = pd.to_datetime(df["data_movimento"])
    df["data_venda_original"] = pd.to_datetime(df["data_venda_original"])
    df["qtd_parcelas"] = df["qtd_parcelas"].astype("Int64")
    df.attrs.update(arquivo=caminho.name, encoding=encoding)
    return df


def _converter(r: dict, linha: int, arquivo: str) -> dict:
    parcelas = r["qtd_parcelas"]
    return {
        "id_transacao": r["id_transacao"],
        "data_movimento": data_br(r["data_movimento"]),
        "cod_estabelecimento": r["cod_estabelecimento"],
        "nome_estabelecimento": r["nome_estabelecimento"],
        "tipo_lancamento": normalizar(r["tipo_lancamento"]),
        "modalidade": normalizar(r["modalidade"]) or None,
        "qtd_parcelas": int(parcelas) if parcelas else None,
        "bandeira": r["bandeira"] or None,
        "valor_bruto": numero_br(r["valor_bruto"]),
        "taxa_aplicada_pct": numero_br(r["taxa_aplicada_pct"]),
        "valor_taxa": numero_br(r["valor_taxa"]),
        "valor_liquido": numero_br(r["valor_liquido"]),
        "id_referencia": r["id_referencia"] or None,
        "data_venda_original": data_br(r["data_venda_original"]),
        "linha_arquivo": linha,
        "ref_origem": r["id_transacao"],
        "arquivo_origem": arquivo,
    }


# --------------------------------------------------------------------------- vários arquivos (relatório + ajustes tardios)

_COLUNAS_IDENTIDADE_EXCLUIDAS = ["linha_arquivo", "arquivo_origem", "ref_origem"]


def ler_orbe_varios(caminhos: list[Path]) -> pd.DataFrame:
    """Lê o relatório principal e os ajustes tardios (mesmo formato) e concatena, cada linha com o seu arquivo_origem.

    id_transacao repetido entre (ou dentro de) arquivos: linhas IDÊNTICAS contam uma vez (attrs["duplicatas_identicas"],
    aviso); linhas com valores DIFERENTES ficam todas no DataFrame (attrs["duplicatas_divergentes"]) e o cálculo de
    checkout tira todas da comissão, com pendência DUPLICATA_DIVERGENTE."""
    caminhos = [Path(c) for c in caminhos]
    partes = [ler_orbe(c) for c in caminhos]
    df = pd.concat(partes, ignore_index=True) if len(partes) > 1 else partes[0]
    identicas, divergentes = [], []
    ids = df["id_transacao"]
    repetidos = sorted(set(ids[ids.duplicated(keep=False)]))
    if repetidos:
        comparavel = df.drop(columns=_COLUNAS_IDENTIDADE_EXCLUIDAS).astype(str)
        manter = pd.Series(True, index=df.index)
        for tid in repetidos:
            idx = df.index[ids == tid]
            arquivos = sorted(set(df.loc[idx, "arquivo_origem"]))
            if (comparavel.loc[idx].nunique(dropna=False) <= 1).all():
                identicas.append({"id": tid, "arquivos": arquivos, "vezes": int(len(idx))})
                manter[idx[1:]] = False
            else:
                divergentes.append({"id": tid, "arquivos": arquivos, "vezes": int(len(idx))})
        df = df[manter].reset_index(drop=True)
    df.attrs.update(arquivo=", ".join(c.name for c in caminhos), arquivos=[c.name for c in caminhos],
                    encoding=partes[0].attrs.get("encoding"), duplicatas_identicas=identicas,
                    duplicatas_divergentes=divergentes)
    return df
