# O que construímos para fechar o mês da Tarvo

*Explicação escrita pelo Claude Code, a pedido do time MN AI (Nader Taha e Murilo Godoy), ao fim do desenvolvimento, 17/10/2026.*

## 1. O problema de verdade

A Tarvo é uma subadquirente: fica entre escolas e agências de intercâmbio (os lojistas) e quem processa o dinheiro. Ela ganha em duas frentes. No **checkout**, uma taxa (MDR) sobre cada venda no cartão ou Pix que passa pela adquirente Orbe, mais a taxa de antecipação. Na **remessa**, metade do spread cambial que o parceiro Ponte Câmbio cobra quando o lojista paga uma escola no exterior.

O fechamento do mês levava oito dias úteis e errava. Olhando os arquivos, a causa não é "falta de automação". São três coisas:

1. **Não existe uma chave comum entre as fontes.** O mesmo lojista aparece com 31 nomes diferentes para 22 códigos na Orbe, três lojistas estão na planilha de taxas sem o código da Orbe, a Ponte abrevia nomes em 20 letras. Quem fecha o mês casa tudo de cabeça.
2. **As regras só existem na cabeça de uma pessoa.** Que a Casa do Estudante tem tarifa zero até dezembro, que estorno usa a taxa do dia da venda, que spread negativo não se aceita: nada disso está escrito em lugar nenhum. "Se eu sair de férias, o mês não fecha."
3. **Ninguém compara o contratado com o aplicado.** A Orbe cobrou 0,50 ponto a mais da Rota Global desde 12/09, cobrou da Casa do Estudante o que não devia, e a Ponte aplica 1,50% onde a Mundo Aberto negociou 1,20%. Só se descobre quando o lojista reclama.

## 2. A ideia central

Construímos um **motor determinístico** em Python que lê os seis arquivos exatamente como chegam, aplica regras **escritas em arquivos que o financeiro edita no Excel**, compara contratado com aplicado em cada transação, e transforma tudo o que não consegue decidir sozinho em **pendência com dono e motivo**. Cada número que sai aponta para as linhas que o compõem, e a soma dessas linhas é conferida a cada execução.

A IA não calcula nada. Ela entra depois, como facilitadora: conduz a analista pelo fechamento, explica de onde vem cada número, mostra as pendências e ajuda a transformar uma decisão em regra, sempre pedindo aprovação antes de gravar. Se o motor falhar, a IA não tem número para mostrar.

Dito de outro jeito: a inteligência está nas regras e no rastro, não no modelo de linguagem.

## 3. Como funciona, de ponta a ponta

**Entrada.** A analista coloca o zip do mês na pasta e roda um comando (`python -m src fechar`). O motor extrai o zip e localiza cada fonte por padrão de nome (configurável), então em outubro basta o arquivo novo.

**Leitores.** Um por fonte, cada um lidando com as armadilhas daquele formato: o CSV da Orbe com vírgula decimal; a planilha de taxas com cabeçalho na linha 5, taxas ora como número, ora como texto "1,49%", ora como "padrão", CNPJs sem o zero à esquerda, duas vigências para a Bridge e uma nota de rodapé que não é lojista; o e-mail da Ponte com uma planilha em base64 dentro, totais no fim e uma operação repetida; o plano de contas em cp1252; o extrato do Aurora com sete linhas de cabeçalho e o saldo anterior; o OFX do Meridiano em SGML que diz ser ASCII mas tem acentos. O encoding é detectado com fallback e validado. Nenhum arquivo é editado.

**Cadastro.** A planilha de taxas é o cadastro mestre: lojista, CNPJ, código na Orbe, taxas por produto e vigência. Um arquivo pequeno, `complemento_cadastro.csv`, guarda só o que a planilha não tem: os três códigos que o financeiro confirmou no Slack, a Atlas como "sem contrato", a Globo Trotter como inativa. Se os dois discordarem, o fechamento para e diz onde. Lojista **nunca** é identificado por nome, só por CNPJ ou código cadastrado.

**Regras.** Tudo o que é regra de negócio mora em `regras/regras_negocio.csv`: 57 regras em sete tipos, cada uma com situação em português, parâmetros que o motor executa, quem decide, vigência, status e **de onde veio** (quem disse, em que canal, a que hora). O motor valida o arquivo ao carregar e, se algo estiver errado, para com a linha, o problema e como corrigir, em português. Não há nome de lojista, taxa, conta contábil ou mês dentro do código, e existe um teste que falha se alguém colocar.

**Cálculo.** Cada linha da Orbe e cada operação da Ponte recebe exatamente um destino: entra na comissão, foi excluída por regra, está sem cadastro, sem taxa, fora do mês, ou é repetição. Nada some. Os valores são calculados em decimal exato, arredondados ao centavo meio-para-cima em cada linha e só então somados.

**Saída.** Seis arquivos CSV no formato do regulamento, mais um `resumo.json` para agentes de IA e um relatório de uma página para a analista e o CFO. A cada execução rodam seis checagens de integridade; se qualquer uma falhar, o motor avisa, não grava o resumo e marca o relatório como inválido.

