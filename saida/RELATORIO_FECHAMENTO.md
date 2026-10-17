# Fechamento Tarvo — competência 09/2026

**Integridade: OK.** Todos os números abaixo têm rastro até as linhas de origem (`rastro.csv`) e passaram nas checagens listadas no fim.

Arquivos do mês: `01_orbe_relatorio_comissoes_set2026.csv`, `02_tabela_taxas_contratadas.xlsx`, `03_email_ponte_cambio_relatorio_set2026.eml`, `04_plano_de_contas_fenix_erp.csv`, `05a_extrato_banco_aurora_cc4471_set2026.csv`, `05b_extrato_banco_meridiano_cc90233_set2026.ofx` (competência inferida dos dados).

Base de regras: 60 regras ativas, 25 lojistas no cadastro (planilha de taxas + complemento). Última alteração registrada no histórico de regras: 2026-10-17.

## Totais do mês

| Linha | Lojistas | Comissão |
|---|---|---|
| CHECKOUT | 21 | R$ 207.039,73 |
| REMESSA | 14 | R$ 39.543,45 |
| **Total** |  | **R$ 246.583,18** |

Notas a emitir: 21, somando R$ 246.588,68. A diferença de R$ 5,50 para a comissão total é o saldo negativo sem nota (Casa do Estudante Viagens Ltda -R$ 5,50). Divergências de taxa: 92 transações de checkout (R$ 1.576,23) e 23 operações de remessa (R$ 1.418,85). Pendências: 16.

## Notas a emitir

| Nota | Linha | Tomador | CNPJ | Valor |
|---|---|---|---|---|
| NF-0001 | CHECKOUT | Fluente Idiomas Online Ltda | 03229837000103 | R$ 7.316,07 |
| NF-0002 | CHECKOUT | Kiwi Experience | 07752116000126 | R$ 10.711,41 |
| NF-0003 | CHECKOUT | Campus Global Ltda | 08780784000120 | R$ 9.336,06 |
| NF-0004 | CHECKOUT | EduAbroad | 16181276000153 | R$ 12.070,17 |
| NF-0005 | CHECKOUT | Mundo Aberto | 17217888000111 | R$ 18.522,09 |
| NF-0006 | CHECKOUT | Vela | 20987545000140 | R$ 9.315,31 |
| NF-0007 | CHECKOUT | Trilha Jovem Turismo Ltda | 21394880000106 | R$ 5.628,57 |
| NF-0008 | CHECKOUT | Escola Bridge de Idiomas Ltda | 22224579000109 | R$ 11.916,02 |
| NF-0009 | CHECKOUT | Oxford Prep Cursos Ltda | 23109187000161 | R$ 16.077,90 |
| NF-0010 | CHECKOUT | Maple Study Assessoria Educacional Ltda | 34671260000100 | R$ 15.010,78 |
| NF-0011 | CHECKOUT | Bagagem Livre Turismo Ltda | 50900987000179 | R$ 7.703,98 |
| NF-0012 | CHECKOUT | Canguru | 53857560000123 | R$ 11.679,43 |
| NF-0013 | CHECKOUT | Lisboa Cursos e Viagens Ltda | 61720397000180 | R$ 8.470,78 |
| NF-0014 | CHECKOUT | Novo Horizonte Intercambio | 66564512000199 | R$ 7.767,78 |
| NF-0015 | CHECKOUT | Bem-Vindo Exchange Ltda | 67869675000142 | R$ 9.259,74 |
| NF-0016 | CHECKOUT | Dublin Hub Intercâmbio Ltda | 68567965000102 | R$ 11.906,08 |
| NF-0017 | CHECKOUT | Horizonte Viagens | 78576234000179 | R$ 9.014,42 |
| NF-0018 | CHECKOUT | Andes Expedições Ltda | 85694108000184 | R$ 3.819,35 |
| NF-0019 | CHECKOUT | Sol Nascente Viagens Ltda | 89779285000114 | R$ 5.898,02 |
| NF-0020 | CHECKOUT | Rota Global Intercâmbio Ltda | 95927868000148 | R$ 15.621,27 |
| NF-0021 | REMESSA | Ponte Câmbio S.A. | 75374179000146 | R$ 39.543,45 |

