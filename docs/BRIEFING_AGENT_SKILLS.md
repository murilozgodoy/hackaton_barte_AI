# Briefing técnico — padrão Agent Skills (SKILL.md) e boas práticas

Data da pesquisa: 2026-10-16. Fontes primárias consultadas: agentskills.io (spec do padrão aberto), platform.claude.com (docs da Anthropic; `docs.claude.com` redireciona para lá), code.claude.com (Claude Code), support.claude.com (Help Center do Claude.ai/Cowork), github.com/anthropics/skills, anthropic.com/engineering, docs do Codex (developers.openai.com → redireciona para learn.chatgpt.com), Cursor, GitHub Copilot/VS Code, agents.md.

Legenda: **[CONFIRMADO]** = lido na fonte primária citada. **[NÃO CONFIRMADO]** = não achei em fonte primária ou as fontes divergem.

---

## 1. Formato exigido do SKILL.md

### 1.1 Estrutura de pastas (spec)
```
skill-name/
├── SKILL.md          # obrigatório: frontmatter YAML + instruções em Markdown
├── scripts/          # opcional: código executável
├── references/       # opcional: documentação carregada sob demanda
├── assets/           # opcional: templates, imagens, dados (tabelas, schemas)
└── ...               # qualquer outro arquivo/pasta é permitido
```
Fonte: https://agentskills.io/specification (seções "Directory structure" e "Optional directories"). As três pastas são **convenções recomendadas**, não obrigatórias; "A skill directory may contain any files and directories beyond the required SKILL.md".

### 1.2 Frontmatter — campos e limites (spec agentskills.io)

| Campo | Obrig. | Restrições |
|---|---|---|
| `name` | sim | 1–64 chars; só `a-z`, `0-9` e `-`; não começa/termina com `-`; sem `--` consecutivos; **deve ser igual ao nome da pasta pai** |
| `description` | sim | 1–1024 chars, não vazia; diz o que a skill faz **e quando usar**; incluir palavras-chave |
| `license` | não | nome da licença ou referência a arquivo bundled |
| `compatibility` | não | 1–500 chars; só se houver requisitos de ambiente (produto, pacotes, rede). Ex.: `Requires Python 3.14+ and uv` |
| `metadata` | não | mapa string→string (ex.: `author`, `version`) |
| `allowed-tools` | não | string separada por espaço de ferramentas pré-aprovadas; **experimental**, suporte varia entre agentes |

Fonte: https://agentskills.io/specification. Validador oficial: `skills-ref validate ./my-skill` (https://github.com/agentskills/agentskills/tree/main/skills-ref).

**Regras adicionais da Anthropic** (valem para Claude.ai, Skills API e empacotamento): `name` e `description` **não podem conter tags XML**; `name` **não pode conter as palavras reservadas "anthropic" e "claude"**. Fonte: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#skill-structure e https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices.

**Campos extras quebram o upload no Claude.ai/API.** Claude Code aceita muitos campos próprios (`when_to_use`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `context`, `agent`, `hooks`, `paths`, `effort`, `model`, `shell`…), mas "If you include any field the spec doesn't allow, packaging or upload fails with a hard error": `Unexpected key(s) in SKILL.md frontmatter: argument-hint. Allowed properties are: allowed-tools, compatibility, description, license, metadata, name`. Recomendação explícita: ficar nos 6 campos da spec para a mesma skill rodar em todo lugar. Fonte: https://code.claude.com/docs/en/skills ("Using skill frontmatter outside Claude Code").

