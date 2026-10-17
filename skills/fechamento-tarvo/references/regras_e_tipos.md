# Base de regras (`regras/`) e os 8 tipos

Tudo o que é regra de negócio mora em `regras/`, em CSV com `;` que abre no Excel:

- `regras_negocio.csv`: as regras. Colunas: `id; situacao; como_identificar; tipo; parametros; o_que_fazer; quem_decide; exemplo; vigencia_de; vigencia_ate; status; informado_por; data`.
- `complemento_cadastro.csv`: só lacunas da **planilha de taxas** (que é o cadastro mestre): EC em branco, lojista sem contrato/inativo. Colunas: `cnpj; ec_orbe; status; informado_por; data; observacao`.
- `historico_alteracoes.csv`: quem criou/alterou o quê e por quê, com `aprovado_por` e `registrado_por` (`regra aplicar` escreve aqui).
- `aprovadores.csv`: quem aprova e quem registra cada tipo de regra (TAXA_EXCECAO = Comercial aprova, Helena registra; `*` = Helena). `regra aplicar` recusa aprovador de outro papel.
- `fontes.csv`: padrões de nome dos arquivos de entrada e abas.
- `COMO_CRIAR_REGRA.md`: guia de uma página para quem não é técnico.

`parametros` é `chave=valor` separado por ` | `. Alternativas de texto: ` OU `. Listas: vírgula.
Só `status=ATIVA` é executada. Vigências inclusivas, AAAA-MM-DD; vazio = sem limite.
O motor valida tudo ao carregar e **para** com a linha, o problema e como corrigir.

## Como escolher o tipo (4 perguntas)

1. Número/texto geral que pode mudar? → **PARAMETRO**
2. Lojista com condição diferente da planilha por um período? → **TAXA_EXCECAO**
3. Algo que não pode ser faturado até alguém decidir? → **EXCLUIR_E_PENDENCIA**
4. Lançamento de extrato que vai sempre para a mesma conta? → **CLASSIFICAR_CONTA**
Nenhum dos quatro → **MANUAL** (lembrete em português; o motor não executa).
Apoio: **IGNORAR_DUPLICADO** (linha repetida conta uma vez), **DONO_PENDENCIA** (quem decide cada tipo de pendência do motor, opcionalmente por `subtipo`) e **ALERTA** (o motor calcula um critério e avisa; nada sai da comissão).

## Tipos, campos de `parametros` e exemplos reais de set/2026

| Tipo | parametros | Exemplo real |
|---|---|---|
| PARAMETRO | exatamente um `nome=valor`. Nomes: participacao_spread (fração), spread_padrao (fração), tolerancia_spread_pp, tolerancia_taxa_checkout_pp, incluir_excesso_contestado (true/false), arredondamento (HALF_UP/TRUNCAR), nota_remessa_tomador_cnpj, nota_remessa_tomador_nome, discriminacao_checkout, discriminacao_remessa (com `{competencia}`), remessa_cnpj_sem_cadastro (COMISSAO/EXCLUIR) | P-01 `participacao_spread=0.50`; P-05 `incluir_excesso_contestado=true`; P-11 `remessa_cnpj_sem_cadastro=COMISSAO` |
| TAXA_EXCECAO | `cnpj= \| linha_negocio=CHECKOUT/REMESSA \| produto=TODOS ou lista \| taxa_pct= [\| tipo_pendencia= \| subtipo= \| divergencia=CONTRATO/DEVOLUCAO_LOJISTA]`; exige `vigencia_de`. `divergencia=DEVOLUCAO_LOJISTA` (exige tipo_pendencia) tira as transações de divergencias_taxa.csv: a diferença é devolução ao lojista, não cobrança da adquirente, e vive só na pendência | X-01 Casa do Estudante: `cnpj=00520815000100 \| linha_negocio=CHECKOUT \| produto=TODOS \| taxa_pct=0 \| tipo_pendencia=TARIFA_ZERO_COBRADA \| divergencia=DEVOLUCAO_LOJISTA`, 2026-09-01 a 2026-12-31 |
| IGNORAR_DUPLICADO | `fonte=ponte \| chave=num_operacao` (ou `fonte=orbe \| chave=id_transacao`) | D-01 |
| EXCLUIR_E_PENDENCIA | `fonte=orbe/ponte \| criterio= \| tipo_pendencia= [\| status= \| aceitos= \| valor_pendencia= \| agrupar=cnpj/ec/linha/tudo \| subtipo=]`. Critérios: orbe `status_cadastro`; ponte `status_cadastro`, `spread_negativo`, `status_compliance_fora` | E-01 Atlas: `fonte=orbe \| criterio=status_cadastro \| status=SEM_CONTRATO \| valor_pendencia=valor_taxa \| agrupar=cnpj \| tipo_pendencia=SEM_CONTRATO`; E-03 spreads negativos |
| CLASSIFICAR_CONTA | `banco=AURORA/MERIDIANO/TODOS \| contem=texto [OU texto] \| conta= \| prioridade=1..99 [\| sinal=credito/debito \| gera_pendencia=true \| tipo_pendencia= \| subtipo= \| transitoria=true \| papel=]` | C-03 `banco=AURORA \| contem=PIX ENVIADO CONTABILIDADE \| sinal=debito \| conta=4.2.06 \| prioridade=10` vence C-02 `PIX ENVIADO` (prioridade 90) |
| DONO_PENDENCIA | `tipo_pendencia= [\| subtipo=]` + colunas quem_decide e o_que_fazer; com subtipo vence a geral só para aquele subtipo | DP-01 DIVERGENCIA_TAXA → Helena (Financeiro); DP-12 CADASTRO/CNPJ_PONTE → Comercial |
| ALERTA | `fonte=orbe \| criterio=antecipacao_acima_das_vendas \| tipo_pendencia= [\| so_para=SEM_CONTRATO,INATIVO,ATIVO,PRIMEIRO_MES \| subtipo=]` + quem_decide. Nada sai da comissão; rastro = linhas de antecipação | A-01 `so_para=SEM_CONTRATO,PRIMEIRO_MES \| tipo_pendencia=ALERTA_ANTECIPACAO` → Helena + Comercial |
| MANUAL | opcional: `linha_negocio=`, `cnpj=`, `banco= \| contem=`, `assunto=` (texto usado pelo relatório, ex.: conciliacao_adquirente, recurso_sem_operacao) | M-01 prazo de 5 dias úteis para contestar a Ponte; M-05 recurso de remessa sem operação no mês |

