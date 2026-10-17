# Especificação — Fechamento Tarvo (time MN AI)

> **Este documento é a fonte única da verdade do projeto.** Ele substitui o prompt inicial, os adendos e todas as mensagens de ajuste anteriores. Onde algo já implementado divergir daqui, vale este documento — mas **liste as divergências e me mostre antes de alterar código já testado**.
>
> Versão: 16/10/2026 22h55 (v3 — v2 + §9.5 implantação e uso no dia a dia). Regras de negócio atualizadas com o Slack até 22h10.

---

## 1. O problema que estamos resolvendo

A Tarvo (subadquirente, ~25 lojistas, linhas CHECKOUT via Orbe e REMESSA via Ponte Câmbio) leva 8 dias úteis para fechar o mês e erra. A causa raiz não é falta de automação:

1. **Não há chave comum entre as fontes.** O mesmo lojista aparece com nomes diferentes; ECs faltam na planilha; a conciliação é feita "de cabeça".
2. **As regras só existem na cabeça de uma pessoa.** "Se eu sair de férias, o mês não fecha."
3. **Ninguém compara contratado × aplicado.** Divergências só aparecem quando o lojista reclama.

A solução ataca as três: um **motor determinístico** que aplica regras **escritas e editáveis pelo financeiro**, compara contratado × aplicado linha a linha, rastreia cada número até a origem e transforma toda exceção em **pendência com dono**. A IA é **facilitadora opcional**: conduz a analista pelo fechamento, explica números e pendências, e ajuda a transformar decisões em regras — **nunca calcula, nunca decide**.

---

## 2. Princípios de arquitetura (valem para toda decisão)

| # | Princípio | Consequência prática |
|---|---|---|
| P1 | **O motor funciona sozinho.** | Tudo (6 CSVs + relatório legível) sai de um comando, sem IA, sem chave de API, sem internet. |
| P2 | **Números só saem do código.** | A IA lê resultados prontos (`resumo.json`, relatório, `explicar`). Se o motor falhar, nenhum número é apresentado. |
| P3 | **Regra é dado, não código.** | Nenhum nome de lojista, mês, taxa ou conta contábil em `src/`. Tudo em `regras/`. |
| P4 | **Uma informação, um lugar.** | A planilha de taxas (entrada mensal) é o cadastro mestre. `regras/` só guarda o que a planilha não tem. Nada duplicado. |
| P5 | **Escrita de regra só por comando validado.** | Nem humano nem IA editam CSV de regra "na mão" no fluxo normal: usam `regra propor` → `regra aplicar`, que validam e registram histórico. (Editar no Excel continua possível; o motor valida ao carregar.) |
| P6 | **Exceção vira pendência, nunca palpite.** | O que nenhuma regra cobre não quebra o fechamento e não é inferido (nem por nome). |
| P7 | **Interface portátil.** | O contrato é a CLI + arquivos. A skill segue o padrão aberto Agent Skills (SKILL.md), e há `AGENTS.md` e um roteiro manual — funciona em Claude, Codex, Copilot/VS Code, Cursor e sem IA. |
| P8 | **Mínimo de dados para a IA.** | A IA recebe resumos e as linhas estritamente necessárias para a pergunta, nunca arquivos inteiros. |

---

## 3. Estrutura do repositório (alvo)

```
README.md                       instalar e rodar do zero; limitações; "Dados enviados à IA"
HIPOTESES.md                    premissas, perguntas MN AI, respostas usadas de outros times
AGENTS.md                       instruções para qualquer agente de IA (aponta para a skill)
COMO_FECHAR_O_MES.md            roteiro para a analista, SEM IA (passo a passo da CLI)
PROMPTS/                        README.md (lista de sessões + links) e MOMENTOS.md (escrito pelo time)
saida/                          6 CSVs + resumo.json + RELATORIO_FECHAMENTO.md
regras/                         base de conhecimento do financeiro (persiste mês a mês)
  regras_negocio.csv
  complemento_cadastro.csv
  fontes.csv                    padrões de nome de arquivo/aba (já existe)
  historico_alteracoes.csv
  COMO_CRIAR_REGRA.md
src/                            motor (leitores/ já prontos — Fase 1)
tests/
skills/fechamento-tarvo/        Agent Skill (padrão SKILL.md)
  SKILL.md
  references/  regras_e_tipos.md · pendencias.md · saidas.md · glossario.md
  evals/       cenarios.md
```

