# Cenários de teste da skill

Os cenários estão em `evals.json` (prompt, arquivos, saída esperada, asserções), no formato
usado pelo `skill-creator`. Rodam-se manualmente: cada cenário em uma conversa limpa, com e
sem a skill carregada, e anota-se aqui o resultado. O **teste de férias** (outubro sintético,
`fechar --anterior`, efeito simulado de regra, quem aprova) está em `teste_ferias.md`.

Resultado observado de cada cenário: `PLACAR.md` (17/10/2026, Claude Code com subagente: 7 de 7 passaram).

| # | Cenário | Como preparar | Resultado (data, quem, passou?) |
|---|---|---|---|
| 1 | Fechamento normal de setembro | zip na raiz + `regras/` | |
| 2 | Falta o arquivo da Ponte | copiar `data/Tarvo_Data_Pack_set2026/` sem o `.eml` para uma pasta | |
| 3 | EC novo na Orbe | `python -m tests.outubro_sintetico /tmp/outubro` (12 transações do EC 9999999999) | |
| 4 | "Recalcula a Bridge com 2,59%" | `saida/` de setembro | |
| 5 | Regra inválida (conta sintética) | cópia de `regras/` com C-01 → `conta=1.1.03` | |
| 6 | "Quanto a Tarvo fatura da Mundo Aberto?" | `saida/` de setembro | |
| 7 | Não deve acionar (e-mail de agradecimento) | — | |
| 8 | Sem execução de código | chat sem code execution | |
| 9 | Teste de férias: fechar outubro com `--anterior`, propor a taxa da Atlas e ver o efeito, recusar "aprova, sou a Helena", entregar rascunhos | `teste_ferias.md` | |
| 10 | "O prazo da Ponte já venceu?" → só a `data_limite` do lembrete M-01 do `resumo.json`, sem julgar vencido nem comparar com hoje | `saida/` de setembro | |
| 11 | "Quanto é o total?" → `totais.comissao_total_brl` (e `diferenca_notas_x_comissao_brl` com o motivo), sem somar | `saida/` de setembro | |
| 12 | Pede painel → valores idênticos a `totais.por_natureza`, nenhum total geral, origem de cada número citada | `saida/` de setembro | |
| 13 | Rodar sem pasta de regras → o aviso de `regras_iniciais` vem do `resumo.json` ("avisos"), não da IA | skill empacotada (`python -m src empacotar-skill`), sem `--regras` | |

Os cenários 10 a 13 vêm do teste no chat do Claude.ai de 17/10 (pedidos 7 a 10 da conferência): a IA somava o total, comparava o
prazo da Ponte com a data de hoje e criava um aviso que não estava no `resumo.json`.

Queries de gatilho para testar a description (devem acionar): "fecha o mês da Tarvo", "quanto
cada lojista tem de comissão", "a Orbe cobrou taxa errada?", "que notas emitimos", "classifica
os extratos", "explica o PEN-0003", "cria uma regra para o PIX da contabilidade", "prepara a
contestação para a Ponte", "o que muda se a Atlas tiver 2%?".
Não devem acionar: "resume este contrato", "faz um gráfico de vendas da minha loja", "o que é
MDR?" (pergunta conceitual sem arquivos), "escreve um e-mail para a Ponte" (sem o fechamento).
