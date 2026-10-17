# A solução: o que é, por que é assim e como se usa

*Time MN AI (Nader Taha e Murilo Godoy). Este documento explica a ideia para quem não vai ler código.
Instalação e comandos estão no [README](README.md); premissas e respostas do financeiro, no
[HIPOTESES.md](HIPOTESES.md). Todos os números citados aqui vêm de `saida/resumo.json` (setembro/2026).*

## Em uma frase

Um **motor de fechamento** que lê os arquivos do mês como eles chegam, aplica as regras do financeiro
**escritas em planilhas que o próprio financeiro edita**, e devolve o que faturar, o que contestar, o que
devolver e o que precisa de uma pessoa, com **cada número ligado às linhas de origem**. Por cima dele, uma
**skill de IA** que conduz a analista pelo fechamento em linguagem natural, no assistente que a empresa já usa.

## 1. O que está quebrado na Tarvo

O fechamento leva oito dias úteis e erra. Automatizar o processo como ele é não resolveria, porque a lentidão
e os erros vêm de três causas:

1. **Não existe chave comum entre as fontes.** O mesmo lojista aparece com nomes diferentes na Orbe, na Ponte
   e na planilha; quem fecha casa tudo de cabeça.
2. **As regras só existem na cabeça de uma pessoa.** Tarifa zero da Casa do Estudante, taxa do estorno pela data
   da venda, spread negativo que não se aceita: nada disso estava escrito. *"Se eu sair de férias, o mês não fecha."*
3. **Ninguém compara o contratado com o aplicado.** A divergência só aparece quando o lojista reclama.

Uma tela nova não resolve nenhuma das três. Regra escrita, conferência linha a linha e uma fila de decisões com
dono resolvem.

## 2. A ideia: três camadas, cada uma com um papel

```
  Analista / Helena  ──── pede em português ────►  Assistente de IA + skill fechamento-tarvo
        ▲                                              │  conduz, explica, propõe regra
        │ decide pendências,                           │  (não calcula, não decide)
        │ aprova regras                                ▼
        │                                     Motor (python -m src)  ◄── arquivos do mês, como vieram
        └──── relatório, CSVs, rascunhos ◄────  calcula, confere, rastreia  ◄── regras/ (CSV no Excel)
```

| Camada | O que faz | Quem mexe |
|---|---|---|
| **Regras** (`regras/`) | O conhecimento do financeiro em CSV que abre no Excel: taxas especiais, exclusões, classificação de extrato, dono de cada pendência, com vigência e de onde veio cada regra | O financeiro, com validação automática; o Comercial aprova taxa |
| **Motor** (`src/`) | Lê as 6 fontes, calcula comissões, divergências, notas e lançamentos, confere 6 checagens de integridade e gera o rastro | Ninguém, no dia a dia. Não tem nome de lojista, taxa ou mês no código |
| **Skill** (`skills/fechamento-tarvo/`) | Ensina qualquer assistente compatível a rodar o motor, apresentar o resultado, explicar números, conduzir pendências e transformar decisão em regra | Ninguém, no dia a dia |

A divisão é de propósito: **o número auditável fica fora do modelo de linguagem.** A IA lê resultados prontos;
se o motor falha, ela não tem número para mostrar.

## 3. Por que não construímos uma plataforma web

Foi uma decisão, não uma falta de tempo. A primeira arquitetura que a própria IA nos propôs foi banco de dados,
backend e chatbot; recusamos ([PROMPTS/MOMENTOS.md](PROMPTS/MOMENTOS.md), momento 1). Os motivos:

1. **O que o cliente precisa é o resultado, não a tela.** O case pede comissões, divergências, notas,
   lançamentos e pendências que fecham com a origem. Cada hora em interface seria uma hora a menos conferindo
   número, e número errado com tela bonita continua errado.
2. **A tela não ataca a causa raiz.** O problema é regra na cabeça de uma pessoa e falta de conferência. Uma
   plataforma com as regras escondidas no código repetiria o problema: só quem programa saberia mudar.
3. **O time financeiro tem três pessoas e nenhum tempo.** Uma plataforma pede hospedagem, login, banco de dados,
   atualização e alguém para manter. Aqui não há servidor: são arquivos, o Excel que o time já usa e um assistente
   que a empresa já assina.
4. **Dado financeiro não precisa ir para um sistema novo.** O motor roda no computador da analista, sem internet.
   No modo com IA, o que sai é só o que o assistente lê (detalhe em "Dados enviados à IA", no README).
