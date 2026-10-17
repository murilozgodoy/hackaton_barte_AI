# Cenários de teste da skill

Os cenários estão em `evals.json` (prompt, arquivos, saída esperada, asserções), no formato
usado pelo `skill-creator`. Rodam-se manualmente: cada cenário em uma conversa limpa, com e
sem a skill carregada, e anota-se aqui o resultado. O **teste de férias** (outubro sintético,
`fechar --anterior`, efeito simulado de regra, quem aprova) está em `teste_ferias.md`.

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

Queries de gatilho para testar a description (devem acionar): "fecha o mês da Tarvo", "quanto
cada lojista tem de comissão", "a Orbe cobrou taxa errada?", "que notas emitimos", "classifica
os extratos", "explica o PEN-0003", "cria uma regra para o PIX da contabilidade", "prepara a
contestação para a Ponte", "o que muda se a Atlas tiver 2%?".
Não devem acionar: "resume este contrato", "faz um gráfico de vendas da minha loja", "o que é
MDR?" (pergunta conceitual sem arquivos), "escreve um e-mail para a Ponte" (sem o fechamento).
