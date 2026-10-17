"""Construtores de dados sintéticos no formato que os leitores devolvem (testes sem o data pack)."""
from __future__ import annotations

import csv
import io
import shutil
from decimal import Decimal
from pathlib import Path

import pandas as pd

from src.regras import carregar_config

RAIZ = Path(__file__).resolve().parents[1]
D = Decimal
ARQ_ORBE, ARQ_PONTE, ARQ_TAXAS = "orbe_teste.csv", "ponte_teste.eml", "taxas_teste.xlsx"
PRODUTOS = ["DEBITO", "CREDITO A VISTA", "CREDITO PARCELADO", "CREDITO PARCELADO", "PIX", "ANTECIPACAO", "SPREAD REMESSA"]
FAIXAS = [(None, None), (None, None), (2, 6), (7, 12), (None, None), (None, None), (None, None)]
COLUNAS_TAXAS = "DEFGHIJ"


def lojista_taxas(linha: int, nome: str, cnpj: str, ec: str | None, taxas: list, vig_de=None, vig_ate=None,
                  spread=None) -> list[dict]:
    """Uma linha da planilha (6 taxas de checkout em % + spread) no formato longo do leitor."""
    rows = []
    valores = list(taxas) + [spread]
    for (produto, (p_de, p_ate), coluna, valor) in zip(PRODUTOS, FAIXAS, COLUNAS_TAXAS, valores):
        if valor == "padrão":
            pct, situacao = None, "PADRAO"
        elif valor is None:
            pct, situacao = None, "VAZIO"
        else:
            pct, situacao = D(str(valor)), "VALOR"
        rows.append({"linha_planilha": linha, "lojista_planilha": nome, "cnpj": cnpj, "ec_orbe": ec,
                     "vigencia_texto": None, "vigencia_de": pd.Timestamp(vig_de) if vig_de else pd.NaT,
                     "vigencia_ate": pd.Timestamp(vig_ate) if vig_ate else pd.NaT, "obs": None,
                     "arquivo_origem": ARQ_TAXAS, "produto": produto, "parcelas_de": p_de, "parcelas_ate": p_ate,
                     "taxa_pct": pct, "taxa_situacao": situacao, "taxa_original": valor,
                     "celula": f"{coluna}{linha}", "ref_origem": f"Taxas vigentes!{coluna}{linha}"})
    return rows