Sem nota: Casa do Estudante Viagens Ltda (00520815000100) fechou em -R$ 5,50 (negativo, vira pendência).

## Divergências de taxa (contratada × aplicada)

| Linha | Lojista | Transações | Contratada × aplicada | Diferença |
|---|---|---|---|---|
| CHECKOUT | Rota Global Intercâmbio Ltda | 87 | 2.49%–3.59% × 2.99%–4.09% | R$ 1.546,28 |
| REMESSA | Mundo Aberto | 23 | 1.2% × 1.5% | R$ 1.418,85 |
| CHECKOUT | Escola Bridge de Idiomas Ltda | 5 | 2.19% × 2.59% | R$ 29,95 |

Cada transação está em `divergencias_taxa.csv`. Nada foi ajustado automaticamente: cada caso é uma pendência para decisão.

**Fora das divergências de contrato** (devolucao lojista, regra X-01): 118 transações de Casa do Estudante Viagens Ltda com condição especial contratada (0%) em que a adquirente aplicou 0.89%–3.79%, R$ 15.397,42 pela taxa. Não é cobrança da adquirente: ver pendência TARIFA_ZERO_COBRADA. As transações não estão em `divergencias_taxa.csv`; o rastro está na pendência.

## Pendências por responsável

"Em jogo" é a soma dos valores absolutos das pendências do responsável; tipos podem se sobrepor (o excesso de spread e a metade da Tarvo sobre ele, por exemplo).

### Helena (Financeiro) + Comercial — 2 pendência(s), R$ 251.340,52 em jogo

- **PEN-0001 · TARIFA_ZERO_COBRADA** (00520815000100, R$ 15.397,42): A adquirente cobrou efetivamente R$ 15.396,77 em 118 transações de checkout com condição especial (0% contratada x 0.89% a 3.79% aplicada pela adquirente): R$ 15.397,42 pela taxa, R$ 0,65 a menos que a divergência calculada porque a adquirente trunca centavos, o que não é divergência. Fica fora das divergências de contrato com a adquirente, por regra (X-01): devolução ao lojista. Taxa contratada = 0 no checkout (MDR e antecipação). Devolução ao lojista: não há o que cobrar da Orbe, porque a isenção não chegou à Orbe nem à planilha (a Orbe cobrou certo pelo que sabia). É diferente de uma divergência de contrato: fica separado, com o valor, e a devolução é decidida com o Comercial. A remessa da Casa segue normal
- **PEN-0012 · ALERTA_ANTECIPACAO** (39566044000119, R$ 235.943,10): ATLAS IDIOMAS (lojista SEM_CONTRATO no cadastro) antecipou R$ 235.943,10 em 5 antecipações no mês tendo vendido R$ 135.428,90. Já em 2026-09-15 a antecipação acumulada (R$ 179.592,82) superava as vendas acumuladas até a data (R$ 55.357,50). Antecipação acima do que o lojista vendeu. Não deveria acontecer: a antecipação é sobre o que o lojista já vendeu. Conferir com a adquirente a agenda de recebíveis do lojista e, se for lojista sem contrato, tratar junto com o Comercial. Nada sai da comissão por este alerta

### Helena (Financeiro) — 10 pendência(s), R$ 6.050,74 em jogo

