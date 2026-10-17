# Como criar ou mudar uma regra

As regras do fechamento ficam em `regras_negocio.csv`, nesta pasta. Cada linha é uma
regra escrita em português, com um pedaço (`parametros`) que o sistema executa.
Ninguém precisa mexer em código. **Na dúvida, use o tipo MANUAL: o sistema vai te
lembrar todo mês até alguém automatizar.**

## Dois caminhos

1. **Com o assistente de IA.** Descreva a situação em português ("a Casa do Estudante
   não paga tarifa até dezembro"). Ele propõe a linha, mostra o que muda no fechamento
   e **só grava depois que você aprovar**. O histórico é registrado sozinho.
2. **Sem IA.** Abra `regras_negocio.csv` no Excel, copie uma linha parecida, ajuste,
   salve e rode `python -m src validar`. Ele aponta qualquer erro com o id da linha e
   como corrigir. Depois, anote a mudança em `historico_alteracoes.csv`.

## Qual tipo usar: 4 perguntas

1. **É um número ou texto geral que pode mudar** (percentual, tolerância, quem é o
   tomador da nota)? → `PARAMETRO`
2. **É um lojista com condição diferente da planilha por um período?** → `TAXA_EXCECAO`
3. **É algo que não pode ser faturado até alguém decidir** (spread negativo, lojista
   sem contrato)? → `EXCLUIR_E_PENDENCIA`
4. **É um lançamento de extrato que vai sempre para a mesma conta?** → `CLASSIFICAR_CONTA`

Não é nenhum dos quatro? → `MANUAL`. O sistema não executa nada: só repete, no
relatório de cada fechamento, o seu texto de `o_que_fazer` como lembrete para quem
está em `quem_decide`.

Dois tipos de apoio: `IGNORAR_DUPLICADO` (linha repetida num relatório conta uma vez)
e `DONO_PENDENCIA` (diz quem decide cada tipo de pendência que o sistema gera sozinho,
como divergência de taxa ou cadastro faltante).

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
`parametros` = `cnpj=00520815000100 | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=0 | tipo_pendencia=TARIFA_ZERO_COBRADA`
Tudo o que a Orbe cobrar nesse período aparece como divergência, e a pendência vai
para quem está em `quem_decide`.

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
