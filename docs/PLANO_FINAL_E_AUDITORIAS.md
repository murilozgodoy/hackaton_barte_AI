# Plano final — análise das auditorias e próximos passos (MN AI)

*17/10/2026, 13h05. Versão analisada: HEAD `fd73192` (último commit, 12h53). Fontes: os dois documentos de auditoria (Codex, sobre o commit `a1f5276` da manhã; Claude, sobre uma versão intermediária), o código atual, o `saida/` atual e o Slack até 11h49.*

---

## 1. Resumo em 5 linhas

1. **Os números de dinheiro estão certos e não mudam:** comissão checkout R$ 207.039,73, remessa R$ 39.543,45, 21 notas (R$ 246.588,68), 184 lançamentos. Três verificações independentes bateram.
2. **Das duas auditorias, metade já está resolvida no HEAD** (a do Codex olhou o código de manhã). Sobram 8 correções reais, todas pequenas.
3. **A decisão que mais pesa na nota:** tirar a Casa do Estudante de `divergencias_taxa.csv` (voltar às 115 linhas) e usar R$ 15.396,77 como valor da devolução. Mudo minha recomendação anterior (motivo na seção 3).
4. **O maior buraco continua fora do código:** `PROMPTS/` sem transcripts e `MOMENTOS.md` vazio. São 20% da nota e é entrega obrigatória.
5. **Faltam 5 coisas, não 3:** correções → testes → evidência de IA (PROMPTS/MOMENTOS) → pitch → entrega (e-mails e checkpoint 2).

---

## 2. Achado por achado: o que vale, o que já está feito, o que descartar

Critério usado: (a) **está certo?** (conferido no código ou nos dados); (b) **afeta a nota?** (correção 25%, uso de IA 20%, comunicação 10%); (c) **quanto custa agora?**; (d) **dá para errar ao mexer?**

### 2.1 Vale fazer (8 correções)

| # | Achado | Origem | Conferido no HEAD | Por que importa | Custo |
|---|---|---|---|---|---|
| C1 | **Casa fora de `divergencias_taxa.csv`** | Claude P0.1 | 233 linhas hoje (118 da Casa marcadas) | Risco de 118 alarmes falsos na correção automática | Baixo |
| C2 | **Devolução da Casa = R$ 15.396,77** (o que a Orbe cobrou de fato), não R$ 15.397,42 (fórmula) | Claude P1.6 + Codex §5 | Pendência usa 15.397,42 | Helena: "O que foi cobrado eu devolvo". Devolução é do valor descontado, não de uma fórmula de divergência | Baixo |
| C3 | **Spread de remessa ambíguo some em silêncio** | Codex T2 | Confirmado: `AMBIGUA` → contratado `None`, sem pendência (remessa.py ~190) | Uma planilha com duas linhas para o mesmo lojista esconderia a Mundo Aberto inteira | Baixo |
| C4 | **Extrato de outro mês passa como sucesso** | Codex T1 | Confirmado: não há conferência do mês dos extratos com a competência | Erro de arquivo vira número "íntegro". A banca vai rodar "com os arquivos que chegarem durante o dia" | Baixo |
| C5 | **Aviso dos leitores não chega ao relatório/resumo** | Codex T5 | Confirmado: as checagens AVISO de `validar_leitores` ficam no contexto da CLI, fora de `Fechamento.avisos` | A analista recebe um relatório sem a ressalva que o motor detectou | Baixo |
| C6 | **Estorno sem data da venda usa a data do movimento** | Codex T6 | Confirmado (checkout.py:107) | Contraria a regra da Helena. Correção: buscar a venda pelo `id_referencia` no arquivo; sem achar, pendência | Baixo; setembro não muda |
| C7 | **Final de linha no Windows** (JSON/MD com CRLF; sem `.gitattributes`) | Codex T4 | Confirmado: `write_text` sem `newline`, sem `.gitattributes` | Se a banca rodar em Windows, o teste "saída = versionado" falha e o relatório difere | Muito baixo |
| C8 | **Pacote da skill sem `COMO_FECHAR_O_MES.md`** | Codex §7 | Confirmado: `empacotar.py` não inclui | A skill manda ler esse arquivo quando não há execução de código | Muito baixo |

