# Saídas do motor (`saida/`)

Formato fixo: CSV com `;`, ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos, UTF-8. As
colunas obrigatórias vêm primeiro; as extras ajudam a explicar. Todo `id_saida` com valor
tem linhas em `rastro.csv` somando exatamente o valor (checagem 1, em todo `fechar`).

| Arquivo | Uma linha por | Colunas obrigatórias | Extras úteis |
|---|---|---|---|
| `comissoes_por_lojista.csv` | lojista × linha de negócio | id_saida (COM-CHK-/COM-REM-), cnpj, lojista, linha_negocio, comissao_brl | qtd_transacoes/qtd_operacoes, valor_bruto_total, taxa_cobrada_orbe_brl (o que a Orbe cobrou, para comparar), spread_realizado_brl, excesso_contestado_brl. Lojista sem contrato (Atlas) **não** aparece: fica na carteira |
| `carteira_pendente.csv` | transação de checkout sem contrato, taxa ou cadastro (ou parcelado fora das faixas), guardada para o próximo `fechar --anterior` | arquivo_origem, ref_origem, cnpj, ec, data_venda, produto, valor_bruto, motivo, competencia_origem | idade_meses, lojista, destino, regra_id e os campos da linha da Orbe (para refazer o cálculo) |
| `divergencias_taxa.csv` | transação com taxa aplicada ≠ contratada, **de qualquer natureza** | id_saida (DIV-), cnpj, linha_negocio, ref_origem, taxa_contratada_pct, taxa_aplicada_pct, diferenca_brl | lojista, data, produto, valor_base_brl, diferenca_pp, regra_id (de onde veio a taxa contratada), tipo_pendencia, **natureza** (CONTRATO = cobrança da contraparte; DEVOLUCAO_LOJISTA = concessão comercial, devolução por conta da Tarvo, fora de qualquer total a cobrar), **observacao** (texto da regra TAXA_EXCECAO) |
| `notas_a_emitir.csv` | nota | id_saida (NF-), tomador_cnpj, tomador, linha_negocio, valor_brl, discriminacao | id_comissao, qtd_itens, competencia. Remessa: nota única para o parceiro, ajustes incluídos; zerada ou negativa não sai (vira pendência) |
| `lancamentos_classificados.csv` | lançamento de extrato | id_saida (LAN-), banco, ref_origem, data, descricao, valor, conta_codigo, metodo, confianca | conta_descricao, regra_id, papel, tipo_pendencia |
| `pendencias.csv` | coisa que precisa de pessoa | id_saida (PEN-), tipo, ref_origem, valor_brl, motivo, quem_decide | subtipo, linha_negocio, cnpj, lojista, qtd_itens, regra_id, o_que_fazer, informativa, incluida_em; só em SPREAD_NEGATIVO: spread_relatorio_brl, spread_contratado_brl, diferenca_contrato_brl, metade_tarvo_contrato_brl (o que aconteceu x o que se pede ao parceiro) |
| `rastro.csv` | ligação saída → origem (uma linha por origem) | id_saida, arquivo_origem, ref_origem, valor | regra_id (regra ou célula da planilha usada; num ajuste do parceiro, "P-01 (ajuste ref PC-…)" cita a operação original), taxa_pct (taxa usada naquela linha) |
| `resumo.json` | — | competencia, status_integridade, totais (comissao_total_brl; diferenca_notas_x_comissao_brl com o motivo e os ids sem nota; por_natureza: {natureza: quantidade, valor_brl, ids, arquivo_origem, fora_da_soma}, FATURAR de notas_a_emitir.csv; CONTESTAR_PONTE = o que se pede à Ponte, soma dos pedidos de comunicacoes/ponte_contestacao.csv com o detalhe em pedidos[] (pedido, valor_brl, ids) e as pendências relacionadas em pendencias; as demais de pendencias.csv pela coluna natureza; nunca somadas entre si; divergencias por natureza, pendencias por responsável/tipo, em_jogo), lancamentos, carteira_pendente, orbe_destinos, ponte_destinos, conciliacao, lembretes (os de prazo trazem data_base, data_limite e base_da_data, tirados do e-mail do parceiro; o motor não compara com a data de hoje), avisos (da execução: base inicial, regras sem aprovador, premissas em uso, data da base; os mesmos do topo do relatório), arquivos | só existe quando a integridade passou |
| `RELATORIO_FECHAMENTO.md` | — | página 1 para o CFO (totais, notas, dinheiro em jogo por natureza (nunca somado entre naturezas), pendências por responsável, rascunhos, conhecimento capturado) + anexo com o detalhe | marcado "INVÁLIDO" se a integridade falhou |
| `comunicacoes/orbe.md` + `orbe_contestacao.csv` | rascunho + anexo da contestação à adquirente (só natureza CONTRATO) | ref_origem, cnpj, lojista, linha_negocio, data, produto, taxa_contratada_pct, taxa_aplicada_pct, valor_brl, natureza | motivo, arquivo_origem |
| `comunicacoes/ponte.md` + `ponte_contestacao.csv` | rascunho + anexo da contestação ao parceiro, em pedidos (a, b, c…) | idem | **pedido**, spread_relatorio_brl, spread_contratado_brl, diferenca_contrato_brl, metade_tarvo_contrato_brl (pedido b), motivo, regra_id, arquivo_origem |
| `comunicacoes/comercial.md`, `avisos_nova_condicao.md` | rascunhos para o Comercial e avisos de condição nova às contrapartes (só vigência a partir da competência seguinte, ou no mês sem divergência: regra P-13; com divergência, o canal é a contestação) | — | tudo é RASCUNHO: quem decide revisa e envia |

## Significados

- **ref_origem**: `id_transacao` da Orbe (TX…/AN…), `Nº Operação` da Ponte (PC-…), linha física do Aurora (`L<n>`, contando o cabeçalho), FITID do Meridiano (MRD…). Em pendência agregada por lojista, é o CNPJ. Uma linha por origem; nunca vários valores na mesma célula.
- **taxas `_pct`**: percentual (2.69 = 2,69%). `spread_pct` da Ponte tem até 4 casas (1.5006).
- **metodo**: REGRA (regra CLASSIFICAR_CONTA, confiança 1), IA (sugestão com chave de API, confiança < 1, sempre com pendência REVISAR_IA), HUMANO (sem regra, conta vazia, pendência EXTRATO_NAO_IDENTIFICADO).
- **conta_codigo** é a **contrapartida** do movimento bancário: se o valor já estava registrado (provisão, recebível, obrigação), é a conta onde estava; só é receita/despesa quando não havia registro anterior.
- **valor_brl negativo em pendência**: spread negativo, saldo negativo de lojista, débito de ajuste do parceiro, valor saindo em trânsito. O "valor em jogo" por responsável soma os absolutos, sem as informativas e sem as já incluídas em outra.
- **Destinos** (em `resumo.json`): toda linha da Orbe e toda operação única da Ponte cai em exatamente um: COMISSAO, AJUSTE_PONTE (ajuste do parceiro, entra na comissão), EXCLUIDO (regra), SEM_CADASTRO, SEM_TAXA, FORA_COMPETENCIA, DUPLICATA_IGNORADA, DUPLICATA_DIVERGENTE, NAO_INTERPRETADA. Nada some.
- **nova / recorrente** (relatório, com `--anterior`): pendência cuja chave (tipo, subtipo, CNPJ ou referência) existia na saída do mês anterior é recorrente.

## Códigos de saída da CLI

0 ok · 1 problema nos arquivos de entrada · 2 problema na base de regras · 3 integridade falhou · 4 id_saida inexistente.