> **Data pack e docs NÃO são versionados** (decisão do time): `Tarvo_Data_Pack_*.zip`, o docx do case e `docs/` ficam no `.gitignore`. O README explica onde colocar o zip para rodar do zero, e os testes que dependem dele são pulados quando ele não existe. Os CSVs de `saida/` **são** versionados, para a banca ver o resultado sem rodar.

> Renomeie `config/` → `regras/` (nome que a analista entende). `--regras <pasta>` permite que, em produção, essa pasta fique com o financeiro, fora do repositório.

---

## 4. O motor: contrato da CLI

Todos os comandos: `python -m src <comando> ...`. Mensagens ao usuário em português. Saída para agentes em JSON quando `--json`.

| Comando | O que faz | Códigos de saída |
|---|---|---|
| `validar --entrada <zip/pasta> --regras <pasta>` | Confere presença e formato das 6 fontes e valida `regras/` inteira. Não calcula nada. | 0 ok · 1 entrada · 2 regras |
| `fechar --entrada ... --regras ... --saida ... [--competencia AAAA-MM]` | Fechamento completo. Escreve os 6 CSVs, `resumo.json`, `RELATORIO_FECHAMENTO.md`. Roda as validações de integridade (§8) ao final. | 0 ok · 1 entrada · 2 regras · 3 integridade (nesse caso, **não** escreve `resumo.json` e marca o relatório como inválido) |
| `explicar <id_saida> --saida ...` | Mostra de onde vem um número: linhas do `rastro.csv` com arquivo, ref_origem, valor e os campos relevantes da linha original; regra aplicada (id) e taxa usada. | 0 · 4 id inexistente |
| `pendencias --saida ... [--quem <nome>] [--tipo <tipo>]` | Lista pendências agrupadas por responsável, com valor total. | 0 |
| `regra propor --regras ... --tipo ... --campos k=v ...` | Monta uma linha de regra, valida (§6.3) e mostra exatamente o que seria gravado + efeito esperado. **Não grava.** | 0 válida · 2 inválida |
| `regra aplicar --regras ... --proposta <arquivo> --aprovado-por <nome>` | Grava a regra validada e registra em `historico_alteracoes.csv`. | 0 · 2 |

Sem subcomando, `python -m src` equivale a `fechar` com os padrões atuais (zip na raiz, `regras/`, `saida/`) — mantém o que a Fase 1 já entregou.

### 4.1 `resumo.json` (consumido por agentes; nada de recalcular)
```json
{
  "competencia": "2026-09",
  "status_integridade": "OK",
  "totais": {
    "comissao_checkout_brl": "...", "comissao_remessa_brl": "...",
    "notas": {"quantidade": 0, "valor_total_brl": "..."},
    "divergencias": {"checkout": {"linhas": 0, "valor_brl": "..."}, "remessa": {"linhas": 0, "valor_brl": "..."}},
    "pendencias": {"por_responsavel": {"Helena (Financeiro)": {"quantidade": 0, "valor_brl": "..."}}, "por_tipo": {}}
  },
  "lancamentos": {"REGRA": 0, "IA": 0, "HUMANO": 0},
  "avisos": ["complemento_cadastro: linha redundante ..."],
  "arquivos": {"comissoes": "saida/comissoes_por_lojista.csv", "...": "..."}
}
```
Valores monetários como string decimal (sem float).

### 4.2 `RELATORIO_FECHAMENTO.md` (gerado pelo motor, sem IA)
Uma página para a analista e o CFO: totais por linha de negócio; notas a emitir; top divergências com R$; pendências por responsável (com o que cada um precisa fazer); avisos; checagens de integridade. É o "facilitador" mesmo para quem não usa IA.

---

## 5. Entradas (Fase 1 concluída — manter)

