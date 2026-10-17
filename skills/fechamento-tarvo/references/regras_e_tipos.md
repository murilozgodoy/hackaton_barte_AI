# Base de regras (`regras/`) e os 9 tipos

Tudo o que é regra de negócio mora em `regras/`, em CSV com `;` que abre no Excel:

- `regras_negocio.csv`: as regras. Colunas: `id; situacao; como_identificar; tipo; parametros; o_que_fazer; quem_decide; exemplo; vigencia_de; vigencia_ate; status; informado_por; data`.
- `complemento_cadastro.csv`: só lacunas da **planilha de taxas** (que é o cadastro mestre): EC em branco, lojista sem contrato/inativo. Colunas: `cnpj; ec_orbe; status; informado_por; data; observacao`.
- `historico_alteracoes.csv`: quem criou/alterou o quê e por quê, com `aprovado_por`, `registrado_por` e `fonte` (`regra aplicar` escreve aqui; o relatório resume em "Conhecimento capturado").
- `aprovadores.csv`: quem aprova e quem registra cada tipo de regra (TAXA_EXCECAO = Comercial aprova, Helena registra; `*` = Helena). `regra aplicar` mostra isso e recusa aprovador de outro papel.
- `causas_divergencia.csv`: a causa de cada divergência por lojista × linha, como o financeiro informou (vai para os rascunhos e para a página 1 do relatório).
- `comunicacoes.csv`: destinatário, assunto e textos dos rascunhos por contraparte (ORBE, PONTE, COMERCIAL, AVISO).
- `fontes.csv`: padrões de nome dos arquivos de entrada e abas.
- `COMO_CRIAR_REGRA.md`: guia de uma página para quem não é técnico.

`parametros` é `chave=valor` separado por ` | `. Alternativas de texto: ` OU `. Listas: vírgula.
Só `status=ATIVA` é executada. Vigências inclusivas, AAAA-MM-DD; vazio = sem limite.
O motor valida tudo ao carregar e **para** com a linha, o problema e como corrigir.
Nenhum `;` dentro de um texto (é o separador do CSV); use vírgula ou ponto.

## Como escolher o tipo (5 perguntas)

1. Número/texto geral que pode mudar? → **PARAMETRO**
2. Lojista com condição diferente da planilha por um período? → **TAXA_EXCECAO**
3. Algo que não pode ser faturado até alguém decidir? → **EXCLUIR_E_PENDENCIA**
4. Linha do relatório do parceiro de câmbio que é ajuste de mês anterior? → **AJUSTE_PARCEIRO**
5. Lançamento de extrato que vai sempre para a mesma conta? → **CLASSIFICAR_CONTA**
Nenhum dos cinco → **MANUAL** (lembrete em português; o motor não executa).
Apoio: **IGNORAR_DUPLICADO** (linha repetida conta uma vez), **DONO_PENDENCIA** (quem decide cada tipo de pendência do motor, opcionalmente por `subtipo`) e **ALERTA** (o motor calcula um critério e avisa; nada sai da comissão).

## Tipos, campos de `parametros` e exemplos reais de set/2026

