#!/usr/bin/env bash
# Fecha o mês com um comando (macOS/Linux):
#   ./fechar.sh [zip ou pasta com os arquivos do mês] [pasta de saída, padrão: saida] [--anterior <saída do mês anterior>]
# Cria o ambiente virtual se não existir, instala as dependências fixas de requirements.txt,
# roda `validar` (para com código 1 ou 2 se entrada ou regras tiverem problema) e `fechar`.
# Mês seguinte: ./fechar.sh outubro.zip saida_outubro --anterior saida   (relê a carteira e a contestação de setembro)
set -euo pipefail
cd "$(dirname "$0")"
ENTRADA=""
SAIDA="saida"
ANTERIOR=""
POS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --anterior) ANTERIOR="${2:-}"; shift 2 ;;
    --saida) SAIDA="${2:-saida}"; shift 2 ;;
    *) if [ $POS -eq 0 ]; then ENTRADA="$1"; elif [ $POS -eq 1 ]; then SAIDA="$1"; fi; POS=$((POS + 1)); shift ;;
  esac
done

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
if [ -n "$ENTRADA" ]; then ARGS+=(--entrada "$ENTRADA"); fi
ANT=()
if [ -n "$ANTERIOR" ]; then ANT+=(--anterior "$ANTERIOR"); fi
# ${X[@]+"${X[@]}"}: expansão segura de array vazio com set -u (bash 3.2 do macOS)
.venv/bin/python -m src validar ${ARGS[@]+"${ARGS[@]}"} --regras regras
.venv/bin/python -m src fechar ${ARGS[@]+"${ARGS[@]}"} --regras regras --saida "$SAIDA" ${ANT[@]+"${ANT[@]}"}