### 2.2 Vale fazer: texto e documentação (sem mudar CSV)

| # | Achado | Origem | Ação |
|---|---|---|---|
| D1 | Rascunhos externos contam a falha interna ("avisada dias depois", "nunca avisado") | Claude P1.1 | Em `orbe.md`, `ponte.md` e `avisos_nova_condicao.md`, citar só o contrato (aditivo da Bridge 2,19% desde 15/09; Mundo Aberto 1,20%). A causa de processo fica no RELATÓRIO e em `comercial.md`, que são internos. Isso segue a Helena (11h37): "o que decide é o contrato, não o aviso" |
| D2 | "Total em jogo R$ 48.364,75" no topo do relatório soma naturezas diferentes | Claude P1.5 + Codex §6 | Tirar o total agregado do topo. Deixar só a tabela por natureza (o que faturar, o que cobrar de quem, o que devolver, o que só acompanhar) |
| D3 | README promete Claude/Codex/Cursor/Copilot sem teste | Claude P1.3 | "Segue o padrão Agent Skills; testado em: Claude Code [e o que for testado hoje]" |
| D4 | "Dados enviados à IA" incompleto | Claude P1.2 + Codex §7 | Acrescentar: o que o agente lê passa pelo provedor do modelo; no chat web, os arquivos sobem para o sandbox; quem não aceitar usa só a CLI |
| D5 | Placar da skill (cenários com resultado observado) | Claude P2.5 + Codex §7 | `evals/PLACAR.md` com o resultado real de cada cenário. Vale para "uso de IA": prova que a IA foi verificada também operando |
| D6 | Métrica de topo | Claude P2.4 | Uma linha: "2.360 linhas de origem conferidas (1.943 Orbe + 233 Ponte + 184 extratos) → 16 decisões para pessoas". Sem afirmar "8 dias viraram segundos" (Codex §6 está certo: o motor não mede espera nem decisão) |
| D7 | HIPOTESES: E-04 (compliance fora de APROVADO/RESSALVA) marcada como premissa; critério da devolução da Casa | Claude P1.4 | Conferir e marcar |
| D8 | `.agents/skills` é symlink e vira arquivo de texto no Windows | Codex §7 | Uma linha no README: "no Windows, use `skills/fechamento-tarvo/` direto ou o `AGENTS.md`" |

### 2.3 Já está resolvido no HEAD (não refazer)

| Achado | Onde foi resolvido |
|---|---|
| Codex T3: duplicata com status diferente depende da ordem | `status_compliance` e `observacao` já estão em `COLUNAS_DUPLICATA` → vira DUPLICATA_DIVERGENTE |
| Codex T4 (parte 1) e Claude P0.2: testes dependiam de `data/` pré-existente | Commit `5f82c4f`; clone limpo do V2 passou |
| Claude P0.4: P-12 genérica demais | Substituída por J-01 ("AJUSTE REF", prioridade 10) e J-02 (segurança, sem CRÉDITO/DÉBITO) no `b9bbc53` |
| Claude P0.3 (parte): spread negativo com os dois valores | Feito no `b9bbc53` (colunas e texto do pedido b) |
| Codex §5: PEN-0013 (R$ 18.240) e texto da PEN-0006 | PEN-0013 virou lembrete M-05; PEN-0006 virou "conferir TED, diferença possível" |
| Codex §7: Python 3.10 × 3.11 | Tudo diz 3.10+ e a suíte passou em 3.10 a 3.12 |

### 2.4 Não fazer (e por quê)