**[NÃO CONFIRMADO / DIVERGENTE]** O artigo do Help Center "How to create custom skills" (https://support.claude.com/en/articles/12512198-creating-custom-skills) foi lido pelo fetcher como dizendo "description: máximo 200 caracteres" e cita um campo `dependencies`. Isso contradiz a spec, a doc da plataforma e a doc do Claude Code (1024 chars; `dependencies` não é campo permitido). Trate o artigo como desatualizado; use 1024 como limite e **não** use `dependencies` no frontmatter (daria erro de "unexpected key" no upload).

**Convenção de nome:** a Anthropic sugere gerúndio (`processing-pdfs`) ou substantivo (`pdf-processing`); evitar `helper`, `utils`, `tools`. Fonte: best-practices acima.

### 1.3 Corpo do SKILL.md
- Sem restrições de formato; seções recomendadas: passos, exemplos de entrada/saída, casos de borda. Fonte: spec.
- **Limite recomendado: < 500 linhas e < 5.000 tokens** para o corpo. Fontes: https://agentskills.io/specification#progressive-disclosure ("Keep your main SKILL.md under 500 lines"), https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices ("Keep SKILL.md body under 500 lines for optimal performance"), https://code.claude.com/docs/en/skills.
- Arquivos de referência com **> 100 linhas devem ter um sumário (TOC) no topo** (Anthropic best-practices) — o skill-creator usa > 300 linhas como gatilho. Fontes: best-practices; https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md.
- **Referências a um nível só**: todo arquivo citado deve ser linkado direto do SKILL.md com caminho relativo à raiz da skill (`references/x.md`, `scripts/y.py`); evitar cadeia SKILL.md → a.md → b.md porque o modelo faz `head -100` e lê parcialmente. Fontes: spec ("File references"), best-practices ("Avoid deeply nested references").
- Dizer **quando** ler cada referência ("Leia `references/pendencias.md` quando `pendencias` devolver ≥1 item"), não "veja references/ para detalhes". Fonte: https://agentskills.io/skill-creation/best-practices.
- Deixar explícito se um script deve ser **executado** ("Run `scripts/x.py`") ou **lido** como referência ("See `scripts/x.py` for the algorithm"). Fonte: best-practices e https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills.
- Sempre barras `/` nos caminhos (nunca `\`). Fonte: best-practices.

### 1.4 Progressive disclosure (como o agente carrega)
1. **Nível 1 — metadata** (~100 tokens/skill): `name` + `description` entram no system prompt no início para **todas** as skills instaladas.
2. **Nível 2 — instruções** (< 5k tokens recomendados): corpo do SKILL.md lido do filesystem (via bash/Read) só quando o agente decide ativar a skill.
3. **Nível 3+ — recursos**: `references/`, `assets/` só entram no contexto quando lidos; `scripts/` são **executados** e só a saída (stdout/stderr) consome tokens — o código nunca entra no contexto.

Fontes: https://agentskills.io/specification#progressive-disclosure; https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#how-skills-work (tabela "Level 1/2/3").

**Detalhes de runtime que afetam o desenho (Claude Code):**
- A listagem de skills tem orçamento de **1% da janela de contexto**; o texto `description` + `when_to_use` de cada skill é cortado em **1.536 chars**; com muitas skills, descrições são descartadas começando pelas menos usadas. Coloque o caso de uso principal **no início** da description. Fonte: https://code.claude.com/docs/en/skills ("Skill descriptions are cut short").
- O conteúdo do SKILL.md, uma vez invocado, **fica na conversa** (não é relido); após auto-compactação só os **primeiros 5.000 tokens** de cada skill são reanexados, dentro de um orçamento combinado de 25.000 tokens. Logo: **as regras mais importantes (limites, "nunca calcular") devem ficar no topo do SKILL.md**. Fonte: idem ("Skill content lifecycle").
- Codex: a lista inicial de skills usa no máx. **2% da janela** (ou 8.000 chars), encurta descrições primeiro; `skills.max_context_tokens` até 10.000. Fonte: https://learn.chatgpt.com/docs/build-skills (redirect de https://developers.openai.com/codex/skills).

---

## 2. O que faz uma description boa (gatilhos) e exemplos ruins

**Princípios (todos de fonte primária):**
- Dizer **o que faz + quando usar**, com termos que o usuário realmente digita. Spec: "Should include specific keywords that help agents identify relevant tasks". https://agentskills.io/specification#description-field
- **Terceira pessoa** (é injetada no system prompt): "Processes Excel files…" e não "I can help you…" / "You can use this…". https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#writing-effective-descriptions
- **Imperativo e focado na intenção do usuário**: "Use this skill when…"; descrever o que o usuário quer alcançar, não a mecânica interna. https://agentskills.io/skill-creation/optimizing-descriptions
- **Ser "pushy"**: modelos tendem a *sub*-acionar skills; listar explicitamente contextos, inclusive quando o usuário não nomeia o domínio ("even if they don't explicitly mention 'CSV'"). Fontes: optimizing-descriptions; skill-creator SKILL.md ("please make the skill descriptions a little bit 'pushy'"; "All 'when to use' info goes here, not in the body").
- Nuance importante: agentes só consultam skills para tarefas que exigem conhecimento além do básico — "read this PDF" pode não acionar a skill de PDF. Para nós isso é favorável: fechamento/comissão/divergência são domínio especializado. https://agentskills.io/skill-creation/optimizing-descriptions#how-skill-triggering-works
- Conciso: "A few sentences to a short paragraph"; limite duro 1024 chars; descrições crescem durante a otimização — vigiar. Idem.
- Para reduzir falsos positivos: dizer o que a skill **não** faz e a fronteira com capacidades vizinhas. Idem ("Revise the description").

**Exemplos ruins (da Anthropic):** `Helps with documents`, `Processes data`, `Does stuff with files`, `Helps with PDFs`, `Process CSV files.` Fontes: best-practices; spec.

**Exemplo bom (Anthropic):**
> `Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.`

**Antes/depois (agentskills.io):**
```yaml
# Before
description: Process CSV files.
# After
description: >
  Analyze CSV and tabular data files — compute summary statistics, add derived
  columns, generate charts, and clean messy data. Use this skill when the user
  has a CSV, TSV, or Excel file and wants to explore, transform, or visualize
  the data, even if they don't explicitly mention "CSV" or "analysis."
```

**Esboço aplicado à nossa skill (sugestão, ≤1024 chars, 3ª pessoa, gatilhos em PT e termos do financeiro):**
> Executa e explica o fechamento mensal da Tarvo (comissões por lojista, divergências de taxa, notas a emitir, remessa, conciliação de extratos e pendências) usando exclusivamente a CLI `python -m src` e a base de regras em `regras/`. Use quando a pessoa pedir para fechar/apurar o mês, conferir comissões ou taxas de checkout, listar notas ou pendências, perguntar "de onde vem esse número", ou quiser criar/alterar uma regra de negócio — mesmo que não diga "fechamento". Não calcula nem estima valores por conta própria; não serve para outras empresas ou planilhas genéricas.

---

## 3. Baixa liberdade onde erro custa caro; ciclos de validação; ambiente sem execução de código

### 3.1 Graus de liberdade (Anthropic)
- **Alta** (texto): várias abordagens válidas, heurísticas (ex.: code review).
- **Média** (pseudocódigo/script com parâmetros): há padrão preferido, alguma variação aceitável.
- **Baixa** (script exato, poucos/nenhum parâmetro): "operations are fragile and error-prone, consistency is critical, a specific sequence must be followed". Exemplo literal da doc:
  ```
  Run exactly this script:
  python scripts/migrate.py --verify --backup
  Do not modify the command or add additional flags.
  ```
  Analogia: "ponte estreita com precipício dos dois lados" → guardrails exatos. Fonte: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#set-appropriate-degrees-of-freedom. agentskills.io reforça: "Most skills have a mix. Calibrate each part independently." https://agentskills.io/skill-creation/best-practices#calibrating-control
- **Defaults, não menus**: um comando padrão com "escape hatch", nunca lista de alternativas equivalentes. Idem.
- **Prefira scripts para operações determinísticas** ("Write validate_form.py rather than asking Claude to generate validation code"); scripts são mais confiáveis, poupam tokens e garantem consistência. best-practices ("Provide utility scripts").
- **Estilo**: imperativo; "explain the why" em vez de MUST/ALWAYS/NEVER em caixa alta — o skill-creator trata ALWAYS/NEVER em maiúsculas como "yellow flag", e agentskills.io diz que instruções com motivo ("Do X because Y tends to cause Z") são seguidas com mais confiabilidade. Fontes: skill-creator SKILL.md; https://agentskills.io/skill-creation/evaluating-skills#iterating-on-the-skill. Observação: a própria doc da Anthropic sugere reforçar com "MUST filter" quando o modelo ignora uma regra — use com parcimônia e só em regras realmente invioláveis (os limites da seção 9.2).
- **Seção "Gotchas"** no SKILL.md: fatos do ambiente que contradizem suposições razoáveis — "the highest-value content in many skills". Cada correção que você fizer ao agente vira um item de gotcha. https://agentskills.io/skill-creation/best-practices#gotchas-sections
- **Terminologia consistente** (um termo só para cada conceito) e **nada datado** ("antes de agosto use X") — se precisar, seção "Old patterns" em `<details>`. best-practices.

### 3.2 Ciclos de validação (feedback loops)
- Padrão: **rodar validador → corrigir → repetir → só então prosseguir** ("Only proceed when validation passes"). best-practices ("Implement feedback loops").
- **Checklist copiável** para fluxos multi-etapa ("Copy this checklist and check off items as you complete them"). best-practices ("Use workflows for complex tasks").
- **Plan-validate-execute** para operações em lote/destrutivas: gerar plano estruturado (JSON) → validar com script contra fonte da verdade → executar → verificar. Mensagens de erro verbosas e acionáveis ("Field 'x' not found. Available fields: a, b, c"). best-practices ("Create verifiable intermediate outputs"); https://agentskills.io/skill-creation/best-practices#plan-validate-execute. **Isso mapeia direto em `regra propor` → mostrar diff → aprovação → `regra aplicar --aprovado-por` → `fechar` de novo.**
- **Design de scripts para agente** (agentskills.io/using-scripts): nunca prompt interativo (trava); `--help` curto; erros dizem o que estava errado, o que era esperado e o que tentar; saída **estruturada** (JSON/CSV) no stdout, diagnósticos no stderr; **códigos de saída distintos e documentados**; idempotência (agente pode repetir comandos); `--dry-run` para operações com estado; **saída de tamanho previsível** (harnesses truncam em ~10–30K chars — oferecer resumo + `--output arquivo`). https://agentskills.io/skill-creation/using-scripts#designing-scripts-for-agentic-use
- **"Solve, don't defer"**: scripts tratam erros em vez de "deixar o Claude descobrir"; nada de constantes mágicas sem justificativa. best-practices.

### 3.3 Quando o ambiente não executa código
- No **Claude.ai/Cowork, skills exigem code execution habilitado** — sem isso a seção Skills nem aparece ("Skills require the code execution environment to function"). https://support.claude.com/en/articles/12512180-using-skills-in-claude. Ou seja, no ecossistema Claude o cenário "skill carregada mas sem execução" praticamente não ocorre; ele ocorre em outros agentes (ex.: chat do Copilot sem shell) ou quando o modo de rede/sandbox bloqueia algo.
- A doc não prescreve texto para esse caso; a orientação aplicável é "state prerequisites… rather than assuming the agent's environment has them" e usar `compatibility` para requisitos de runtime. https://agentskills.io/skill-creation/using-scripts. A regra da nossa seção 9.2 ("dizer que não é possível fechar ali e apontar `COMO_FECHAR_O_MES.md`; não tentar fazer à mão") é coerente com "baixa liberdade" e com o princípio de que a skill não deve degradar para cálculo manual. Reforce **no topo** do SKILL.md e repita como gotcha: "Se não houver shell/Python, pare e explique; não calcule."
- **Diferença API vs Claude.ai**: na API o container **não tem rede nem instala pacotes**; no Claude.ai depende do admin (Team: "package managers only" por padrão; Enterprise: egress **off** por padrão). Listar pacotes no SKILL.md e checar que existem no container. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#runtime-environment-constraints; https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude.

---

## 4. Empacotar e distribuir

### 4.1 Zip / `.skill`
- **Zipar a pasta, não os arquivos soltos**; a pasta da skill é a raiz do arquivo e **o nome da pasta tem de ser igual ao `name`**:
  ```
  fechamento-tarvo.zip
  └── fechamento-tarvo/
      ├── SKILL.md
      └── references/ …
  ```
  Fonte: https://support.claude.com/en/articles/12512198-creating-custom-skills. Para a Skills API: `SKILL.md` na raiz do upload **ou** dentro de uma única pasta envolvente; `zip -r financial_skill.zip financial_skill/`. https://platform.claude.com/docs/en/build-with-claude/skills-guide
- `anthropics/skills` tem `scripts/package_skill.py` (`python -m scripts.package_skill <pasta>`) que gera um arquivo **`.skill`** (zip renomeado) e **valida o frontmatter** com as mesmas regras do upload. Fontes: skill-creator SKILL.md; https://code.claude.com/docs/en/skills (menciona `package_skill.py` como caminho que aplica a validação dos 6 campos).
- Erros comuns de upload listados pelo Help Center: tamanho do zip, nome da pasta ≠ `name`, SKILL.md ausente, caracteres inválidos em `name`/`description`. https://support.claude.com/en/articles/12512180-using-skills-in-claude. **[NÃO CONFIRMADO]** o valor numérico do limite de zip no Claude.ai — nenhum artigo o declara. Referências disponíveis: Skills API = **30 MB descompactado**; arquivos no sandbox do Claude.ai = **30 MB por arquivo** (upload/download).

### 4.2 Claude.ai (web/desktop)
- Habilitar: **Settings > Capabilities > "Code execution and file creation"** (Free/Pro/Max) ou **Organization settings > Plugins & skills > Policy** (Team/Enterprise: ligar "Cloud code execution and file creation" e "Skills"). https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude; https://support.claude.com/en/articles/13119606
- Upload individual: **Customize > Skills > "+" > "+ Create skill" > "Upload a skill"** → zip; depois ligar o toggle. https://support.claude.com/en/articles/12512180-using-skills-in-claude
- **Provisionar para a organização (Team/Enterprise, só Owners):** Organization settings > Plugins & skills > **Add > Upload a skill** (zip com SKILL.md). Vai para todos os membros, ligada por padrão (usuário pode desligar). Para subgrupo (Enterprise): empacotar como **plugin** e atribuir ao grupo. Alternativa: usuário publica na biblioteca da org ("Publish to org"), com revisão opcional (Owner aprova; ninguém aprova a própria). Skills provisionadas aparecem **no chat, no Cowork e no Claude Code** de quem loga com a conta. https://support.claude.com/en/articles/13119606
- **Atenção à divergência:** a doc da plataforma ainda diz "Custom Skills are individual to each user… cannot be centrally managed by admins" (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#claudeai). O Help Center (mais recente) descreve provisioning org-wide em detalhe. Siga o Help Center.
- Enterprise pode ligar **Skill and plugin security scanning** (bloqueia skills reprovadas). https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise#skill-content-scanning

### 4.3 Claude Code
- Locais: pessoal `~/.claude/skills/<name>/SKILL.md`; projeto `.claude/skills/<name>/SKILL.md` (commitar para o time); aninhado `<subdir>/.claude/skills/`; enterprise (managed settings); plugin `<plugin>/skills/<name>/`. Precedência em conflito de nome: enterprise > pessoal > projeto. https://code.claude.com/docs/en/skills
- Invocação: automática pela description ou `/fechamento-tarvo`. Substituições úteis: `${CLAUDE_SKILL_DIR}` (pasta do SKILL.md), `${CLAUDE_PROJECT_DIR}`, `$ARGUMENTS`. `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/x.py *)` permite rodar script bundled sem prompt. Idem. **Mas** `${CLAUDE_*}`, `!`comando`` e `@arquivo` são recursos só do Claude Code: em skills **sincronizadas do claude.ai** eles chegam como texto literal/placeholder; no Claude.ai/API não funcionam. Idem ("How Claude Code handles the body of a synced skill"; "Using skill frontmatter outside Claude Code").
- **Sync com a conta claude.ai**: desde v2.1.273, Claude Code no terminal logado com conta claude.ai baixa as skills habilitadas (pessoais + provisionadas pela org) para `~/.claude/skills/synced/` e as expõe como `/anthropic-skills:<name>` (ou `/<name>` se livre). Desligar com `syncClaudeAiSkills: false`. Nunca edite em `synced/` (é sobrescrito). Idem ("Skills synced from claude.ai").
- Validação local: `claude plugin validate .claude/skills` (v2.1.233+) acha frontmatter inválido. Troubleshooting de trigger: description com palavras que o usuário diz; `What skills are available?`; `--debug`. Idem.

### 4.4 Cowork (Claude Desktop)
- **Cowork não lê `~/.claude/skills/` da máquina**; sessões Cowork (interativas e agendadas) carregam **as skills habilitadas na conta claude.ai**, sincronizadas no início da sessão; gerencia-se em **Customize** na sidebar do Desktop ou nas configurações de skills do claude.ai. Sessões cloud do Claude Code adicionalmente carregam `.claude/skills/` do repo clonado. https://code.claude.com/docs/en/skills#skills-in-cowork-and-cloud-sessions. **[NÃO CONFIRMADO]** se Cowork carrega `.claude/skills/` de uma pasta local anexada — a doc só afirma isso para "cloud sessions".
- Cowork roda código em **VM Linux isolada** (sessões locais: Apple Virtualization/Hyper-V) ou em **sandbox cloud da Anthropic** (padrão atual); pastas conectadas ficam acessíveis; MCP locais não rodam em sessão cloud. https://support.claude.com/en/articles/14479288. **[NÃO CONFIRMADO]** versão de Python/pacotes disponíveis na VM do Cowork — a doc não lista.
- Em Cowork, linhas `!`cmd`` do SKILL.md são substituídas por placeholder (não executam). code.claude.com/docs/en/skills.
- Skill-creator está disponível no Cowork ("ask Claude to package a completed workflow, using the built-in skill-creator"). https://academy.claude.com/tutorials/customize-claude-cowork

### 4.5 `scripts/` e dependências no sandbox
- **Skills API / container do code execution tool** [CONFIRMADO]: **Python 3.11**; 5 GiB RAM, 5 GiB disco, 1 CPU; **sem internet** ("Completely disabled"), sem instalar pacotes em runtime; containers expiram em 30 dias; pré-instalados incluem **pandas, numpy, scipy, scikit-learn, statsmodels, pyarrow, openpyxl, xlsxwriter, xlrd, pillow, python-pptx, python-docx, pypdf, pdfplumber, reportlab**… https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool (seção "Runtime environment"/"Pre-installed libraries").
- **Claude.ai** [CONFIRMADO]: sandbox isolado com Python/JS; rede depende do nível configurado — **Off** (só pré-instalado), **Package managers only** (padrão Team; registries aprovados: pypi.org, files.pythonhosted.org, registry.npmjs.org, github.com…), **+ domínios específicos**, **All domains**; Free/Pro/Max têm instalação de pacotes ligada por padrão; **Enterprise começa com egress off**; 30 MB por arquivo. https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude. **[NÃO CONFIRMADO]** versão exata do Python no sandbox do Claude.ai e a lista de pacotes pré-instalados (a doc da plataforma remete à lista do code execution tool, que é a do container da API).
- Consequência: **pandas + openpyxl são seguros** (pré-instalados na API; instaláveis no Claude.ai com "package managers only"; já existem no ambiente do Claude Code do usuário se o `requirements.txt` for instalado). Qualquer dependência fora dessa lista é risco em Enterprise com egress off.
- Claude Code: rede total; "Global package installation discouraged: Skills should only install packages locally". overview#runtime-environment-constraints.
- Scripts autocontidos: agentskills.io recomenda PEP 723 (`# /// script` + `uv run`) para declarar deps inline, mas isso exige `uv` no ambiente — **não assuma** no sandbox do Claude.ai/API. https://agentskills.io/skill-creation/using-scripts
- Segurança/vetting enterprise: scripts, chamadas de rede, credenciais hardcoded e referências MCP são "High concern"; nunca segredos no zip. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise

---

## 5. Portabilidade: Codex, Cursor, Copilot

### 5.1 Quem já lê SKILL.md nativamente [CONFIRMADO]
A vitrine oficial lista Claude, Claude Code, ChatGPT & Codex, Cursor, GitHub Copilot, VS Code, Gemini CLI, Goose, OpenCode, OpenHands, Amp, Factory, Junie, Kiro, Roo Code, Letta, etc. https://agentskills.io/clients

| Agente | Onde procura skills | Frontmatter que lê | Observações |
|---|---|---|---|
| **Codex** (CLI/IDE/ChatGPT) | repo: `.agents/skills/` em cada dir do cwd até a raiz; usuário `~/.agents/skills`; admin `/etc/codex/skills`; **segue symlinks** | `name`, `description` (+ opcional `agents/openai.yaml` com `interface`, `policy.allow_implicit_invocation`, `dependencies.tools`) | invocação `$skill-name` ou implícita; lista inicial ≤2% do contexto; `$skill-creator` e `$skill-installer` embutidos. https://learn.chatgpt.com/docs/build-skills |
| **Cursor** | projeto `.cursor/skills/`, `.agents/skills/`; usuário `~/.cursor/skills/`, `~/.agents/skills/`; **compat: `.claude/skills/`, `.codex/skills/`** e equivalentes em `~` | `name` (= nome da pasta), `description`, `paths`, `disable-model-invocation`, `icon`, `color`, `metadata` | automático ou `/skill`; skills aninhadas em subpastas ficam escopadas; só `~/.cursor/skills` sincroniza para Cloud Agents; `/create-skill`, `/migrate-to-skills`. https://cursor.com/docs/context/skills |
| **GitHub Copilot** (cloud agent, code review, CLI, app, VS Code, JetBrains) | projeto `.github/skills/`, **`.claude/skills/`**, `.agents/skills/`; pessoal `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` | `name` (≤64, = pasta), `description` (≤1024); VS Code também: `argument-hint`, `user-invocable`, `disable-model-invocation`, `context: fork` | automático ou `/skill-name`; recursos referenciados com link Markdown ou `#file:`; `gh skill` instala de repos. https://docs.github.com/en/copilot/concepts/agents/about-agent-skills; https://code.visualstudio.com/docs/copilot/customization/agent-skills |

### 5.2 Arquivos de instrução (não-skill) e como apontar para a skill
- **AGENTS.md** (padrão aberto, Agentic AI Foundation/Linux Foundation): Markdown livre, sem campos obrigatórios, na raiz do repo; aninhado em monorepo; o mais próximo vence; prompt do usuário sobrepõe. Lido por Codex, Cursor, Copilot coding agent, Gemini CLI, Jules, Factory, Amp, Devin, Windsurf, Zed, Warp, Aider, Junie… https://agents.md/
- **Codex**: concatena `~/.codex/AGENTS.md` (ou `AGENTS.override.md`) + um arquivo por diretório da raiz até o cwd; **limite combinado padrão 32 KiB** (`project_doc_max_bytes`); verificar com `codex --ask-for-approval never "Summarize the current instructions."`. https://learn.chatgpt.com/docs/agent-configuration/agents-md
- **Cursor rules**: `.cursor/rules/*.mdc` com `description`/`globs`/`alwaysApply` (tipos Always / Apply Intelligently / Specific Files / Manual); **AGENTS.md suportado** (raiz e subpastas); manter cada regra < 500 linhas. https://cursor.com/docs/context/rules
- **Copilot**: `.github/copilot-instructions.md` (repo inteiro), `.github/instructions/*.instructions.md` com `applyTo` (globs), **`AGENTS.md` em qualquer pasta** (mais próximo vence) e **`CLAUDE.md`/`GEMINI.md` na raiz** também são lidos pelo coding agent. https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions

**Como apontar da instrução para a skill (recomendação derivada das fontes):**
1. Manter a skill **também** num local de descoberta nativo: `.claude/skills/fechamento-tarvo/` cobre Claude Code, Cursor (compat) e Copilot; `.agents/skills/fechamento-tarvo/` cobre Codex, Cursor e Copilot. Uma pasta `skills/fechamento-tarvo/` na raiz do repo **não é lida automaticamente por nenhum deles**. Codex segue symlinks (confirmado); **[NÃO CONFIRMADO]** se Cursor/Copilot seguem symlinks — se precisar garantir, copiar em vez de linkar (ou gerar as cópias no `empacotar-skill`).
2. No AGENTS.md (≤ 1 página, < 32 KiB), além do resumo do fluxo/limites, dizer explicitamente: "Antes de qualquer tarefa de fechamento, leia `skills/fechamento-tarvo/SKILL.md` e siga-o; se o seu agente suporta skills, invoque `fechamento-tarvo`." Codex/Copilot Chat sem suporte a skills ainda leem o caminho e abrem o arquivo.
3. Codex: opcionalmente adicionar `agents/openai.yaml` com `interface.display_name` em PT para a UI (campo fora da spec, mas fica fora do frontmatter, então não quebra o upload no Claude.ai).

---

## 6. Avaliar/testar a skill (evals), skill-creator e armadilhas

### 6.1 Processo recomendado pela Anthropic
- **Evals antes de documentação extensa**: rodar o agente sem skill em tarefas reais → documentar falhas → criar 3 cenários → baseline → escrever o **mínimo** de instrução que passa → iterar. "Evaluations are your source of truth". https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#build-evaluations-first
- Formato de eval (Anthropic): `{"skills": [...], "query": "...", "files": [...], "expected_behavior": [...]}`. "There is not currently a built-in way to run these evaluations." Idem.
- **Claude A / Claude B**: um Claude ajuda a escrever/refinar; outro (contexto limpo) executa; observar onde erra e voltar ao A. Idem.
- Testar com **todos os modelos** que vão usar (Haiku precisa de mais guia; Opus de menos). Idem.
- Checklist final da Anthropic: description específica com termos-chave; corpo < 500 linhas; refs a um nível; sem info datada; terminologia consistente; exemplos concretos; scripts com erros explícitos e sem constantes mágicas; pacotes listados e verificados; validação para operações críticas; **≥ 3 evals**; testado com Haiku/Sonnet/Opus; cenários reais; feedback do time. Idem.
- Enterprise: suite de **3–5 queries** por skill cobrindo deve-acionar, não-deve-acionar e ambíguos; dimensões: trigger accuracy, isolamento, coexistência, instruction following, qualidade. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise#evaluating-skills-before-deployment

### 6.2 Formato de evals do padrão aberto (agentskills.io + skill-creator)
- `evals/evals.json` dentro da skill: `{"skill_name": "...", "evals": [{"id": 1, "prompt": "...", "expected_output": "...", "files": ["evals/files/x.csv"], "assertions": ["...", "..."]}]}`. Começar com 2–3 casos; variar fraseado/formalidade; ≥1 caso de borda; prompts realistas (caminhos, nomes de colunas). Assertions só depois da primeira rodada; devem ser verificáveis ("output é JSON válido", "tem ≥3 recomendações"), não vagas nem frágeis. https://agentskills.io/skill-creation/evaluating-skills
- Rodar cada caso **com e sem skill** (ou vs. versão anterior), em **contexto limpo** (subagente ou sessão nova); gravar `timing.json` (tokens, duração), `grading.json` (PASS/FAIL com evidência), `benchmark.json` (delta). Remover assertions que sempre passam nos dois braços; investigar as que sempre falham. Revisão humana em `feedback.json`. Idem.
- **Evals de trigger** (description): ~20 queries, 8–10 deve-acionar e 8–10 não-deve-acionar com **near-misses** (compartilham vocabulário mas precisam de outra coisa); 3 runs por query; limiar 0,5; split treino 60% / validação 40% para não sobreajustar; ≤5 iterações. Script bash exemplo usa `claude -p ... --output-format json` e detecta `tool_use` com `name == "Skill"`. https://agentskills.io/skill-creation/optimizing-descriptions
- **skill-creator** (github.com/anthropics/skills/skills/skill-creator; também plugin oficial do Claude Code e embutido no Claude.ai/Cowork/Codex): fluxo capturar intenção → entrevistar → rascunhar → testar com evals → iterar → empacotar; automatiza grading (`agents/grader.md`), benchmark (`scripts.aggregate_benchmark`), viewer HTML, comparação cega A/B e o loop de otimização de description (exige `claude` CLI). Fontes: SKILL.md do skill-creator; https://code.claude.com/docs/en/skills (menciona o plugin `skill-creator` e `claude plugin eval` com grader `tool_used: Skill`).

### 6.3 Armadilhas comuns (fontes primárias)
- Description vaga ou em 1ª/2ª pessoa → não aciona. best-practices.
- Skill gerada "do nada" pelo LLM sem contexto de domínio → procedimentos genéricos ("handle errors appropriately"). Partir de uma tarefa real feita com o agente ou de artefatos do projeto. https://agentskills.io/skill-creation/best-practices#start-from-real-expertise
- SKILL.md enciclopédico → o agente segue instruções que não se aplicam ("Aim for moderate detail"). Idem.
- Referências aninhadas → leitura parcial com `head`. best-practices.
- Muitas opções sem default. best-practices.
- Caminhos Windows. best-practices.
- Assumir pacote instalado / rede. best-practices; overview.
- Nome de ferramenta MCP sem prefixo do servidor (`Server:tool`). best-practices.
- Regra que **precisa valer sempre** colocada só no SKILL.md: após compactação o Claude Code pode manter só os 5k tokens iniciais; a doc sugere mover regras invioláveis para **hooks** (campo `hooks` do frontmatter — mas é campo só do Claude Code, quebraria o upload no Claude.ai). Para skill portátil: regras críticas no topo + validação **no código** (o motor recusa, não a skill). https://code.claude.com/docs/en/skills#claude-stops-following-a-skill
- Mesmo nome em outro local/skill → conflito e aliasing (`anthropic-skills:` reservado). Idem.
- Skills **não sincronizam entre superfícies** (claude.ai ↔ API ↔ Claude Code filesystem); exceção: skills da conta claude.ai → Cowork/Claude Code via sync. Git como fonte única da verdade. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview#cross-surface-availability; enterprise.
- Frontmatter YAML inválido: Claude Code carrega o corpo com metadata vazia (`/name` funciona, trigger automático não). code.claude.com.
- Prompt interativo em script → trava o agente. using-scripts.

---

## 7. Limites relevantes (tabela)

| Item | Valor | Fonte |
|---|---|---|
| `name` | ≤64 chars, `a-z0-9-`, = pasta, sem "anthropic"/"claude", sem XML | spec; platform overview |
| `description` | ≤1024 chars, não vazia, sem XML | spec; platform overview |
| `compatibility` | ≤500 chars | spec |
| Corpo SKILL.md | <500 linhas / <5k tokens (recomendação) | spec; best-practices |
| Listagem no Claude Code | 1% do contexto; 1.536 chars por skill (`description`+`when_to_use`) | code.claude.com/docs/en/skills |
| Pós-compactação (Claude Code) | 5.000 tokens por skill, 25.000 combinados | idem |
| Listagem no Codex | 2% do contexto ou 8.000 chars; `max_context_tokens` ≤10.000 | learn.chatgpt.com/docs/build-skills |
| Upload Skills API | 30 MB descompactado; 20 skills por request; versões são snapshots completos | platform skills-guide |
| Zip no Claude.ai | **[NÃO CONFIRMADO]** valor não publicado; erro "check the ZIP size" existe | support 12512180 |
| Arquivos no sandbox Claude.ai | 30 MB por arquivo (upload/download) | support 12111783 |
| Container API (code execution) | Python **3.11**; 5 GiB RAM; 5 GiB disco; 1 CPU; **sem rede**; expira em 30 dias; 90 s por célula REPL (PTC) | platform code-execution-tool |
| Rede no Claude.ai | Off / Package managers only (Team default) / + domínios / All; Enterprise default **off**; Free/Pro/Max ligado | support 12111783 |
| Python no Claude.ai/Cowork | **[NÃO CONFIRMADO]** versão não publicada | — |
| AGENTS.md no Codex | 32 KiB combinados (default) | learn.chatgpt.com agents-md |
| Cursor rules | <500 linhas por regra | cursor.com/docs/context/rules |
| Evals | ≥3 (Anthropic); 3–5 queries por skill (enterprise); ~20 queries de trigger | best-practices; enterprise; agentskills.io |

---

## 8. O que na seção 9 da ESPECIFICACAO.md parece errado, incompleto ou desatualizado

1. **Frontmatter só com `name`/`description`** — correto como mínimo, mas convém adicionar `compatibility: "Requer Python 3.11+ com pandas e openpyxl; executa a CLI python -m src"`, `license` e `metadata: {version, author}`. **Não** usar campos do Claude Code (`when_to_use`, `argument-hint`, `hooks`, `paths`…) nem `dependencies`: o upload no Claude.ai falha com erro duro. (code.claude.com "Using skill frontmatter outside Claude Code")
2. **`evals/cenarios.md` manual** — o padrão (agentskills.io, skill-creator, Anthropic) é `evals/evals.json` com `prompt`/`expected_output`/`files`/`assertions`, rodado com e sem skill, mais um conjunto de ~20 queries de trigger com **near-misses negativos** (ex.: "monta um DRE da Tarvo", "quanto é 2,59% de 10 mil", "fecha o caixa do restaurante"). Os 6 cenários da 9.4 viram `evals` com assertions verificáveis (ex.: "a resposta cita o `resumo.json` e não contém número ausente dele"). Manter `cenarios.md` como registro humano é ok, mas adotar o JSON.
3. **`scripts/` = cópia do `src/` + `regras_iniciais/` na raiz da skill** — permitido (qualquer arquivo é aceito), mas: (a) `python -m src` depende do cwd; dentro da skill o caminho será `<skill>/scripts/src/`, e no Claude.ai a pasta da skill é read-only e tem caminho absoluto desconhecido a priori → os comandos no SKILL.md devem ser relativos à raiz da skill ("o agente roda a partir da raiz da skill" — agentskills.io using-scripts) ou o script deve descobrir seu próprio diretório; (b) `regras_iniciais/` encaixa melhor em `assets/regras_iniciais/` (convenção para "data files, lookup tables"); (c) o motor deve gravar saídas **fora** da pasta da skill (cwd/`saidas/`), nunca dentro dela.
4. **"A mesma skill funciona no Cowork e no Claude Code"** — verdadeiro **só via conta claude.ai**: Cowork não lê `~/.claude/skills/` nem (confirmado) `.claude/skills/` do projeto; ele carrega as skills habilitadas/provisionadas na conta. Claude Code terminal recebe-as por sync (v2.1.273+). Para o fluxo "pasta no computador" funcionar no Cowork, a skill tem de estar **provisionada na org ou habilitada na conta**, e o motor precisa aceitar caminhos de pastas conectadas. Além disso, `!`cmd``, `@arquivo` e `${CLAUDE_PROJECT_DIR}` não funcionam em skills sincronizadas — não usar.
5. **Provisionamento** — a 9.5 está certa (Owner liga Code execution + Skills e provisiona), mas o caminho atual é **Organization settings > Plugins & skills > Policy** e **Add > Upload a skill**; a doc da plataforma que diz "não há distribuição org-wide" está desatualizada. Em Enterprise, egress de rede vem **desligado**: pandas/openpyxl precisam já existir no sandbox (na API existem; no Claude.ai não há lista publicada — testar antes do demo).
6. **"SKILL.md < 300 linhas"** — mais restritivo que o padrão (500/5k tokens); ok. Mas acrescentar: **limites e "nunca calcular" no topo** (só os 5k primeiros tokens sobrevivem à compactação no Claude Code) e a description com o caso principal nas primeiras palavras (corte em 1.536 chars na listagem).
7. **Portabilidade (9.6)** — `AGENTS.md` apontando para `skills/fechamento-tarvo/` cobre quem só lê AGENTS.md, mas Codex, Cursor e Copilot **já leem SKILL.md nativamente** em `.agents/skills/` e `.claude/skills/`; a pasta `skills/` na raiz não é descoberta por nenhum. Recomendação: fonte em `skills/fechamento-tarvo/` + cópias/symlinks em `.claude/skills/` e `.agents/skills/` geradas pelo `empacotar-skill`; AGENTS.md curto (<32 KiB no Codex) dizendo "leia e siga `…/SKILL.md`". Opcional: `agents/openai.yaml` para UI do Codex.
8. **Comportamento sem execução de código** — coerente com o padrão; só notar que no Claude.ai a skill nem carrega sem code execution, então a mensagem "não posso fechar aqui" vale sobretudo para outros agentes/chats; manter e repetir como gotcha.
9. **Nome** `fechamento-tarvo` — válido (sem palavras reservadas, kebab-case, = pasta). Zip deve conter `fechamento-tarvo/SKILL.md` na raiz do arquivo.
10. **Empacotamento** — além do zip, validar com `skills-ref validate` ou `claude plugin validate .claude/skills` e, se possível, `python -m scripts.package_skill` do repo anthropics/skills (gera `.skill` e aplica as mesmas regras do upload).
