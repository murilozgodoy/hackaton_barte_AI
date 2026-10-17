# Pendências: o que mostrar, o que perguntar, quem decide

Sempre comece com `explicar <PEN-...>` e mostre as linhas de origem. Nunca sugira o valor
da decisão; pergunte e registre. "Vira regra?" diz se a decisão costuma valer para os
próximos meses (então passe por `regra propor`, que mostra o efeito simulado antes de gravar).

Quem decide vem das regras DONO_PENDENCIA (`regras/regras_negocio.csv`), nunca do código.
Hoje: Helena (Financeiro) decide o fechamento; **cadastro e contrato quem decide é o Comercial**
(Helena à Casa Barton, 17/10 11h01); extratos são do Financeiro.

**Informativas** (`informativa=true` na regra): aparecem com valor e rastro, mas ficam fora do
"em jogo": EM_TRANSITO, ALERTA_ANTECIPACAO, CONFERIR_AJUSTE_PONTE, DUPLICATA_PONTE. **Já incluída em outra**
(`incluida_em=`): EXCESSO_SPREAD_CONTESTADO, cuja metade já está na divergência da Mundo Aberto.
Pendência de acompanhamento com motivo e próximo passo não é alarme falso (Organização, 17/10 11h27).

| Tipo | O que mostrar | O que perguntar | Quem decide | Vira regra? |
|---|---|---|---|---|
| **TARIFA_ZERO_COBRADA** (natureza **DEVOLUCAO_LOJISTA**) | As transações do lojista com taxa 0 contratada (concessão comercial fora do contrato, regra X-01) em que a adquirente cobrou o que estava contratado; valor pela taxa e valor cobrado; o truncamento. As 118 linhas estão em `divergencias_taxa.csv` marcadas `natureza=DEVOLUCAO_LOJISTA` com a `observacao` da regra, **fora** de `orbe_contestacao.csv`. **Não há o que cobrar da adquirente**: a Tarvo abriu mão da receita, a devolução ao lojista é custo da Tarvo (Helena ao Theo 17/10 11h37) | "Como e quando devolvemos ao lojista? Qual conta (2.1.01.002)? O Comercial confirma a concessão até 31/12?" | Helena + Comercial | A exceção já é regra (TAXA_EXCECAO). A devolução é decisão do mês |
| **DIVERGENCIA_TAXA** (natureza **CONTRATO**) | Transações do lojista com contratada ≠ aplicada, agrupadas por lojista × linha; a soma em R$ (líquida de estornos, que entram com sinal negativo); a taxa que o contrato/planilha diz. **O que decide é o contrato, não o aviso** (Helena 17/10 11h37): Rota (erro da Orbe), Bridge (aditivo 2,19% desde 15/09), Mundo Aberto (1,20% desde julho) | "Confirma a contestação com a Orbe/Ponte (rascunhos em saida/comunicacoes)? Como e quando ressarcimos o lojista?" | Helena | Se a planilha estiver desatualizada: a correção é na **planilha de taxas**, não em regra. Se for condição especial com prazo: TAXA_EXCECAO |
| **EXCESSO_SPREAD_CONTESTADO** | Operações de remessa com spread acima do contratado; excesso cheio e a metade da Tarvo que entrou na nota (P-05). Já incluída na DIVERGENCIA_TAXA da Mundo Aberto (fora do "em jogo") | "Contestar com a Ponte dentro do prazo (M-01)? Se devolverem, o ajuste vem no relatório do mês seguinte (AJUSTE REF) e estorna a metade no mês do ajuste (M-03)" | Helena | O comportamento já é parâmetro (incluir_excesso_contestado) |
| **CONFERIR_REPASSE_PONTE** | Nota de remessa × 50% do total declarado pela Ponte, decomposto em negativos, repetição e arredondamento: a diferença possível no TED (data do e-mail da Ponte) | "O TED caiu? Veio quanto? Registrar a diferença no mês do ajuste" (não é perda: a contestação ainda não foi aberta, Helena 16/10 22h33) | Helena | Não; é da operação do mês |
| **CONFERIR_AJUSTE_PONTE** (informativa) | Linha de ajuste da Ponte no relatório do mês (`AJUSTE REF <operação original>`, Spread R$ negativo = débito): quanto abateu na participação do mês dentro da nota única; a operação original e, com `--anterior`, o pedido da contestação de origem | "O ajuste corresponde ao que contestamos (valor e operação)? O TED refletiu o abatimento?" | Helena (DP-14) | Já é regra (J-01/J-02). Nada a decidir no cálculo |
| **SPREAD_NEGATIVO** | A operação, a observação da Ponte ("Taxa travada no pedido (D-1)") e **os dois valores** (Helena 17/10 11h37): `spread_relatorio_brl` (o que aconteceu, = valor_brl) e `spread_contratado_brl` / `diferenca_contrato_brl` (o que se pede à Ponte, porque a trava deveria ter sido honrada) e `metade_tarvo_contrato_brl` | "Contestamos com a Ponte pela diferença até o contrato (pedido b do rascunho)? Aceitamos?" | Helena | Já é regra (E-03). Se a Helena passar a aceitar, inativa-se E-03 |
| **SEM_CONTRATO** | Transações do lojista sem contrato (fora de `comissoes_por_lojista.csv`, na `carteira_pendente.csv`); quanto a adquirente cobrou e a que taxas; que isso **não** é receita da Tarvo; o repasse ao lojista não para (Helena ao Lucca 17/10 11h03) | "Qual é a taxa contratada? Desde quando?" → `regra propor --tipo TAXA_EXCECAO` com `vigencia_de` retroativa mostra o efeito (ex.: Atlas desde 10/09) e o Comercial aprova; o próximo `fechar --anterior` fatura a carteira | Comercial | Sim: TAXA_EXCECAO aprovada pelo Comercial (ou linha na planilha + status no complemento) |
| **ALERTA_ANTECIPACAO** (informativa) | Lojista sem histórico no arquivo (sem contrato ou primeiro mês) cuja antecipação acumulada (bruta, antes das reversões) passou das vendas acumuladas em algum dia; o total antecipado, o vendido, as reversões e o dia em que estourou; as antecipações no rastro. Nada saiu da comissão. Critério do time (Helena 17/10 11h37 e 11h49: "o critério é de vocês") | "A adquirente confirma a agenda de recebíveis desse lojista? Se for sem contrato, o Comercial já está tratando?" | Helena + Comercial (A-01) | Já é regra (ALERTA) |
| **SALDO_NEGATIVO_LOJISTA** | Checkout: a comissão negativa do lojista no mês e as linhas (estornos > vendas). Remessa (`subtipo=REMESSA_PARCEIRO`): a participação do mês zerada ou negativa por ajustes da Ponte; sem nota única | "Compensa no próximo mês? Cobra? Deixa?" | Helena | Não (decisão do mês) |
| **CADASTRO / EC_ORBE** | EC desconhecido, nomes como aparecem na Orbe, nº de transações e valor bruto; as linhas vão para a carteira pendente | "Esse EC é de qual lojista (CNPJ)? É novo ou já está na planilha sem EC?" | Comercial (DP-04) | Sim: EC na planilha (coluna EC Orbe) ou `regra propor --tipo COMPLEMENTO --campos cnpj=... ec_orbe=...` |
| **CADASTRO / CNPJ_PONTE** | CNPJ da Ponte que não está na planilha. As operações **entraram** na comissão e na nota pela metade do spread realizado (a Ponte paga; parâmetro P-11), sem conferência de spread contratado | "Lojista novo? Qual a linha dele na planilha (spread contratado)?" | Comercial (DP-12) | Sim: linha na planilha de taxas |
| **CADASTRO / TAXA_NAO_CADASTRADA** | Lojista sem taxa para o produto/data (célula vazia, vigência que não cobre) | "Qual é a taxa? Desde quando?" | Comercial (DP-04) | Sim: completar a planilha |
| **CADASTRO / PARCELAS_FORA_FAIXA** | Venda parcelada com quantidade que nenhuma faixa da planilha cobre (ex.: 13x). Fora da comissão, na carteira pendente, mesmo com TAXA_EXCECAO vigente. "A gente não vende acima de 12x. Se aparecer, é pendência" (Helena 17/10 11h01) | "O que aconteceu na adquirente? Há taxa para essa quantidade?" | Helena (DP-13) | Se houver taxa: faixa nova na planilha |
| **CADASTRO / REMESSA_LOJISTA_SEM_CONTRATO** | Lojista sem contrato de checkout que fez remessa; comissão entrou (informativo) | "Está tudo bem o lojista operar só remessa?" | Comercial | Normalmente não |
| **LINHA_NAO_INTERPRETADA** | Linha do relatório da Ponte sem os números mínimos (Valor ME, PTAX, Spread…) ou sem Nº Operação; nada entrou por ela; nunca é erro fatal | "É uma operação? Pedir o relatório corrigido à Ponte" | Helena (DP-15) | Não |
| **RECURSO_SEM_OPERACAO** | Não é gerada por padrão (DP-10 INATIVA, Helena 17/10): dinheiro de lojista para remessa ainda não contratada é normal e sai no mês seguinte. A conciliação mostra a diferença com o lembrete M-05 | Só se DP-10 for reativada | Financeiro | Não |
| **EXTRATO_NAO_IDENTIFICADO / CREDITO_SEM_ORIGEM** | O lançamento sem identificação, classificado em créditos não identificados | "De quem é? Para onde vai?" | Financeiro | Se recorrente: CLASSIFICAR_CONTA |
| **EXTRATO_NAO_IDENTIFICADO / SEM_REGRA ou CONFLITO_DE_REGRAS** | Lançamento que nenhuma regra cobre (ou duas discordam); conta vazia | "Qual é a contrapartida?" | Financeiro | Sim, quase sempre: `regra propor --tipo CLASSIFICAR_CONTA` (ou ajustar prioridades) |
| **DEVOLUCAO** | Repasse que voltou (devolução PIX), com o lojista; fica em 2.1.01.001 (C-18) | "Por que voltou? Dados bancários errados? Repassar de novo?" | Financeiro | Não |
| **DUPLICATA_PONTE** (informativa, valor 0) | Operação repetida no relatório da Ponte, com os mesmos valores, contada uma vez; rastro com as duas linhas físicas (valor 0); o efeito no repasse já está na CONFERIR_REPASSE_PONTE | "Mando o pedido de correção do relatório (pedido c) junto com a contestação?" | Helena (DP-18) | Já é regra |
| **EM_TRANSITO** (informativa) | Transferência entre contas próprias que saiu de um banco e não entrou no outro no mês | Informativo: "confere no próximo fechamento" | Financeiro | Não |
| **REVISAR_IA** | Conta sugerida pela IA com a confiança | "A conta está certa?" | Financeiro | Se certa e recorrente: CLASSIFICAR_CONTA |
| **FORA_COMPETENCIA / COMPLIANCE / DUPLICATA_DIVERGENTE** | As linhas e por que ficaram fora | "Pertence a outro mês? A Ponte confirma qual linha vale?" | Helena | Não |

