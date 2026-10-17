# Como criar ou mudar uma regra

As regras do fechamento ficam em `regras_negocio.csv`, nesta pasta. Cada linha é uma
regra escrita em português, com um pedaço (`parametros`) que o sistema executa.
Ninguém precisa mexer em código. **Na dúvida, use o tipo MANUAL: o sistema vai te
lembrar todo mês até alguém automatizar.**

## Dois caminhos

1. **Com o assistente de IA (ou `python -m src regra propor`).** Descreva a situação em
   português ("a Casa do Estudante não paga tarifa até dezembro"). Ele propõe a linha, **simula
   o fechamento com a regra** (comissão e nota por lojista que mudam, pendências que somem ou
   aparecem) e **só grava depois que quem pode aprovar aquele tipo disser sim** (`aprovadores.csv`).
   O histórico é registrado sozinho, com quem aprovou e quem registrou.
2. **Sem IA.** Abra `regras_negocio.csv` no Excel, copie uma linha parecida, ajuste,
   salve e rode `python -m src validar`. Ele aponta qualquer erro com o id da linha e
   como corrigir. Depois, anote a mudança em `historico_alteracoes.csv`.

## Qual tipo usar: 5 perguntas

1. **É um número ou texto geral que pode mudar** (percentual, tolerância, quem é o
   tomador da nota)? → `PARAMETRO`
2. **É um lojista com condição diferente da planilha por um período?** → `TAXA_EXCECAO`
3. **É algo que não pode ser faturado até alguém decidir** (spread negativo, lojista
   sem contrato)? → `EXCLUIR_E_PENDENCIA`
4. **É uma linha do relatório da Ponte que é ajuste de um mês anterior** (observação
   "AJUSTE REF PC-…", Spread R$ negativo)? → `AJUSTE_PARCEIRO` (já existe: J-01 e J-02;
   tem `prioridade` menor que a exclusão por spread negativo, por isso o ajuste não cai nela)
5. **É um lançamento de extrato que vai sempre para a mesma conta?** → `CLASSIFICAR_CONTA`

Não é nenhum dos cinco? → `MANUAL`. O sistema não executa nada: só repete, no
relatório de cada fechamento, o seu texto de `o_que_fazer` como lembrete para quem
está em `quem_decide`.

Três tipos de apoio: `IGNORAR_DUPLICADO` (linha repetida num relatório conta uma vez),
`DONO_PENDENCIA` (diz quem decide cada tipo de pendência que o sistema gera sozinho,
como divergência de taxa ou cadastro faltante; com `subtipo=` dá um dono específico, ex.:
CNPJ da Ponte sem cadastro → Comercial) e `ALERTA` (o sistema calcula um critério e avisa
quem está em `quem_decide`, sem tirar nada da comissão; ex.: A-01, antecipação acima do que
o lojista vendeu, só para lojista sem contrato ou novo no mês).

## Quem aprova cada regra

`aprovadores.csv` diz quem aprova por tipo: **taxa e condição comercial** (`TAXA_EXCECAO`,
e a planilha de taxas) = Comercial aprova, Helena registra; **regra de como fechar** (todos
os outros tipos e o complemento de cadastro) = Helena aprova. O comando
`python -m src regra aplicar --aprovado-por "<nome> (Comercial)" --registrado-por "Helena (Financeiro)"`
recusa, com a mensagem em português, aprovador de outro papel, e grava `aprovado_por` e
`registrado_por` no `historico_alteracoes.csv`. Substituto de férias: acrescente na coluna
`quem_aprova` com " OU " (ex.: `Helena OU Marcos`).

## Quatro exemplos reais de setembro/2026

**Lembrete em português (M-01).** A Ponte dá 5 dias úteis para contestar o relatório.
`tipo` = MANUAL · `parametros` = `linha_negocio=REMESSA`
`o_que_fazer` = "Em caso de divergência, responder o e-mail mensal da Ponte em até 5 dias
úteis do recebimento..." · `quem_decide` = Helena (Financeiro)
Nada é calculado: o texto aparece no relatório de todo fechamento, com o nome de quem
decide, até alguém transformar a situação em regra automática.