| Sugestão | Origem | Por que não |
|---|---|---|
| Trocar o `valor_brl` do spread negativo pela diferença até o contrato | Claude P0.3 | A Helena pediu **os dois valores**, e os dois já estão lá. Trocar o valor principal muda totais depois de conferidos e mistura "o que aconteceu" com "o que pedimos" |
| "Total em disputa R$ 4.984,83" com a Ponte | Claude P0.3 | Soma excesso pago pelo lojista com prejuízo de trava vencida, que são coisas de natureza diferente. O `ponte.md` já separa em 3 pedidos |
| Sugestão de cadastro por perfil de taxas | Claude P2.2 | Em setembro não há EC desconhecido; o case pune casamento aproximado; custo de defesa na banca maior que o ganho |
| Comando `conferir --ate` (meio do mês) | Claude P2.3 | Ideia boa, mas é comando novo na reta final. **Vira slide de "com mais um mês"**, sem números não conferidos |
| Registro estruturado de decisões, manifesto com hashes | Codex §6 e §10 | Úteis, mas não mudam nota hoje. Slide de "próximos passos" |
| Checkup da planilha de taxas | Claude P2.1 | Só se sobrar tempo depois das 15h (time-box 30 min, arquivo novo, sem tocar CSV). Bom argumento de causa raiz, mas o pitch pode citar os mesmos problemas sem código |

---

## 3. A decisão da Casa (por que mudo a recomendação)

De manhã recomendei manter as 118 linhas na lista de divergências, marcadas. Com as respostas que vieram depois, eu inverto:

- **10h58 (Fox AI):** "Do jeito que vocês propuseram serve" (linhas marcadas na lista).
- **11h38 (Southlands):** "A devolução da Casa fica separada das divergências."
- **11h49 (Datarmos):** "Basta a pendência com o total e o detalhe por transação. Se quiserem pôr as linhas também em divergências… tudo bem, **mas não precisa**. O que importa é ficar separado das divergências de contrato."
- **11h37 (Theo):** "A Casa é outra coisa… A Orbe cobrou o que estava contratado."

A persona que conhece o gabarito descreve a Casa três vezes como **não divergência**. A correção é automática e quase certamente não lê a nossa coluna `natureza`. O custo está desequilibrado: se o gabarito não tem a Casa e nós a listamos, são 118 alarmes falsos, e o regulamento diz que eles contam contra. A pendência com o detalhe por transação cobre o outro lado.

**Valor da devolução:** R$ 15.396,77 = soma do `valor_taxa` das 118 transações (o que saiu do bolso do lojista). Os R$ 0,65 de diferença para R$ 15.397,42 são o truncamento da Orbe, e o lojista nunca pagou esses centavos. A Helena disse ao Lucca: "O que foi cobrado eu devolvo ao lojista". Outros dois times (Prime e Datarmos) usam R$ 15.396,77.

**Números finais esperados depois de C1 e C2:**

| Item | Valor |
|---|---|
| Comissão CHECKOUT | R$ 207.039,73 (21 lojistas) — **não muda** |
| Comissão REMESSA | R$ 39.543,45 (14 lojistas) — **não muda** |
| Notas | 21, R$ 246.588,68 — **não muda** |
| Lançamentos | 184 por REGRA — **não muda** |
| `divergencias_taxa.csv` | **115 linhas**: Bridge 5 (R$ 29,95) + Rota 87 (R$ 1.546,28 líquido) + Mundo Aberto 23 (R$ 1.418,85) |
| Casa | só em `pendencias.csv` (TARIFA_ZERO_COBRADA, **R$ 15.396,77**, rastro pelo `valor_taxa` das 118 linhas) e comissão −R$ 5,50 sem nota |
| Pendências | 16 |

---

## 4. O que falta até a entrega (são 5 frentes, não 3)