## 4. O que o motor calcula

**Comissão de checkout.** Valor bruto vezes a taxa **contratada** vigente na data da venda, não a que a Orbe cobrou. Estorno usa a taxa do dia da venda original e abate no mês do estorno (um estorno em setembro de venda de agosto entra em setembro; agosto não reabre). Antecipação entra na mesma comissão; reversão anula só a antecipação que reverte. A Orbe trunca o centavo; a Tarvo não, e isso é conferido em todas as 1.943 linhas.

**Comissão de remessa.** Metade do spread realizado, por operação, pela data de contratação. A operação repetida conta uma vez. Os quatro spreads negativos (a Ponte deixou a trava de câmbio vencer) ficam fora da comissão e viram pendência de contestação. O excesso de spread cobrado da Mundo Aberto entra na nota pelo realizado, como o financeiro decidiu, e a metade da Tarvo sobre ele vira pendência.

**Divergências.** Uma linha por transação em que a taxa aplicada difere da contratada: 118 da Casa do Estudante (taxa zero contratada, Orbe cobrou normalmente), 87 da Rota Global (+0,50 ponto desde 12/09, inclusive quatro estornos), 5 da Bridge (três dias em que a Orbe ainda não aplicava a renegociação) e 23 da Mundo Aberto na remessa (1,50% contra 1,20%). Centavo de truncamento não é divergência: a comparação é de taxa, não de valor.

**Notas a emitir.** Uma por lojista de checkout com saldo positivo (vinte), nenhuma para a Casa do Estudante (fechou em −R$ 5,50 por causa do estorno de agosto, que vira pendência) e uma única de remessa para a Ponte Câmbio pelo total da participação.

**Extratos.** Os 184 lançamentos dos dois bancos classificados no plano de contas pela contrapartida: folha e impostos de agosto baixam a provisão, não viram despesa de novo; TED da Orbe baixa o recebível; PIX a lojista baixa o repasse a pagar; o resto é despesa do mês. Regras específicas vencem genéricas por prioridade ("PIX ENVIADO CONTABILIDADE" é contabilidade, não repasse; "PONTE AÉREA" é um lojista, não o parceiro Ponte Câmbio). O PIX sem identificação, a devolução da Mundo Aberto e a transferência de R$ 300 mil que só cai no outro banco em outubro viram pendências.

**Pendências.** Dezesseis em setembro, cada uma com motivo em português, valor em jogo, quem decide e rastro até as linhas: a devolução à Casa do Estudante (R$ 15.397,42, para Helena e Comercial), as divergências por lojista, a Atlas sem contrato (R$ 7.876,05 que a Orbe cobrou e **não** é receita da Tarvo, para o Comercial), os spreads negativos, a diferença de R$ 506,65 entre a nota e o que a Ponte pretende repassar (decomposta em negativos, repetição e arredondamento, com o prazo de 5 dias úteis do e-mail), um PIX de R$ 18.240 de lojista sem operação de remessa, e os casos dos extratos.

**Conciliação entre fontes.** O motor confere que as TEDs à Ponte somam exatamente o valor das operações mais IOF (diferença zero), que os recursos de lojistas excedem a liquidação em exatamente um PIX, e por que a Ponte repassaria R$ 506,65 a menos. Adquirente contra banco **não** é conciliável com os arquivos do mês, porque a Orbe liquida parcelado em parcelas mensais; o relatório diz isso como limitação em vez de inventar uma conclusão.

## 5. Os sete tipos de regra

| Tipo | Serve para | Exemplo real |
|---|---|---|
| PARAMETRO | número ou texto que pode mudar | participação de 50% no spread; spread padrão 1,5%; tolerância de 0,01 ponto; incluir o excesso contestado na nota |
| TAXA_EXCECAO | condição comercial de um lojista com prazo | Casa do Estudante, taxa zero de 01/09 a 31/12/2026 |
| IGNORAR_DUPLICADO | linha repetida conta uma vez | operação da Ponte pelo número |
| EXCLUIR_E_PENDENCIA | não fatura até alguém decidir | lojista sem contrato; spread negativo; compliance não aprovado |
| CLASSIFICAR_CONTA | lançamento de extrato vai sempre para a mesma conta | 26 regras cobrem os 184 lançamentos de setembro |
| DONO_PENDENCIA | quem decide cada tipo de pendência que o motor gera | divergência de taxa é da Helena; cadastro é Financeiro/Comercial |
| MANUAL | regra em português que o sistema **não** executa, só lembra | prazo de contestação da Ponte; nota antes da data de repasse |

Na dúvida, a analista usa MANUAL: o sistema lembra todo mês até alguém automatizar. Há um guia de uma página (`regras/COMO_CRIAR_REGRA.md`) e um histórico de quem mudou o quê e por quê.

## 6. Onde a IA atua e onde não atua