Leitores prontos e testados (42 testes): Orbe, planilha de taxas (formato longo lojista × vigência × produto, com célula de origem), Ponte (xlsx dentro do .eml), plano de contas, Aurora (ref `L<n>` = linha física), Meridiano (FITID). Encoding por fonte com fallback validado. `fontes.csv` com padrões de nome. Totais conferidos a cada execução.

---

## 6. Base de regras (`regras/`)

### 6.1 Cadastro: planilha de taxas é o mestre (P4)
- Lojista, CNPJ, EC e taxas vêm **da planilha de taxas do mês**. Lojista novo = linha nova na planilha (processo que o financeiro já tem). Nada a fazer no sistema.
- `complemento_cadastro.csv` guarda **só lacunas/correções** da planilha:
  `cnpj; ec_orbe; status; informado_por; data; observacao`
  - status ∈ {ATIVO, SEM_CONTRATO, INATIVO}
  - Hoje: Kiwi (EC 1038867654), Horizonte Viagens e Turismo (1043396662), Novo Horizonte Intercâmbio (1043300981) — Slack/Helena 20h24; Atlas Idiomas (CNPJ 39566044000119, identificado pela aba antiga; SEM_CONTRATO).
- Resolução: planilha → complemento. Conflito (mesmo CNPJ, EC diferente) = erro em português. Complemento redundante com a planilha = aviso "linha pode ser removida".
- **EC da Orbe sem cadastro** ou **CNPJ da Ponte sem cadastro**: não quebra, não casa por nome. Pendência `CADASTRO` com nomes como aparecem na fonte, nº de transações e valor bruto; essas linhas ficam fora de comissão/nota/divergência até o cadastro.

### 6.2 `regras_negocio.csv`
`id; situacao; como_identificar; tipo; parametros; o_que_fazer; quem_decide; exemplo; vigencia_de; vigencia_ate; status; informado_por; data`

`tipo` — lista fechada (o motor executa):

| tipo | Para quê | Exemplo |
|---|---|---|
| PARAMETRO | número/opção que pode mudar | participacao_spread=0.50; spread_padrao=0.015; tolerancia_spread_pp=0.01; tolerancia_taxa_checkout_pp=0 (Helena: qualquer diferença de taxa é divergência); incluir_excesso_contestado=true; arredondamento=HALF_UP; tomador da nota de remessa (CNPJ/nome); textos de discriminação. **Competência NÃO é parâmetro de regra** (vem da CLI ou é inferida dos dados; senão a analista teria de editar regra todo mês). |
| TAXA_EXCECAO | taxa especial por CNPJ/linha/produto com vigência | Casa do Estudante, CHECKOUT, MDR e antecipação = 0, 2026-09-01 a 2026-12-31 |
| IGNORAR_DUPLICADO | não contar repetição por chave | Ponte: chave = Nº Operação |
| EXCLUIR_E_PENDENCIA | tirar do cálculo e mandar para pessoa | Ponte: spread_brl < 0 → contestar (Helena); lojista SEM_CONTRATO (Comercial) |
| CLASSIFICAR_CONTA | texto do extrato → conta contábil | banco=AURORA; contem=ORBE ADQUIRENCIA; conta=1.1.03.001; prioridade=50 |
| DONO_PENDENCIA | define, para cada tipo de pendência gerada pelo motor, quem decide e o texto do motivo | tipo_pendencia=DIVERGENCIA_TAXA (quem_decide e o_que_fazer nas colunas próprias) |
| MANUAL | regra em português que o motor **não** executa | gera pendência/lembrete com `o_que_fazer` sempre que aplicável |

- `status` ∈ {ATIVA, PROPOSTA, INATIVA}. Só ATIVA é executada.
- Colunas de texto livre são para humanos e para a skill explicar; o código não interpreta texto livre.
- `parametros`: pares `chave=valor` separados por ` | `.
- `CLASSIFICAR_CONTA` **não usa regex** (quem não é técnico não escreve regex, e o `|` colidiria com o separador). Casamento por **"contém o texto"**, após normalizar acentos e caixa. Várias alternativas no mesmo campo separadas por ` OU ` (ex.: `contem=PONTE AEREA OU PONTE AÉREA`). `prioridade` explícita: **menor número vence** (específicas ~10, genéricas ~90). Empate de prioridade levando a contas diferentes → pendência EXTRATO_NAO_IDENTIFICADO. Casos que exigem prioridade: "PONTE AEREA" (lojista) antes de "PONTE CAMBIO" (parceiro); "PIX ENVIADO CONTABILIDADE" antes de "PIX ENVIADO".
- `DONO_PENDENCIA` mantém dono e texto de cada tipo de pendência editáveis (P3), sem misturar com MANUAL, que significa "o motor não executa".

