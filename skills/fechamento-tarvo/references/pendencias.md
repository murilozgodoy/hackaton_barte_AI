# Pendências: o que mostrar, o que perguntar, quem decide

Sempre comece com `explicar <PEN-...>` e mostre as linhas de origem. Nunca sugira o valor
da decisão; pergunte e registre. "Vira regra?" diz se a decisão costuma valer para os
próximos meses (então passe por `regra propor`).

| Tipo | O que mostrar | O que perguntar | Quem decide | Vira regra? |
|---|---|---|---|---|
| **TARIFA_ZERO_COBRADA** | As transações do lojista com taxa 0 contratada (acordo comercial) em que a adquirente cobrou; valor cobrado × 0; o truncamento | "Devolvemos ao lojista o que a adquirente cobrou? Cobramos a adquirente? Alguém avisou a adquirente do acordo?" | Helena + Comercial | A exceção já é regra (TAXA_EXCECAO). A devolução é decisão do mês |
| **DIVERGENCIA_TAXA** | Transações do lojista com contratada ≠ aplicada, agrupadas por lojista × linha; a soma em R$; a taxa que a planilha diz | "A planilha está certa? Houve renegociação não registrada? Devolve ao lojista / contesta a adquirente?" | Helena | Se a planilha estiver desatualizada: a correção é na **planilha de taxas**, não em regra. Se for condição especial com prazo: TAXA_EXCECAO |
| **EXCESSO_SPREAD_CONTESTADO** | Operações de remessa com spread acima do contratado; excesso cheio e a metade da Tarvo que entrou (ou não) na nota | "Contestar com a Ponte dentro do prazo? Se devolverem, estornamos no mês do ajuste (regra M-03)" | Helena | O comportamento já é parâmetro (incluir_excesso_contestado) |
| **REPASSE_PONTE_DIVERGENTE** | Nota de remessa × 50% do total declarado pela Ponte, decomposto em negativos, repetições e arredondamento | "Contestar dentro dos 5 dias úteis do e-mail (M-01) anexando as operações negativas e a repetição?" | Helena | Não; é da operação do mês |
| **SPREAD_NEGATIVO** | A operação, a observação da Ponte ("Taxa travada no pedido (D-1)"), o spread negativo | "Contestamos com a Ponte? Aceitamos?" | Helena | Já é regra (E-03). Se a Helena passar a aceitar, inativa-se E-03 |
| **SEM_CONTRATO** | Transações do lojista sem contrato; quanto a adquirente cobrou e a que taxas; que isso **não** é receita da Tarvo | "Qual é a taxa contratada? Desde quando?" → a resposta entra na **planilha de taxas** (linha nova) e o status sai do complemento | Comercial | Sim: linha na planilha + remover/alterar o status no complemento (`regra propor --tipo COMPLEMENTO`) |
| **SALDO_NEGATIVO_LOJISTA** | A comissão negativa do lojista no mês e as linhas (estornos > vendas) | "Compensa no próximo mês? Cobra? Deixa?" | Helena | Não (decisão do mês) |
| **CADASTRO / EC_ORBE** | EC desconhecido, nomes como aparecem na Orbe, nº de transações e valor bruto | "Esse EC é de qual lojista (CNPJ)? É novo ou já está na planilha sem EC?" | Financeiro/Comercial | Sim: EC na planilha (coluna EC Orbe) ou `regra propor --tipo COMPLEMENTO --campos cnpj=... ec_orbe=...` |
| **CADASTRO / CNPJ_PONTE** | CNPJ da Ponte que não está na planilha | "Lojista novo? Qual a linha dele na planilha (spread contratado)?" | Financeiro/Comercial | Sim: linha na planilha de taxas |
| **CADASTRO / TAXA_NAO_CADASTRADA** | Lojista sem taxa para o produto/parcelas/data | "Qual é a taxa? Desde quando?" | Financeiro/Comercial | Sim: completar a planilha |
| **CADASTRO / REMESSA_LOJISTA_SEM_CONTRATO** | Lojista sem contrato de checkout que fez remessa; comissão entrou (informativo) | "Está tudo bem o lojista operar só remessa?" | Financeiro/Comercial | Normalmente não |
| **RECURSO_SEM_OPERACAO** | PIX de lojista na conta de remessas sem operação correspondente no relatório da Ponte | "A operação foi contratada no mês seguinte ou o valor deve ser devolvido?" | Financeiro | Não |
| **EXTRATO_NAO_IDENTIFICADO / CREDITO_SEM_ORIGEM** | O lançamento sem identificação, classificado em créditos não identificados | "De quem é? Para onde vai?" | Financeiro | Se recorrente: CLASSIFICAR_CONTA |
| **EXTRATO_NAO_IDENTIFICADO / SEM_REGRA ou CONFLITO_DE_REGRAS** | Lançamento que nenhuma regra cobre (ou duas discordam); conta vazia | "Qual é a contrapartida?" | Financeiro | Sim, quase sempre: `regra propor --tipo CLASSIFICAR_CONTA` (ou ajustar prioridades) |
| **DEVOLUCAO** | Repasse que voltou (devolução PIX), com o lojista | "Por que voltou? Dados bancários errados? Repassar de novo?" | Financeiro | Não |
| **EM_TRANSITO** | Transferência entre contas próprias que saiu de um banco e não entrou no outro no mês | Informativo: "confere no próximo fechamento" | Financeiro | Não |
| **REVISAR_IA** | Conta sugerida pela IA com a confiança | "A conta está certa?" | Financeiro | Se certa e recorrente: CLASSIFICAR_CONTA |
| **FORA_COMPETENCIA / COMPLIANCE / DUPLICATA_DIVERGENTE** | As linhas e por que ficaram fora | "Pertence a outro mês? A Ponte confirma qual linha vale?" | Helena | Não |

## Regras de conduta

- Uma pendência por vez. Mostre a evidência antes de perguntar.
- Se a pessoa responder com um número ("então a comissão é X"), não acolha o número: o
  motor recalcula depois da regra. Diga isso.
- Decisão que muda cadastro vai para a **planilha de taxas** (processo que o financeiro já
  tem) ou para o `complemento_cadastro.csv`; nunca para o código.
- Depois de aplicar uma regra, rode `fechar` e mostre a diferença no `resumo.json`.
