# Glossário (linguagem do financeiro)

Fontes: Helena (financeiro da Tarvo) no Slack, 16 e 17/10/2026; data pack de set/2026.

## Checkout (adquirente Orbe)
- **Subadquirente**: a Tarvo. Fica entre o lojista e a adquirente (Orbe); recebe dos alunos pelo lojista e repassa, ficando com a taxa.
- **EC (código de estabelecimento)**: identificador do lojista na adquirente. Um lojista tem um EC; o mesmo EC aparece com nomes diferentes no relatório da Orbe, por isso a chave é o EC/CNPJ, nunca o nome.
- **MDR**: a taxa percentual sobre cada venda no cartão/Pix. Varia por produto: débito, crédito à vista, parcelado 2–6x, parcelado 7–12x, Pix. A Tarvo não vende acima de 12x: parcelado fora das faixas da planilha é pendência (Helena, 17/10 11h01).
- **Antecipação**: o lojista recebe antes do prazo e paga uma taxa de antecipação sobre o valor antecipado. **Reversão de antecipação** desfaz uma antecipação e anula só a taxa dela. A antecipação é sobre a **agenda inteira** do lojista (vendas de meses anteriores também), por isso o alerta de antecipação só vale para lojista sem histórico no arquivo (Helena, 17/10 11h37).
- **Estorno**: devolução de uma venda. Entra com sinal negativo no mês em que ocorre, com a taxa vigente na data da venda original e a faixa (modalidade, parcelas) da própria linha do estorno (Helena, 17/10 11h38).
- **Taxa contratada × taxa aplicada**: a contratada está na planilha de taxas, no aditivo ou numa exceção comercial; a aplicada é a que a adquirente cobrou. A comissão da Tarvo é sempre pela contratada; a diferença é **divergência**.
- **Natureza da divergência**: `CONTRATO` quando a contraparte cobrou diferente de uma condição contratada (contesta-se com a Orbe/Ponte e o lojista é ressarcido); `DEVOLUCAO_LOJISTA` quando a condição é uma **concessão comercial fora do contrato** (ex.: isenção da Casa do Estudante): a adquirente cobrou o contratado, não há o que cobrar dela e a devolução ao lojista é custo da Tarvo. "O que decide é o contrato, não o aviso" (Helena, 17/10 11h37).
- **Aviso à contraparte**: comunicação de condição nova à Orbe ou à Ponte antes da vigência. É controle de processo; não decide quem deve.
- **Truncamento da Orbe**: a adquirente corta o valor da taxa na segunda casa decimal; a Tarvo arredonda ao centavo (meio centavo para cima). Diferença de centavo por isso **não** é divergência.
- **Liquidação**: o momento em que a adquirente paga a Tarvo pelo que o lojista vendeu. Débito e Pix caem no dia seguinte (**D+1**); crédito e parcelado caem ao longo dos meses seguintes, parcela a parcela (**D+30** por parcela, salvo antecipação). Por isso o que entra no banco em um mês mistura parcelas de vendas anteriores (Helena ao Insper AI, 16/10 22h34).
- **A Orbe liquida o líquido**: a taxa é descontada quando a Orbe paga; o lojista já recebe menos. A nota fiscal só **documenta** a taxa já descontada e não gera cobrança nova. Consequência: quando a Orbe cobra a mais, o lojista já recebeu a menos e a Tarvo precisa **devolver** (Helena à Turma do Barulho, 17/10 10h44).
- **Aprovado não é pago**: uma transação aprovada na adquirente ainda não virou dinheiro na conta; só a liquidação paga. O fechamento calcula a comissão pela transação (competência), não pelo caixa.
- **Domicílio bancário**: a conta em que a adquirente deposita as liquidações. A Orbe deposita tudo no Aurora (conta da Tarvo); ela não paga lojista direto.
- **Repasse ao lojista**: a Tarvo repassa duas vezes por mês, perto dos dias **10 e 24**, o que a Orbe já liquidou (Helena, 17/10 10h44). O fechamento não para o repasse: o que fica suspenso para lojista sem contrato é só o faturamento da taxa da Tarvo (Helena ao Lucca, 17/10 11h03).
- **Conta garantida**: limite que o banco Aurora dá à Tarvo para pagar lojistas antes de a Orbe liquidar. O saldo negativo do extrato do Aurora é essa conta, não erro (Helena ao Insper AI, 16/10 22h34). Não tem limite escrito: "quando um lojista pressiona, a Bia às vezes paga antes de a Orbe liquidar, e aí entra a conta garantida" (Helena à Turma do Barulho, 17/10 10h59).
- **Competência**: o mês ao qual uma operação pertence. Checkout: data do movimento. Remessa: data de contratação (mesmo que liquide no mês seguinte).

