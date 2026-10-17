"""Carteira pendente: linhas da Orbe que ficaram fora da comissão por falta de contrato, taxa ou cadastro.

`fechar` grava saida/carteira_pendente.csv com essas linhas (dados de origem completos, competência de origem
e idade em meses). `fechar --anterior <saida do mês anterior>` relê a carteira: cada linha passa de novo pelo
cálculo de checkout com a base de regras atual; se agora houver taxa vigente na data da venda (ex.: TAXA_EXCECAO
retroativa aprovada pelo Comercial), a linha entra na comissão e na nota do mês atual, com rastro apontando para
o arquivo do mês de origem; senão continua na carteira (idade + 1) e na pendência.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd

from .leitores.comum import ErroLeitura, celula_vazia

COLUNAS = ["arquivo_origem", "ref_origem", "cnpj", "ec", "data_venda", "produto", "valor_bruto", "motivo",
           "competencia_origem", "idade_meses", "lojista", "destino", "regra_id", "id_transacao", "tipo_lancamento",
           "modalidade", "qtd_parcelas", "data_movimento", "data_venda_original", "taxa_aplicada_pct", "valor_taxa",
           "id_referencia", "nome_estabelecimento"]
DESTINOS_CARTEIRA = {"SEM_TAXA", "SEM_CADASTRO"}          # + EXCLUIDO por falta de contrato (tipo_pendencia SEM_CONTRATO)
TIPOS_ANTECIPACAO = {"ANTECIPACAO", "REVERSAO ANTECIPACAO"}


def meses_entre(competencia_origem: str, competencia: str) -> int:
    a, m = (int(x) for x in competencia_origem.split("-"))
    b, n = (int(x) for x in competencia.split("-"))
    return (b - a) * 12 + (n - m)


def montar(chk_linhas: pd.DataFrame, competencia: str) -> pd.DataFrame:
    """Linhas do mês (e da carteira anterior que continuam pendentes) que vão para carteira_pendente.csv."""
    sel = chk_linhas[chk_linhas["destino"].isin(DESTINOS_CARTEIRA)
                     | ((chk_linhas["destino"] == "EXCLUIDO") & (chk_linhas["tipo_pendencia"] == "SEM_CONTRATO"))]
    if sel.empty:
        return pd.DataFrame(columns=COLUNAS)
    origem = (sel["competencia_origem"] if "competencia_origem" in sel.columns else pd.Series(None, index=sel.index))
    origem = origem.where(origem.notna(), competencia)
    df = pd.DataFrame({
        "arquivo_origem": sel["arquivo_origem"], "ref_origem": sel["ref_origem"], "cnpj": sel["cnpj"],
        "ec": sel["cod_estabelecimento"], "data_venda": sel["data_taxa"], "produto": sel["produto"],
        "valor_bruto": sel["valor_bruto"], "motivo": sel["motivo"], "competencia_origem": origem,
        "idade_meses": origem.map(lambda o: meses_entre(o, competencia)), "lojista": sel["lojista"],
        "destino": sel["destino"], "regra_id": sel["destino_regra"].where(sel["destino_regra"].notna(), sel["regra_id"]),
        "id_transacao": sel["id_transacao"], "tipo_lancamento": sel["tipo_lancamento"],
        "modalidade": [None if t in TIPOS_ANTECIPACAO else p for t, p in zip(sel["tipo_lancamento"], sel["produto"])],
        "qtd_parcelas": sel["qtd_parcelas"], "data_movimento": sel["data_movimento"],
        "data_venda_original": sel["data_venda_original"] if "data_venda_original" in sel.columns else pd.NaT,
        "taxa_aplicada_pct": sel["taxa_aplicada_pct"], "valor_taxa": sel["valor_taxa_orbe"],
        "id_referencia": sel["id_referencia"], "nome_estabelecimento": sel["nome_orbe"],
    })
    df = df.sort_values(["competencia_origem", "cnpj", "data_movimento", "ref_origem"]).reset_index(drop=True)
    df["qtd_parcelas"] = df["qtd_parcelas"].astype("Int64")
    return df[COLUNAS]


def _dec(v) -> Decimal | None:
    return None if celula_vazia(v) else Decimal(str(v))


def ler(pasta_anterior: Path) -> pd.DataFrame:
    """carteira_pendente.csv de uma saída anterior, no formato que o leitor da Orbe devolve (+ competencia_origem)."""
    caminho = Path(pasta_anterior) / "carteira_pendente.csv"
    if not caminho.exists():
        raise ErroLeitura(f"{caminho} não existe: --anterior precisa apontar para a pasta de saída do mês anterior")
    df = pd.read_csv(caminho, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    faltam = [c for c in COLUNAS if c not in df.columns]
    if faltam:
        raise ErroLeitura(f"{caminho}: colunas ausentes na carteira: {faltam}")
    out = pd.DataFrame({
        "id_transacao": df["id_transacao"], "data_movimento": pd.to_datetime(df["data_movimento"]),
        "cod_estabelecimento": df["ec"], "nome_estabelecimento": df["nome_estabelecimento"],
        "tipo_lancamento": df["tipo_lancamento"], "modalidade": df["modalidade"].map(lambda v: v or None),
        "qtd_parcelas": pd.to_numeric(df["qtd_parcelas"].replace("", None), errors="coerce").astype("Int64"),
        "bandeira": None, "valor_bruto": df["valor_bruto"].map(_dec), "taxa_aplicada_pct": df["taxa_aplicada_pct"].map(_dec),
        "valor_taxa": df["valor_taxa"].map(_dec),
        "valor_liquido": [b - t if b is not None and t is not None else None
                          for b, t in zip(df["valor_bruto"].map(_dec), df["valor_taxa"].map(_dec))],
        "id_referencia": df["id_referencia"].map(lambda v: v or None),
        "data_venda_original": pd.to_datetime(df["data_venda_original"].replace("", None)),
        "linha_arquivo": None, "ref_origem": df["ref_origem"], "arquivo_origem": df["arquivo_origem"],
        "competencia_origem": df["competencia_origem"],
    })
    return out
