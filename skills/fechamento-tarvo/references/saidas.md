# Saídas do motor (`saida/`)

Formato fixo: CSV com `;`, ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos, UTF-8. As
colunas obrigatórias vêm primeiro; as extras ajudam a explicar. Todo `id_saida` com valor
tem linhas em `rastro.csv` somando exatamente o valor (checagem 1, em todo `fechar`).

| Arquivo | Uma linha por | Colunas obrigatórias | Extras úteis |
|---|---|---|---|
| `comissoes_por_lojista.csv` | lojista × linha de negócio | id_saida (COM-CHK-/COM-REM-), cnpj, lojista, linha_negocio, comissao_brl | qtd_transacoes/qtd_operacoes, valor_bruto_total, taxa_cobrada_orbe_brl (o que a Orbe cobrou, para comparar), spread_realizado_brl, excesso_contestado_brl |
| `carteira_pendente.csv` | transação de checkout sem contrato, taxa ou cadastro, guardada para o próximo `fechar --anterior` | arquivo_origem, ref_origem, cnpj, ec, data_venda, produto, valor_bruto, motivo, competencia_origem | idade_meses, lojista, destino, regra_id e os campos da linha da Orbe (para refazer o cálculo) |
| `divergencias_taxa.csv` | transação com taxa aplicada ≠ contratada (só divergências de contrato: a diferença marcada `divergencia=DEVOLUCAO_LOJISTA` numa TAXA_EXCECAO fica fora, na pendência) | id_saida (DIV-), cnpj, linha_negocio, ref_origem, taxa_contratada_pct, taxa_aplicada_pct, diferenca_brl | lojista, data, produto, valor_base_brl, diferenca_pp, regra_id (de onde veio a taxa contratada), tipo_pendencia |
| `notas_a_emitir.csv` | nota | id_saida (NF-), tomador_cnpj, tomador, linha_negocio, valor_brl, discriminacao | id_comissao, qtd_itens, competencia |
| `lancamentos_classificados.csv` | lançamento de extrato | id_saida (LAN-), banco, ref_origem, data, descricao, valor, conta_codigo, metodo, confianca | conta_descricao, regra_id, papel, tipo_pendencia |
| `pendencias.csv` | coisa que precisa de pessoa | id_saida (PEN-), tipo, ref_origem, valor_brl, motivo, quem_decide | subtipo, linha_negocio, cnpj, lojista, qtd_itens, regra_id, o_que_fazer |
| `rastro.csv` | ligação saída → origem | id_saida, arquivo_origem, ref_origem, valor | regra_id (regra ou célula da planilha usada), taxa_pct (taxa usada naquela linha) |
| `resumo.json` | — | competencia, status_integridade, totais, lancamentos, pendencias por responsável/tipo, conciliacao, lembretes, avisos, arquivos | só existe quando a integridade passou |
| `RELATORIO_FECHAMENTO.md` | — | uma página para a analista e o CFO | marcado "INVÁLIDO" se a integridade falhou |

## Significados

- **ref_origem**: `id_transacao` da Orbe (TX…/AN…), `Nº Operação` da Ponte (PC-…), linha física do Aurora (`L<n>`, contando o cabeçalho), FITID do Meridiano (MRD…). Em pendência agregada por lojista, é o CNPJ.
- **taxas `_pct`**: percentual (2.69 = 2,69%). `spread_pct` da Ponte tem até 4 casas (1.5006).
- **metodo**: REGRA (regra CLASSIFICAR_CONTA, confiança 1), IA (sugestão com chave de API, confiança < 1, sempre com pendência REVISAR_IA), HUMANO (sem regra, conta vazia, pendência EXTRATO_NAO_IDENTIFICADO).
- **conta_codigo** é a **contrapartida** do movimento bancário: se o valor já estava registrado (provisão, recebível, obrigação), é a conta onde estava; só é receita/despesa quando não havia registro anterior.
- **valor_brl negativo em pendência**: spread negativo, saldo negativo de lojista, valor saindo em trânsito. O "valor em jogo" por responsável soma os absolutos.
- **Destinos** (não saem em CSV, mas aparecem em `resumo.json`): toda linha da Orbe e toda operação única da Ponte cai em exatamente um: COMISSAO, EXCLUIDO (regra), SEM_CADASTRO, SEM_TAXA, FORA_COMPETENCIA, DUPLICATA_IGNORADA, DUPLICATA_DIVERGENTE. Nada some.

## Códigos de saída da CLI

0 ok · 1 problema nos arquivos de entrada · 2 problema na base de regras · 3 integridade falhou · 4 id_saida inexistente.
