# Fechamento Tarvo — competência 09/2026

**Integridade: OK.** Todos os números abaixo têm rastro até as linhas de origem (`rastro.csv`) e passaram nas checagens listadas no fim.

Arquivos do mês: `01_orbe_relatorio_comissoes_set2026.csv, 06_orbe_ajustes_tardios_set2026.csv`, `02_tabela_taxas_contratadas.xlsx`, `03_email_ponte_cambio_relatorio_set2026.eml`, `04_plano_de_contas_fenix_erp.csv`, `05a_extrato_banco_aurora_cc4471_set2026.csv`, `05b_extrato_banco_meridiano_cc90233_set2026.ofx` (competência inferida dos dados).

Base de regras: 68 regras ativas, 25 lojistas no cadastro (planilha de taxas + complemento). Última alteração registrada no histórico de regras: 2026-10-17.

## Avisos desta execução

- base de regras: 76 item(ns) ativo(s) sem aprovador em historico_alteracoes.csv (gravados fora de `regra aplicar`): P-01, P-02, P-03, P-04, P-05, P-06, P-07, P-08, P-09, P-10, X-01, D-01, E-01, E-02, E-03, E-04, C-01, C-02, C-03, C-04, C-05, C-06, C-07, C-08, C-09, C-10, C-11, C-12, C-13, C-14, C-15, C-16, C-17, C-18, C-19, C-20, C-21, C-22, C-23, C-24, C-25, C-26, DP-01, DP-02, DP-03, DP-04, DP-05, DP-06, DP-07, DP-08, DP-09, M-01, M-02, M-03, DP-11, M-04, M-05, P-11, DP-12, A-01, M-06, DP-13, DP-14, DP-15, DP-16, DP-17, J-01, J-02, complemento:07752116000126, complemento:78576234000179, complemento:66564512000199, complemento:39566044000119, complemento:22348118000148, aprovadores.csv, comunicacoes.csv, causas_divergencia.csv. Confirme com quem aprova cada tipo (regras/aprovadores.csv) e registre o aprovador; até lá, o fechamento usa a regra como está
- base de regras: última alteração registrada em historico_alteracoes.csv em 2026-10-17

## Página 1 — o que o CFO precisa saber

### Totais do mês

| Linha | Lojistas | Comissão (receita da Tarvo) | Notas a emitir |
|---|---|---|---|
| CHECKOUT | 21 | R$ 203.735,34 | 20 notas, R$ 203.740,84 (Casa do Estudante Viagens Ltda sem nota (-R$ 5,50)) |
| REMESSA | 14 | R$ 39.543,45 | 1 nota, R$ 39.543,45 |
| **Total** |  | **R$ 243.278,79** | **21 notas, R$ 243.284,29** |

Divergências: 115 transações, todas 115 de contrato (checkout R$ 1.576,23 + remessa R$ 1.418,85 = R$ 2.995,08); fora do arquivo, por regra, 118 transações de concessão comercial fora do contrato (R$ 15.396,77 cobrados de fato pela adquirente, devolução ao lojista por conta da Tarvo, só em pendência).

**2.374 linhas de origem conferidas** (1.957 da adquirente + 233 do parceiro de câmbio + 184 dos extratos) → **16 decisões para pessoas** (pendências com dono). O motor não mede tempo de espera nem de decisão.

### Dinheiro em jogo, por natureza

O que fazer com cada dinheiro. Naturezas diferentes nunca são somadas (faturar, cobrar, contestar, devolver e acompanhar são coisas distintas); dentro de uma linha só há pendências do mesmo tipo. Pendência já incluída em outra fica fora; informativa aparece marcada.