### 6.3 Validação ao carregar (e em `regra propor`)
Tipo válido; parâmetros parseáveis para o tipo; conta existe e `ACEITA_LANCTO=S`; vigências sem sobreposição para o mesmo alvo; ids únicos. Erro → para com: id da regra, campo, problema e como corrigir, em português simples.
**Tolerância ao Excel:** CNPJ sem zero à esquerda e data dd/mm/aaaa são aceitos e normalizados **com aviso** (é exatamente o que o Excel faz ao salvar). Qualquer outro formato inválido é erro.

### 6.4 `historico_alteracoes.csv`
`data; quem; id_regra; acao (CRIOU/ALTEROU/INATIVOU); antes; depois; motivo; fonte`. Popule com a origem de cada regra atual (Slack, horário). Linhas do complemento usam `id_regra = complemento:<CNPJ>`.

### 6.5 `COMO_CRIAR_REGRA.md`
Uma página para não técnico: como escolher o tipo (fluxograma simples de 4 perguntas), 3 exemplos reais deste mês, e "na dúvida, use MANUAL — o sistema vai te lembrar todo mês até alguém automatizar". **Dois caminhos, nesta ordem:**
1. **Com assistente de IA:** descreva a situação em português; ele propõe a linha, mostra o efeito e só grava com sua aprovação.
2. **Sem IA:** abra `regras_negocio.csv` no Excel, copie uma linha parecida, ajuste, salve e rode `validar` — ele aponta qualquer erro com o id da linha.
(`regra propor`/`regra aplicar` são o mecanismo usado pelo assistente e por quem usa terminal; não exija que a analista os use.)

---

## 7. Regras de negócio (todas com fonte)

### 7.1 Checkout
- Comissão = valor_bruto × **taxa CONTRATADA**, linha a linha. Vai para a nota. *(Fox AI 20h05)*
- Taxa vigente = a da **data da venda**. Estorno e reversão usam a data da venda original. Estorno de venda de mês anterior abate no mês do estorno (mês anterior não reabre). *(MN AI 20h06)* Modalidade/parcelas de estorno de venda ausente no arquivo vêm da própria linha do estorno.
- Faixas: débito, crédito à vista, 2–6x, 7–12x (do cabeçalho da planilha), Pix, antecipação.
- Antecipação entra na mesma comissão/nota; reversão anula só a taxa da antecipação revertida. *(MN AI notas 20h47)*
- **Arredondamento:** Tarvo NÃO trunca (a Orbe trunca). HALF_UP ao centavo, simétrico no negativo, **por linha e depois soma**. `Decimal` em todo valor monetário; proibido `round()` e `float` em dinheiro. *(Fox AI 21h13)*
- Casa do Estudante: tarifa 0 no checkout (MDR e antecipação) de set a dez/2026; remessa normal. *(Lucca 21h06)* → TAXA_EXCECAO.
- Rota Global: sem mudança contratual em 2026 → o +0,50 p.p. aplicado pela Orbe desde 12/09 (crédito) é divergência. *(Lucca 21h06)*
- Atlas: sem contrato, não fatura até o Comercial confirmar. *(Fox AI 20h24)* → SEM_CONTRATO + EXCLUIR_E_PENDENCIA.

### 7.2 Divergências de taxa
- Só existe quando **taxa aplicada ≠ contratada**; centavo de truncamento não é divergência. Valor = valor_bruto × (aplicada − contratada), HALF_UP por linha. *(Fox AI 21h13)*
- `divergencias_taxa.csv`: **uma linha por transação**.
- Não ajusta nada sozinho: a Helena decide caso a caso → **uma pendência por lojista × linha de negócio**, com rastro para todas as linhas. *(Fox AI 20h05)*
- Estorno com taxa diferente da contratada: mesma fórmula (sinal negativo). [PREMISSA]

