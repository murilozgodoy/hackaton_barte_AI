"""Fechamento mensal Tarvo.

Uso:
    python -m src.main --entrada <zip ou pasta> --saida saida [--competencia AAAA-MM]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fontes import carregar_config_fontes, localizar, preparar_entrada
from .leitores import carregar_todas
from .leitores.comum import ErroLeitura
from .validacao import validar_leitores

RAIZ = Path(__file__).resolve().parents[1]


def inferir_competencia(dados) -> str:
    """Mês mais frequente nas datas de movimento da Orbe, no formato AAAA-MM."""
    meses = dados["orbe"]["data_movimento"].dt.strftime("%Y-%m")
    return meses.mode().iloc[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fechamento mensal Tarvo")
    ap.add_argument("--entrada", type=Path, help="zip do pacote do mês ou pasta com os arquivos")
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida")
    ap.add_argument("--competencia", help="AAAA-MM; se omitido, é inferido dos dados")
    ap.add_argument("--config", type=Path, default=RAIZ / "config")
    args = ap.parse_args(argv)

    try:
        cfg = carregar_config_fontes(args.config)
        pasta = preparar_entrada(args.entrada, RAIZ, RAIZ / "data", cfg)
        arquivos = localizar(pasta, cfg)
        dados = carregar_todas(arquivos, cfg)
    except ErroLeitura as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2

    competencia = args.competencia or inferir_competencia(dados)
    print(f"Pasta de entrada: {pasta}")
    print(f"Competência: {competencia}{'' if args.competencia else ' (inferida dos dados)'}")
    for fonte, df in dados.items():
        enc = df.attrs.get("encoding", "-")
        print(f"  {fonte:<13} {len(df):>5} linhas  {arquivos[fonte].name}  (encoding: {enc})")

    checagens = validar_leitores(dados)
    erros = [c for c in checagens if c.nivel == "ERRO" and not c.ok]
    print("\nChecagens dos leitores:")
    for c in checagens:
        marca = "ok " if c.ok else ("ERRO" if c.nivel == "ERRO" else "aviso")
        print(f"  [{marca:<5}] {c.fonte}: {c.nome} - {c.detalhe}")
    if erros:
        print(f"\n{len(erros)} checagem(ns) falharam; fechamento interrompido.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