5. **A interface em linguagem natural já existe.** Assistentes como Claude já sabem conversar, montar tabela e
   gráfico e rodar código. Faltava a eles o procedimento da Tarvo e um motor confiável. É isso que entregamos.

**O que se perde com essa escolha, e como tratamos:**

| Custo | Tratamento |
|---|---|
| Não há um painel fixo para o CFO abrir | `RELATORIO_FECHAMENTO.md` é a página do CFO, gerada pelo motor. O assistente monta painel a partir do `resumo.json` quando pedido. Uma tela por cima do `resumo.json` é o primeiro item de "com mais um mês" |
| O modo conversacional depende de um assistente pago com execução de código | O motor roda sem IA, com o mesmo resultado ([COMO_FECHAR_O_MES.md](COMO_FECHAR_O_MES.md)) |
| Sem IA, a analista usa terminal | Um comando só (`./fechar.sh`) e mensagens de erro em português. A instalação (Python) é feita uma vez |

## 4. Vantagens que vêm da escolha

- **Fecha nas férias de quem fecha.** As regras estão escritas, com a origem de cada uma, e o procedimento está na
  skill. Outra pessoa do time fecha o mês pedindo "fecha outubro". Ensaiamos isso com um outubro sintético
  (`skills/fechamento-tarvo/evals/teste_ferias.md`).
- **Outubro roda sem retrabalho.** Não há código para mudar no mês seguinte: o arquivo novo entra, as regras
  continuam valendo, as transações que ficaram pendentes em setembro (Atlas, por exemplo) são relidas com
  `--anterior` e faturadas quando ganharem taxa.
- **A regra muda sem programador.** Decisão nova vira regra pelo assistente (que mostra o efeito antes e só grava
  com aprovação de quem pode aprovar aquele tipo) ou direto no Excel, e o `validar` aponta qualquer erro com a
  linha e como corrigir. Tudo fica no histórico: quem mudou, quando e por quê.
- **Não fica preso a um fornecedor de IA.** A skill segue o padrão aberto Agent Skills (`SKILL.md`), o `AGENTS.md`
  serve aos agentes que não leem skills, e o motor funciona sem nenhum dos dois.
- **Todo número se defende.** `explicar <id>` mostra as linhas de origem, a regra e a taxa usadas. A soma do rastro
  é conferida a cada execução; se não bater, o fechamento sai marcado como inválido.

## 5. Onde a solução roda

| Ambiente | Como usar | Status |
|---|---|---|
| **Claude Code** (terminal ou VS Code) | Abrir a pasta do projeto e pedir "fecha setembro" (lê `.agents/skills/` e `AGENTS.md`) | **Testado**: 7 de 7 cenários ([PLACAR](skills/fechamento-tarvo/evals/PLACAR.md)) |
| **Claude.ai** (chat, com execução de código e Skills ligadas) | Subir `dist/fechamento-tarvo.zip` como skill; anexar os arquivos do mês e pedir o fechamento | **Testado** em chat limpo, duas rodadas; a primeira expôs dois erros, corrigidos na skill e no motor (MOMENTOS, momento 4) |
| Cowork / Claude Desktop | Mesma skill, com a pasta do fechamento conectada | Mesmo formato, não testado à parte |
| Cursor, Codex, GitHub Copilot | Abrir o repositório; o agente lê o `AGENTS.md`, que aponta para a skill | Não testado |
| ChatGPT e outros chats com execução de código | Anexar o zip da skill e os arquivos e pedir que siga o `SKILL.md` | Não testado; não há suporte nativo a skills garantido |
| **Sem IA** | `./fechar.sh` (ou `fechar.bat`) e [COMO_FECHAR_O_MES.md](COMO_FECHAR_O_MES.md) | **Testado** (suíte automática de testes) |

Onde está "não testado", esperamos que funcione porque o contrato é o mesmo (comandos e arquivos), mas não
afirmamos sem ter rodado.

## 6. O fluxo de uso, de ponta a ponta

### Uma vez (implantação)

| Quem | Faz |
|---|---|
| Responsável de TI ou admin do assistente | Instala o Python 3.10+ no computador da analista, **ou** habilita execução de código e Skills na conta da empresa e publica `fechamento-tarvo.zip` para o time |
| Financeiro | Cria a pasta compartilhada `Fechamento Tarvo/` com `regras/` (copiada deste repositório), `entradas/` e `saidas/` |

### Todo mês

