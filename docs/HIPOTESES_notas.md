# Notas para o HIPOTESES.md (Fase 8) — acumuladas durante as fases

Premissas que ainda não estão em nenhum documento entregável e não podem se perder:

- [PREMISSA] Comissão de remessa de lojista SEM_CONTRATO/INATIVO é mantida (o spread é pago pelo parceiro, não depende de taxa contratada com o lojista); gera pendência CADASTRO/REMESSA_LOJISTA_SEM_CONTRATO informativa. Decisão do time, 17/10, após achado M-3 da revisão da Fase 4.
- [PREMISSA] Antecipação usa `data_movimento` como data da taxa (a Orbe não preenche `data_venda_original` nas 38 antecipações); reversão usa `data_venda_original` = data da antecipação revertida. Sem efeito numérico em set/26 (taxa de antecipação 2,10% para todos, sem vigência que mude).
- [PREMISSA] Duplicata da Ponte: fica a primeira linha do arquivo; a marcada "reprocessada" é ignorada. Comparação de igualdade só em cnpj, data, moeda, Valor ME, Taxa Cliente, PTAX, Valor R$, Spread R$, Spread % e IOF (status de compliance e observação fora). Se os valores diferirem, nenhuma linha entra (DUPLICATA_DIVERGENTE).
- [PREMISSA] Divergência de remessa usa a coluna Spread % (6 casas) do relatório, para a conta ser reproduzível a partir das colunas de saída; pela fórmula exata Spread R$ − contratado daria R$ 1.418,88 (diferença de R$ 0,03 na Mundo Aberto). Decisão B, aprovada 16/10.
- [PREMISSA] Spread negativo NÃO entra em divergencias_taxa (decisão A). O Lucca Landeiro (21h56) propôs listar como divergência; revisar se a Helena validar a abordagem dele.
- [PREMISSA] Tolerância de spread de remessa 0,01 p.p. (lojistas sem renegociação oscilam ≤ 0,0016 p.p.); a Helena delegou com motivo escrito.
- [PREMISSA] Conciliação adquirente × banco: não conciliável com os arquivos do mês (parcelas mensais D+30 salvo antecipação). Apresentada como limitação, sem conclusão. Decisão do usuário, 17/10.
- [DECISÃO] RECURSO_SEM_OPERACAO (MRD2026090425, R$ 18.240,00) e REPASSE_PONTE_DIVERGENTE (R$ 506,65 = 917,03 − 410,94 + 0,57) viram pendências com rastro; donos via DP-10/DP-11. 17/10.
- [PREMISSA] Pendência com valor negativo (spread negativo, saldo negativo, trânsito) mantém o sinal em `valor_brl`; o total por responsável é a soma dos valores absolutos ("em jogo").
- [PREMISSA] Nota fiscal de remessa única com discriminação "Intermediação de câmbio - participação no spread - competência MM/AAAA" (texto do time; o formato serviço + competência foi confirmado pela Helena 20h47).
- [PREMISSA] IOF no Meridiano (MRD2026090586) → 4.3.01; seguro → 4.2.05; CDB → 1.1.02.001; rendimento → 3.2.01; TED LIQ Ponte → 2.1.02.001; TED mesma titularidade → 1.1.09.001; contabilidade L53 → 4.2.06; tarifas → 4.2.01 (decisão F, aprovada 16/10).
- [CONFIRMADA] Repasse da Ponte = 50% do total declarado; a Ponte liquida Valor R$ + IOF (conferido: TEDs = Σ(Valor R$ + IOF) das 232 operações únicas, diferença zero).
- Para o PROMPTS/MOMENTOS.md (marcadores, texto é do time): (1) teste "EXPEDIÇÕES × EXPEDICÕES": teste corrigido conferindo os bytes, leitor mantido; (2) eu somei errado a expectativa da Casa (15.402,27 vs 15.391,27), motor estava certo; (3) revisor da Fase 3 pegou `--competencia` mal formatado zerando o mês com exit 0; (4) revisor da Fase 4 pegou EM_TRANSITO desaparecendo quando nada cai no outro banco; (5) detecção genérica inicial de trânsito marcou tarifas como "em trânsito" (corrigido por regra `transitoria=true`).
