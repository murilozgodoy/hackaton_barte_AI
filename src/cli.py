"""CLI do fechamento Tarvo: python -m src <comando> ...

Comandos desta versão: validar, fechar. Sem subcomando, equivale a `fechar`.
Códigos de saída: 0 ok · 1 entrada · 2 regras · 3 integridade · 4 id inexistente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .dinheiro import brl, soma
from .fechamento import Fechamento, escrever, executar, totais
from .fontes import carregar_config_fontes, localizar, preparar_entrada
from .leitores import carregar_todas
from .leitores.comum import ErroLeitura
from .regras import Config, ErroConfig, carregar_config
from .validacao import Checagem, validar_leitores

RAIZ = Path(__file__).resolve().parents[1]
COMANDOS = ("validar", "fechar")
SAIDA_OK, SAIDA_ENTRADA, SAIDA_REGRAS, SAIDA_INTEGRIDADE, SAIDA_ID = 0, 1, 2, 3, 4
_RE_COMPETENCIA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


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
    if args.competencia and not _RE_COMPETENCIA.match(args.competencia):
        raise Parada(SAIDA_ENTRADA, f"--competencia '{args.competencia}' inválida: use AAAA-MM (ex.: 2026-10)")
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
                   "lojistas_por_origem": {k: int(v) for k, v in cad["origem"].value_counts().items()},
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


def _tabela_comissoes(df: pd.DataFrame, titulo: str, col_qtd: str, rotulo_qtd: str) -> None:
    print(f"\n{titulo}:")
    print(f"  {'id_saida':<13}{'lojista':<42}{'cnpj':<16}{rotulo_qtd:>10}  {'comissão':>16}")
    for r in df.itertuples(index=False):
        print(f"  {r.id_saida:<13}{str(r.lojista)[:40]:<42}{r.cnpj:<16}{int(getattr(r, col_qtd)):>10}  "
              f"{brl(r.comissao_brl):>16}")
    print(f"  {'TOTAL':<13}{'':<42}{'':<16}{int(df[col_qtd].sum()):>10}  {brl(soma(df['comissao_brl'])):>16}")


def imprimir_fechamento(f: Fechamento) -> None:
    _tabela_comissoes(f.comissoes_checkout, f"Comissão de CHECKOUT por lojista ({f.competencia})",
                      "qtd_transacoes", "transações")
    print("  Destino das linhas da Orbe: " + ", ".join(f"{k} {v}" for k, v in f.destinos_orbe.items()))
    _tabela_comissoes(f.comissoes_remessa, f"Comissão de REMESSA por lojista ({f.competencia})",
                      "qtd_operacoes", "operações")
    print("  Destino das linhas da Ponte: " + ", ".join(f"{k} {v}" for k, v in f.destinos_ponte.items()))

    print("\nDivergências de taxa (contratada x aplicada), por lojista:")
    if f.divergencias.empty:
        print("  nenhuma")
    for (linha, _cnpj), g in f.divergencias.groupby(["linha_negocio", "cnpj"], sort=False):
        print(f"  {linha:<9}{str(g['lojista'].iloc[0])[:40]:<42}{len(g):>5} linhas  {brl(soma(g['diferenca_brl'])):>16}")

    print("\nNotas a emitir:")
    for r in f.notas.itertuples(index=False):
        print(f"  {r.id_saida:<9}{r.linha_negocio:<9}{str(r.tomador)[:40]:<42}{r.tomador_cnpj:<16}{brl(r.valor_brl):>16}")
    print(f"  {'TOTAL':<9}{'':<9}{'':<42}{'':<16}{brl(soma(f.notas['valor_brl'])):>16}")
    for r in f.sem_nota.itertuples(index=False):
        print(f"  sem nota: {r.lojista} ({r.cnpj}) com comissão {brl(r.comissao_brl)} (zero ou negativa)")

    met = f.lancamentos["metodo"].value_counts().to_dict()
    print("\nLançamentos classificados: " + ", ".join(f"{k} {v}" for k, v in met.items())
          + f" (total {len(f.lancamentos)})")
    pend = f.lancamentos[f.lancamentos["tipo_pendencia"].notna()]
    for r in pend.itertuples(index=False):
        print(f"  [{r.tipo_pendencia}] {r.banco} {r.ref_origem} {r.data.date()} {brl(r.valor)} {r.descricao}")
    for r in f.em_transito.itertuples(index=False):
        print(f"  [EM_TRANSITO] {r.banco} {r.ref_origem} {r.data.date()} {brl(r.valor)} {r.descricao}: {r.motivo}")

    print("\nChecagens de integridade:")
    for c in f.checagens:
        print(f"  [{'ok' if c.ok else 'ERRO':<5}] {c.nome} - {c.detalhe}")
    for aviso in f.avisos:
        print(f"  [aviso] {aviso}")


def imprimir_conciliacao(f: Fechamento) -> None:
    c = f.conciliacao
    print("\nConciliação entre fontes (informativo, não gera pendência):")
    o = c["orbe"]
    print(f"  Orbe: bruto {brl(o['valor_bruto_total'])}, taxa cobrada {brl(o['valor_taxa_total'])}, "
          f"líquido aos lojistas {brl(o['valor_liquido_total'])}")
    for tipo, v in o["valor_liquido_por_tipo"].items():
        print(f"    líquido {tipo:<22} {brl(v):>18}")
    print("  Extratos por conta contábil (créditos / débitos):")
    for r in c["extratos_por_conta"]:
        print(f"    {r['banco']:<10}{r['conta_codigo']:<12}{str(r['conta_descricao'])[:44]:<46}{r['qtd']:>4}  "
              f"{brl(r['creditos']):>18}  {brl(r['debitos']):>18}")
    p = c["ponte"]
    print(f"  Ponte: spread total declarado {brl(p['spread_total_declarado'])} (com duplicata e negativos); "
          f"operações únicas {brl(p['spread_operacoes_unicas'])}")
    print(f"    repasse pelo total declarado x participação = {brl(p['repasse_pelo_total_declarado'])}; "
          f"comissão calculada = {brl(p['comissao_calculada'])}; diferença = {brl(p['diferenca'])}")


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
    fech = executar(ctx.dados, ctx.config, ctx.competencia, usar_ia=not args.sem_ia)
    arquivos = escrever(fech, args.saida)
    codigo = SAIDA_OK if fech.integro else SAIDA_INTEGRIDADE
    if args.json:
        print(json.dumps({
            "comando": "fechar", "ok": fech.integro, "codigo": codigo,
            "status_integridade": "OK" if fech.integro else "FALHA",
            **resumo_contexto(ctx), "totais": totais(fech),
            "orbe_destinos": {k: int(v) for k, v in fech.destinos_orbe.items()},
            "ponte_destinos": {k: int(v) for k, v in fech.destinos_ponte.items()},
            "integridade": [{"nome": c.nome, "ok": c.ok, "detalhe": c.detalhe} for c in fech.checagens],
            "avisos": fech.avisos, "arquivos": {k: str(v) for k, v in arquivos.items()},
        }, ensure_ascii=False, indent=2, default=str))
        return codigo

    imprimir_contexto(ctx)
    imprimir_fechamento(fech)
    imprimir_conciliacao(fech)
    print("\nArquivos gravados: " + ", ".join(str(p) for p in arquivos.values()))
    if not fech.integro:
        print("\nINTEGRIDADE FALHOU: os números acima não podem ser apresentados como válidos.", file=sys.stderr)
    return codigo


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
        p.add_argument("--sem-ia", action="store_true",
                       help="não consultar a IA para lançamentos sem regra, mesmo com ANTHROPIC_API_KEY")
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
