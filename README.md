# Fechamento Tarvo — Desafio Barte AI (time MN AI)

Motor **determinístico** que fecha o mês da Tarvo Pagamentos a partir dos arquivos como
eles chegam (relatório da Orbe, planilha de taxas, e-mail da Ponte Câmbio, plano de contas,
extratos Aurora e Meridiano) e entrega comissões, divergências de taxa, notas a emitir,
lançamentos classificados e pendências, **cada número com rastro até as linhas de origem**.
As regras de negócio são **dados editáveis pelo financeiro** (`regras/`), não código. A IA é
facilitadora opcional (skill `fechamento-tarvo`): conduz, explica e propõe regras; **nunca calcula**.

Time MN AI: Nader Taha e Murilo Godoy.

## Instalar e rodar do zero

Requer Python 3.11+ (sem banco, sem servidor, sem chave de API).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# coloque o zip do mês na raiz (ex.: Tarvo_Data_Pack_set2026.zip) e rode:
.venv/bin/python -m src validar          # confere as 6 fontes e a base de regras, não calcula
.venv/bin/python -m src fechar           # gera saida/ (6 CSVs + resumo.json + RELATORIO_FECHAMENTO.md)
```

O data pack **não é versionado** (decisão do time; repositório público). O motor acha o único
`Tarvo_Data_Pack_*.zip` da raiz e extrai em `data/`. Para apontar outro mês ou outra base:

```bash
.venv/bin/python -m src fechar --entrada <zip ou pasta> --regras <pasta ou zip> --saida saida --competencia 2026-10
```

Todos os comandos aceitam `--json` (saída para agentes). Códigos de saída: 0 ok · 1 problema
nos arquivos de entrada · 2 problema na base de regras · 3 integridade falhou (nesse caso
`resumo.json` não é gravado e o relatório sai marcado como inválido) · 4 id inexistente.

### Outros comandos

| Comando | Para quê |
|---|---|
| `python -m src explicar <id_saida> --saida saida [--entrada ... --regras ...]` | De onde vem um número: linhas do rastro, regra e taxa usadas, campos da linha original |
| `python -m src pendencias --saida saida [--quem Helena] [--tipo SPREAD_NEGATIVO]` | Pendências por responsável, com valor em jogo |
| `python -m src regra propor --regras regras --tipo <TIPO> --campos chave=valor ...` | Monta e valida uma regra, mostra o efeito; **não grava** |
| `python -m src regra aplicar --regras regras --proposta <arquivo> --aprovado-por "<nome>"` | Grava a regra validada e registra em `historico_alteracoes.csv` |
| `python -m src empacotar-skill` | Gera `dist/fechamento-tarvo.zip` (skill autocontida com o motor e a base inicial) |

Roteiro completo para a analista, sem IA: [COMO_FECHAR_O_MES.md](COMO_FECHAR_O_MES.md).

## O que sai (`saida/`, versionada para a banca)

Os 6 CSVs do regulamento (`;`, ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos, UTF-8):
`comissoes_por_lojista`, `divergencias_taxa`, `notas_a_emitir`, `lancamentos_classificados`,
`pendencias`, `rastro`. Mais `resumo.json` (totais em string decimal, para agentes) e
`RELATORIO_FECHAMENTO.md` (uma página para a analista e o CFO). A cada `fechar` rodam 6
checagens de integridade: soma do rastro = valor reportado para todo id; notas = comissões
positivas; nota de remessa = soma da remessa; toda linha da Orbe e toda operação da Ponte em
exatamente um destino (nada some); todo lançamento classificado; saldo do Aurora fecha.

Setembro/2026: comissão CHECKOUT R$ 207.039,73 (21 lojistas), REMESSA R$ 39.543,45 (14),
21 notas (R$ 246.588,68), 233 divergências (R$ 16.973,65 checkout + R$ 1.418,85 remessa),
184 lançamentos classificados por regra, 16 pendências.

## Como funciona

```
regras/                 base de conhecimento do financeiro (CSV que abre no Excel)
  regras_negocio.csv      7 tipos: PARAMETRO, TAXA_EXCECAO, IGNORAR_DUPLICADO, EXCLUIR_E_PENDENCIA,
                          CLASSIFICAR_CONTA, DONO_PENDENCIA, MANUAL — com vigência, status e fonte
  complemento_cadastro.csv  só lacunas da planilha de taxas (EC em branco, lojista sem contrato)
  historico_alteracoes.csv  quem mudou o quê e por quê
  fontes.csv              padrões de nome dos arquivos e abas
  COMO_CRIAR_REGRA.md     guia de uma página para quem não é técnico
