# Hipóteses, perguntas e respostas — Fechamento Tarvo, set/2026 (time MN AI)

Marcação: **[CONFIRMADA — fonte/horário]** o financeiro disse; **[PREMISSA — motivo]** assumimos
e escrevemos; **[ABERTA]** sem resposta. Horários de 16/10/2026, canal #tarvo-financeiro,
salvo indicação. Cada premissa está também na regra correspondente em `regras/regras_negocio.csv`
(coluna `informado_por`), que é o que o motor executa.

## 1. Premissas e regras

### Cadastro e identificação
- **[CONFIRMADA — Helena, resposta à Fox AI 20h24]** EC 1043300981 = Novo Horizonte Intercâmbio (66564512000199); EC 1043396662 = Horizonte Viagens e Turismo (78576234000179), empresas distintas; EC 1038867654 = Kiwi Experience (07752116000126). Atlas Idiomas (EC 1076801732) sem contrato: não fatura até o Comercial confirmar.
- **[PREMISSA — repositório público e P4 da nossa arquitetura]** A planilha de taxas do mês é o cadastro mestre (lojista, CNPJ, EC, taxas). `complemento_cadastro.csv` só guarda lacunas (ECs acima, Atlas SEM_CONTRATO, Globo Trotter INATIVO). Conflito de EC entre planilha e complemento para o fechamento.
- **[PREMISSA — regra do case: nunca casar por nome]** EC da Orbe ou CNPJ da Ponte fora da planilha e do complemento vira pendência CADASTRO (nomes como aparecem na fonte, nº de linhas, valor bruto); as linhas ficam fora de comissão, nota e divergência. Não ocorreu em set/26.
- **[PREMISSA]** CNPJ da Atlas (39566044000119) vem da aba "ANTIGO 2025 - nao usar" só para identificação; nenhuma taxa vem de lá.
- **[PREMISSA]** Globo Trotter marcado INATIVO no complemento: a planilha só diz "INATIVO desde jul/26" em texto livre, que o sistema não interpreta. Sem movimento em set/26.

### Checkout
- **[CONFIRMADA — Helena à Fox AI 20h05]** Comissão = valor_bruto × taxa **contratada**, linha a linha; é o que vai na nota. O `valor_taxa` da Orbe é só o que ela cobrou. Divergência de taxa gera pendência para a Helena decidir caso a caso.
- **[CONFIRMADA — Helena à MN AI 20h06]** Taxa vigente = a da data da venda. Estorno usa a taxa vigente na data da venda original. Venda de agosto estornada em setembro abate em setembro (agosto não reabre). Modalidade e parcelas do estorno vêm da própria linha do estorno quando a venda não está no arquivo (9 casos em set/26).
- **[CONFIRMADA — Helena à Fox AI 21h13]** A Tarvo **não trunca**: arredondamento ao centavo, meio para cima, simétrico no negativo, linha a linha e depois soma. A Orbe trunca em 2 casas (confere em 1.943/1.943 linhas); o centavo de diferença não é divergência. Divergência só quando taxa aplicada ≠ contratada; `diferenca_brl = bruto × (aplicada − contratada)` arredondado por linha.
- **[CONFIRMADA — Helena ao Lucca Landeiro 21h06]** Casa do Estudante (EC 1018325654): tarifa zero no checkout (MDR e antecipação) de 01/09 a 31/12/2026, acordo comercial; a Orbe não foi avisada e cobrou → tudo é divergência; comissão de checkout 0, sem nota; remessa normal. Rota Global: nenhuma mudança contratual em 2026 → +0,50 p.p. aplicado pela Orbe no crédito desde 12/09 é divergência. Competência do checkout pela data de movimento.
- **[PREMISSA — mesma fórmula]** Estorno com taxa diferente da contratada entra em divergência com sinal negativo (4 estornos da Rota).
- **[PREMISSA]** Antecipação usa a data de movimento como data da taxa (a Orbe não preenche data da venda original nas antecipações); reversão usa a data da antecipação revertida. Sem efeito numérico em set/26.
- **[PREMISSA]** O estorno de 07/09 da Casa (venda em débito de 21/08) é anterior ao acordo e abate a 1,49%: comissão da Casa −R$ 5,50 → sem nota, pendência SALDO_NEGATIVO_LOJISTA.
- Bridge: 5 vendas à vista entre 15 e 18/09 cobradas a 2,59% com 2,19% contratado desde 15/09 → divergência de R$ 29,95 (não citada no Slack; vem da planilha).

