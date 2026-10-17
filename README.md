# Fechamento Tarvo — Desafio Barte AI (time MN AI)

Motor de fechamento mensal da Tarvo Pagamentos: lê os arquivos do mês como eles
chegam (zip do data pack) e gera as saídas em `saida/`, com rastro até a linha
de origem. *Documentação completa em construção (Fase 6).*

## Instalar

Requer Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
## Rodar

```bash
# usa o único Tarvo_Data_Pack_*.zip da raiz e extrai em data/ automaticamente
.venv/bin/python -m src.main

# ou apontando o pacote/pasta do mês
.venv/bin/python -m src.main --entrada Tarvo_Data_Pack_set2026.zip --saida saida --competencia 2026-09
```

## Testes

```bash
.venv/bin/python -m pytest
```