### 7.3 Remessa
- Comissão = **50% do Spread R$ realizado, por operação**, HALF_UP, depois soma (ex.: 262,01 → 131,01). *(MN AI 20h48; Fox AI 21h13)*
- Nº de operação é único → duplicata conta uma vez. Ressalva de compliance não muda nada. Competência = **data de contratação**. *(MN AI 20h48)*
- Spread negativo: não aceito (trava de 2h vencida) → fora da comissão e da nota; pendência de contestação (Helena). **Não** entra em `divergencias_taxa` (não é taxa contratada ≠ aplicada). [DECISÃO A] ⚠️ O Lucca (21h56) propôs listá-los como divergência; se a Helena validar a abordagem dele, revisar.
- Spread contratado = coluna "Spread remessa"; vazio/"padrão" = 1,5%. *(MN AI 20h48)*
- Divergência de remessa = (Spread % aplicado − contratado) × PTAX × Valor ME, **valor cheio**, usando a coluna Spread % do relatório. *(Fox AI 20h58)* Tolerância: |diferença| ≤ 0,01 p.p. = arredondamento da Ponte (demais lojistas oscilam ≤ 0,0016 p.p.). [PREMISSA — Helena delegou a nós com motivo escrito]
- Excesso contestado (Mundo Aberto): **entra na nota de setembro** pelo realizado; contestação é processo à parte; ajuste sai no mês em que ocorrer; pendência para a Helena. *(Theo Garcia ~22h)*

### 7.4 Notas fiscais
- CHECKOUT: 1 nota por lojista/mês = comissão contratada (vendas − estornos + antecipações − reversões). Zero ou negativo **não emite**; negativo vira pendência para a Helena (não carrega automático). *(MN AI 20h47)* Casa do Estudante: −5,50 (estorno de venda de agosto, anterior ao acordo) → sem nota, pendência.
- REMESSA: **uma nota**, tomadora Ponte Câmbio S.A., CNPJ 75374179000146, pelo total da participação no mês. *(MN AI 20h47)*
- Discriminação: serviço + competência.

### 7.5 Extratos
- `conta_codigo` = **contrapartida** do movimento. Já registrado → baixa a conta onde estava. *(Fox AI 21h14)*
- Provisionados: folha 08/2026, tributos de agosto, repasse Ponte de 04/09 (MRD2026090132 → 1.1.03.002). Todo o resto (tarifas, aluguel, cloud, assinaturas, serviços) = despesa do mês. *(Lucca 21h06; Fox AI 21h14)*
- Casos: PIX R$ 7.350 sem identificação → 1.1.09.002 + pendência; devolução PIX Mundo Aberto R$ 12.400 → 2.1.01.001 + pendência; transferência R$ 300 mil 30/09 (cai no Meridiano em 01/10) → 1.1.09.001, pendência informativa. *(Lucca 21h06)*
- Premissas [DECISÃO F]: TED PONTE CAMBIO LIQ OPERACOES → 2.1.02.001; CDB aplicação/resgate → 1.1.02.001; rendimento → 3.2.01; IOF → 4.3.01; seguro → 4.2.05; contabilidade (L53) → 4.2.06; tarifas → 4.2.01; TED mesma titularidade → 1.1.09.001; TED Orbe → 1.1.03.001; PIX enviado a lojista → 2.1.01.001; PIX recebido de lojista (Meridiano) → 2.1.02.001.
- Sem regra: com `ANTHROPIC_API_KEY`, sugestão por IA só com (data, descrição, valor, banco) daquela linha + lista de contas analíticas → `metodo=IA`, `confianca`<1, **e pendência de revisão**. Sem chave → `metodo=HUMANO`, conta vazia, pendência.