**Acordo comercial (X-01).** A Casa do Estudante não paga tarifa no checkout de
01/09 a 31/12/2026.
`tipo` = TAXA_EXCECAO · `vigencia_de` = 2026-09-01 · `vigencia_ate` = 2026-12-31
`parametros` = `cnpj=00520815000100 | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=0 | tipo_pendencia=TARIFA_ZERO_COBRADA | divergencia=DEVOLUCAO_LOJISTA | destino=PENDENCIA`
Tudo o que a Orbe cobrar nesse período vira a pendência TARIFA_ZERO_COBRADA para quem está
em `quem_decide`, pelo que a Orbe **cobrou de fato** (soma do valor_taxa dela, não a fórmula
bruto × taxa), com o rastro de cada transação. `divergencia=DEVOLUCAO_LOJISTA` diz que não é
divergência de contrato com a Orbe (ela cobrou o que estava contratado): é devolução ao
lojista por conta da Tarvo. `destino=PENDENCIA` diz que as transações ficam **fora** de
`divergencias_taxa.csv` e de `orbe_contestacao.csv`: só existem na pendência (total + detalhe
por transação). Com `destino=DIVERGENCIA` (padrão) elas entram em `divergencias_taxa.csv`
marcadas com a natureza e a `observacao=` da regra, ainda fora da cobrança da Orbe; sem
`divergencia=` (ou com `divergencia=CONTRATO`), entram como qualquer divergência de contrato.

**Lançamento de extrato (C-03).** O PIX para a Contabilidade Exata não é repasse a lojista.
`tipo` = CLASSIFICAR_CONTA
`parametros` = `banco=AURORA | contem=PIX ENVIADO CONTABILIDADE | sinal=debito | conta=4.2.06 | prioridade=10`
O texto em `contem` é procurado na descrição do extrato, sem diferenciar acento nem
maiúscula. Quando duas regras servem, vence a de **menor prioridade** (10 vence 90):
por isso esta vence a regra geral `PIX ENVIADO` (repasse, prioridade 90). Para aceitar
grafias diferentes, use ` OU `: `contem=PONTE AEREA OU PONTE AÉREA`. A conta precisa
existir no plano do Fênix e aceitar lançamento.

**Não faturar e avisar (E-03).** Remessa com spread negativo não é aceita.
`tipo` = EXCLUIR_E_PENDENCIA
`parametros` = `fonte=ponte | criterio=spread_negativo | valor_pendencia=spread_brl | agrupar=linha | tipo_pendencia=SPREAD_NEGATIVO`
A operação sai da comissão e da nota e vira pendência para quem está em `quem_decide`.

**Alerta (A-01).** Antecipação maior do que o lojista vendeu, só para lojista sem contrato
ou novo no mês (os outros antecipam vendas de meses anteriores, que não estão no arquivo).
`tipo` = ALERTA
`parametros` = `fonte=orbe | criterio=antecipacao_acima_das_vendas | so_para=SEM_CONTRATO,PRIMEIRO_MES | tipo_pendencia=ALERTA_ANTECIPACAO`
Gera a pendência para quem está em `quem_decide`, com as linhas de antecipação no rastro.
Nada sai da comissão. `so_para` vazio = todos os lojistas.

**Lembrete que substitui uma pendência (M-05).** Dinheiro de lojista na conta de remessas
sem operação no mês é normal (a operação sai no mês seguinte): a regra DP-10, que gerava a
pendência RECURSO_SEM_OPERACAO, está INATIVA e o lembrete M-05 aparece na conciliação. Para
voltar a ter a pendência, basta reativar DP-10 (é dado, não código).

## Lojista sem EC ou sem contrato

Lojista, CNPJ, EC e taxas vêm da **planilha de taxas** do mês. Lojista novo = linha
nova na planilha, como já é feito. Só quando a planilha não tem a informação (EC em
branco, lojista sem contrato) use `complemento_cadastro.csv`, uma linha por CNPJ. Se
a planilha e o complemento tiverem ECs diferentes para o mesmo CNPJ, o fechamento para
até alguém corrigir. Se o complemento repetir o que a planilha já diz, o sistema avisa
que a linha pode ser removida.

## Cuidados no Excel

- Não use `;` dentro de nenhum texto: é o separador das colunas.
- Formate a coluna de CNPJ como **Texto**. Se o Excel tirar o zero da frente, o
  sistema completa e avisa.
- Datas no formato AAAA-MM-DD (ex.: 2026-09-01). Se vier dd/mm/aaaa, o sistema aceita e avisa.
- Só regras com `status` = ATIVA são executadas. PROPOSTA e INATIVA ficam guardadas.
- Em `parametros`, separe os pares com ` | ` e use ponto ou vírgula nos números
  (`spread_padrao=0.015` é 1,5%; `participacao_spread=0.50` é 50%).
- Sempre preencha `informado_por` e `data`: é o que prova de onde veio a regra.
