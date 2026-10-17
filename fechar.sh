#!/usr/bin/env bash
# Fecha o mês com um comando (macOS/Linux):
#   ./fechar.sh [zip ou pasta com os arquivos do mês] [pasta de saída, padrão: saida]
# Cria o ambiente virtual se não existir, instala as dependências fixas de requirements.txt,
# roda `validar` (para com código 1 ou 2 se entrada ou regras tiverem problema) e `fechar`.
set -euo pipefail
cd "$(dirname "$0")"
ENTRADA="${1:-}"
SAIDA="${2:-saida}"

if [ ! -x .venv/bin/python ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"; break
    fi
  done
  if [ -z "$PY" ]; then
    echo "ERRO: não encontrei Python 3.10 ou mais novo. Instale em https://www.python.org/downloads/ e rode de novo." >&2
    exit 1
  fi
  echo "Criando o ambiente virtual .venv com $("$PY" --version)..."
  "$PY" -m venv .venv
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  .venv/bin/python -m ensurepip --upgrade >/dev/null
fi
.venv/bin/python -m pip install -q -r requirements.txt

ARGS=()
if [ -n "$ENTRADA" ]; then ARGS=(--entrada "$ENTRADA"); fi
.venv/bin/python -m src validar "${ARGS[@]}" --regras regras
.venv/bin/python -m src fechar "${ARGS[@]}" --regras regras --saida "$SAIDA"