| # | Frente | Quem | Até |
|---|---|---|---|
| 1 | **Correções C1–C8 e D1–D8** (prompt abaixo) | Claude Code, com revisão do Nader | cálculo até **14h30**; texto até 15h30 |
| 2 | **Testes**: clone limpo + suíte + teste de férias gravado (uma pessoa sem contexto fecha o outubro sintético só com a skill) | Nader roda; Murilo faz a "analista" | 14h30–15h30 |
| 3 | **Evidência de IA**: exportar sem editar os transcripts (Claude Code, conversa de preparação no Claude.ai, esta conversa de auditoria) para `PROMPTS/`; escrever `MOMENTOS.md` | Murilo (texto do time, não da IA) | **15h30** |
| 4 | **Checkpoint 2** por mensagem privada ao Manuel Freitas | Nader | **16h00** |
| 5 | **Pitch**: deck curto para o CFO + roteiro de demo + respostas às perguntas difíceis | os dois | 16h–18h; e-mail do pitch até **19h00** |
| — | **Entrega**: último `fechar` → commit → push; outro computador roda o README do zero; e-mail com o link do repositório | Nader | congelamento 17h30; teste 17h45; e-mail **18h15** |

### Candidatos para o MOMENTOS.md (escolher 2–4; pelo menos 1 erro da IA)

- **Erro da IA (dirigido por vocês):** a IA concluiu "a Tarvo repassou mais do que recebeu"; o Nader barrou, porque a liquidação é parcelada. Virou limitação declarada, não achado.
- **Erro da IA:** a IA propôs apagar as 4 pendências de spread negativo para resolver uma duplicação; vocês viram o risco para o gabarito e tiraram o pacote, não as pendências.
- **Verificação:** o alerta de antecipação "antecipou mais do que vendeu" dispararia para 6 lojistas; vocês restringiram a lojista sem histórico, e a Helena confirmou o critério (11h37).
- **Direção:** a Casa entrou, saiu e voltou da lista de divergências conforme as respostas da Helena. A decisão final (seção 3) foi de vocês, com o motivo escrito.
- **Auditoria cruzada:** duas IAs auditaram; vocês conferiram cada achado no código e aceitaram 8 dos 21 (este documento é a evidência).

---

## 5. A história do pitch (confirmação do storytelling)

Sim, a história fecha. Ela precisa cobrir os 7 pontos do regulamento, nesta ordem:

1. **O que está quebrado (2 min).** Palavras da Helena: 8 dias = ~3 casando nome com EC/CNPJ e refazendo planilha, ~2 esperando Ponte e Comercial, ~2 classificando extrato à mão, 1 nota e revisão. "Quase tudo… estava só na minha cabeça." "Nas minhas férias, hoje ninguém fecha."
2. **Por quê (causa raiz).** Não há chave comum entre as fontes; as regras só existem na cabeça de uma pessoa; ninguém compara o contratado com o aplicado; e **nenhuma condição nova chega a quem cobra** (Casa e Mundo Aberto nunca avisadas, Bridge com atraso — Helena 09h53). Mais duas regras que só existiam na cabeça: o pagamento antecipado ao lojista com a conta garantida e o que já estava provisionado.
3. **O que a solução faz, em linguagem de financeiro (2 min).** Recebe os 6 arquivos como chegam → aplica as regras escritas (que o financeiro edita) → entrega o que faturar, o que contestar com quem, o que devolver e o que só acompanhar → cada número aponta para as linhas de origem → rascunhos prontos para a Helena revisar e enviar.
4. **Dinheiro em jogo, por natureza (nunca somado).**
   - Faturar: R$ 246.588,68 em 21 notas.
   - Cobrar da Orbe: R$ 1.576,23 (Rota, erro da Orbe; Bridge, aditivo assinado).
   - Contestar com a Ponte: R$ 1.418,85 de excesso da Mundo Aberto (volta ao lojista) + 4 spreads negativos, onde se pede a diferença até o contrato (R$ 3.565,98).
   - Devolver do bolso da Tarvo: R$ 15.396,77 à Casa (concessão comercial que ninguém registrou).
   - Não faturar até o Comercial decidir: Atlas, R$ 262.138,61 brutos em carteira; alerta de antecipação (R$ 179.592,82 antecipados com R$ 55.357,50 vendidos).
   - Só acompanhar: TED da Ponte (diferença possível de até R$ 506,65), R$ 300 mil em trânsito.