- **PEN-0002 · DIVERGENCIA_TAXA** (22224579000109, R$ 29,95): Divergência calculada pela taxa (2.19% contratada x 2.59% aplicada pela adquirente) em 5 transações de checkout: R$ 29,95. A adquirente cobrou efetivamente R$ 193,93 (pela taxa contratada seria R$ 163,99), R$ 0,01 a menos que a divergência calculada porque a adquirente trunca centavos, o que não é divergência. Não ajustar nada automaticamente. Decidir caso a caso se devolve ao lojista e cobra a Orbe (checkout) ou contesta a Ponte (remessa). No checkout, venda e estorno se anulam: cobra-se da Orbe só a diferença líquida. Uma pendência por lojista e linha de negócio, com rastro para todas as linhas
- **PEN-0003 · DIVERGENCIA_TAXA** (95927868000148, R$ 1.546,28): Divergência calculada pela taxa (2.49% a 3.59% contratada x 2.99% a 4.09% aplicada pela adquirente) em 87 transações de checkout, valor LÍQUIDO R$ 1.546,28 = R$ 1.644,72 a maior em 83 vendas − R$ 98,44 devolvidos em 4 estornos (venda e estorno se anulam: cobra-se da adquirente só a diferença líquida). A adquirente cobrou efetivamente R$ 11.341,82 (pela taxa contratada seria R$ 9.795,96), R$ 0,42 a menos que a divergência calculada porque a adquirente trunca centavos, o que não é divergência. Não ajustar nada automaticamente. Decidir caso a caso se devolve ao lojista e cobra a Orbe (checkout) ou contesta a Ponte (remessa). No checkout, venda e estorno se anulam: cobra-se da Orbe só a diferença líquida. Uma pendência por lojista e linha de negócio, com rastro para todas as linhas
- **PEN-0004 · DIVERGENCIA_TAXA** (17217888000111, R$ 1.418,85): 23 operações de remessa com spread aplicado pelo parceiro (1.5%) acima do contratado (1.2%). Excesso cobrado do lojista R$ 1.418,85 (valor cheio). A metade da Tarvo, R$ 709,46, entrou na nota do mês. Não ajustar nada automaticamente. Decidir caso a caso se devolve ao lojista e cobra a Orbe (checkout) ou contesta a Ponte (remessa). No checkout, venda e estorno se anulam: cobra-se da Orbe só a diferença líquida. Uma pendência por lojista e linha de negócio, com rastro para todas as linhas
- **PEN-0005 · EXCESSO_SPREAD_CONTESTADO** (17217888000111, R$ 709,46): Metade da Tarvo sobre o excesso de spread cobrado de Mundo Aberto em 23 operações: R$ 709,46 (excesso cheio R$ 1.418,85). Entrou na nota do mês pela regra P-05 (Excesso de spread em contestação entra na nota). Acompanhar a contestação com a Ponte. Se a Ponte devolver, o ajuste sai no mês do ajuste
- **PEN-0006 · REPASSE_PONTE_DIVERGENTE** (linha 241 do relatório (SPREAD TOTAL R$:), R$ 506,65): Diferença entre a nota NF-0021 (R$ 39.543,45) e 50% do spread total declarado pelo parceiro (R$ 78.073,59 -> R$ 39.036,80): R$ 506,65 = - R$ 410,94 de 1 repetição(ões) idêntica(s) contada(s) uma vez + R$ 917,03 de 4 operações excluídas por regra (ex.: spread negativo) + R$ 0,56 de arredondamento por operação (dentro do limite de R$ 1,15). Contestar a diferença com a Ponte dentro do prazo de 5 dias úteis do e-mail mensal (regra M-01), anexando a lista das operações negativas e da repetição. Sem contestação, a Ponte credita só 50% do total declarado
- **PEN-0007 · SPREAD_NEGATIVO** (PC-0926-0326, -R$ 509,22): Spread negativo na remessa: operação PC-0926-0326 de Canguru, valor R$ 32.295,52, spread -R$ 509,22 (Taxa travada no pedido (D-1)). Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte. Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada
- **PEN-0008 · SPREAD_NEGATIVO** (PC-0926-0545, -R$ 345,03): Spread negativo na remessa: operação PC-0926-0545 de Novo Horizonte Intercambio, valor R$ 20.574,76, spread -R$ 345,03 (Taxa travada no pedido (D-1)). Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte. Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada
- **PEN-0009 · SPREAD_NEGATIVO** (PC-0926-0491, -R$ 292,28): Spread negativo na remessa: operação PC-0926-0491 de Dublin Hub Intercâmbio Ltda, valor R$ 18.549,46, spread -R$ 292,28 (Taxa travada no pedido (D-1)). Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte. Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada
- **PEN-0010 · SPREAD_NEGATIVO** (PC-0926-0210, -R$ 687,52): Spread negativo na remessa: operação PC-0926-0210 de Ponte Aérea Estudantil Ltda, valor R$ 43.602,79, spread -R$ 687,52 (Taxa travada no pedido (D-1)). Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte. Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada
- **PEN-0013 · SALDO_NEGATIVO_LOJISTA** (00520815000100, -R$ 5,50): A comissão de checkout de Casa do Estudante Viagens Ltda em 119 transações fechou em -R$ 5,50 (estornos ou reversões maiores que as vendas do mês). Não há nota a emitir. Não emite nota e não carrega automaticamente para o mês seguinte. Decidir o que fazer com o saldo