## Remessa (parceiro Ponte Câmbio)
- **Remessa**: pagamento de escola no exterior via parceiro de câmbio (Ponte Câmbio). O lojista deposita reais na conta de remessas (Meridiano); a Tarvo liquida com a Ponte (Valor R$ + IOF).
- **Spread**: diferença entre a taxa de câmbio cobrada do cliente e a PTAX de referência. **Spread R$** = (Taxa Cliente − PTAX) × Valor em moeda estrangeira. **Spread %** = Taxa Cliente / PTAX − 1. A Tarvo recebe uma participação (50%) do spread realizado, paga pela Ponte no **TED de repasse** (data no e-mail mensal), mediante nota fiscal.
- **PTAX**: taxa de câmbio de referência do Banco Central do dia.
- **Spread negativo**: cliente pagou menos que a PTAX (taxa travada em pedido D-1 e trava vencida). Não é aceito: fica fora da comissão e da nota e vira contestação com **dois valores**: o spread negativo do relatório (o que aconteceu) e a diferença até o spread do contrato (o que se pede à Ponte, porque a trava deveria ter sido honrada) (Helena, 17/10 11h37).
- **Excesso de spread**: spread aplicado acima do contratado do lojista. O valor cheio é devolvido ao lojista pela Ponte; a metade da Tarvo entrou na nota pelo realizado e é estornada no mês em que a Ponte ajustar.
- **Ajuste da Ponte**: resposta da Ponte a uma contestação. Vem no relatório do **mês seguinte** como uma linha nova, com Nº de Operação próprio e Spread R$ negativo, e a observação `AJUSTE REF PC-…` cita a operação original. Entra no mês em que aparece, abate a participação da Tarvo dentro da **nota única** para a Ponte (não há nota complementar); se o mês fechar zerado ou negativo, não há nota e vira pendência (Helena à Desbravadores, 17/10 11h33). No motor: destino `AJUSTE_PONTE`, pendência `CONFERIR_AJUSTE_PONTE`.
- **Pedido** (coluna `pedido` de `ponte_contestacao.csv`): cada assunto da contestação com a Ponte, com o seu valor e as suas operações: (a) excesso de spread de um lojista, (b) spreads negativos, (c) operação repetida. Não há "total em disputa" único.
- **IOF**: imposto sobre a operação de câmbio, pago pelo cliente; a Ponte liquida Valor R$ + IOF.
- **Prazo de contestação**: 5 dias úteis do e-mail mensal da Ponte; depois o relatório é considerado aceito.

## Notas, contas e saídas
- **Nota fiscal de intermediação**: checkout, uma por lojista pela comissão do mês (tomador = lojista); remessa, uma única para a Ponte Câmbio pela participação total do mês (ajustes incluídos). Zero ou negativo não emite e vira pendência.
- **Contrapartida**: a conta contábil do "outro lado" do movimento bancário. Dinheiro que já estava registrado (provisão de folha, imposto a recolher, recebível) baixa a conta onde estava; só é receita/despesa quando não havia registro anterior.
- **Provisionado**: despesa já reconhecida no mês anterior (folha de agosto paga em setembro). O pagamento baixa a obrigação, não é despesa de novo. A **provisão do mês corrente** é da contabilidade, fora deste fechamento (Helena à Datarmos, 17/10 11h49).
- **Conta transitória**: onde fica uma transferência entre contas próprias enquanto não aparece no outro banco ("em trânsito").
- **Carteira pendente**: transações de checkout sem contrato, taxa ou cadastro, guardadas em `carteira_pendente.csv` para o próximo `fechar --anterior` faturar quando houver taxa (ex.: Atlas, retroativa a 10/09).
- **Rastro**: a lista das linhas de origem que compõem cada número de saída; a soma delas é igual ao número. Uma linha por origem (`ref_origem`).
- **Pendência**: tudo que o sistema não decide sozinho: com motivo, valor em jogo, quem decide e próximo passo. **Informativa**: aparece com valor e rastro, mas fica fora do "em jogo" (em trânsito, alerta de antecipação, ajuste da Ponte). Pendência de acompanhamento com motivo e próximo passo não é alarme falso (Organização, 17/10 11h27).