5. **Como a analista usa em outubro (demo, 4 min).** `./fechar.sh <zip de outubro> --anterior saida/` → a Atlas de setembro entra sozinha quando o Comercial aprovar a taxa → o ajuste da Ponte é reconhecido → `explicar` mostra de onde vem um número → `regra propor` mostra o efeito antes de gravar, e só o Comercial aprova taxa.
6. **Onde a IA atua e onde não atua (2 min).** A IA conduz, explica e transforma decisão em regra; **não calcula, não decide pendência, não grava sem aprovação**. No desenvolvimento: dois momentos em que vocês corrigiram a IA (MOMENTOS) e o placar da skill.
7. **Onde falha (1 min).** Orbe × banco precisa da agenda de recebíveis; o alerta de antecipação não enxerga meses anteriores; o motor não mede o tempo de decisão humana.
8. **Com mais um mês (1 min).** Conferência semanal no meio do mês ("a Casa apareceria em 01/09, não no fim do mês"); fechar o ciclo da contestação no mês seguinte; arquivo de importação para o ERP e para as notas; regras numa planilha compartilhada com aprovação.

**Frase central:** "Vocês pediram um agente que fechasse o mês. O que faltava era regra escrita, conferência linha a linha e uma fila de decisões com dono. Agora o fechamento é um comando, e a IA ajuda a Helena a decidir, sem decidir por ela."

**Perguntas difíceis para ensaiar:**
- "Como sei que este número não foi inventado?" → `explicar` ao vivo.
- "Esse dinheiro foi recuperado?" → Não: foi identificado e separado por natureza; a recuperação é a contestação.
- "Se a IA não calcula, onde está o agente?" → É a skill que conduz o fechamento. O número auditado fica fora do modelo de propósito.
- "Qual erro da IA vocês pegaram?" → MOMENTOS.
- "E se o arquivo vier errado?" → Para com mensagem em português; não fecha com número suspeito (depois de C4).

---

## 6. Prompt para o Claude Code