def taxas_df(*lojistas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([r for l in lojistas for r in l])
    df["parcelas_de"] = df["parcelas_de"].astype("Int64")
    df["parcelas_ate"] = df["parcelas_ate"].astype("Int64")
    return df


def linha_orbe(i: int, data: str, ec: str, nome: str, bruto: str, taxa: str, tipo="VENDA", modalidade="CREDITO A VISTA",
               parcelas=1, ref=None, data_venda=None) -> dict:
    b, t = D(bruto), D(taxa)
    valor_taxa = (b * t / 100).quantize(D("0.01"), rounding="ROUND_DOWN")   # a Orbe trunca
    if tipo in ("ANTECIPACAO", "REVERSAO ANTECIPACAO"):
        modalidade, parcelas = None, None
    return {"id_transacao": f"TX{i:06d}", "data_movimento": pd.Timestamp(data), "cod_estabelecimento": ec,
            "nome_estabelecimento": nome, "tipo_lancamento": tipo, "modalidade": modalidade, "qtd_parcelas": parcelas,
            "bandeira": "VISA", "valor_bruto": b, "taxa_aplicada_pct": t, "valor_taxa": valor_taxa,
            "valor_liquido": b - valor_taxa, "id_referencia": ref,
            "data_venda_original": pd.Timestamp(data_venda) if data_venda else pd.NaT, "linha_arquivo": i + 1,
            "ref_origem": f"TX{i:06d}", "arquivo_origem": ARQ_ORBE}


def orbe_df(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    df["qtd_parcelas"] = df["qtd_parcelas"].astype("Int64")
    return df


def operacao_ponte(num: str, data: str, cnpj: str, cliente: str, valor_me: str, taxa_cliente: str, ptax: str,
                   linha: int, status="APROVADO", observacao=None, data_liq=None) -> dict:
    me, tc, px = D(valor_me), D(taxa_cliente), D(ptax)
    hu = lambda v: v.quantize(D("0.01"), rounding="ROUND_HALF_UP")
    spread_frac = (tc / px - 1).quantize(D("0.000001"))
    return {"num_operacao": num, "data_contratacao": pd.Timestamp(data),
            "data_liquidacao": pd.Timestamp(data_liq or data), "cnpj": cnpj, "cnpj_original": cnpj,
            "cliente": cliente, "moeda": "USD", "status_compliance": status, "observacao": observacao,
            "valor_me": me, "taxa_cliente": tc, "ptax": px, "valor_brl": hu(me * tc), "spread_brl": hu((tc - px) * me),
            "spread_frac": spread_frac, "spread_estimado_brl": None, "iof_brl": D("0"),
            "spread_pct": spread_frac * 100, "linha_planilha": linha, "ref_origem": num, "arquivo_origem": ARQ_PONTE}


def ponte_df(ops: list[dict], total_declarado=None) -> pd.DataFrame:
    df = pd.DataFrame(ops)
    df.attrs["totais_declarados"] = {"TOTAL DE OPERACOES:": D(len(df)),
                                     "SPREAD TOTAL R$:": total_declarado if total_declarado is not None
                                     else sum(df["spread_brl"], D("0"))}
    return df


def plano_contas_para(regras_dir: Path) -> pd.DataFrame:
    """Plano de contas sintético com todas as contas usadas nas regras CLASSIFICAR_CONTA."""
    texto = (regras_dir / "regras_negocio.csv").read_text(encoding="utf-8").lstrip("﻿")
    contas = set()
    for r in csv.DictReader(io.StringIO(texto), delimiter=";"):
        for parte in r["parametros"].split("|"):
            if parte.strip().startswith("conta="):
                contas.add(parte.strip().split("=", 1)[1])
    rows = [{"cod_conta": c, "descricao": f"Conta {c}", "tipo": "ANALITICA", "natureza": "D", "aceita_lancto": True,
             "cod_superior": None, "dt_criacao": None, "linha_arquivo": i + 2, "ref_origem": c,
             "arquivo_origem": "plano_teste.csv"} for i, c in enumerate(sorted(contas))]
    rows.append({"cod_conta": "9.9", "descricao": "Sintética", "tipo": "SINTETICA", "natureza": "D",
                 "aceita_lancto": False, "cod_superior": None, "dt_criacao": None, "linha_arquivo": 99,
                 "ref_origem": "9.9", "arquivo_origem": "plano_teste.csv"})
    return pd.DataFrame(rows)


def regras_copia(tmp_path: Path, substituicoes: list[tuple[str, str]] = ()) -> Path:
    destino = tmp_path / "regras"
    shutil.copytree(RAIZ / "regras", destino)
    p = destino / "regras_negocio.csv"
    t = p.read_text(encoding="utf-8")
    for a, b in substituicoes:
        assert a in t, a
        t = t.replace(a, b)
    p.write_text(t, encoding="utf-8")
    return destino


def config_para(regras_dir: Path, taxas: pd.DataFrame):
    return carregar_config(regras_dir, taxas, plano_contas_para(regras_dir), {"AURORA", "MERIDIANO"})


# lojistas sintéticos: o CNPJ da Casa do Estudante precisa existir porque a regra X-01 aponta para ele
CASA = "00520815000100"
LOJA_A, EC_A = "11111111000191", "2000000001"
LOJA_B, EC_B = "22222222000172", "2000000002"


def taxas_padrao() -> pd.DataFrame:
    return taxas_df(
        lojista_taxas(6, "Loja A", LOJA_A, EC_A, ["1.49", "2.59", "3.19", "3.79", "0.89", "2.10"], vig_de="2026-01-01",
                      vig_ate="2026-09-14", spread="1.5"),
        lojista_taxas(7, "Loja A (nova)", LOJA_A, EC_A, ["1.49", "2.19", "3.19", "3.79", "0.89", "2.10"],
                      vig_de="2026-09-15", spread="1.5"),
        lojista_taxas(8, "Loja B", LOJA_B, EC_B, ["1.00", "2.00", "3.00", "4.00", "0.50", "2.00"],
                      vig_de="2026-01-01", spread="1.2"),
        lojista_taxas(9, "Casa", CASA, "1018325654", ["1.49", "2.69", "3.19", "3.79", "0.89", "2.10"],
                      vig_de="2026-01-01", spread="padrão"),
    )