### Remessa
- **[CONFIRMADA — Helena à MN AI 20h48]** Comissão = 50% do Spread R$ realizado, por operação, arredondado e depois somado por CNPJ. Nº de operação é único (PC-0926-0162 repetida conta uma vez). Spread negativo não aceito (trava de 2h vencida): fora da comissão e da nota, pendência de contestação. "APROVADO C/ RESSALVA" não muda nada. Spread contratado = coluna "Spread remessa"; em branco ou "padrão" = 1,5% sobre a PTAX.
- **[CONFIRMADA — Helena ao Lucca 21h06]** Competência = data de contratação (6 operações liquidadas em outubro entram em setembro).
- **[CONFIRMADA — Helena à Fox AI 20h58]** Divergência de remessa pelo valor cheio: (spread % aplicado − contratado) × PTAX × Valor ME, por operação. Mundo Aberto contratou 1,20% (jul/26) e a Ponte aplicou ~1,50%.
- **[PREMISSA — a Helena delegou com motivo escrito: "sem alarme de centavo, sem deixar passar diferença real"]** Tolerância de 0,01 p.p.: lojistas sem renegociação oscilam no máximo 0,0016 p.p. Parâmetro P-03.
- **[PREMISSA — decisão B]** A divergência usa a coluna Spread % (6 casas) do relatório, para a conta ser reproduzível a partir das colunas de saída. Pela fórmula exata (Spread R$ − contratado) daria R$ 1.418,88; pela coluna, R$ 1.418,85 (diferença de R$ 0,03 na Mundo Aberto).
- **[PREMISSA — decisão A]** Spread negativo **não** entra em `divergencias_taxa`: não é taxa contratada ≠ aplicada; seria alarme falso. ⚠️ O Lucca Landeiro (21h56) propôs listá-los como divergência; se a Helena validar a abordagem dele, revisar (bastaria uma regra).
- **[CONFIRMADA — Helena ao Theo Garcia ~22h]** A metade da Tarvo sobre o excesso de spread contestado (Mundo Aberto, R$ 709,46) **entra** na nota de setembro pelo realizado; a contestação é processo à parte; se a Ponte devolver, o ajuste sai no mês do ajuste. Parâmetro P-05 (antes disso era premissa do time pela regra literal).
- **[PREMISSA]** Duplicata: fica a primeira linha do arquivo; a "reprocessada" é ignorada. Igualdade conferida em CNPJ, data, moeda, Valor ME, Taxa Cliente, PTAX, Valor R$, Spread R$, Spread % e IOF. Valores diferentes: nenhuma linha entra (pendência DUPLICATA_DIVERGENTE).
- **[PREMISSA — decisão do time 17/10]** Lojista SEM_CONTRATO/INATIVO que faz remessa mantém a comissão (o spread é pago pelo parceiro) e gera pendência CADASTRO informativa. Não ocorre em set/26.
- **[CONFIRMADA — e-mail da Ponte de 02/10/2026]** Prazo de 5 dias úteis para contestar o relatório; repasse de 50% creditado em 06/10 mediante nota fiscal (lembretes M-01 e M-02).

### Notas fiscais
- **[CONFIRMADA — Helena à MN AI 20h47]** CHECKOUT: uma nota por lojista por mês = comissão contratada (vendas − estornos + antecipações − reversões), tomador = lojista; zero ou negativo não emite; negativo vira pendência (não carrega automático). REMESSA: nota única para Ponte Câmbio S.A., CNPJ 75374179000146, pelo total da participação. Discriminação: serviço + competência.
- **[PREMISSA]** Texto da remessa: "Intermediação de câmbio - participação no spread - competência MM/AAAA" (o formato foi confirmado; o texto é nosso). O rastro de cada nota são as mesmas transações da comissão.

### Extratos
- **[CONFIRMADA — Helena à Fox AI 21h14]** `conta_codigo` = contrapartida do movimento; o que já estava registrado baixa a conta onde estava. Provisionados: folha 08/2026 → 2.1.04.001; ISS/INSS/FGTS/IRRF/PIS/COFINS de agosto → 2.1.03.x/2.1.04.x; repasse Ponte de 04/09 (MRD2026090132) → 1.1.03.002. Tudo o mais não provisionado (tarifas, aluguel/condomínio, cloud, assinaturas, serviços) = despesa direta do mês (4.x).
- **[CONFIRMADA — Helena ao Lucca 21h06]** PIX R$ 7.350 de 16/09 sem identificação → 1.1.09.002 + pendência; devolução PIX Mundo Aberto R$ 12.400 de 23/09 → 2.1.01.001 + pendência; transferência de R$ 300 mil de 30/09 que cai no Meridiano em 01/10 → 1.1.09.001, pendência informativa (em trânsito).
- **[PREMISSA — decisão F]** TED PONTE CAMBIO LIQ OPERACOES → 2.1.02.001; aplicação/resgate CDB → 1.1.02.001; rendimento → 3.2.01; IOF → 4.3.01; seguro → 4.2.05; contabilidade (L53) → 4.2.06; tarifas → 4.2.01; TED mesma titularidade → 1.1.09.001; TED Orbe → 1.1.03.001; PIX enviado a lojista → 2.1.01.001; PIX recebido de lojista no Meridiano → 2.1.02.001. "PONTE AÉREA/AEREA" é lojista (≠ "PONTE CAMBIO"); "PIX ENVIADO CONTABILIDADE" não é repasse.
- **[PREMISSA]** Detecção de "em trânsito" por regra (`transitoria=true` na conta de transferências entre contas próprias): débito sem crédito de mesmo valor no outro banco dentro do mês. Só L92 em set/26.
- **[PREMISSA]** Lançamento sem regra: sem chave de IA, `metodo=HUMANO`, conta vazia, pendência; com chave, sugestão da IA com confiança < 1 e pendência REVISAR_IA. Em set/26 todos os 184 lançamentos tiveram regra.