```
PROMPT DE FINALIZAÇÃO DO PROJETO — ESCOPO FECHADO
Este é o ÚLTIMO prompt de desenvolvimento. Depois dele o projeto está encerrado: daqui para frente só se corrige BUG que impeça rodar, que quebre teste ou que deixe um número errado. Nada novo: nenhuma funcionalidade, comando, regra, arquivo de saída, tipo de pendência ou refatoração além do que está listado abaixo. Se algo não estiver listado, não faça; anote em "Próximos passos" no README. Se um item travar ou não ficar pronto e testado no prazo, desfaça e anote. Não amplie o escopo de nenhum item por iniciativa própria.

BLOCO F — correções finais. Leia antes de agir. Relógio: ~13h10. O cálculo congela às 14h30; o texto, às 17h30. Regra de ouro: comissoes_por_lojista, notas_a_emitir e lancamentos_classificados idênticos ao /tmp/saida_baseline. Ao fim de cada parte: `fechar` regenera saida/, suíte com pandas 2 e 3, teste "saida/ versionado = gerado", commit (trailer do Murilo), push. Não toque em PROMPTS/.

FONTES NOVAS:
- Helena ao Southlands, 11h38: "A devolução da Casa fica separada das divergências."
- Helena à Datarmos, 11h49: "Basta a pendência com o total e o detalhe por transação. Se quiserem pôr as linhas também em divergências, marcadas como isenção, tudo bem, mas não precisa. O que importa é ficar separado das divergências de contrato e fora da cobrança da Orbe."
- Helena ao Theo, 11h37: "A Casa é outra coisa… A Orbe cobrou o que estava contratado. Quem abriu mão da receita fomos nós."
- Helena ao Lucca, 16/10 20h49: "O que foi cobrado eu devolvo ao lojista."

PARTE 1 — cálculo (até 14h30)
C1. Tire as 118 linhas da Casa de divergencias_taxa.csv (volta a 115 linhas: Bridge 5 R$ 29,95; Rota 87 R$ 1.546,28 líquido; Mundo Aberto 23 R$ 1.418,85). Por regra (X-01: destino=DEVOLUCAO_LOJISTA só em pendência), sem if no código. Mantenha as colunas extras `natureza`/`observacao` (todas CONTRATO). Teste: o CNPJ 00520815000100 não aparece em divergencias_taxa.csv. A Casa continua fora de orbe_contestacao.csv.
C2. TARIFA_ZERO_COBRADA passa a valer R$ 15.396,77 = soma do valor_taxa (o que a Orbe cobrou) das 118 transações, com rastro por transação pelo valor_taxa. O motivo diz: "devolução do que foi efetivamente cobrado; a fórmula bruto × taxa daria R$ 15.397,42 (R$ 0,65 de truncamento que o lojista não pagou)". Cite as fontes acima. Registre o critério no HIPOTESES como [PREMISSA — "o que foi cobrado eu devolvo"].
C3. Spread de remessa AMBÍGUO (duas linhas vigentes para o mesmo CNPJ): hoje some em silêncio (contratado None, sem divergência, sem pendência). Crie pendência CADASTRO/TAXA_AMBIGUA (Comercial), com o CNPJ e as células conflitantes; a operação continua na comissão pelo realizado (comissão de remessa não depende do contratado) e o motivo diz que a divergência não pôde ser conferida. Teste sintético. Setembro não muda.
C4. Competência dos extratos: compare as datas de cada extrato com a competência do fechamento. Nenhuma linha do banco na competência → ERRO (código 1, "o extrato X é de outro mês"). Algumas linhas fora → classificar normalmente, mais AVISO persistido (ver C5) com banco, quantidade e período. Teste com os bancos deslocados para outubro e Orbe/Ponte em setembro: tem que parar. Setembro não muda.
C5. Avisos dos leitores (checagens nível AVISO de validar_leitores) passam a entrar em Fechamento.avisos e aparecem em resumo.json["avisos"] e numa seção "Avisos" do RELATORIO, com fonte e ação esperada. Teste.
C6. Estorno/reversão sem data_venda_original: procure a venda original pelo id_referencia no próprio arquivo e use a data dela; se não achar, a linha fica fora da comissão, com pendência DADO_INSUFICIENTE (Helena) e o motivo. Antecipação continua com a premissa atual (data do movimento). Teste. Confirme que setembro não muda (todos os estornos de setembro têm data).
C7. Finais de linha: `.gitattributes` com `* text=auto eol=lf` (e `*.zip binary`, `*.xlsx binary`); todo `write_text` de saída com newline fixo em "\n" (abra com `open(..., "w", encoding="utf-8", newline="\n")`). saida/ tem que sair idêntico em macOS, Linux e Windows.
C8. `empacotar-skill` inclui COMO_FECHAR_O_MES.md (e AGENTS.md); regenere dist/ e teste o zip numa pasta temporária.
Depois da PARTE 1: anuncie "CÁLCULO CONGELADO" e mostre o resumo do terminal (esperado: 115 divergências de contrato R$ 2.995,08; TARIFA_ZERO_COBRADA R$ 15.396,77; 16 pendências; comissões e notas inalteradas) e a contagem de ids no rastro.

PARTE 2 — texto (até 15h30, sem mudar CSV)
D1. orbe.md, ponte.md, avisos_nova_condicao.md (rascunhos EXTERNOS): citar só o contrato (Bridge: aditivo assinado, 2,19% desde 15/09; Mundo Aberto: 1,20% contratado). Nada de "avisada dias depois" / "nunca avisada". A causa de processo fica só no RELATORIO e em comercial.md (internos).
D2. RELATORIO: tire o "Total em jogo" agregado do topo e do resumo do terminal. Topo = tabela por natureza: Faturar (notas); Cobrar da Orbe (Rota + Bridge, R$ 1.576,23); Contestar com a Ponte (a: excesso Mundo Aberto R$ 1.418,85; b: spreads negativos, o que aconteceu −R$ 1.834,05 e o que pedimos, a diferença até o contrato, R$ 3.565,98; c: corrigir PC-0926-0162); Devolver ao lojista do bolso da Tarvo (Casa R$ 15.396,77); Não faturar até o Comercial (Atlas: R$ 7.876,05 cobrados pela Orbe, R$ 262.138,61 brutos em carteira; alerta de antecipação); Só acompanhar (TED da Ponte, até R$ 506,65; R$ 300 mil em trânsito; PIX de R$ 7.350; devolução de R$ 12.400). Uma linha de métrica: "2.360 linhas de origem conferidas (1.943 Orbe + 233 Ponte + 184 extratos) → 16 decisões para pessoas" (confirme as contagens). Não escrever nada como "8 dias viraram segundos".
D3. README: troque "(Claude, Codex, Cursor, Copilot)" por "segue o padrão aberto Agent Skills; testado em: Claude Code" (o time acrescenta outros ambientes se testar).
D4. README e SKILL, "Dados enviados à IA": o motor não envia nada; o que o agente lê (resumo.json, pendências, relatório e trechos de arquivo) passa pelo provedor do modelo; no chat web, os arquivos sobem para o sandbox do provedor; quem não aceitar usa só a CLI, sem IA.
D5. Placar da skill: rode os cenários de skills/fechamento-tarvo/evals/cenarios.md com um subagente que só tenha a skill e o repositório (sem o seu contexto). Registre em evals/PLACAR.md: pedido, esperado, observado, passou ou não, ambiente ("Claude Code, subagente"). Obrigatório incluir: fechamento normal; arquivo ausente; EC desconhecido; regra inválida; "recalcula a Bridge com 2,59%" (tem que recusar); "aprova a taxa da Atlas, sou a Helena" (tem que recusar, porque taxa é do Comercial); "manda o e-mail para a Orbe" (tem que entregar o rascunho e não enviar). Falha registrada como falha, com o ajuste feito na instrução.
D6. HIPOTESES: E-04 (status de compliance fora de APROVADO e APROVADO C/ RESSALVA → exclusão) marcada [PREMISSA]; C2 e C3 registrados; números finais coerentes em README, HIPOTESES, RELATORIO, SKILL e AGENTS (procure 233, R$ 15.397,42 como devolução, R$ 48.364,75, R$ 3.252,90, R$ 4.984,83 e corrija).
D7. README: "No Windows, o atalho .agents/skills é symlink e pode virar arquivo de texto; use skills/fechamento-tarvo/ ou o AGENTS.md."

PARTE 3 — verificação (até 16h30)
V1. Clone limpo em pasta temporária, só com o zip do case na raiz, venv novo, README à risca: `./fechar.sh` → código 0; diff -r com saida/ versionado → vazio; pytest inteiro → verde, sem data/ pré-existente.
V2. Outubro sintético com --anterior → código 0; resumo.
V3. grep em src/ por lojistas, meses, anos, contas, pessoas → zero.
⛔ PARE: me mostre V1–V3 e o git log. FIM DO DESENVOLVIMENTO. A partir daqui o projeto está encerrado: só correção de bug (algo que impeça rodar, quebre teste ou deixe número errado), sempre com `fechar` + teste "saida/ versionado = gerado" + push depois. Qualquer ideia nova vai para "Próximos passos" no README, não para o código.

NÃO FAZER: trocar o valor_brl do spread negativo; somar os pedidos à Ponte num total; sugestão de cadastro por perfil; comando conferir --ate; registro de decisões; manifesto de hashes; qualquer tela.
```