Tipos de pendência válidos: DIVERGENCIA_TAXA, TARIFA_ZERO_COBRADA, SEM_CONTRATO, SPREAD_NEGATIVO, EXCESSO_SPREAD_CONTESTADO, SALDO_NEGATIVO_LOJISTA, CADASTRO, EXTRATO_NAO_IDENTIFICADO, DEVOLUCAO, EM_TRANSITO, REVISAR_IA, MANUAL, FORA_COMPETENCIA, COMPLIANCE, DUPLICATA_DIVERGENTE, RECURSO_SEM_OPERACAO (opcional: só com DONO_PENDENCIA ativa; DP-10 está INATIVA), REPASSE_PONTE_DIVERGENTE, ALERTA_ANTECIPACAO.

## Como propor pela CLI (sem editar o CSV à mão)

```
python -m src regra propor --regras <regras> --saida <saida> --entrada <zip ou pasta> \
  --tipo CLASSIFICAR_CONTA \
  --campos "situacao=Assinatura do Slack" "como_identificar=cartão PJ Slack" \
           "parametros=banco=AURORA | contem=SLACK | sinal=debito | conta=4.2.04 | prioridade=50" \
           "o_que_fazer=Despesa do mês (softwares)" "quem_decide=Financeiro" \
           "informado_por=Helena, Slack 17/10 10h20"
```
O comando mostra a linha exata, valida como o motor validaria (com `--entrada` confere conta
e CNPJ) e descreve o efeito, inclusive quantos lançamentos do último fechamento casariam.
`id`, `status` e `data` são preenchidos automaticamente se faltarem. Nada é gravado.

Para EC novo ou status de lojista: `--tipo COMPLEMENTO --campos cnpj=... ec_orbe=... status=ATIVO informado_por=...`.

Aplicar (só depois do "sim" de quem pode aprovar aquele tipo, conforme `regras/aprovadores.csv`; o `propor` já diz quem é):
```
python -m src regra aplicar --regras <regras> --proposta <saida>/propostas/<id>.json --aprovado-por "Helena (Financeiro)"
python -m src regra aplicar --regras <regras> --proposta <saida>/propostas/X-02.json --aprovado-por "Diego (Comercial)" --registrado-por "Helena (Financeiro)"   # TAXA_EXCECAO
```
O comando recusa (código 2, mensagem em português) aprovador de outro papel. Grava a linha, registra em
`historico_alteracoes.csv` (com `aprovado_por` e `registrado_por`) e, se a base era um zip, devolve um zip novo.

## Armadilhas

- Nunca use `;` dentro de um texto de regra.
- Para corrigir a **taxa** de um lojista, o lugar é a planilha de taxas, não uma regra.
- Duas regras CLASSIFICAR_CONTA de mesma prioridade casando o mesmo lançamento com contas diferentes viram pendência, não erro: ajuste prioridades.
- `transitoria=true` marca a conta de transferência entre contas próprias (detecção de EM_TRANSITO). `papel` alimenta a conciliação (recebimento_adquirente, repasse_lojista, recurso_remessa, liquidacao_remessa).
- Não tente "desligar" uma exclusão apagando a regra: use `status=INATIVA` e registre o motivo no histórico.