src/                    motor: leitores/ (uma fonte cada), regras.py (validação), checkout.py,
                        remessa.py, divergencias.py, notas.py, extratos.py, pendencias.py,
                        conciliacao.py, relatorio.py, validacao.py, cli.py
skills/fechamento-tarvo/  Agent Skill (SKILL.md + references + evals); atalho em .agents/skills/
tests/                  228 testes (pytest), inclusive casos sintéticos que rodam sem o data pack
```

Princípios: a planilha de taxas é o cadastro mestre; lojista só se identifica por CNPJ/EC,
nunca por nome; dinheiro só em `Decimal` com arredondamento HALF_UP por linha; nenhum nome de
lojista, taxa, conta ou mês dentro de `src/` (há teste); o que nenhuma regra cobre vira
pendência com dono, nunca palpite.

## Usar com IA

A skill `skills/fechamento-tarvo/SKILL.md` segue o padrão aberto Agent Skills e funciona em
Claude (Claude.ai, Claude Code, Cowork), Codex, Cursor e Copilot (que a encontram em
`.agents/skills/`). `AGENTS.md` resume o fluxo para agentes que não leem skills. Para
distribuir: `python -m src empacotar-skill` gera um zip autocontido (motor em `scripts/`,
base inicial em `assets/regras_iniciais/`) para upload na organização.

A skill só executa o motor e lê `saida/`. Toda regra proposta por ela passa por `regra propor`
(mostra o que seria gravado) e só é gravada com aprovação nominal (`regra aplicar --aprovado-por`).

### Dados enviados à IA

- **No fluxo da skill, nenhum arquivo é enviado pelo motor a serviço externo.** O agente roda
  `python -m src` localmente (ou no sandbox de code execution) e lê os resultados.
- **Classificação de extrato por IA é opcional e desligada por padrão.** Só acontece se
  `ANTHROPIC_API_KEY` estiver definida e houver lançamento que nenhuma regra cobre. Nesse
  caso o motor envia, **só desses lançamentos**, banco, data, descrição e valor, mais a lista
  de contas analíticas do plano. Nunca arquivos inteiros, nunca dados da Orbe, da Ponte ou de
  lojistas. A sugestão volta com `metodo=IA`, confiança < 1 e **sempre** vira pendência de
  revisão humana. Para desligar: não defina a chave, ou use `--sem-ia`.
- Em setembro/2026 todos os 184 lançamentos tiveram regra; nada foi enviado.

## Limitações conhecidas

- **Adquirente × banco não é conciliável com os arquivos do mês.** A adquirente liquida
  crédito parcelado em parcelas mensais (salvo antecipação), então o que entra no banco em
  setembro mistura parcelas de vendas anteriores e deixa de fora parcelas futuras. O relatório
  mostra os totais só como informativos (regra M-04); conciliar exige a agenda de recebíveis.
- O extrato OFX do Meridiano não traz saldo inicial, então o saldo desse banco não é conferido
  linha a linha (o do Aurora é).
- A duplicata da Ponte é resolvida ficando a primeira linha do arquivo quando os valores são
  iguais; se diferirem, nenhuma entra e vira pendência.
- Lojista sem contrato de checkout que faz remessa recebe comissão (o spread é pago pelo
  parceiro) e gera pendência informativa.
- A sugestão de conta por IA, quando ligada, usa o modelo definido em `ANTHROPIC_MODEL`
  (padrão `claude-opus-5-5`) e não foi exercitada com dados reais neste mês.

## Documentos

- [HIPOTESES.md](HIPOTESES.md): premissas, perguntas ao financeiro e respostas usadas.
- [PROMPTS/](PROMPTS/): histórico das sessões de IA e os momentos que importaram.
- [COMO_FECHAR_O_MES.md](COMO_FECHAR_O_MES.md): roteiro sem IA.
- [AGENTS.md](AGENTS.md): instruções para agentes.

## Testes

```bash
.venv/bin/python -m pytest
```
Sem o data pack na raiz, os testes que dependem dele são pulados; os sintéticos rodam.