### Comercial — 1 pendência(s), R$ 7.876,05 em jogo

- **PEN-0011 · SEM_CONTRATO** (39566044000119, R$ 7.876,05): Lojista sem contrato vigente: 57 transações de ATLAS IDIOMAS, valor bruto R$ 262.138,61, a adquirente cobrou R$ 7.876,05 a taxas de 0.99% a 4.49%. Fica fora de comissão, nota e divergência até o Comercial confirmar a taxa. O valor da pendência é o que a Orbe cobrou a taxas sem contrato: NÃO é receita da Tarvo, a receita depende da taxa que o Comercial definir

### Financeiro — 3 pendência(s), R$ 319.750,00 em jogo

- **PEN-0014 · EXTRATO_NAO_IDENTIFICADO / CREDITO_SEM_ORIGEM** (L50, R$ 7.350,00): AURORA 2026-09-16: "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO" R$ 7.350,00, classificado em 1.1.09.002 (Créditos não identificados). Fica em créditos não identificados até descobrir quem pagou e por quê
- **PEN-0015 · DEVOLUCAO** (L65, R$ 12.400,00): AURORA 2026-09-23: "DEVOLUCAO PIX - MUNDO ABERTO INTERC" R$ 12.400,00, classificado em 2.1.01.001 (Repasses a lojistas a pagar). O repasse volta a ser obrigação com o lojista (motivo desconhecido). Descobrir o motivo e repassar de novo
- **PEN-0016 · EM_TRANSITO** (L92, -R$ 300.000,00): AURORA 2026-09-30: "TRANSF ENTRE CONTAS P/ BCO MERIDIANO AG 0091 CC 90233-5" -R$ 300.000,00, em 1.1.09.001 (Transferências entre contas próprias): saiu do AURORA em 2026-09-30 e não há crédito de R$ 300.000,00 em outro banco até o fim do extrato. Informativo: fica em 1.1.09.001 até o crédito aparecer no extrato do mês seguinte. Conferir no próximo fechamento

## Lembretes do fechamento (regras em português, não executadas pelo sistema)

- **M-01 · Prazo de contestação com a Ponte Câmbio** (Helena (Financeiro)): Em caso de divergência, responder o e-mail mensal da Ponte em até 5 dias úteis do recebimento. Vale para os spreads negativos e para o excesso de spread contestado. Depois do prazo a Ponte considera o relatório aceito
- **M-02 · Nota de intermediação antes da data de repasse da Ponte** (Financeiro): Emitir a nota de intermediação para a Ponte Câmbio antes da data de repasse informada no e-mail mensal. Sem a nota, o repasse da participação não é creditado
- **M-03 · Estorno da metade da Tarvo se a Ponte devolver excesso contestado** (Helena (Financeiro)): Se a Ponte devolver ao lojista o excesso de spread contestado, a metade da Tarvo sobre esse excesso é estornada no mês em que o ajuste ocorrer (não se reabre o mês faturado)
- **M-05 · Recurso de lojista para remessa sem operação no mês** (Financeiro): É dinheiro do lojista para uma remessa que ainda não foi contratada: fica em 2.1.02.001 (recursos de lojistas para remessas a liquidar). Conferir no fechamento do mês seguinte que a operação saiu no relatório do parceiro. Não é pendência nem devolução

