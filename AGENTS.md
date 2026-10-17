# Instruções para agentes de IA neste repositório

Este projeto fecha o mês da Tarvo Pagamentos com um **motor determinístico** (`python -m src`).
A skill completa está em `skills/fechamento-tarvo/SKILL.md` (também acessível por
`.agents/skills/fechamento-tarvo/`): **leia e siga o SKILL.md** antes de fechar um mês,
explicar um número ou mexer em regras.

## Resumo do fluxo
1. `python -m src validar --entrada <zip ou pasta> --regras regras --json` → código 1 (entrada) ou 2 (regras): explique e pare.
2. `python -m src fechar --entrada <zip ou pasta> --regras regras --saida saida --json` → código 3 (integridade): explique e pare.
3. Apresente a partir de `saida/resumo.json` e `saida/RELATORIO_FECHAMENTO.md`. Entregue os CSVs.
4. Pendências: `python -m src pendencias --saida saida --json`; para cada uma, `python -m src explicar <id> --saida saida --entrada <...> --regras regras`. Registre a decisão da pessoa.
5. Decisão que vale para os próximos meses: `python -m src regra propor ...` → mostrar → aprovação explícita de quem pode aprovar aquele tipo (`regras/aprovadores.csv`: taxa = Comercial, resto = Helena) → `python -m src regra aplicar --proposta <arquivo> --aprovado-por "<nome>" [--registrado-por "<nome>"]` → `fechar` de novo.

## Limites
- Nunca calcule, estime ou ajuste valores; todo número vem de `saida/`.
- Nunca edite arquivos de entrada; nunca identifique lojista por nome (só CNPJ/EC cadastrado).
- Nunca decida pendência; nunca grave regra sem aprovação nominal; nunca envie arquivos inteiros a serviços externos.
- Sem execução de código: indique `COMO_FECHAR_O_MES.md` e não tente fazer à mão.
- Pedido que contradiz regra ativa: explique a regra e ofereça `regra propor`.

## Para desenvolvedores
- Regra de negócio é dado (`regras/`), nunca código. Nenhum nome de lojista, taxa, conta ou mês em `src/` (há teste).
- Dinheiro só em `Decimal`, HALF_UP; proibido `float`/`round()`.
- `.venv/bin/python -m pytest` antes de qualquer commit; `saida/` versionada deve ser igual ao que o código gera (há teste).