| Natureza | O quê | Valor | Quem decide |
|---|---|---|---|
| Faturar | 21 notas a emitir (20 de checkout + 1 de remessa) | R$ 243.284,29 | Financeiro (emite) |
| Cobrar da adquirente | Escola Bridge de Idiomas Ltda: Divergência de contrato: aditivo assinado com 2,19% a partir de 15/09 e a Orbe cobrou 2,59%. Contestar com a Orbe e ressarcir o lojista. O aviso à Orbe saiu atrasado (falha de processo nossa), mas o que decide é o contrato, não o aviso (5 transações, R$ 29,95); Rota Global Intercâmbio Ltda: Erro da Orbe: +0,50 p.p. no crédito desde 12/09 sem nenhuma mudança contratual (87 transações, R$ 1.546,28). Rascunho: comunicacoes/orbe.md | R$ 1.576,23 | Helena (Financeiro) |
| Contestar com o parceiro de câmbio | a: excesso de spread cobrado do lojista, volta ao lojista. Mundo Aberto: Divergência de contrato: spread de 1,20% negociado e registrado desde julho e a Ponte aplicou cerca de 1,50%. Contestar com a Ponte e ressarcir o lojista. A Ponte não foi avisada (falha de processo nossa), mas o que decide é o contrato, não o aviso (23 transações, R$ 1.418,85) | R$ 1.418,85 | Helena (Financeiro) |
|  | b: 4 operações com spread negativo (trava vencida), fora da comissão e da nota. O que aconteceu: -R$ 1.834,05 de spread no relatório; o que se pede ao parceiro: a diferença até o spread contratado, R$ 3.565,98. Os dois valores, nunca somados | -R$ 1.834,05 aconteceu / R$ 3.565,98 pedido | Helena (Financeiro) |
|  | c: corrigir o relatório: PC-0926-0162 aparece mais de uma vez (contada uma vez no fechamento). Rascunho: comunicacoes/ponte.md | R$ 0,00 | Helena (Financeiro) |
| Devolver ao lojista por conta da Tarvo | Casa do Estudante Viagens Ltda: Concessão do Comercial fora do contrato, para segurar o cliente: a Orbe cobrou o que estava contratado e não há o que cobrar dela. A Tarvo abriu mão da receita, então a devolução ao lojista sai do nosso bolso (custo da Tarvo) (118 transações, o que a adquirente cobrou de fato) | R$ 15.396,77 | Helena (Financeiro) + Comercial |
| Não faturar até decidir | ATLAS IDIOMAS: Sem contrato assinado: taxa a confirmar pelo Comercial (vale desde 10/09 quando confirmar); R$ 7.876,05 cobrados pela adquirente em 57 transações, R$ 262.138,61 brutos na carteira pendente | R$ 7.876,05 | Comercial |
|  | Alerta antecipacao: ATLAS IDIOMAS: Em 2026-09-15, R$ 179.592,82 antecipados contra R$ 55.357,50 vendidos até a data | R$ 179.592,82 (informativa) | Helena (Financeiro) + Comercial |
|  | Comissão negativa no mês (sem nota): Casa do Estudante Viagens Ltda: A comissão de checkout de Casa do Estudante Viagens Ltda em 119 transações fechou em -R$ 5,50 (estornos ou reversões maiores que as vendas do mês) | R$ 5,50 | Helena (Financeiro) |
| Só acompanhar | TED do parceiro de câmbio a conferir contra a nota de remessa: Conferir o TED do parceiro de câmbio previsto para 2026-10-06 (data do e-mail do parceiro) contra a nota NF-0021 (R$ 39.543,45) | até R$ 506,65 | Helena (Financeiro) |
|  | Lançamento de extrato sem identificação: AURORA 2026-09-16: "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO" R$ 7.350,00, classificado em 1.1.09.002 (Créditos não identificados) | R$ 7.350,00 | Financeiro |
|  | Repasse devolvido pelo banco: AURORA 2026-09-23: "DEVOLUCAO PIX - MUNDO ABERTO INTERC" R$ 12.400,00, classificado em 2.1.01.001 (Repasses a lojistas a pagar) | R$ 12.400,00 | Financeiro |
|  | Em transito: AURORA 2026-09-30: "TRANSF ENTRE CONTAS P/ BCO MERIDIANO AG 0091 CC 90233-5" -R$ 300.000,00, em 1.1.09.001 (Transferências entre contas próprias): saiu do AUROR… | R$ 300.000,00 (informativa) | Financeiro |

### Pendências por responsável

- **Helena (Financeiro) + Comercial**: 2 pendência(s), R$ 15.396,77 em jogo (1 informativa): TARIFA_ZERO_COBRADA, ALERTA_ANTECIPACAO.
- **Helena (Financeiro)**: 10 pendência(s), R$ 5.341,28 em jogo (1 já incluída em outra): DIVERGENCIA_TAXA, EXCESSO_SPREAD_CONTESTADO, CONFERIR_REPASSE_PONTE, SPREAD_NEGATIVO, SALDO_NEGATIVO_LOJISTA.
- **Comercial**: 1 pendência(s), R$ 7.876,05 em jogo: SEM_CONTRATO.
- **Financeiro**: 3 pendência(s), R$ 19.750,00 em jogo (1 informativa): EXTRATO_NAO_IDENTIFICADO, DEVOLUCAO, EM_TRANSITO.

### Rascunhos prontos para revisão (nada foi enviado)