### Conciliação
- **[PREMISSA — orientação do Nader Taha, 17/10]** Adquirente × banco não é conciliável com os arquivos do mês: a adquirente liquida crédito parcelado em parcelas mensais (D+30 por parcela, salvo antecipação). Apresentado como limitação (regra M-04), sem comparar totais.
- **[CONFIRMADA pelos dados]** As 21 TEDs à Ponte somam R$ 5.611.447,12 = exatamente Σ(Valor R$ + IOF) das 232 operações únicas. Os PIX de lojistas na conta de remessas somam R$ 18.240,00 a mais, valor que coincide com o PIX MRD2026090425 (Ponte Aérea, 17/09) → pendência RECURSO_SEM_OPERACAO.
- **[DECISÃO do time, 17/10]** Diferença entre a nota de remessa (R$ 39.543,45) e 50% do total declarado pela Ponte (R$ 39.036,80) = R$ 506,65 = R$ 917,03 (4 spreads negativos tirados da base) − R$ 410,94 (repetição) + R$ 0,56 (arredondamento por operação, dentro do limite de meio centavo por operação) → pendência REPASSE_PONTE_DIVERGENTE com rastro, prazo da M-01. O Lucca estimou ~R$ 506.

### Outras decisões de desenho
- **[PREMISSA]** `id_saida` numerado por CNPJ ordenado (renomear lojista não muda ids); estável enquanto o conjunto de lojistas não muda.
- **[PREMISSA]** Pendência com valor negativo mantém o sinal; o total por responsável é a soma dos absolutos ("em jogo"), e tipos podem se sobrepor (excesso e sua metade).
- **[PREMISSA]** Regras `MANUAL` viram lembretes no relatório, não pendências com valor.
- **[ABERTA]** O financeiro quer devolver aos lojistas o que a Orbe cobrou a mais (Casa, Rota, Bridge) e cobrar a Orbe? É a decisão das pendências TARIFA_ZERO_COBRADA e DIVERGENCIA_TAXA; o motor não ajusta nada.

## 2. Perguntas do time MN AI ao financeiro

| Hora | Pergunta | Resposta |
|---|---|---|
| 20h04 | Estorno em setembro de venda de agosto: qual taxa e qual mês? | 20h06 — taxa vigente na data da venda original; abate em setembro, agosto não reabre. |
| 20h26 | Regras de nota fiscal: uma por lojista? remessa por lojista ou para a Ponte? saldo negativo? discriminação? | 20h47 — checkout: uma por lojista/mês pela comissão contratada, zero ou negativo não emite (negativo vira pendência, não carrega); remessa: nota única para Ponte Câmbio S.A. 75374179000146; discriminação = serviço + competência. |
| 20h30 | Regras de remessa: base da comissão, duplicata, spread negativo, ressalva de compliance, spread padrão, competência? | 20h48 — 50% do Spread R$ realizado por operação; Nº de operação único; spread negativo não aceito (trava vencida), contestar; ressalva não muda nada; em branco/padrão = 1,5% sobre a PTAX; competência = contratação (confirmada também ao Lucca 21h06). |

## 3. Respostas a outros times usadas nesta solução

| Time / pessoa | Hora | O que foi usado |
|---|---|---|
| Fox AI | 20h05 | Comissão pela taxa contratada; divergência decidida caso a caso pela Helena. |
| Fox AI | 20h24 | Mapeamento dos ECs (Novo Horizonte, Horizonte Viagens, Kiwi); Atlas sem contrato não fatura. |
| Fox AI | 20h58 | Divergência de remessa pelo valor cheio: (spread aplicado − contratado) × PTAX × Valor ME. |
| Fox AI | 21h13 | Arredondamento HALF_UP por linha, Tarvo não trunca; divergência só por taxa, não por centavo. |
| Fox AI | 21h14 | Contrapartidas dos extratos: provisionados de agosto, repasse Ponte 08/2026, despesas diretas. |
| Lucca Landeiro | 21h06 | Rota sem mudança contratual; Casa do Estudante tarifa zero set–dez; competência da remessa; PIX sem identificação, devolução e transferência em trânsito. |
| Lucca Landeiro | 21h56 | Validação cruzada: mesmo total de R$ 39.543,45 para a nota da Ponte; estimativa de ~R$ 506 a menos no repasse; proposta de listar spreads negativos como divergência (não adotada, ver decisão A). |
| Theo Garcia | 21h16 → ~22h | Excesso contestado entra na nota pelo realizado; contestação à parte; ajuste no mês do ajuste. |
