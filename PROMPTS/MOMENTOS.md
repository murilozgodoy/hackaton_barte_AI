# Momentos que importaram

*(Modelo. O texto de cada momento é escrito pelo time: o que pedimos, o que a IA devolveu, o que
fizemos com isso. Pelo menos um momento em que a IA errou ou nos levou para o lugar errado.)*

## Momento 1 — 

**O que pedimos:** 

**O que a IA devolveu:** 

**O que fizemos com isso:** 

## Momento 2 — (um em que a IA errou)

**O que pedimos:** 

**O que a IA devolveu:** 

**O que fizemos com isso:** 

## Momento 3 — 

**O que pedimos:** 

**O que a IA devolveu:** 

**O que fizemos com isso:** 

## Momento 4 — 

**O que pedimos:** 

**O que a IA devolveu:** 

**O que fizemos com isso:** 

---

### Candidatos (marcadores para escolher; apagar o que não for usado)

- Teste "EXPEDIÇÕES × EXPEDICÕES" (Fase 1): a IA escreveu o teste esperando a grafia certa; o banco escreve com C sem cedilha. Conferimos os bytes do arquivo e corrigimos o teste, não o leitor.
- A IA somou errado a expectativa da Casa do Estudante (15.402,27 em vez de 15.391,27) e o teste acusou; o motor estava certo.
- Revisor da Fase 3 pegou `--competencia 2026-9` zerando o mês com código 0 e "integridade OK".
- Detecção genérica de "em trânsito" marcou tarifas como transferência (Fase 4); virou marcação por regra (`transitoria=true`). O revisor da Fase 4 ainda achou o caso em que tudo está em trânsito e nada era detectado.
- Revisor da Fase 5: a decomposição da diferença com a Ponte chamava de "arredondamento" qualquer operação fora da comissão e o mesmo número saía com três decomposições (rastro, motivo, `resumo.json` com HALF_EVEN escondido).
- A conciliação adquirente × banco: a IA concluiu "repassou mais do que recebeu"; a liquidação parcelada da adquirente invalida a comparação. Virou limitação declarada (regra M-04), não achado.
- Pesquisa do padrão Agent Skills: uma pasta `skills/` na raiz não é descoberta por nenhum agente; a spec foi ajustada (`.agents/skills/`, frontmatter com 6 campos).