- `comunicacoes/orbe_contestacao.csv`: anexo da contestação à adquirente.
- `comunicacoes/orbe.md`: contestação à adquirente (divergências de contrato do checkout).
- `comunicacoes/ponte_contestacao.csv`: anexo da contestação ao parceiro.
- `comunicacoes/ponte.md`: contestação ao parceiro de câmbio, um pedido por assunto.
- `comunicacoes/comercial.md`: o que depende do Comercial.
- `comunicacoes/avisos_nova_condicao.md`: avisos de condição comercial nova às contrapartes.

### Conhecimento capturado

- Base de regras: 103 alterações registradas em `historico_alteracoes.csv` desde 2026-09-01 (77 criou, 23 alterou, 1 inativou, 2 removeu), em 78 regras/arquivos. Cada linha traz quem aprovou, quem registrou e a fonte (pessoa, canal, hora). Últimas:
  - 2026-10-17 · J-01 · CRIOU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, resposta à Desbravadores 17/10 11h33 (“A Ponte manda o ajust
  - 2026-10-17 · J-02 · CRIOU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Premissa do time MN AI
  - 2026-10-17 · E-03 · ALTEROU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, resposta ao Theo 17/10 11h37 (“Coloquem os dois na pendência
  - 2026-10-17 · DP-14 · ALTEROU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, resposta à Desbravadores 17/10 11h33 (“A Ponte manda o ajust
  - 2026-10-17 · X-01 · ALTEROU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, resposta ao Theo 17/10 11h37 (“O que decide é o contrato, nã
  - 2026-10-17 · causas_divergencia.csv · ALTEROU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, resposta ao Theo 17/10 11h37 (“O que decide é o contrato, nã
  - 2026-10-17 · comunicacoes.csv · ALTEROU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, resposta ao Theo 17/10 11h37 (“O que decide é o contrato, nã
  - 2026-10-17 · X-01 · ALTEROU · aprovado por —, registrado por Time MN AI (Nader Taha e Murilo Godoy), com Claude Code · fonte: Helena (Financeiro), Slack #duvidas-hackathon-ai, ao Southlands 17/10 11h38 (“A devolução da Casa fica separad
- Pendências: sem `--anterior`, não dá para dizer quais são novas e quais são recorrentes.

---

## Anexo — detalhe do fechamento

## Totais do mês

| Linha | Lojistas | Comissão |
|---|---|---|
| CHECKOUT | 21 | R$ 203.735,34 |
| REMESSA | 14 | R$ 39.543,45 |
| **Total** |  | **R$ 243.278,79** |

Notas a emitir: 21, somando R$ 243.284,29. A diferença de R$ 5,50 para a comissão total é o saldo negativo sem nota (Casa do Estudante Viagens Ltda -R$ 5,50). Divergências: 115 transações, todas 115 de contrato (checkout R$ 1.576,23 + remessa R$ 1.418,85 = R$ 2.995,08); fora do arquivo, por regra, 118 transações de concessão comercial fora do contrato (R$ 15.396,77 cobrados de fato pela adquirente, devolução ao lojista por conta da Tarvo, só em pendência). Pendências: 16.

## Notas a emitir

| Nota | Linha | Tomador | CNPJ | Valor |
|---|---|---|---|---|
| NF-0001 | CHECKOUT | Fluente Idiomas Online Ltda | 03229837000103 | R$ 7.316,07 |
| NF-0002 | CHECKOUT | Kiwi Experience | 07752116000126 | R$ 10.886,22 |
| NF-0003 | CHECKOUT | Campus Global Ltda | 08780784000120 | R$ 9.336,06 |
| NF-0004 | CHECKOUT | EduAbroad | 16181276000153 | R$ 11.858,16 |
| NF-0005 | CHECKOUT | Mundo Aberto | 17217888000111 | R$ 18.508,09 |
| NF-0006 | CHECKOUT | Vela | 20987545000140 | R$ 9.315,31 |
| NF-0007 | CHECKOUT | Trilha Jovem Turismo Ltda | 21394880000106 | R$ 5.628,57 |
| NF-0008 | CHECKOUT | Escola Bridge de Idiomas Ltda | 22224579000109 | R$ 11.769,74 |
| NF-0009 | CHECKOUT | Oxford Prep Cursos Ltda | 23109187000161 | R$ 13.845,71 |
| NF-0010 | CHECKOUT | Maple Study Assessoria Educacional Ltda | 34671260000100 | R$ 14.165,77 |
| NF-0011 | CHECKOUT | Bagagem Livre Turismo Ltda | 50900987000179 | R$ 7.703,98 |
| NF-0012 | CHECKOUT | Canguru | 53857560000123 | R$ 11.679,43 |
| NF-0013 | CHECKOUT | Lisboa Cursos e Viagens Ltda | 61720397000180 | R$ 8.470,78 |
| NF-0014 | CHECKOUT | Novo Horizonte Intercambio | 66564512000199 | R$ 7.767,78 |
| NF-0015 | CHECKOUT | Bem-Vindo Exchange Ltda | 67869675000142 | R$ 9.259,74 |
| NF-0016 | CHECKOUT | Dublin Hub Intercâmbio Ltda | 68567965000102 | R$ 11.876,37 |
| NF-0017 | CHECKOUT | Horizonte Viagens | 78576234000179 | R$ 9.014,42 |
| NF-0018 | CHECKOUT | Andes Expedições Ltda | 85694108000184 | R$ 3.819,35 |
| NF-0019 | CHECKOUT | Sol Nascente Viagens Ltda | 89779285000114 | R$ 5.898,02 |
| NF-0020 | CHECKOUT | Rota Global Intercâmbio Ltda | 95927868000148 | R$ 15.621,27 |
| NF-0021 | REMESSA | Ponte Câmbio S.A. | 75374179000146 | R$ 39.543,45 |

Sem nota: Casa do Estudante Viagens Ltda (00520815000100) fechou em -R$ 5,50 (negativo, vira pendência).

## Divergências de taxa (contratada × aplicada)

115 transações, todas 115 de contrato (checkout R$ 1.576,23 + remessa R$ 1.418,85 = R$ 2.995,08); fora do arquivo, por regra, 118 transações de concessão comercial fora do contrato (R$ 15.396,77 cobrados de fato pela adquirente, devolução ao lojista por conta da Tarvo, só em pendência). A coluna `natureza` de `divergencias_taxa.csv` separa as duas: CONTRATO é cobrança da contraparte (anexos em `comunicacoes/`); outra natureza é marcada pela regra TAXA_EXCECAO e fica fora de qualquer total a cobrar.

| Natureza | Linha | Lojista | Transações | Contratada × aplicada | Diferença |
|---|---|---|---|---|---|
| CONTRATO | CHECKOUT | Rota Global Intercâmbio Ltda | 87 | 2.49%–3.59% × 2.99%–4.09% | R$ 1.546,28 |
| CONTRATO | REMESSA | Mundo Aberto | 23 | 1.2% × 1.5% | R$ 1.418,85 |
| CONTRATO | CHECKOUT | Escola Bridge de Idiomas Ltda | 5 | 2.19% × 2.59% | R$ 29,95 |

Cada transação está em `divergencias_taxa.csv`. Nada foi ajustado automaticamente: cada caso é uma pendência para decisão.

**Fora de `divergencias_taxa.csv`, por regra** (X-01): 118 transações de Casa do Estudante Viagens Ltda com condição especial contratada (0%) em que a adquirente aplicou 0.89%–3.79%: R$ 15.396,77 cobrados de fato (a fórmula bruto × taxa daria R$ 15.397,42; R$ 0,65 de truncamento da adquirente que o lojista não pagou). Observação da regra: concessão comercial fora do contrato (a Orbe cobrou o contratado). Devolução ao lojista por conta da Tarvo, não cobrar da Orbe. Não é divergência de contrato: fica fora deste arquivo, de `orbe_contestacao.csv` e de qualquer cobrança da adquirente. O total e o detalhe por transação estão na pendência TARIFA_ZERO_COBRADA (rastro).

## Pendências por responsável

"Em jogo" é a soma dos valores absolutos das pendências do responsável, sem as informativas (marcadas por regra, ex.: em trânsito e alertas) e sem as já incluídas em outra pendência: nenhuma linha de origem conta duas vezes.

### Helena (Financeiro) + Comercial — 2 pendência(s), R$ 15.396,77 em jogo (1 informativa)

- **PEN-0001 · TARIFA_ZERO_COBRADA** (00520815000100, R$ 15.396,77): A adquirente cobrou efetivamente R$ 15.396,77 em 118 transações de checkout com condição especial (0% contratada x 0.89% a 3.79% aplicada pela adquirente). Devolução ao lojista do que foi efetivamente cobrado: a fórmula bruto × taxa daria R$ 15.397,42 (R$ 0,65 de truncamento da adquirente que o lojista não pagou). As transações ficam fora de divergencias_taxa.csv e de qualquer cobrança da adquirente, por regra (X-01), com o detalhe por transação no rastro desta pendência (concessão comercial fora do contrato (a Orbe cobrou o contratado). Devolução ao lojista por conta da Tarvo, não cobrar da Orbe). Taxa contratada = 0 no checkout (MDR e antecipação). Concessão do Comercial fora do contrato, para segurar o cliente: a Orbe cobrou o que estava contratado e não há o que cobrar da Orbe. Quem abriu mão da receita foi a Tarvo, então a devolução ao lojista sai do nosso bolso (custo da Tarvo). Não é divergência de contrato: fica FORA de divergencias_taxa.csv e de orbe_contestacao.csv, só na pendência TARIFA_ZERO_COBRADA, com o total e o detalhe por transação, pelo que a Orbe cobrou de fato (o que foi cobrado, devolve-se), decidida com o Comercial. A remessa da Casa segue normal
- **PEN-0012 · ALERTA_ANTECIPACAO** (informativa) (39566044000119, R$ 179.592,82): Em 2026-09-15, R$ 179.592,82 antecipados contra R$ 55.357,50 vendidos até a data. No mês, R$ 235.943,10 antecipados e R$ 108.712,14 revertidos (líquido R$ 127.230,96) contra R$ 135.428,90 vendidos. ATLAS IDIOMAS: lojista SEM_CONTRATO no cadastro. Alerta de controle, não perda: a antecipação deve ser sobre o que o lojista já vendeu. Conferir com a adquirente a agenda de recebíveis do lojista e, se for lojista sem contrato, tratar junto com o Comercial. Nada sai da comissão por este alerta

### Helena (Financeiro) — 10 pendência(s), R$ 5.341,28 em jogo

- **PEN-0002 · DIVERGENCIA_TAXA** (22224579000109, R$ 29,95): Divergência calculada pela taxa (2.19% contratada x 2.59% aplicada pela adquirente) em 5 transações de checkout: R$ 29,95. A adquirente cobrou efetivamente R$ 193,93 (pela taxa contratada seria R$ 163,99), R$ 0,01 a menos que a divergência calculada porque a adquirente trunca centavos, o que não é divergência. Não ajustar nada automaticamente. Decidir caso a caso se devolve ao lojista e cobra a Orbe (checkout) ou contesta a Ponte (remessa). No checkout, venda e estorno se anulam: cobra-se da Orbe só a diferença líquida. Uma pendência por lojista e linha de negócio, com rastro para todas as linhas
- **PEN-0003 · DIVERGENCIA_TAXA** (95927868000148, R$ 1.546,28): Divergência calculada pela taxa (2.49% a 3.59% contratada x 2.99% a 4.09% aplicada pela adquirente) em 87 transações de checkout, valor LÍQUIDO R$ 1.546,28 = R$ 1.644,72 a maior em 83 vendas − R$ 98,44 devolvidos em 4 estornos (venda e estorno se anulam: cobra-se da adquirente só a diferença líquida). A adquirente cobrou efetivamente R$ 11.341,82 (pela taxa contratada seria R$ 9.795,96), R$ 0,42 a menos que a divergência calculada porque a adquirente trunca centavos, o que não é divergência. Não ajustar nada automaticamente. Decidir caso a caso se devolve ao lojista e cobra a Orbe (checkout) ou contesta a Ponte (remessa). No checkout, venda e estorno se anulam: cobra-se da Orbe só a diferença líquida. Uma pendência por lojista e linha de negócio, com rastro para todas as linhas
- **PEN-0004 · DIVERGENCIA_TAXA** (17217888000111, R$ 1.418,85): 23 operações de remessa com spread aplicado pelo parceiro (1.5%) acima do contratado (1.2%). Excesso cobrado do lojista R$ 1.418,85 (valor cheio). A metade da Tarvo, R$ 709,46, entrou na nota do mês. Não ajustar nada automaticamente. Decidir caso a caso se devolve ao lojista e cobra a Orbe (checkout) ou contesta a Ponte (remessa). No checkout, venda e estorno se anulam: cobra-se da Orbe só a diferença líquida. Uma pendência por lojista e linha de negócio, com rastro para todas as linhas
- **PEN-0005 · EXCESSO_SPREAD_CONTESTADO** (já incluída em DIVERGENCIA_TAXA) (17217888000111, R$ 709,46): Metade da Tarvo sobre o excesso de spread cobrado de Mundo Aberto em 23 operações: R$ 709,46 (excesso cheio R$ 1.418,85). Entrou na nota do mês pela regra P-05 (Excesso de spread em contestação entra na nota). Acompanhar a contestação com a Ponte. Se a Ponte devolver, o ajuste sai no mês do ajuste. É a metade da Tarvo sobre o excesso que já está na divergência do lojista: mostrada, mas fora da soma do em jogo
- **PEN-0006 · CONFERIR_REPASSE_PONTE** (linha 241 do relatório (SPREAD TOTAL R$:), R$ 506,65): Conferir o TED do parceiro de câmbio previsto para 2026-10-06 (data do e-mail do parceiro) contra a nota NF-0021 (R$ 39.543,45). Se o parceiro pagar 50% do total que declarou (R$ 78.073,59 -> R$ 39.036,80), a diferença possível é R$ 506,65 (= - R$ 410,94 de 1 operação repetida, contada uma vez + R$ 917,03 de 4 operações excluídas (Spread negativo na remessa, regra E-03) + R$ 0,56 de arredondamento por operação (dentro do limite de R$ 1,15)). Não é perda: a contestação ainda não foi aberta. Conferir o TED da Ponte quando ele cair (a data de repasse vem do e-mail mensal) e registrar o ajuste no fechamento do mês em que ele aparecer
- **PEN-0007 · SPREAD_NEGATIVO** (PC-0926-0326, -R$ 509,22): Spread negativo na remessa: operação PC-0926-0326 de Canguru, valor R$ 32.295,52, spread -R$ 509,22 (Taxa travada no pedido (D-1)). O que aconteceu: spread -R$ 509,22 no relatório. O que pedimos ao parceiro (a trava deveria ter sido honrada): spread contratado R$ 492,07 (1.5% x PTAX x Valor ME), ou seja, a diferença de R$ 1.001,29 até esse spread contratado, do qual a metade da Tarvo seria R$ 246,04. Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte com os dois valores: o spread negativo do relatório (o que aconteceu) e a diferença até o spread do contrato (o que se pede, porque a trava deveria ter sido honrada). Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada. Prioridade 50: um ajuste do parceiro (J-01/J-02, prioridade 10/20) com spread negativo não cai aqui
- **PEN-0008 · SPREAD_NEGATIVO** (PC-0926-0545, -R$ 345,03): Spread negativo na remessa: operação PC-0926-0545 de Novo Horizonte Intercambio, valor R$ 20.574,76, spread -R$ 345,03 (Taxa travada no pedido (D-1)). O que aconteceu: spread -R$ 345,03 no relatório. O que pedimos ao parceiro (a trava deveria ter sido honrada): spread contratado R$ 292,88 (1.4% x PTAX x Valor ME), ou seja, a diferença de R$ 637,91 até esse spread contratado, do qual a metade da Tarvo seria R$ 146,44. Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte com os dois valores: o spread negativo do relatório (o que aconteceu) e a diferença até o spread do contrato (o que se pede, porque a trava deveria ter sido honrada). Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada. Prioridade 50: um ajuste do parceiro (J-01/J-02, prioridade 10/20) com spread negativo não cai aqui
- **PEN-0009 · SPREAD_NEGATIVO** (PC-0926-0491, -R$ 292,28): Spread negativo na remessa: operação PC-0926-0491 de Dublin Hub Intercâmbio Ltda, valor R$ 18.549,46, spread -R$ 292,28 (Taxa travada no pedido (D-1)). O que aconteceu: spread -R$ 292,28 no relatório. O que pedimos ao parceiro (a trava deveria ter sido honrada): spread contratado R$ 282,63 (1.5% x PTAX x Valor ME), ou seja, a diferença de R$ 574,91 até esse spread contratado, do qual a metade da Tarvo seria R$ 141,32. Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte com os dois valores: o spread negativo do relatório (o que aconteceu) e a diferença até o spread do contrato (o que se pede, porque a trava deveria ter sido honrada). Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada. Prioridade 50: um ajuste do parceiro (J-01/J-02, prioridade 10/20) com spread negativo não cai aqui
- **PEN-0010 · SPREAD_NEGATIVO** (PC-0926-0210, -R$ 687,52): Spread negativo na remessa: operação PC-0926-0210 de Ponte Aérea Estudantil Ltda, valor R$ 43.602,79, spread -R$ 687,52 (Taxa travada no pedido (D-1)). O que aconteceu: spread -R$ 687,52 no relatório. O que pedimos ao parceiro (a trava deveria ter sido honrada): spread contratado R$ 664,35 (1.5% x PTAX x Valor ME), ou seja, a diferença de R$ 1.351,87 até esse spread contratado, do qual a metade da Tarvo seria R$ 332,18. Não aceito (a trava vale 2h e venceu): fica fora da comissão e da nota. Contestar com a Ponte com os dois valores: o spread negativo do relatório (o que aconteceu) e a diferença até o spread do contrato (o que se pede, porque a trava deveria ter sido honrada). Não entra em divergencias_taxa porque não é taxa contratada diferente da aplicada. Prioridade 50: um ajuste do parceiro (J-01/J-02, prioridade 10/20) com spread negativo não cai aqui
- **PEN-0013 · SALDO_NEGATIVO_LOJISTA** (00520815000100, -R$ 5,50): A comissão de checkout de Casa do Estudante Viagens Ltda em 119 transações fechou em -R$ 5,50 (estornos ou reversões maiores que as vendas do mês). Não há nota a emitir. Não emite nota e não carrega automaticamente para o mês seguinte. Decidir o que fazer com o saldo
- Rodapé: EXCESSO_SPREAD_CONTESTADO (R$ 709,46) já incluído em DIVERGENCIA_TAXA de Mundo Aberto: mostrado, mas fora da soma do "em jogo".

### Comercial — 1 pendência(s), R$ 7.876,05 em jogo

- **PEN-0011 · SEM_CONTRATO** (39566044000119, R$ 7.876,05): Lojista sem contrato vigente: 57 transações de ATLAS IDIOMAS, valor bruto R$ 262.138,61, a adquirente cobrou R$ 7.876,05 a taxas de 0.99% a 4.49%. Fica fora de comissão, nota e divergência até o Comercial confirmar a taxa. O valor da pendência é o que a Orbe cobrou a taxas sem contrato: NÃO é receita da Tarvo, a receita depende da taxa que o Comercial definir

### Financeiro — 3 pendência(s), R$ 19.750,00 em jogo (1 informativa)

- **PEN-0014 · EXTRATO_NAO_IDENTIFICADO / CREDITO_SEM_ORIGEM** (L50, R$ 7.350,00): AURORA 2026-09-16: "PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO" R$ 7.350,00, classificado em 1.1.09.002 (Créditos não identificados). Fica em créditos não identificados até descobrir quem pagou e por quê
- **PEN-0015 · DEVOLUCAO** (L65, R$ 12.400,00): AURORA 2026-09-23: "DEVOLUCAO PIX - MUNDO ABERTO INTERC" R$ 12.400,00, classificado em 2.1.01.001 (Repasses a lojistas a pagar). O repasse volta a ser obrigação com o lojista (motivo desconhecido). Descobrir o motivo e repassar de novo
- **PEN-0016 · EM_TRANSITO** (informativa) (L92, -R$ 300.000,00): AURORA 2026-09-30: "TRANSF ENTRE CONTAS P/ BCO MERIDIANO AG 0091 CC 90233-5" -R$ 300.000,00, em 1.1.09.001 (Transferências entre contas próprias): saiu do AURORA em 2026-09-30 e não há crédito de R$ 300.000,00 em outro banco até o fim do extrato. Informativo: fica em 1.1.09.001 até o crédito aparecer no extrato do mês seguinte. Conferir no próximo fechamento

## Carteira pendente (`carteira_pendente.csv`)

- 57 transações de checkout sem contrato, taxa ou cadastro ficam fora da comissão e guardadas para o próximo fechamento (valor bruto R$ 262.138,61; 0 vieram de meses anteriores). Com a taxa confirmada (ex.: TAXA_EXCECAO retroativa), o próximo `fechar --anterior` fatura essas linhas junto com as do mês.

## Lembretes do fechamento (regras em português, não executadas pelo sistema)

- **M-01 · Prazo de contestação com a Ponte Câmbio** (Helena (Financeiro)): Em caso de divergência, responder o e-mail mensal da Ponte em até 5 dias úteis do recebimento. Vale para os spreads negativos e para o excesso de spread contestado. Depois do prazo a Ponte considera o relatório aceito
- **M-02 · Nota de intermediação antes da data de repasse da Ponte** (Financeiro): Emitir a nota de intermediação para a Ponte Câmbio antes da data de repasse informada no e-mail mensal. Sem a nota, o repasse da participação não é creditado
- **M-03 · Estorno da metade da Tarvo se a Ponte devolver excesso contestado** (Helena (Financeiro)): Se a Ponte devolver ao lojista o excesso de spread contestado, a metade da Tarvo sobre esse excesso é estornada no mês em que o ajuste ocorrer (não se reabre o mês faturado)
- **M-05 · Recurso de lojista para remessa sem operação no mês** (Financeiro): É dinheiro do lojista para uma remessa que ainda não foi contratada: fica em 2.1.02.001 (recursos de lojistas para remessas a liquidar). Conferir no fechamento do mês seguinte que a operação saiu no relatório do parceiro. Não é pendência nem devolução
- **M-06 · Aviso à Orbe ou à Ponte antes de toda condição comercial nova** (Comercial): Toda condição comercial nova (TAXA_EXCECAO ou vigência) exige aviso à Orbe (checkout) ou à Ponte (remessa) antes da data de início, com lojista, CNPJ/EC, produto, taxa e vigência. O fechamento seguinte confere se a taxa foi aplicada a partir da data. Rascunhos prontos em saida/comunicacoes/avisos_nova_condicao.md

## Conciliação entre fontes (informativa)

- **Adquirente × banco:** Conciliação adquirente x banco não é possível com os arquivos do mês: A adquirente liquida crédito parcelado em parcelas mensais (D+30 por parcela, salvo antecipação), então o que entra no banco mistura parcelas de vendas de meses anteriores e deixa de fora parcelas futuras das vendas deste mês. Para conciliar, pedir à adquirente a agenda de recebíveis do mês e comparar parcela a parcela (regra M-04, Financeiro). Os totais do mês são só informativos e **não se comparam entre si**: recebido da adquirente R$ 3.557.246,29 (21 créditos); repassado a lojistas R$ 4.217.867,61 (45 lançamentos).
- **Remessa × banco:** liquidado no parceiro R$ 5.611.447,12; operações do relatório (Valor R$ + IOF) R$ 5.611.447,12; diferença R$ 0,00. Recursos recebidos de lojistas R$ 5.629.687,12: R$ 18.240,00 acima do liquidado (Recursos recebidos de lojistas superam o liquidado no parceiro em R$ 18.240,00: Recurso de lojista para remessa sem operação no mês. É dinheiro do lojista para uma remessa que ainda não foi contratada: fica em 2.1.02.001 (recursos de lojistas para remessas a liquidar). Conferir no fechamento do mês seguinte que a operação saiu no relatório do parceiro. Não é pendência nem devolução (regra M-05, Financeiro)).
- **Parceiro de câmbio:** pelo total declarado (R$ 78.073,59) o parceiro repassaria R$ 39.036,80; a nota é R$ 39.543,45. Diferença R$ 506,65 = − R$ 410,94 (1 duplicata ignorada) + R$ 917,03 (4 excluido) + R$ 0,56 (arredondamento por operação) — ver pendência CONFERIR_REPASSE_PONTE.

## Checagens de integridade

- ✅ 4. transações em comissão de checkout = transações no rastro COM-CHK: 1900 transações
- ✅ 1. soma do rastro = valor reportado (comissoes_por_lojista.csv): 35 ids conferidos
- ✅ 1. soma do rastro = valor reportado (divergencias_taxa.csv): 115 ids conferidos
- ✅ 1. soma do rastro = valor reportado (notas_a_emitir.csv): 21 ids conferidos
- ✅ 1. soma do rastro = valor reportado (lancamentos_classificados.csv): 184 ids conferidos
- ✅ 1. soma do rastro = valor reportado (pendencias.csv): 16 ids conferidos
- ✅ 1. todo id do rastro existe nas saídas: 371 ids no rastro
- ✅ 2. comissões de checkout com saldo > 0 = notas CHECKOUT: 20 lojistas somam 203740.84; 20 notas somam 203740.84
- ✅ 3. nota REMESSA = soma da comissão de remessa: comissão 39543.45; 1 nota(s) somam 39543.45
- ✅ 4. toda linha da Orbe tem exatamente um destino: 1957 linhas -> COMISSAO 1900, EXCLUIDO 57
- ✅ 4. há linhas da Orbe na competência fechada: ok
- ✅ 4. toda operação única da Ponte tem exatamente um destino: 233 linhas, 232 operações únicas -> COMISSAO 228, EXCLUIDO 4, DUPLICATA_IGNORADA 1
- ✅ 5. todo lançamento do AURORA está classificado: 84 lançamentos
- ✅ 5. todo lançamento do MERIDIANO está classificado: 100 lançamentos
- ✅ 5. lançamento classificado por REGRA tem conta: 0 sem conta
- ✅ 6. saldo do AURORA fecha linha a linha: 612334.81 + -2532423.41 = -1920088.60; extrato diz -1920088.60

Arquivos: `comissoes_por_lojista.csv`, `divergencias_taxa.csv`, `notas_a_emitir.csv`, `lancamentos_classificados.csv`, `pendencias.csv`, `rastro.csv`, `carteira_pendente.csv`, `comunicacoes`, `comunicacoes/orbe_contestacao.csv`, `comunicacoes/orbe.md`, `comunicacoes/ponte_contestacao.csv`, `comunicacoes/ponte.md`, `comunicacoes/comercial.md`, `comunicacoes/avisos_nova_condicao.md`.
