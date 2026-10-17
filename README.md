# Fechamento Tarvo — Desafio Barte AI (time MN AI)

Motor **determinístico** que fecha o mês da Tarvo Pagamentos a partir dos arquivos como
eles chegam (relatório da Orbe, planilha de taxas, e-mail da Ponte Câmbio, plano de contas,
extratos Aurora e Meridiano) e entrega comissões, divergências de taxa, notas a emitir,
lançamentos classificados e pendências, **cada número com rastro até as linhas de origem**.
As regras de negócio são **dados editáveis pelo financeiro** (`regras/`), não código. A IA é
facilitadora opcional (skill `fechamento-tarvo`): conduz, explica e propõe regras; **nunca calcula**.

Time MN AI: Nader Taha e Murilo Godoy.

## Rodar em 3 passos

1. **Instale o Python** 3.10 ou mais novo ([python.org/downloads](https://www.python.org/downloads/)).
   Nada mais: sem banco, sem servidor, sem chave de API.
2. **Coloque os arquivos do mês numa pasta**, ou use o zip do data pack como veio. Serve o zip
   (com qualquer nome), uma pasta com o zip dentro, os 6 arquivos soltos ou em subpastas. A pasta
   `entrada/` deste projeto já existe para isso.
3. **Rode um comando** na raiz do projeto:
   ```bash
   ./fechar.sh caminho/do/zip_ou_pasta      # macOS/Linux
   fechar.bat caminho\do\zip_ou_pasta      # Windows
   ```
   Sem argumento, usa `entrada/` (e, se ela estiver vazia, o único `Tarvo_Data_Pack_*.zip` da raiz).
   O script cria o `.venv` se não existir, instala as versões fixas de `requirements.txt`, roda
   `validar` (para com código 1 ou 2 se a entrada ou a base de regras tiverem problema) e `fechar`.
   No fim imprime o **resumo do fechamento** (totais por linha de negócio, notas, divergências,
   pendências por responsável, checagens) e onde estão os arquivos: `saida/` com os 6 CSVs,
   `resumo.json` e `RELATORIO_FECHAMENTO.md`.

Mesmo resultado sem o script:
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src validar --entrada <zip ou pasta> --regras regras      # confere, não calcula
.venv/bin/python -m src fechar  --entrada <zip ou pasta> --regras regras --saida saida
```

- **Entrada:** cada arquivo é reconhecido pelo padrão de nome em `regras/fontes.csv` (`01_orbe_*.csv`,
  `02_tabela_taxas*.xlsx`, `03_email_ponte*.eml`, `04_plano_de_contas*.csv`, `05a_extrato_banco_aurora*.csv`,
  `05b_extrato_banco_meridiano*.ofx`), nunca por nome fixo de um mês. A competência vem dos dados
  (`--competencia AAAA-MM` só se quiser forçar). Arquivo ausente ou repetido para o fechamento com
  uma mensagem em português dizendo qual. O data pack **não é versionado** (repositório público).
- **Determinismo:** rodar de novo, em qualquer máquina, gera os mesmos arquivos byte a byte (sem data
  ou hora, ordem estável, UTF-8, quebra de linha `\n`). Há teste que compara o `saida/` versionado
  com o que o código gera (`tests/test_conciliacao_revisao.py::test_saida_versionada_e_a_do_codigo_atual`)
  e outro que fecha por pasta solta, subpasta e pasta com zip e confere que sai o mesmo `saida/`.
- **Versões:** `requirements.txt` fixa pandas 2.3.3, openpyxl 3.1.5 e pytest 9.1.1. O motor foi
  testado em Python 3.10, 3.11, 3.12, 3.13 e 3.14, com pandas 2.3.3 e com pandas 3.0.6, e o
  `saida/` é idêntico em todas as combinações (pandas 3 exige Python 3.11+).
- Todos os comandos aceitam `--json` (saída para agentes). Códigos de saída: 0 ok · 1 problema nos
  arquivos de entrada · 2 problema na base de regras · 3 integridade falhou (nesse caso `resumo.json`
  não é gravado e o relatório sai marcado como inválido) · 4 id inexistente.

## Chave de API

**Não é necessária.** O fechamento inteiro é determinístico e roda sem internet.

`ANTHROPIC_API_KEY` é **opcional** e serve para uma única coisa: sugerir uma conta contábil para
lançamento de extrato que **nenhuma regra** de `regras/regras_negocio.csv` cobre. Está desligada por
padrão (sem a chave, nada acontece) e **nunca foi usada em setembro/2026**: os 184 lançamentos do mês
tiveram regra. Se quiser ligar:

1. Instale o cliente: `.venv/bin/pip install anthropic`.
2. Defina a variável de ambiente antes de rodar: `export ANTHROPIC_API_KEY=sk-ant-...` (macOS/Linux)
   ou `set ANTHROPIC_API_KEY=sk-ant-...` (Windows). Não há arquivo de configuração nem `.env`;
   o motor só lê a variável. Opcional: `ANTHROPIC_MODEL` (padrão `claude-opus-5-5`).
3. Rode o `fechar` normalmente. Para desligar sem apagar a chave: `--sem-ia`.

O que é enviado, e só se houver lançamento sem regra: banco, data, descrição e valor **desses
lançamentos**, mais a lista de contas analíticas do plano de contas. Nunca arquivos inteiros, nunca
dados da Orbe, da Ponte ou de lojistas. A sugestão volta com `metodo=IA`, confiança menor que 1 e
**sempre** vira pendência de revisão humana; a IA não calcula nem decide nada. Código: `src/ia.py`.

## Usar com assistente de IA (opcional)

A skill `skills/fechamento-tarvo/SKILL.md` (padrão aberto Agent Skills; atalho em `.agents/skills/`)
ensina um assistente (Claude, Codex, Cursor, Copilot) a conduzir o fechamento **usando os mesmos
comandos deste README**: ele roda `validar` e `fechar`, lê `saida/resumo.json` e o relatório,
explica de onde vem cada número (`explicar`), conduz as pendências e propõe regras, que só são
gravadas com aprovação nominal. Ele nunca calcula nem edita entradas. `AGENTS.md` resume o fluxo
para agentes que não leem skills. Para distribuir: `python -m src empacotar-skill` gera um zip
autocontido em `dist/`. Detalhes em "Dados enviados à IA", abaixo.

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
entrada/                onde deixar o zip ou os arquivos do mês (ignorada pelo git)
fechar.sh / fechar.bat  um comando: cria o venv, instala, valida e fecha
  COMO_CRIAR_REGRA.md     guia de uma página para quem não é técnico
src/                    motor: leitores/ (uma fonte cada), regras.py (validação), checkout.py,
                        remessa.py, divergencias.py, notas.py, extratos.py, pendencias.py,
                        conciliacao.py, relatorio.py, validacao.py, cli.py
skills/fechamento-tarvo/  Agent Skill (SKILL.md + references + evals); atalho em .agents/skills/
tests/                  251 testes (pytest), inclusive casos sintéticos que rodam sem o data pack
```

Princípios: a planilha de taxas é o cadastro mestre; lojista só se identifica por CNPJ/EC,
nunca por nome; dinheiro só em `Decimal` com arredondamento HALF_UP por linha; nenhum nome de
lojista, taxa, conta ou mês dentro de `src/` (há teste); o que nenhuma regra cobre vira
pendência com dono, nunca palpite.

## Dados enviados à IA

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
