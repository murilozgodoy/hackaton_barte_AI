# Pendências: o que mostrar, o que perguntar, quem decide

Sempre comece com `explicar <PEN-...>` e mostre as linhas de origem. Nunca sugira o valor
da decisão; pergunte e registre. "Vira regra?" diz se a decisão costuma valer para os
próximos meses (então passe por `regra propor`).

| Tipo | O que mostrar | O que perguntar | Quem decide | Vira regra? |
|---|---|---|---|---|
| **TARIFA_ZERO_COBRADA** | As transações do lojista com taxa 0 contratada (acordo comercial) em que a adquirente cobrou; valor pela taxa e valor cobrado; o truncamento. **Não é divergência de contrato** (a adquirente cobrou certo pelo que sabia): é devolução ao lojista, fora de `divergencias_taxa.csv` (regra X-01, `divergencia=DEVOLUCAO_LOJISTA`) | "Como e quando devolvemos ao lojista? Quem avisa a adquirente do acordo para o próximo mês?" (não há o que cobrar da adquirente) | Helena + Comercial | A exceção já é regra (TAXA_EXCECAO). A devolução é decisão do mês |
| **DIVERGENCIA_TAXA** | Transações do lojista com contratada ≠ aplicada, agrupadas por lojista × linha; a soma em R$; a taxa que a planilha diz | "A planilha está certa? Houve renegociação não registrada? Devolve ao lojista / contesta a adquirente?" | Helena | Se a planilha estiver desatualizada: a correção é na **planilha de taxas**, não em regra. Se for condição especial com prazo: TAXA_EXCECAO |
| **EXCESSO_SPREAD_CONTESTADO** | Operações de remessa com spread acima do contratado; excesso cheio e a metade da Tarvo que entrou (ou não) na nota | "Contestar com a Ponte dentro do prazo? Se devolverem, estornamos no mês do ajuste (regra M-03)" | Helena | O comportamento já é parâmetro (incluir_excesso_contestado) |
| **CONFERIR_REPASSE_PONTE** | Nota de remessa × 50% do total declarado pela Ponte, decomposto em negativos, repetição e arredondamento: a diferença possível no TED | "O TED caiu? Veio quanto? Registrar a diferença no mês do ajuste" (não é perda: a contestação ainda não foi aberta) | Helena | Não; é da operação do mês |
| **CONTESTACAO_PONTE** | A lista que a Helena manda para a Ponte: operações com excesso de spread (valor cheio), spreads negativos (valor absoluto) e repetidas (valor 0, só para corrigir o relatório); total em disputa | "Enviar a contestação dentro dos 5 dias úteis (M-01)? Rascunho em saida/comunicacoes/ponte.md" | Helena | Não |
| **SPREAD_NEGATIVO** | A operação, a observação da Ponte ("Taxa travada no pedido (D-1)"), o spread negativo | "Contestamos com a Ponte? Aceitamos?" | Helena | Já é regra (E-03). Se a Helena passar a aceitar, inativa-se E-03 |
| **SEM_CONTRATO** | Transações do lojista sem contrato; quanto a adquirente cobrou e a que taxas; que isso **não** é receita da Tarvo | "Qual é a taxa contratada? Desde quando?" → a resposta entra na **planilha de taxas** (linha nova) e o status sai do complemento | Comercial | Sim: linha na planilha + remover/alterar o status no complemento (`regra propor --tipo COMPLEMENTO`) |
| **SALDO_NEGATIVO_LOJISTA** | A comissão negativa do lojista no mês e as linhas (estornos > vendas) | "Compensa no próximo mês? Cobra? Deixa?" | Helena | Não (decisão do mês) |
| **CADASTRO / EC_ORBE** | EC desconhecido, nomes como aparecem na Orbe, nº de transações e valor bruto | "Esse EC é de qual lojista (CNPJ)? É novo ou já está na planilha sem EC?" | Financeiro/Comercial | Sim: EC na planilha (coluna EC Orbe) ou `regra propor --tipo COMPLEMENTO --campos cnpj=... ec_orbe=...` |
| **CADASTRO / CNPJ_PONTE** | CNPJ da Ponte que não está na planilha. As operações **entraram** na comissão e na nota pela metade do spread realizado (a Ponte paga; parâmetro P-11), sem conferência de spread contratado | "Lojista novo? Qual a linha dele na planilha (spread contratado)?" | Comercial (DP-12) | Sim: linha na planilha de taxas |
| **CADASTRO / TAXA_NAO_CADASTRADA** | Lojista sem taxa para o produto/parcelas/data | "Qual é a taxa? Desde quando?" | Financeiro/Comercial | Sim: completar a planilha |
| **CADASTRO / REMESSA_LOJISTA_SEM_CONTRATO** | Lojista sem contrato de checkout que fez remessa; comissão entrou (informativo) | "Está tudo bem o lojista operar só remessa?" | Financeiro/Comercial | Normalmente não |
| **RECURSO_SEM_OPERACAO** | Não é mais gerada por padrão (DP-10 INATIVA, Helena 17/10): dinheiro de lojista para remessa ainda não contratada é normal e sai no mês seguinte. A conciliação mostra a diferença com o lembrete M-05 | Só se DP-10 for reativada: "A operação saiu no mês seguinte?" | Financeiro | Não |
| **ALERTA_ANTECIPACAO** | Lojista sem contrato ou novo no mês cuja antecipação acumulada passou das vendas acumuladas em algum dia; o total antecipado, o vendido e o dia em que estourou; as linhas de antecipação no rastro. Nada saiu da comissão | "A adquirente confirma a agenda de recebíveis desse lojista? Se for sem contrato, o Comercial já está tratando?" | Helena + Comercial (A-01) | Já é regra (ALERTA). Se o lojista passar a ter contrato, a planilha resolve |
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
