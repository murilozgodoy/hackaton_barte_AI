# Fechamento Tarvo — Desafio Barte AI (time MN AI)

Motor de fechamento mensal da Tarvo Pagamentos: lê os arquivos do mês como eles
chegam (zip do data pack), aplica as regras escritas pelo financeiro em `regras/` e
gera as saídas em `saida/`, com rastro até a linha de origem. *Documentação completa
em construção.*

## Instalar

Requer Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Dados de entrada

O data pack **não é versionado**. Antes de rodar, copie o zip do mês, sem
descompactar nem editar, para a raiz do repositório (ex.: `Tarvo_Data_Pack_set2026.zip`).
O motor extrai sozinho para `data/`.

## Rodar

```bash
# confere as 6 fontes e a base de regras, sem calcular nada
.venv/bin/python -m src validar

# fechamento completo (sem argumentos usa o único zip da raiz, regras/ e saida/)
.venv/bin/python -m src fechar
.venv/bin/python -m src fechar --entrada Tarvo_Data_Pack_set2026.zip --regras regras --saida saida --competencia 2026-09

# saída em JSON, para agentes
.venv/bin/python -m src validar --json
```

Códigos de saída: 0 ok · 1 problema nos arquivos de entrada · 2 problema na base de
regras · 3 integridade das saídas falhou (nesse caso `resumo.json` não é gravado e o
relatório sai marcado como inválido).

## Saídas (`saida/`)

Os 6 CSVs do regulamento (`comissoes_por_lojista`, `divergencias_taxa`, `notas_a_emitir`,
`lancamentos_classificados`, `pendencias`, `rastro`), mais `resumo.json` (para agentes:
totais em string decimal, nada a recalcular) e `RELATORIO_FECHAMENTO.md` (uma página para a
analista e o CFO). A soma de `valor` por `id_saida` no `rastro.csv` é igual ao valor
reportado em cada saída; isso é conferido a cada execução.

## Limitações conhecidas

- **Adquirente × banco não é conciliável com os arquivos do mês.** A adquirente liquida
  crédito parcelado em parcelas mensais (salvo antecipação), então o que entra no banco em
  setembro mistura parcelas de vendas anteriores e deixa de fora parcelas futuras. O relatório
  mostra os totais só como informativos; a conciliação exige a agenda de recebíveis da adquirente.
- O extrato OFX do Meridiano não traz saldo inicial, então o saldo desse banco não é conferido
  linha a linha (o do Aurora é).

## Base de regras (`regras/`)

Tudo o que é regra de negócio fica em CSVs que abrem no Excel, editáveis pelo
financeiro: `regras_negocio.csv`, `complemento_cadastro.csv` (só lacunas da planilha
de taxas), `fontes.csv` e `historico_alteracoes.csv`. Veja `regras/COMO_CRIAR_REGRA.md`.
Em produção a pasta pode ficar fora do repositório: `--regras <pasta>`.

## Testes

```bash
.venv/bin/python -m pytest
```