### 7.6 Pendências — tipos e donos
| tipo | quem_decide |
|---|---|
| DIVERGENCIA_TAXA (por lojista × linha) | Helena (Financeiro) |
| TARIFA_ZERO_COBRADA (Casa do Estudante; motivo cita R$ cobrado e R$ 0,65 de truncamento) | Helena + Comercial |
| SEM_CONTRATO (Atlas; motivo: R$ 7.876,05 foi o que a Orbe cobrou a taxas sem contrato — **não é receita da Tarvo**) | Comercial |
| SPREAD_NEGATIVO (contestar Ponte) | Helena |
| EXCESSO_SPREAD_CONTESTADO (Mundo Aberto) | Helena |
| SALDO_NEGATIVO_LOJISTA | Helena |
| CADASTRO (EC/CNPJ desconhecido) | Financeiro/Comercial |
| EXTRATO_NAO_IDENTIFICADO / DEVOLUCAO / EM_TRANSITO / REVISAR_IA | Financeiro |
| MANUAL (regra em português) | conforme a regra |

- Donos e textos desta tabela ficam em regras `DONO_PENDENCIA` (editáveis), não no código.
- Coluna extra `subtipo` em `pendencias.csv` para o detalhe (ex.: CADASTRO/EC_ORBE, CADASTRO/CNPJ_PONTE, EXTRATO_NAO_IDENTIFICADO/CREDITO_SEM_ORIGEM).
- Casa do Estudante: tipo TARIFA_ZERO_COBRADA e dono definidos na própria regra TAXA_EXCECAO dela.
- Exclusões de robustez (não ocorrem em setembro, mas sustentam a checagem 4 "nada some"): sem taxa contratada → CADASTRO; lojista inativo → SEM_CONTRATO; fora da competência, compliance não aprovado e duplicata com valores diferentes → tipos próprios (FORA_COMPETENCIA, COMPLIANCE, DUPLICATA_DIVERGENTE).
- Lançamento sem regra e sem IA → EXTRATO_NAO_IDENTIFICADO, conta vazia, `metodo=HUMANO`.

### 7.7 Conciliação a investigar (não gerar pendência ainda)
Aurora fecha em −R$ 1.920.088,60, negativo desde ~18/09. Na Fase 4, calcular e só me mostrar: Σ valor_liquido Orbe × Σ TEDs Orbe no Aurora; Σ PIX enviados a lojistas × líquido devido. Ponte: repasse esperado pelo total dela × devido (o Lucca estimou ~R$ 506 a menos).

---

## 8. Saídas e integridade

Formato fixo (correção automática): CSV `;`, ponto decimal, datas AAAA-MM-DD, CNPJ 14 dígitos, UTF-8. Colunas obrigatórias conforme o docx (extras bem-vindas). `id_saida` legível e estável (COM-CHK-0001, COM-REM-0001, DIV-0001, NF-0001, LAN-0001, PEN-0001). `ref_origem`: id_transacao / Nº Operação / L<n> / FITID.

`rastro.csv` carrega colunas extras `regra_id` e `taxa_pct` (aplicada/contratada usada naquela linha), para `explicar` funcionar sem recalcular.

Checagens a cada `fechar` (falha = código 3, nada apresentado como válido):
1. Σ rastro por id_saida == valor reportado, para todo id com valor.
2. Σ comissão checkout por lojista com saldo > 0 == Σ notas CHECKOUT.
3. Nota REMESSA == Σ comissão REMESSA.
4. Toda linha da Orbe e toda operação única da Ponte está em exatamente um destino: comissão, exclusão com pendência, ou pendência de cadastro (nada some).
5. Todo lançamento dos dois extratos aparece em `lancamentos_classificados`.
6. Saldo Aurora fecha linha a linha.

Valores de referência para conferência (set/2026): Orbe 1.943 linhas; Ponte 232 operações únicas; 4 negativos (−R$ 1.834,05); comissão remessa R$ 39.543,45 (validado também pelo Lucca); Casa do Estudante checkout −R$ 5,50 e divergência R$ 15.397,42; Bridge 5 divergências (15–18/09); Rota ~R$ 1.546 em divergência.

---

## 9. A skill (`skills/fechamento-tarvo/`)

Padrão aberto Agent Skills (SKILL.md com frontmatter `name` e `description`), para rodar em qualquer agente compatível. Princípios de uma boa skill aplicados:

- **SKILL.md curto** (< 300 linhas): quando usar, fluxo com checklist, limites. Detalhe em `references/` (carregado só quando necessário).
- **Baixa liberdade onde erro custa caro**: comandos exatos da CLI, sem improviso.
- **Ciclo de validação**: validar → executar → conferir status → só então apresentar.
- **description** com gatilhos claros: fechamento mensal Tarvo, comissões, divergências de taxa, notas, conciliação, pendências, "explica esse número", "cria uma regra".

### 9.1 Fluxo (o que o SKILL.md instrui)
1. **Preparar:** identificar os arquivos do mês e a pasta `regras/`. Rodar `validar`. Erro → explicar em português o que falta/está errado e **parar**.
2. **Fechar:** rodar `fechar`. Código ≠ 0 → explicar o erro e **parar**. Nunca apresentar número com integridade falha.
3. **Apresentar:** ler `resumo.json` e `RELATORIO_FECHAMENTO.md`. Mostrar comissões por linha, notas a emitir, divergências em R$, pendências por responsável. Se a plataforma permitir, montar painel visual **a partir desses arquivos**; senão, tabela em markdown. Entregar os CSVs.
4. **Conduzir pendências:** agrupar por responsável. Para cada uma: `explicar` → mostrar evidência → registrar a decisão da pessoa. Se a decisão vale para os próximos meses: `regra propor` → mostrar o que muda → pedir aprovação explícita → `regra aplicar --aprovado-por` → `fechar` de novo.
5. **Responder dúvidas:** "de onde vem X?" → `explicar <id>`. Nunca responder número de memória ou de cálculo próprio.

### 9.2 Limites (escritos na skill)
- Nunca calcular, estimar ou ajustar valores; nunca editar arquivos de entrada; nunca casar lojista por nome; nunca decidir pendência; nunca gravar regra sem aprovação explícita; nunca enviar arquivos inteiros a serviços externos.
- Se o ambiente **não executa código**, dizer que não é possível fechar o mês ali e indicar `COMO_FECHAR_O_MES.md`. Não tentar fazer à mão.
- Se a pessoa pedir algo que contradiz uma regra ativa ("usa 2,59% para a Bridge"), explicar a regra vigente e oferecer o caminho de alteração (propor regra), em vez de obedecer em silêncio.

### 9.3 `references/`
- `regras_e_tipos.md`: os 6 tipos, quando usar cada um, exemplos reais.
- `pendencias.md`: para cada tipo de pendência, o que mostrar, que pergunta fazer, quem decide, se costuma virar regra.
- `saidas.md`: significado de cada arquivo e coluna.
- `glossario.md`: MDR, antecipação, EC, spread, PTAX, competência, contrapartida — em linguagem de financeiro.

### 9.4 `evals/cenarios.md` (testes da skill, executados manualmente e registrados)
1. Fechamento normal de setembro → apresenta totais iguais ao `resumo.json`.
2. Falta o arquivo da Ponte → para no `validar`, explica.
3. EC novo na Orbe → mostra pendência CADASTRO; ao receber a resposta, propõe ajuste no complemento, pede aprovação, reexecuta.
4. "Recalcula a Bridge com 2,59%" → recusa recalcular, explica a regra, oferece `regra propor`.
5. Regra inválida no CSV (conta sintética) → mensagem do validador, sem fechar.
6. "Quanto a Tarvo fatura da Mundo Aberto?" → usa `explicar`, não calcula.

### 9.5 Implantação e uso no dia a dia (decisão v3)

**Empacotamento:** o zip da skill é autocontido: `SKILL.md` + `references/` + `scripts/` (cópia do motor `src/`, gerada por `python -m src empacotar-skill`) + `regras_iniciais/` (a base atual, como ponto de partida). Dependências só pandas e openpyxl. Ao rodar, o motor usa a pasta/zip de regras que a analista fornecer; se não houver, usa `regras_iniciais/` e avisa.

**Implantação (uma vez):** no Claude Team da Tarvo, a pessoa owner habilita "Code execution" e "Skills" e provisiona a skill para a organização. Ela aparece para as 3 analistas. A mesma skill funciona no Cowork e no Claude Code (e em agentes compatíveis com SKILL.md).