## Conciliação entre fontes (informativa)

- **Adquirente × banco:** Conciliação adquirente x banco não é possível com os arquivos do mês: A adquirente liquida crédito parcelado em parcelas mensais (D+30 por parcela, salvo antecipação), então o que entra no banco mistura parcelas de vendas de meses anteriores e deixa de fora parcelas futuras das vendas deste mês. Para conciliar, pedir à adquirente a agenda de recebíveis do mês e comparar parcela a parcela (regra M-04, Financeiro). Os totais do mês são só informativos e **não se comparam entre si**: recebido da adquirente R$ 3.557.246,29 (21 créditos); repassado a lojistas R$ 4.217.867,61 (45 lançamentos).
- **Remessa × banco:** liquidado no parceiro R$ 5.611.447,12; operações do relatório (Valor R$ + IOF) R$ 5.611.447,12; diferença R$ 0,00. Recursos recebidos de lojistas R$ 5.629.687,12: R$ 18.240,00 acima do liquidado (Recursos recebidos de lojistas superam o liquidado no parceiro em R$ 18.240,00: Recurso de lojista para remessa sem operação no mês. É dinheiro do lojista para uma remessa que ainda não foi contratada: fica em 2.1.02.001 (recursos de lojistas para remessas a liquidar). Conferir no fechamento do mês seguinte que a operação saiu no relatório do parceiro. Não é pendência nem devolução (regra M-05, Financeiro)).
- **Parceiro de câmbio:** pelo total declarado (R$ 78.073,59) o parceiro repassaria R$ 39.036,80; a nota é R$ 39.543,45. Diferença R$ 506,65 = − R$ 410,94 (1 duplicata ignorada) + R$ 917,03 (4 excluido) + R$ 0,56 (arredondamento por operação) — ver pendência REPASSE_PONTE_DIVERGENTE.

## Checagens de integridade

- ✅ 4. transações em comissão de checkout = transações no rastro COM-CHK: 1886 transações
- ✅ 1. soma do rastro = valor reportado (comissoes_por_lojista.csv): 35 ids conferidos
- ✅ 1. soma do rastro = valor reportado (divergencias_taxa.csv): 115 ids conferidos
- ✅ 1. soma do rastro = valor reportado (notas_a_emitir.csv): 21 ids conferidos
- ✅ 1. soma do rastro = valor reportado (lancamentos_classificados.csv): 184 ids conferidos
- ✅ 1. soma do rastro = valor reportado (pendencias.csv): 16 ids conferidos
- ✅ 1. todo id do rastro existe nas saídas: 371 ids no rastro
- ✅ 2. comissões de checkout com saldo > 0 = notas CHECKOUT: 20 lojistas somam 207045.23; 20 notas somam 207045.23
- ✅ 3. nota REMESSA = soma da comissão de remessa: comissão 39543.45; 1 nota(s) somam 39543.45
- ✅ 4. toda linha da Orbe tem exatamente um destino: 1943 linhas -> COMISSAO 1886, EXCLUIDO 57
- ✅ 4. há linhas da Orbe na competência fechada: ok
- ✅ 4. toda operação única da Ponte tem exatamente um destino: 233 linhas, 232 operações únicas -> COMISSAO 228, EXCLUIDO 4, DUPLICATA_IGNORADA 1
- ✅ 5. todo lançamento do AURORA está classificado: 84 lançamentos
- ✅ 5. todo lançamento do MERIDIANO está classificado: 100 lançamentos
- ✅ 5. lançamento classificado por REGRA tem conta: 0 sem conta
- ✅ 6. saldo do AURORA fecha linha a linha: 612334.81 + -2532423.41 = -1920088.60; extrato diz -1920088.60

Arquivos: `comissoes_por_lojista.csv`, `divergencias_taxa.csv`, `notas_a_emitir.csv`, `lancamentos_classificados.csv`, `pendencias.csv`, `rastro.csv`.