| # | Quem | O quê | O que sai |
|---|---|---|---|
| 1 | Analista | Junta os 6 arquivos do mês **como vieram** (Orbe, planilha de taxas, e-mail da Ponte, plano de contas, extratos) numa pasta. Não edita nada | |
| 2 | Analista | Pede ao assistente "fecha outubro" (ou roda `./fechar.sh <pasta> saida_outubro --anterior saida`) | |
| 3 | Motor | Valida arquivos e regras. Se falta arquivo ou uma regra está errada, para e diz qual, em português | Mensagem de erro, ou segue |
| 4 | Motor | Fecha e confere as 6 checagens de integridade | 6 CSVs, `resumo.json`, relatório, rascunhos de e-mail |
| 5 | Assistente | Apresenta, a partir do `resumo.json`: comissão por linha, notas, divergências, dinheiro em jogo por natureza, pendências por responsável | Resumo na conversa, painel se pedido |
| 6 | Analista ↔ assistente | Para cada pendência, o assistente mostra a evidência (`explicar`) e pergunta. **Quem decide é a pessoa** indicada na pendência (Helena, Comercial) | Decisão registrada |
| 7 | Helena | Revisa e envia os rascunhos de contestação (Orbe, Ponte) e o que depende do Comercial. O assistente nunca envia | E-mails enviados pela Helena |
| 8 | Analista ↔ assistente | Se uma decisão vale para os próximos meses: o assistente propõe a regra, mostra o efeito simulado no fechamento e pede aprovação; grava só com o nome de quem pode aprovar | Regra nova + linha no histórico |
| 9 | Motor | Fecha de novo com a regra nova | Saída final do mês |
| 10 | Analista | Emite as notas de `notas_a_emitir.csv`, lança no ERP `lancamentos_classificados.csv` | |

No chat web, que não guarda arquivos entre conversas, se uma regra mudar o assistente entrega um zip novo de regras,
e a analista o salva na pasta compartilhada no lugar do anterior.

### Quando algo foge do normal

| Situação | O que acontece |
|---|---|
| Lojista novo | Uma linha nova na planilha de taxas, como o financeiro já faz. Nada a mudar no sistema |
| Código de lojista que ninguém cadastrou | Vira pendência de cadastro com o nome como aparece na fonte. **Nunca** é casado por nome |
| Arquivo faltando ou de outro mês | O fechamento para e diz qual arquivo |
| Alguém pede ao assistente "recalcula com 2,59%" | Ele não recalcula: explica a regra vigente e oferece o caminho para alterá-la |
| Alguém sem o papel certo tenta aprovar uma taxa | O motor recusa: taxa é do Comercial |

## 7. Onde a IA atua e onde não atua

| A IA faz | A IA não faz |
|---|---|
| Roda os comandos na ordem certa e para quando há erro | Calcular, estimar ou somar qualquer valor |
| Apresenta e explica os números a partir dos arquivos do motor | Editar os arquivos de entrada |
| Conduz as pendências, mostrando a evidência | Decidir uma pendência |
| Escreve a proposta de regra e mostra o efeito | Gravar regra sem aprovação nominal de quem pode |
| Entrega os rascunhos de e-mail | Enviar e-mail |

O motivo é o regulamento e o bom senso: número que vai para nota fiscal precisa ser reproduzível e auditável, e um
modelo de linguagem não garante isso. Onde a IA ajuda de verdade é em tirar o fechamento da cabeça de uma pessoa e
deixá-lo conduzível por qualquer um do time.

## 8. Setembro/2026 em números

| | |
|---|---|
| Notas a emitir | 21, somando R$ 243.284,29 (checkout R$ 203.735,34; remessa R$ 39.543,45) |
| Cobrar da Orbe (taxa acima do contrato) | R$ 1.576,23 |
| Contestar com a Ponte | R$ 4.984,83 em 3 pedidos |
| Devolver ao lojista (Casa do Estudante, concessão comercial fora do contrato) | R$ 15.396,77 |
| Não faturar até o Comercial decidir | Atlas Idiomas, sem contrato |
| Lançamentos de extrato classificados | 184 de 184, todos por regra |
| Pendências com dono | 17 (3 informativas) |

As naturezas não se somam entre si (faturar, cobrar, contestar e devolver são dinheiros diferentes). O detalhe está em
`saida/RELATORIO_FECHAMENTO.md`.

## 9. Limites e próximos passos

As limitações conhecidas estão no [README](README.md#limitações-conhecidas). Com mais um mês: conciliar adquirente
× banco com a agenda de recebíveis da Orbe; ler o retorno das contestações e fechar o ciclo no mês seguinte; gerar
os arquivos de importação do ERP e das notas; uma tela de leitura sobre o `resumo.json`; testar a skill nos outros
ambientes da tabela da seção 5.