## O que não é pendência (e onde está)

- **Contestação à Ponte**: anexo `saida/comunicacoes/ponte_contestacao.csv` + rascunho `ponte.md`, em pedidos (a, b, c…). Somar os pedidos repetiria as pendências atômicas. O pedido c (operação repetida) também tem a pendência de acompanhamento DUPLICATA_PONTE, de valor 0.
- **Contestação à Orbe**: `orbe_contestacao.csv` + `orbe.md` (só natureza CONTRATO; a Casa fica fora).
- **Recurso de remessa sem operação** (PIX de R$ 18.240): lembrete M-05 na conciliação.
- **Carteira pendente**: `carteira_pendente.csv` (Atlas, EC novo, parcelado fora da faixa) para o próximo `fechar --anterior`.

## Regras de conduta

- Uma pendência por vez. Mostre a evidência antes de perguntar.
- Se a pessoa responder com um número ("então a comissão é X"), não acolha o número: o
  motor recalcula depois da regra. Diga isso.
- Decisão que muda cadastro vai para a **planilha de taxas** (processo que o financeiro já
  tem) ou para o `complemento_cadastro.csv`; nunca para o código.
- Depois de aplicar uma regra, rode `fechar` e mostre a diferença no `resumo.json` (o `regra propor --entrada` já
  mostrou o efeito simulado antes de gravar).
