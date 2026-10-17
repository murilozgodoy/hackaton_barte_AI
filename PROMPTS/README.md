# Histórico das sessões de IA

Regra do regulamento: o histórico é entregue como está (podem-se remover chaves de API e
dados pessoais; fora isso, não se edita). Os exports foram adicionados pelo time, sem edição.

| # | Sessão | Ferramenta | Período | Para quê | Onde está |
|---|---|---|---|---|---|
| 1 | Preparação ("Case bottleneck e objetivo") | Claude.ai | 16/10, 19h–23h50 | Leitura do case, causa raiz, perguntas ao financeiro, especificação (`docs/ESPECIFICACAO.md`, v1→v3), prompt inicial para o Claude Code, revisão das Fases 1–4 | [link](https://claude.ai/share/8c326d73-0c0e-4a9e-9b5d-7d5a5b0e9095) · `claude_ai/01_preparacao.pdf` |
| 2 | Construção | Claude Code (VS Code), Opus 5.5 e depois Fable 5.1 | 16/10 21h30 → 17/10 | Fases 0 a 8: leitores, base de regras, motor, pendências, relatório, testes, skill, documentos. Inclui os agentes revisores (um por fase) e o pesquisador de Agent Skills | `claude_code/*.jsonl` (transcripts originais) |
| 3 | Acompanhamento do dia ("Avaliação do projeto e qualidade") | Claude.ai | 17/10, manhã até ~14h | Recálculo independente das comissões, leitura do Slack, triagem das duas auditorias, prompt de finalização | [link](https://claude.ai/share/f0c0e9c0-72b5-4eb8-87cb-49b480c0ebcb) · `claude_ai/03_dia.pdf` |
| 4 | Auditorias do repositório | Codex e Claude (sessões do Murilo) | 17/10 | Duas auditorias independentes; 8 dos 21 achados aceitos (`docs/PLANO_FINAL_E_AUDITORIAS.md`) | `claude_ai/04_auditoria_*.pdf` · LINK |
| 5 | Teste da skill, 1ª rodada | Claude.ai (chat limpo, só a skill) | 17/10 ~14h15 | "Feche o mês de setembro": a IA somou o total sozinha e deu alarme falso de prazo | [link](https://claude.ai/share/4829c915-6943-45f8-b043-872897adda83) · `claude_ai/05_teste_skill_1.pdf` |
| 6 | Revisão dos testes e correções | Claude.ai (projeto Case-BarteAi) | 17/10 14h20–15h30 | Análise do teste, prompts de correção das 5 causas para o Claude Code, revisão do reteste, rascunho do `MOMENTOS.md` | `claude_ai/06_revisao_testes.pdf` · https://claude.ai/share/b74f3778-8554-4466-a257-73036de178d3 |
| 7 | Teste da skill, 2ª rodada | Claude.ai (chat limpo, só a skill) | 17/10 ~15h15 | Reteste depois das correções | `claude_ai/07_teste_skill_2.pdf` · https://claude.ai/share/6bf018df-35e4-473c-bf61-547b264d5818 |
| 8 | Funcionalidades e documentação (sessão do Murilo) | Claude.ai | 17/10 | Ideias de funcionalidades do dia e apoio na documentação | [link](https://claude.ai/share/f13a7242-7107-41cb-9bd5-b6ed0c40e92a) |

`MOMENTOS.md` marca os 4 momentos que importaram.