| Tipo | parametros | Exemplo real |
|---|---|---|
| PARAMETRO | exatamente um `nome=valor`. Nomes: participacao_spread (fração), spread_padrao (fração), tolerancia_spread_pp, tolerancia_taxa_checkout_pp, incluir_excesso_contestado (true/false), arredondamento (HALF_UP/TRUNCAR), nota_remessa_tomador_cnpj, nota_remessa_tomador_nome, discriminacao_checkout, discriminacao_remessa (com `{competencia}`), remessa_cnpj_sem_cadastro (COMISSAO/EXCLUIR) | P-01 `participacao_spread=0.50`; P-05 `incluir_excesso_contestado=true`; P-11 `remessa_cnpj_sem_cadastro=COMISSAO` |
| TAXA_EXCECAO | `cnpj= \| linha_negocio=CHECKOUT/REMESSA \| produto=TODOS ou lista \| taxa_pct= [\| tipo_pendencia= \| subtipo= \| divergencia=CONTRATO/DEVOLUCAO_LOJISTA \| observacao=texto]`; exige `vigencia_de`. A diferença entre a taxa da exceção e a aplicada sai em `divergencias_taxa.csv` com a `natureza` declarada em `divergencia=` (padrão CONTRATO = cobrança da contraparte) e a `observacao` da regra; `DEVOLUCAO_LOJISTA` (exige tipo_pendencia) marca a diferença como devolução ao lojista, fora de qualquer total a cobrar da contraparte. Parcelado fora de toda faixa da planilha fica fora da comissão mesmo com a exceção | X-01 Casa do Estudante: `cnpj=00520815000100 \| linha_negocio=CHECKOUT \| produto=TODOS \| taxa_pct=0 \| tipo_pendencia=TARIFA_ZERO_COBRADA \| divergencia=DEVOLUCAO_LOJISTA \| observacao=concessão comercial fora do contrato…`, 2026-09-01 a 2026-12-31 |
| IGNORAR_DUPLICADO | `fonte=ponte \| chave=num_operacao` (ou `fonte=orbe \| chave=id_transacao`) | D-01 |
| EXCLUIR_E_PENDENCIA | `fonte=orbe/ponte \| criterio= \| tipo_pendencia= [\| status= \| aceitos= \| valor_pendencia= \| agrupar=cnpj/ec/linha/tudo \| subtipo= \| prioridade=1..99]`. Critérios: orbe `status_cadastro`; ponte `status_cadastro`, `spread_negativo`, `status_compliance_fora`. `prioridade` (padrão 50, menor vence) ordena as regras de destino junto com AJUSTE_PARCEIRO | E-01 Atlas: `fonte=orbe \| criterio=status_cadastro \| status=SEM_CONTRATO \| valor_pendencia=valor_taxa \| agrupar=cnpj \| tipo_pendencia=SEM_CONTRATO`; E-03 spreads negativos (`prioridade=50`) |
| AJUSTE_PARCEIRO | `fonte=ponte \| criterio=observacao_ref/observacao_contem \| contem=texto [OU texto] \| tipo_pendencia= [\| prioridade= \| subtipo=]` + quem_decide. `observacao_ref`: a observação traz um dos trechos seguido do Nº da operação original ("AJUSTE REF PC-…"); `observacao_contem`: só o trecho. A linha vira AJUSTE_PONTE: 50% do Spread R$ (HALF_UP, com sinal) entra na comissão do lojista e na nota única do mês; pendência informativa CONFERIR_AJUSTE_PONTE cita a operação original (e, com `--anterior`, o pedido da contestação). Avaliada antes da exclusão por spread negativo e antes do portão de competência | J-01 `fonte=ponte \| criterio=observacao_ref \| contem=AJUSTE REF \| tipo_pendencia=CONFERIR_AJUSTE_PONTE \| prioridade=10`; J-02 (segurança) `criterio=observacao_contem \| contem=AJUSTE OU ESTORNO OU CORRECAO \| prioridade=20` |
| CLASSIFICAR_CONTA | `banco=AURORA/MERIDIANO/TODOS \| contem=texto [OU texto] \| conta= \| prioridade=1..99 [\| sinal=credito/debito \| gera_pendencia=true \| tipo_pendencia= \| subtipo= \| transitoria=true \| papel=]` | C-03 `banco=AURORA \| contem=PIX ENVIADO CONTABILIDADE \| sinal=debito \| conta=4.2.06 \| prioridade=10` vence C-02 `PIX ENVIADO` (prioridade 90) |
| DONO_PENDENCIA | `tipo_pendencia= [\| subtipo= \| informativa=true \| incluida_em=tipo]` + colunas quem_decide e o_que_fazer; com subtipo vence a geral só para aquele subtipo; informativa fica fora do "em jogo"; incluida_em marca valor já dentro de outra pendência | DP-01 DIVERGENCIA_TAXA → Helena; DP-04 CADASTRO → Comercial; DP-13 CADASTRO/PARCELAS_FORA_FAIXA → Helena; DP-14 CONFERIR_AJUSTE_PONTE informativa; DP-02 EXCESSO_SPREAD_CONTESTADO `incluida_em=DIVERGENCIA_TAXA` |
| ALERTA | `fonte=orbe \| criterio=antecipacao_acima_das_vendas \| tipo_pendencia= [\| so_para=SEM_CONTRATO,INATIVO,ATIVO,PRIMEIRO_MES \| subtipo= \| informativa=true]` + quem_decide. Nada sai da comissão; valor = antecipação acumulada (bruta) no dia em que passou das vendas; rastro = essas antecipações | A-01 `so_para=SEM_CONTRATO,PRIMEIRO_MES \| tipo_pendencia=ALERTA_ANTECIPACAO \| informativa=true` → Helena + Comercial |
| MANUAL | opcional: `linha_negocio=`, `cnpj=`, `banco= \| contem=`, `assunto=` (texto usado pelo relatório, ex.: conciliacao_adquirente, recurso_sem_operacao, aviso_nova_condicao) | M-01 prazo de 5 dias úteis para contestar a Ponte; M-05 recurso de remessa sem operação no mês; M-06 aviso de condição nova |

