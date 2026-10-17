"""CLI do fechamento Tarvo: python -m src <comando> ...

Comandos desta versão: validar, fechar. Sem subcomando, equivale a `fechar`.
Códigos de saída: 0 ok · 1 entrada · 2 regras · 3 integridade · 4 id inexistente.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .fontes import carregar_config_fontes, localizar, preparar_entrada
from .leitores import carregar_todas
from .leitores.comum import ErroLeitura
from .regras import Config, ErroConfig, carregar_config
from .validacao import Checagem, validar_leitores

RAIZ = Path(__file__).resolve().parents[1]
COMANDOS = ("validar", "fechar")
SAIDA_OK, SAIDA_ENTRADA, SAIDA_REGRAS, SAIDA_INTEGRIDADE, SAIDA_ID = 0, 1, 2, 3, 4


class Parada(Exception):
    def __init__(self, codigo: int, mensagem: str):
        self.codigo, self.mensagem = codigo, mensagem
        super().__init__(mensagem)


@dataclass
class Contexto:
    pasta: Path
    arquivos: dict[str, Path]
    dados: dict[str, pd.DataFrame]
    config: Config
    competencia: str
    competencia_inferida: bool
    checagens: list[Checagem]


def inferir_competencia(dados) -> str:
    """Mês mais frequente nas datas de movimento da Orbe, no formato AAAA-MM."""
    return dados["orbe"]["data_movimento"].dt.strftime("%Y-%m").mode().iloc[0]


def carregar_contexto(args) -> Contexto:
    """Lê entradas, roda as checagens dos leitores e carrega a base de regras."""
    try:
        fontes = carregar_config_fontes(args.regras)
        pasta = preparar_entrada(args.entrada, RAIZ, RAIZ / "data", fontes)
        arquivos = localizar(pasta, fontes)
        dados = carregar_todas(arquivos, fontes)
    except ErroLeitura as e:
        raise Parada(SAIDA_ENTRADA, f"Entrada com problema: {e}") from None
    except ErroConfig as e:
        raise Parada(SAIDA_REGRAS, str(e)) from None

    checagens = validar_leitores(dados)
    falhas = [c for c in checagens if c.nivel == "ERRO" and not c.ok]
    if falhas:
        detalhe = "\n  - ".join(f"{c.fonte}: {c.nome} ({c.detalhe})" for c in falhas)
        raise Parada(SAIDA_ENTRADA, f"Arquivos de entrada não fecham:\n  - {detalhe}")

    try:
        bancos = {f["rotulo"] for f in fontes.values() if f.get("rotulo")}
        config = carregar_config(args.regras, dados["taxas"], dados["plano_contas"], bancos)
    except ErroConfig as e:
        raise Parada(SAIDA_REGRAS, str(e)) from None

    competencia = args.competencia or inferir_competencia(dados)
    return Contexto(pasta, arquivos, dados, config, competencia, not args.competencia, checagens)


def resumo_contexto(ctx: Contexto) -> dict:
    cad = ctx.config.cadastro
    por_tipo = pd.Series([r.tipo for r in ctx.config.regras]).value_counts().to_dict()
    return {
        "competencia": ctx.competencia,
        "competencia_inferida": ctx.competencia_inferida,
        "pasta_entrada": str(ctx.pasta),
        "fontes": {f: {"arquivo": ctx.arquivos[f].name, "linhas": int(len(df)),
                       "encoding": df.attrs.get("encoding")} for f, df in ctx.dados.items()},
        "checagens": [{"fonte": c.fonte, "nome": c.nome, "ok": c.ok, "nivel": c.nivel, "detalhe": c.detalhe}
                      for c in ctx.checagens],
        "regras": {"lojistas": int(len(cad)),
                   "lojistas_por_origem": cad["origem"].value_counts().to_dict(),
                   "ativas_por_tipo": {k: int(v) for k, v in por_tipo.items()},
                   "nao_ativas": [r.id for r in ctx.config.todas if r.status != "ATIVA"],
                   "avisos": list(ctx.config.avisos)},
    }


def imprimir_contexto(ctx: Contexto) -> None:
    print(f"Pasta de entrada: {ctx.pasta}")
    print(f"Competência: {ctx.competencia}{' (inferida dos dados)' if ctx.competencia_inferida else ''}")
    for fonte, df in ctx.dados.items():
        print(f"  {fonte:<13} {len(df):>5} linhas  {ctx.arquivos[fonte].name}  "
              f"(encoding: {df.attrs.get('encoding', '-')})")
    print("\nChecagens dos leitores:")
    for c in ctx.checagens:
        marca = "ok" if c.ok else c.nivel.lower()
        print(f"  [{marca:<5}] {c.fonte}: {c.nome} - {c.detalhe}")
    r = resumo_contexto(ctx)["regras"]
    print("\nBase de regras:")
    origem = ", ".join(f"{n} {o}" for o, n in r["lojistas_por_origem"].items())
    print(f"  cadastro: {r['lojistas']} lojistas ({origem})")
    print("  regras ativas: " + ", ".join(f"{t} {n}" for t, n in r["ativas_por_tipo"].items()))
    if r["nao_ativas"]:
        print(f"  regras não ativas (ignoradas): {', '.join(r['nao_ativas'])}")
    for aviso in r["avisos"]:
        print(f"  [aviso] {aviso}")


def cmd_validar(args) -> int:
    ctx = carregar_contexto(args)
    if args.json:
        print(json.dumps({"comando": "validar", "ok": True, "codigo": SAIDA_OK, **resumo_contexto(ctx)},
                         ensure_ascii=False, indent=2, default=str))
    else:
        imprimir_contexto(ctx)
        print("\nEntradas e base de regras válidas. Nada foi calculado (use `fechar`).")
    return SAIDA_OK


def cmd_fechar(args) -> int:
    ctx = carregar_contexto(args)
    if args.json:
        print(json.dumps({"comando": "fechar", "ok": True, "codigo": SAIDA_OK, **resumo_contexto(ctx)},
                         ensure_ascii=False, indent=2, default=str))
    else:
        imprimir_contexto(ctx)
        print("\nCálculo do fechamento: ainda não implementado nesta versão (próxima fase).")
    return SAIDA_OK


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m src", description="Fechamento mensal Tarvo")
    sub = ap.add_subparsers(dest="comando")
    for nome, ajuda in (("validar", "confere as 6 fontes e a base de regras; não calcula nada"),
                        ("fechar", "fechamento completo: 6 CSVs, resumo.json e relatório")):
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--entrada", type=Path, help="zip do pacote do mês ou pasta com os arquivos")
        p.add_argument("--regras", type=Path, default=RAIZ / "regras",
                       help="pasta da base de regras do financeiro (padrão: regras/)")
        p.add_argument("--saida", type=Path, default=RAIZ / "saida")
        p.add_argument("--competencia", help="AAAA-MM; se omitido, é inferida dos dados")
        p.add_argument("--json", action="store_true", help="saída em JSON (para agentes)")
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in COMANDOS and argv[0] not in ("-h", "--help")):
        argv.insert(0, "fechar")  # sem subcomando = fechar com os padrões
    args = construir_parser().parse_args(argv)
    try:
        return {"validar": cmd_validar, "fechar": cmd_fechar}[args.comando](args)
    except Parada as p:
        if args.json:
            print(json.dumps({"comando": args.comando, "ok": False, "codigo": p.codigo, "erro": p.mensagem},
                             ensure_ascii=False, indent=2))
        else:
            print(f"ERRO: {p.mensagem}", file=sys.stderr)
        return p.codigo