A skill `fechamento-tarvo` segue o padrão aberto Agent Skills e funciona em Claude (web, Claude Code, Cowork), Codex, Cursor e Copilot. Ela instrui o agente a: validar os arquivos, rodar o motor, apresentar os números lendo o `resumo.json`, conduzir as pendências uma a uma mostrando a evidência (`explicar <id>` abre o rastro, a regra e a taxa usadas), e, quando uma decisão vale para os próximos meses, propor a regra (`regra propor` mostra a linha exata e o efeito), pedir aprovação nominal e só então gravar (`regra aplicar --aprovado-por`), registrando no histórico.

Os limites estão escritos no topo da skill: nunca calcular, estimar ou ajustar um valor; nunca editar arquivos de entrada; nunca identificar lojista por nome; nunca decidir pendência; nunca gravar regra sem aprovação; nunca enviar arquivos inteiros para fora. Se a pessoa pedir algo que contradiz uma regra ativa ("usa 2,59% para a Bridge"), a skill explica a regra vigente e oferece o caminho de alteração, em vez de obedecer.

Dados enviados à IA: no fluxo da skill, nenhum; o motor roda localmente e o agente lê os resultados. Existe um caminho opcional, desligado por padrão, em que um lançamento de extrato que nenhuma regra cobre pode receber uma sugestão de conta de um modelo; só vai banco, data, descrição e valor daquela linha, e a sugestão sempre vira pendência de revisão. Em setembro não foi necessário: todos os lançamentos tinham regra.

## 7. Como garantimos que está certo

- **Rastro.** Todo id de saída tem linhas no `rastro.csv` somando exatamente o valor reportado; são 489 ids conferidos a cada execução. Um teste adultera um centavo no rastro e confirma que o motor acusa.
- **Seis checagens de integridade** em todo fechamento, com código de saída próprio quando falham.
- **228 testes automatizados**, inclusive casos sintéticos que rodam sem o data pack: vigência inclusiva nas duas pontas, estorno de mês anterior, meio centavo positivo e negativo, repetição idêntica e divergente, borda da tolerância, código de lojista desconhecido, todas as datas deslocadas um mês, e um teste de que o código não contém mês, lojista, conta ou CNPJ.
- **Três revisões adversariais independentes** (um agente por fase) que recalcularam comissões, divergências, notas e lançamentos a partir dos arquivos brutos, sem usar o nosso código, e bateram centavo a centavo. Cada achado deles está registrado e foi corrigido ou justificado.
- **Conferência à mão** de três lojistas contra a origem antes de qualquer commit: Bridge com as duas vigências, Casa do Estudante com o estorno de agosto, Oxford com o estorno de agosto parcelado.

## 8. Setembro de 2026 em números

| | |
|---|---|
| Comissão de checkout | R$ 207.039,73 em 21 lojistas (1.886 transações; 57 da Atlas fora) |
| Comissão de remessa | R$ 39.543,45 em 14 lojistas (228 operações; 4 negativas e 1 repetição fora) |
| Notas a emitir | 21, somando R$ 246.588,68 |
| Divergências | 233 transações: R$ 16.973,65 no checkout e R$ 1.418,85 na remessa |
| Lançamentos classificados | 184 de 184, todos por regra |
| Pendências | 16, com dono e rastro |
| Dinheiro em jogo nas pendências | devolução à Casa R$ 15.397,42; Rota R$ 1.546,28; Bridge R$ 29,95; Mundo Aberto R$ 1.418,85 (metade da Tarvo R$ 709,46 na nota); Atlas R$ 7.876,05 que não é receita; Ponte repassaria R$ 506,65 a menos; R$ 18.240 de lojista sem operação |

## 9. Limitações e o que ficou em aberto

- Adquirente contra banco não concilia com os arquivos do mês (liquidação parcelada); precisa da agenda de recebíveis da Orbe.
- O OFX do Meridiano não traz saldo inicial, então esse banco não é conferido linha a linha (o Aurora é).
- Três decisões continuam com o financeiro, como pendências: devolver aos lojistas e cobrar a Orbe; tratar spread negativo como divergência ou não (um time propôs que sim; nós não adotamos); e o destino do excesso contestado se a Ponte devolver.
- A sugestão de conta por IA não foi exercitada com dados reais.
- Os ids de saída não mudam quando um lojista é renomeado, mas um lojista novo desloca a numeração dos seguintes.

## 10. Como a analista usa em outubro

Recebe os arquivos, coloca o zip na pasta, roda `validar` e `fechar` (ou pede ao assistente "fecha outubro"). Lê o relatório de uma página: totais, notas, divergências, pendências por responsável. Resolve as pendências com quem decide. O que virou decisão permanente entra em `regras/` pelo assistente ou pelo Excel; o sistema valida. Lojista novo é uma linha na planilha de taxas, como já se faz hoje. Nenhum código é tocado.

## 11. Com mais um mês

Pedir a agenda de recebíveis da Orbe e conciliar parcela a parcela; ler o retorno da Ponte sobre contestações para fechar o ciclo das pendências; gerar os arquivos de importação do Fênix e das notas fiscais direto do motor; rodar os cenários de avaliação da skill com as analistas de verdade; e uma tela simples sobre o `resumo.json`, já que todos os números e textos já existem nele.