Tipos de pendência válidos: DIVERGENCIA_TAXA, TARIFA_ZERO_COBRADA, SEM_CONTRATO, SPREAD_NEGATIVO, EXCESSO_SPREAD_CONTESTADO, SALDO_NEGATIVO_LOJISTA, CADASTRO (subtipos EC_ORBE, CNPJ_PONTE, TAXA_NAO_CADASTRADA, PARCELAS_FORA_FAIXA, REMESSA_LOJISTA_SEM_CONTRATO), EXTRATO_NAO_IDENTIFICADO, DEVOLUCAO, EM_TRANSITO, REVISAR_IA, MANUAL, FORA_COMPETENCIA, COMPLIANCE, DUPLICATA_DIVERGENTE, RECURSO_SEM_OPERACAO (opcional: só com DONO_PENDENCIA ativa; DP-10 está INATIVA), CONFERIR_REPASSE_PONTE, CONFERIR_AJUSTE_PONTE, LINHA_NAO_INTERPRETADA, ALERTA_ANTECIPACAO.

Destinos de linha (resumo.json, `orbe_destinos`/`ponte_destinos`): COMISSAO, AJUSTE_PONTE (entra na comissão), EXCLUIDO, SEM_CADASTRO, SEM_TAXA, FORA_COMPETENCIA, DUPLICATA_IGNORADA, DUPLICATA_DIVERGENTE, NAO_INTERPRETADA. Nada some.

## Como propor pela CLI (sem editar o CSV à mão)

```
python -m src regra propor --regras <regras> --saida <saida> --entrada <zip ou pasta> [--anterior <saida anterior>] \
  --tipo CLASSIFICAR_CONTA \
  --campos "situacao=Assinatura do Slack" "como_identificar=cartão PJ Slack" \
           "parametros=banco=AURORA | contem=SLACK | sinal=debito | conta=4.2.04 | prioridade=50" \
           "o_que_fazer=Despesa do mês (softwares)" "quem_decide=Financeiro" \
           "informado_por=Helena, Slack 17/10 10h20"
```
O comando mostra a linha exata, valida como o motor validaria (com `--entrada` confere conta
e CNPJ), descreve o efeito esperado e, com `--entrada`, **simula o efeito**: fecha o mês duas
vezes numa pasta temporária (base atual x base + proposta) e lista comissão e nota por lojista
que mudam, pendências que somem ou aparecem, divergências por natureza, lançamentos que trocam
de conta e linhas da carteira anterior que entrariam (com `--anterior`). Ex.: TAXA_EXCECAO da
Atlas desde 10/09 → "ATLAS IDIOMAS passa a gerar R$ 5.242,78 em 57 transações; nova nota
NF-0011; pendência SEM_CONTRATO some; nenhum outro lojista muda". Em português e em `--json`
(`efeito_simulado`). `id`, `status` e `data` são preenchidos automaticamente se faltarem.
**Nada é gravado.**

Para EC novo ou status de lojista: `--tipo COMPLEMENTO --campos cnpj=... ec_orbe=... status=ATIVO informado_por=...`.

Aplicar (só depois do "sim" de quem pode aprovar aquele tipo, conforme `regras/aprovadores.csv`; o `propor` já diz quem é e o `aplicar` repete antes de gravar):
```
python -m src regra aplicar --regras <regras> --proposta <saida>/propostas/<id>.json --aprovado-por "Helena (Financeiro)"
python -m src regra aplicar --regras <regras> --proposta <saida>/propostas/X-02.json --aprovado-por "Diego (Comercial)" --registrado-por "Helena (Financeiro)"   # TAXA_EXCECAO
```
Aprovador de outro papel é recusado com código 2 e a mensagem diz quem pode. Depois, `fechar` de novo.
