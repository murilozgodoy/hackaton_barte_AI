# Fechamento Tarvo — Desafio Barte AI (time MN AI)

Motor **determinístico** que fecha o mês da Tarvo Pagamentos a partir dos arquivos como
eles chegam (relatório da Orbe, planilha de taxas, e-mail da Ponte Câmbio, plano de contas,
extratos Aurora e Meridiano) e entrega comissões, divergências de taxa, notas a emitir,
lançamentos classificados e pendências, **cada número com rastro até as linhas de origem**.
As regras de negócio são **dados editáveis pelo financeiro** (`regras/`), não código. A IA é
facilitadora opcional (skill `fechamento-tarvo`): conduz, explica e propõe regras; **nunca calcula**.

Time MN AI: Nader Taha e Murilo Godoy.

> **Comece por aqui:** [SOLUCAO.md](SOLUCAO.md) explica a ideia sem código: a causa raiz, por que entregamos
> um motor com skill de IA em vez de uma plataforma web, o fluxo completo de uso (o que a analista faz, o que o
> motor faz, o que a IA faz) e em quais assistentes a solução foi testada.

## Rodar em 3 passos

1. **Instale o Python** 3.10 ou mais novo ([python.org/downloads](https://www.python.org/downloads/)).
   Nada mais: sem banco, sem servidor, sem chave de API.
2. **Coloque os arquivos do mês numa pasta**, ou use o zip do data pack como veio. Serve o zip
   (com qualquer nome), uma pasta com o zip dentro, os 6 arquivos soltos ou em subpastas. A pasta
   `entrada/` deste projeto já existe para isso.
3. **Rode um comando** na raiz do projeto:
   ```bash
   ./fechar.sh caminho/do/zip_ou_pasta      # macOS/Linux
   ./fechar.sh pasta_do_mes                 # pasta com o zip + os arquivos que chegarem depois (ex.: 06_orbe_ajustes_tardios)
   fechar.bat caminho\do\zip_ou_pasta      # Windows
   ```
   Sem argumento, usa `entrada/` (e, se ela estiver vazia, o único `Tarvo_Data_Pack_*.zip` da raiz).
   O script cria o `.venv` se não existir, instala as versões fixas de `requirements.txt`, roda
   `validar` (para com código 1 ou 2 se a entrada ou a base de regras tiverem problema) e `fechar`.
   No fim imprime o **resumo do fechamento** (totais por linha de negócio, notas, divergências,
   pendências por responsável, checagens) e onde estão os arquivos: `saida/` com os 6 CSVs,
   `carteira_pendente.csv` (transações sem contrato/taxa guardadas para o mês seguinte), `resumo.json`
   e `RELATORIO_FECHAMENTO.md`.

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

## Fechar o mês seguinte

Quando chegarem os arquivos de outubro, feche **apontando para a saída de setembro**:
```bash
./fechar.sh caminho/do/zip_de_outubro saida_outubro --anterior saida      # macOS/Linux
fechar.bat caminho\do\zip_de_outubro saida_outubro --anterior saida      # Windows
.venv/bin/python -m src fechar --entrada <zip de outubro> --regras regras --saida saida_outubro --anterior saida
```
Com `--anterior`, o fechamento (a) relê `saida/carteira_pendente.csv` e fatura, junto com o mês, as
transações guardadas que agora têm taxa (ex.: TAXA_EXCECAO retroativa da Atlas aprovada pelo Comercial;
as demais continuam na carteira com a idade em meses); (b) reconhece os **ajustes da Ponte** (linha nova
com `AJUSTE REF PC-…` e Spread R$ negativo), que abatem a participação do mês dentro da nota única e viram
pendência informativa ligada ao pedido da contestação de setembro; (c) marca no relatório as pendências
**novas** e **recorrentes**. A competência vem dos dados; nada de setembro muda, e `saida/` continua sendo
só setembro (não haverá pacote de outubro, Organização 17/10). Para ensaiar sem arquivos reais há um
**outubro sintético** completo: `python -m tests.outubro_sintetico <pasta>` gera os 6 arquivos a partir de
setembro (EC novo, Bridge na taxa nova, Casa zerada, venda em 13x, carteira da Atlas, um ajuste da Ponte,
CNPJ novo na Ponte); o roteiro de uso está em `skills/fechamento-tarvo/evals/teste_ferias.md`.

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

## Usar com assistente de IA

A skill `skills/fechamento-tarvo/SKILL.md` segue o padrão aberto Agent Skills (atalho em `.agents/skills/`;
testada no Claude Code e no Claude.ai; ver [SOLUCAO.md](SOLUCAO.md), seção 5) e ensina um assistente a conduzir o fechamento **usando os mesmos
comandos deste README**: ele roda `validar` e `fechar`, lê `saida/resumo.json` e o relatório,
explica de onde vem cada número (`explicar`), conduz as pendências e propõe regras, que só são
gravadas com aprovação nominal. Ele nunca calcula nem edita entradas. `AGENTS.md` resume o fluxo
para agentes que não leem skills. Detalhes do que vai para a IA em "Dados enviados à IA", abaixo.

Há dois jeitos de usar: **abrir o repositório** (nada a instalar) ou **instalar a skill empacotada**
(zip autocontido, para usar fora do repositório ou no Claude.ai).

### Opção A: abrir o repositório (nada a instalar)

Abra a pasta do projeto no assistente (Claude Code no terminal ou no VS Code, Cursor, Codex, Copilot) e
peça, por exemplo, "fecha setembro com o zip que está na raiz". O Claude Code encontra a skill em
`.agents/skills/fechamento-tarvo/`; os demais agentes leem o `AGENTS.md`, que aponta para ela. O
assistente roda os comandos a partir da raiz, com o `.venv` criado pelo `./fechar.sh` (ou pelo
`pip install -r requirements.txt`). No Windows, o atalho `.agents/skills` é symlink e pode virar arquivo
de texto: aponte o assistente para `skills/fechamento-tarvo/SKILL.md` ou para o `AGENTS.md`.

### Opção B: instalar a skill empacotada

O zip **não é versionado** (`dist/` está no `.gitignore`); ele é gerado a partir do repositório e leva
tudo de que a skill precisa: `SKILL.md`, `references/`, uma cópia do motor em `scripts/src/`,
`scripts/requirements.txt`, a base de regras atual em `assets/regras_iniciais/`, o `AGENTS.md` e o
`COMO_FECHAR_O_MES.md`.

1. **Gerar o zip** (na raiz do repositório, com o `.venv` já criado):
   ```bash
   .venv/bin/python -m src empacotar-skill        # cria dist/fechamento-tarvo.zip
   ```
2. **Instalar** conforme o assistente:

   | Assistente | Como instalar |
   |---|---|
   | **Claude Code**, para todos os projetos | `mkdir -p ~/.claude/skills && unzip -o dist/fechamento-tarvo.zip -d ~/.claude/skills/` |
   | **Claude Code**, só em um projeto | `unzip -o dist/fechamento-tarvo.zip -d <projeto>/.claude/skills/` |
   | **Claude.ai** (chat) | Em *Configurações*, ligue a execução de código e as Skills; na lista de Skills, envie `dist/fechamento-tarvo.zip` |
   | **Claude Desktop / Cowork** | O mesmo zip, pela tela de Skills (mesmo formato, não testado à parte) |
   | Outros agentes compatíveis com SKILL.md | Descompacte o zip na pasta de skills do agente (por exemplo `.agents/skills/` do projeto); deve ficar `<pasta de skills>/fechamento-tarvo/SKILL.md` |

   No Windows (PowerShell): `Expand-Archive dist\fechamento-tarvo.zip -DestinationPath $HOME\.claude\skills -Force`.
3. **Instalar as dependências do motor** uma vez (o Claude.ai faz isso sozinho no ambiente dele):
   ```bash
   python3 -m pip install -r ~/.claude/skills/fechamento-tarvo/scripts/requirements.txt
   ```
   Se o pip recusar por ambiente gerenciado (Python do Homebrew ou do sistema), use o Python do `.venv`
   do repositório (`.venv/bin/python`) ao pedir ao assistente que rode a skill.
4. **Conferir:** reinicie o assistente e peça "fecha o mês com os arquivos desta pasta". Na skill
   instalada, os comandos rodam a partir de `fechamento-tarvo/scripts/`; sem `--regras`, o motor usa
   `assets/regras_iniciais/` e avisa no `resumo.json` e no relatório que está na base inicial. Para usar
   a base de regras do time (com as regras aprovadas depois), passe `--regras <pasta ou zip>`.

Para atualizar a skill depois de mudar o motor ou as regras, gere o zip de novo e repita o passo 2
(o `unzip -o` sobrescreve a versão anterior).

### Instalação por um agente com acesso ao repositório

Um agente que só tem o endereço do repositório consegue baixar e instalar a skill com este bloco
(macOS/Linux; precisa de `git`, Python 3.10+ e `unzip`):

```bash
git clone --depth 1 https://github.com/murilozgodoy/hackaton_barte_AI.git
cd hackaton_barte_AI
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m src empacotar-skill                          # gera dist/fechamento-tarvo.zip
mkdir -p ~/.claude/skills && unzip -o dist/fechamento-tarvo.zip -d ~/.claude/skills/
python3 -m pip install -r ~/.claude/skills/fechamento-tarvo/scripts/requirements.txt
```

Para outro agente, troque `~/.claude/skills` pela pasta de skills dele. Para o Claude.ai, pare depois do
`empacotar-skill` e envie `dist/fechamento-tarvo.zip` pela tela de Skills.

### Prompt para qualquer IA baixar a skill e fechar o mês

Serve para qualquer assistente que **execute código** (Claude, ChatGPT, Gemini, Cursor, Codex, Copilot e
outros), com ou sem suporte a skills. Anexe os arquivos do mês (ou o zip do data pack) e cole:

```text
Quero fechar o mês da Tarvo Pagamentos com a skill fechamento-tarvo, do repositório público
https://github.com/murilozgodoy/hackaton_barte_AI. Siga estes passos, sem pular nenhum:

1. Baixe o repositório. Com git: git clone --depth 1 https://github.com/murilozgodoy/hackaton_barte_AI.git
   Sem git: baixe https://github.com/murilozgodoy/hackaton_barte_AI/archive/refs/heads/main.zip e
   descompacte (a pasta se chama hackaton_barte_AI-main). Se você não tiver acesso à internet, peça
   que eu anexe esse zip.
2. Na raiz do repositório, instale as dependências (Python 3.10+):
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   (no Windows: .venv\Scripts\pip; se não puder criar venv, use pip install -r requirements.txt)
3. Leia skills/fechamento-tarvo/SKILL.md inteiro e siga as regras dele durante toda a conversa,
   começando pela seção "Limites". Se a sua ferramenta instala skills, pode instalar esta; se não,
   apenas siga o arquivo.
4. Rode, a partir da raiz, com os arquivos do mês que anexei (zip ou pasta). Onde está "python",
   use o Python do venv (.venv/bin/python) se você o criou:
   python -m src validar --entrada <zip ou pasta> --regras regras --json
   Se o código de saída for 1 ou 2, explique o problema e pare.
   python -m src fechar --entrada <zip ou pasta> --regras regras --saida saida --json
   Se o código for 3, explique e pare.
5. Apresente o resultado a partir de saida/resumo.json e saida/RELATORIO_FECHAMENTO.md (página 1 é
   para o CFO), me entregue os CSVs de saida/ e conduza as pendências com
   python -m src pendencias --saida saida --json e python -m src explicar <id> ...

Regras: todo número vem de saida/; não calcule, estime nem ajuste valores por conta própria; não edite
os arquivos de entrada; não decida pendências; não grave regra sem a minha aprovação nominal; não
envie e-mail. Se você não puder executar código, diga isso e me indique o COMO_FECHAR_O_MES.md do
repositório, sem tentar fazer o fechamento à mão.
```

Os arquivos do mês precisam ser anexados: o data pack não está no repositório, que é público. Com o zip de
setembro em mãos, a IA também consegue ensaiar o mês seguinte com
`python -m tests.outubro_sintetico <pasta> <zip de setembro>` e `fechar --anterior saida`.

### Outros comandos

| Comando | Para quê |
|---|---|
| `python -m src explicar <id_saida> --saida saida [--entrada ... --regras ...]` | De onde vem um número: linhas do rastro, regra e taxa usadas, campos da linha original |
| `python -m src pendencias --saida saida [--quem Helena] [--tipo SPREAD_NEGATIVO]` | Pendências por responsável, com valor em jogo |
| `python -m src regra propor --regras regras --entrada <mês> [--anterior <saida anterior>] --tipo <TIPO> --campos chave=valor ...` | Monta e valida uma regra, mostra o efeito esperado e, com `--entrada`, o **efeito simulado** (fecha o mês de novo numa pasta temporária com a regra: comissão e nota por lojista que mudam, pendências que somem ou aparecem, carteira que entraria); **não grava** |
| `python -m src regra aplicar --regras regras --proposta <arquivo> --aprovado-por "<nome>" [--registrado-por "<nome>"]` | Diz quem aprova e quem registra aquele tipo, grava a regra validada e registra em `historico_alteracoes.csv`; recusa aprovador de outro papel (taxa e condição comercial = Comercial, resto = Helena, `regras/aprovadores.csv`) |
| `python -m tests.outubro_sintetico <pasta>` | Gera um pacote completo do mês seguinte a partir de setembro, para ensaiar `fechar --anterior` |
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

Setembro/2026 (relatório da Orbe + os 14 ajustes tardios do arquivo 06, publicados em 17/10): comissão
CHECKOUT R$ 203.735,34 (21 lojistas, 1.900 transações), REMESSA R$ 39.543,45 (14), 21 notas (R$ 243.284,29;
sem o 06 seriam R$ 207.039,73 e R$ 246.588,68), 115 divergências de contrato (R$ 1.576,23 checkout + R$ 1.418,85 remessa,
contestadas), 184 lançamentos classificados por regra, 16 pendências. As 118 transações da Casa do
Estudante ficam fora de `divergencias_taxa.csv` por regra (X-01, `destino=PENDENCIA`): são uma concessão
comercial fora do contrato, e a devolução ao lojista por conta da Tarvo (R$ 15.396,77, o que a Orbe cobrou de
fato; a fórmula daria R$ 15.397,42) existe só na pendência TARIFA_ZERO_COBRADA, com o detalhe por transação
no rastro. O `RELATORIO_FECHAMENTO.md` abre com a página do CFO (totais, notas, dinheiro em jogo por
natureza, nunca somado entre naturezas, pendências por responsável, rascunhos prontos em
`saida/comunicacoes/`, conhecimento capturado) e traz o detalhe em anexo.

Arquivos que chegarem depois (ajustes tardios, reenvios): coloque o zip e os arquivos novos na mesma pasta e rode
`./fechar.sh <pasta>`. Cada arquivo é reconhecido pelo **conteúdo** (assinatura da fonte em `regras/fontes.csv`: cabeçalho
do CSV, aba do xlsx, anexo do e-mail, tag e conta do OFX), não pelo nome; a Orbe e a Ponte aceitam vários arquivos no
mesmo formato, e o que não for reconhecido vira aviso no relatório ("arquivo X não reconhecido; não foi usado"), nunca
some em silêncio. Fonte obrigatória ausente para com código 1 dizendo o que falta e o que foi encontrado.

## Como funciona

```
regras/                 base de conhecimento do financeiro (CSV que abre no Excel)
  regras_negocio.csv      9 tipos: PARAMETRO, TAXA_EXCECAO, IGNORAR_DUPLICADO, EXCLUIR_E_PENDENCIA,
                          AJUSTE_PARCEIRO, CLASSIFICAR_CONTA, DONO_PENDENCIA, ALERTA, MANUAL — com vigência,
                          status, prioridade (regras de destino) e fonte
  aprovadores.csv         quem aprova e quem registra cada tipo de regra
  causas_divergencia.csv  a causa de cada divergência por lojista (vai para os rascunhos e o relatório)
  comunicacoes.csv        destinatários e textos dos rascunhos por contraparte
  complemento_cadastro.csv  só lacunas da planilha de taxas (EC em branco, lojista sem contrato)
  historico_alteracoes.csv  quem mudou o quê e por quê
  fontes.csv              padrões de nome dos arquivos e abas
  COMO_CRIAR_REGRA.md     guia de uma página para quem não é técnico
entrada/                onde deixar o zip ou os arquivos do mês (ignorada pelo git)
fechar.sh / fechar.bat  um comando: cria o venv, instala, valida e fecha
src/                    motor: leitores/ (uma fonte cada), regras.py (validação), checkout.py,
                        remessa.py, divergencias.py, notas.py, extratos.py, pendencias.py, carteira.py,
                        conciliacao.py, comunicacoes.py (rascunhos), relatorio.py, simulacao.py (efeito de
                        regra antes de gravar), validacao.py, cli.py
skills/fechamento-tarvo/  Agent Skill (SKILL.md + references + evals); atalho em .agents/skills/
tests/                  mais de 300 testes (pytest), inclusive casos sintéticos que rodam sem o data pack e o
                        outubro sintético (tests/outubro_sintetico.py) fechado de ponta a ponta com --anterior
```

Princípios: a planilha de taxas é o cadastro mestre; lojista só se identifica por CNPJ/EC,
nunca por nome; dinheiro só em `Decimal` com arredondamento HALF_UP por linha; nenhum nome de
lojista, taxa, conta ou mês dentro de `src/` (há teste); o que nenhuma regra cobre vira
pendência com dono, nunca palpite.

## Dados enviados à IA

- **O motor não envia nada a serviço externo.** O agente roda `python -m src` localmente (ou no sandbox de
  code execution) e lê os resultados.
- **O que o agente lê passa pelo provedor do modelo.** Tudo o que o assistente lê para conduzir o fechamento
  (`resumo.json`, `pendencias.csv`, o relatório, a saída de `explicar` e trechos dos arquivos que ele abrir) vai
  para o provedor do modelo de IA como parte da conversa. No chat web (Claude.ai, Cowork), os arquivos anexados
  sobem para o sandbox do provedor. Quem não aceitar isso usa só a CLI, sem IA (`COMO_FECHAR_O_MES.md`): o
  resultado é o mesmo.
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
- **Alerta de antecipação sem histórico de meses anteriores.** O motor só enxerga as vendas do arquivo
  do mês; lojistas antigos antecipam vendas de meses anteriores, por isso o alerta (A-01) só vale para
  lojista sem contrato ou cuja primeira transação é no próprio mês, comparando o bruto antecipado com o
  vendido até o dia (critério do time, delegado pela Helena em 17/10; `HIPOTESES.md`).
- **Formato do ajuste da Ponte** foi descrito pela Helena (linha nova, `AJUSTE REF PC-…`, Spread R$
  negativo), mas nenhum ajuste real chegou em setembro: as regras J-01/J-02 foram exercitadas só com o
  outubro sintético.
- **`fechar.bat` não foi testado em Windows** pelo time (só o `fechar.sh` em macOS/Linux). O motor em si
  roda em qualquer sistema com Python 3.10+.
- **Aprovação da base de regras.** 32 itens da base são premissas do time, sem aprovação do financeiro
  (`validar` e o topo do relatório listam todos). A X-01 (Casa do Estudante, TAXA_EXCECAO, que o Comercial
  aprova) só tem as mensagens da Helena relatando a concessão, sem aprovação nominal do Comercial no Slack.
  Regra confirmada pela Helena e alterada depois pelo time conta como premissa (a linha mais recente do
  histórico decide).
- **Os cenários 10 a 13 dos evals** (prazo, total, painel, base inicial) estão descritos, mas ainda não
  foram rodados num modelo; o comportamento do motor que eles cobram tem teste automatizado.
- A sugestão de conta por IA, quando ligada, usa o modelo definido em `ANTHROPIC_MODEL`
  (padrão `claude-opus-5-5`) e não foi exercitada com dados reais neste mês.
- **`ref_origem` em pendências.** Nas pendências por lojista (ex.: Atlas sem contrato), `ref_origem` é o CNPJ,
  porque a pendência não tem uma linha de origem só; as linhas que a compõem estão no `rastro.csv`. Na PEN-0006
  (CONFERIR_REPASSE_PONTE), R$ 0,56 vêm da linha de total "SPREAD TOTAL R$:" do relatório da Ponte (linha 241),
  que não tem Nº Operação; o `ref_origem` aponta a linha do relatório. As outras 5 parcelas usam o Nº Operação.
  A soma do rastro bate com o valor da pendência.

## Documentos

- [SOLUCAO.md](SOLUCAO.md): a ideia, por que não uma plataforma, fluxo de uso e onde roda.
- [HIPOTESES.md](HIPOTESES.md): premissas, perguntas ao financeiro e respostas usadas.
- [PROMPTS/](PROMPTS/): histórico das sessões de IA e os momentos que importaram.
- [COMO_FECHAR_O_MES.md](COMO_FECHAR_O_MES.md): roteiro sem IA.
- [AGENTS.md](AGENTS.md): instruções para agentes.

## Testes

```bash
.venv/bin/python -m pytest
```
Sem o data pack na raiz, os testes que dependem dele são pulados; os sintéticos rodam.