**Uso mensal — caminho recomendado (pasta no computador, Cowork/Claude Code):**
Pasta compartilhada `Fechamento Tarvo/` com `regras/`, `entradas/AAAA-MM/` e `saidas/AAAA-MM/`. A analista coloca os arquivos do mês em `entradas/`, pede "fecha outubro", e a skill lê e grava direto nas pastas. Regras alteradas ficam salvas no próprio `regras/`, sem passo manual.

**Uso mensal — caminho alternativo (chat na web):** a analista anexa os 6 arquivos + `regras_tarvo.zip` e pede o fechamento. Como o ambiente do chat não guarda arquivos entre conversas, **se alguma regra mudar, a skill entrega um `regras_tarvo_AAAA-MM-DD.zip` novo e o último passo do fluxo é obrigatório: "salve este arquivo na pasta compartilhada; ele substitui o anterior"**. `fechar` registra no relatório a data da última alteração do histórico de regras usado, para detectar se alguém fechou com uma base antiga.

**Sem IA:** `COMO_FECHAR_O_MES.md` com a CLI.

`fechar` aceita `--regras` como pasta **ou** zip; `regra aplicar` em modo zip devolve um zip novo.

### 9.6 Portabilidade
- `AGENTS.md` na raiz: resumo de 1 página do fluxo 9.1 e dos limites 9.2, apontando para `skills/fechamento-tarvo/` — para agentes que leem AGENTS.md e não skills.
- `COMO_FECHAR_O_MES.md`: o mesmo fluxo só com a CLI, para a analista sem IA.

---

## 10. Documentos de entrega

- **README.md**: instalar (Python 3.11+, venv, requirements), rodar do zero (um comando), usar com IA (skill/AGENTS.md), chaves (opcional `ANTHROPIC_API_KEY`), seção "Dados enviados à IA" (o que sai, quando, como desligar), limitações conhecidas.
- **HIPOTESES.md**: (1) premissas marcadas [CONFIRMADA — fonte/horário] / [PREMISSA — motivo] / [ABERTA]; (2) perguntas MN AI: 20h04 estorno (resp. 20h06), 20h26 notas (resp. 20h47), 20h30 remessa (resp. 20h48); (3) respostas a outros times usadas: Fox AI (20h05, 20h24, 20h58, 21h13, 21h14), Lucca (21h06; validação cruzada 21h56), Theo Garcia (~22h).
- **PROMPTS/**: `README.md` listando as sessões (Claude.ai — preparação; Claude Code — construção) e onde estão os exports. **Não criar nem editar transcrições.** `MOMENTOS.md`: apenas o modelo com 2–4 seções vazias e uma lista de marcadores de candidatos (ex.: "teste EXPEDIÇÕES × EXPEDICÕES"); **o texto é escrito pelo time**.

---

## 11. Plano e cortes (prazo duro 18h30 de 17/10)

| Fase | Entrega | Quando |
|---|---|---|
| 2 | `regras/` completa + validador + `historico` + `COMO_CRIAR_REGRA.md` | hoje |
| 3 | **MÍNIMO**: comissão CHECKOUT + rastro + checagem 1 | hoje |
| 4 | Divergências, remessa, notas, lançamentos + checagens 2–6 + conciliação §7.7 (só números) | até 12h |
| 5 | Pendências + `resumo.json` + `RELATORIO_FECHAMENTO.md` | até 13h30 |
| 6 | Testes de robustez (taxa por data, estorno de mês anterior, HALF_UP ±0,005, duplicata, EC novo, datas +1 mês, grep sem mês fixo) | até 14h |
| 7 | CLI `explicar`/`pendencias`/`regra` + skill + AGENTS.md + roteiro manual + evals | 14h–16h |
| 8 | README, HIPOTESES, revisão final | 16h–17h30 |

**Corte:** se às 14h as fases 3–5 não estiverem verdes, a Fase 7 se reduz a `SKILL.md` com `validar`/`fechar`/`explicar` e AGENTS.md. Números corretos vêm antes de qualquer interface.

## 12. Git
Commits pequenos por fase, mensagem em português no imperativo, trailer `Co-authored-by: murilozgodoy <murilozg@al.insper.edu.br>`. Sem push sem pedido. Pare ao fim de cada fase e mostre o resultado.
