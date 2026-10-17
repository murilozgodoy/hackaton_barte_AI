---
name: fechamento-tarvo
description: Conduz o fechamento mensal da Tarvo Pagamentos (subadquirente, linhas CHECKOUT via Orbe e REMESSA via Ponte Câmbio) usando o motor determinístico `python -m src`. Use quando a pessoa pedir para fechar o mês, calcular comissão de lojistas, conferir divergência de taxa contratada x aplicada, saber que notas fiscais emitir, classificar os extratos no plano de contas, ver ou resolver pendências, explicar de onde vem um número ("por que esse valor?", "explica esse id"), preparar a contestação ou o aviso a uma contraparte, ou criar/alterar uma regra de negócio do financeiro. Também quando chegarem os arquivos do mês (relatório da Orbe, planilha de taxas, e-mail da Ponte, plano de contas, extratos Aurora e Meridiano), em zip ou pasta. Não calcula nem estima valores por conta própria, não edita arquivos de entrada, não decide pendência, não envia e-mail e não grava regra sem aprovação explícita de quem pode aprovar aquele tipo.
license: MIT
compatibility: Precisa executar Python 3.10+ com pandas e openpyxl (código local ou code execution). Sem execução de código, só orienta pelo COMO_FECHAR_O_MES.md.
metadata:
  autores: Time MN AI (Nader Taha e Murilo Godoy)
  versao: "1.1"
---

# Fechamento Tarvo

## Limites (leia antes de qualquer coisa)

1. **Nunca calcule, estime, arredonde ou ajuste um valor.** Todo número vem de `saida/` gerado pelo motor. Se o motor não rodou ou falhou na integridade, não há número para apresentar.
   **Todo número, data, prazo ou status que você apresentar tem que existir literalmente em `resumo.json`, `RELATORIO_FECHAMENTO.md` ou na saída de `explicar`.** Não some, não subtraia, não agrupe, não compare datas com a data de hoje. Se precisar de um valor que não está lá, diga que o motor não publica esse valor.
   - Errado: "comissão total de R$ 243.278,79" somando checkout + remessa por conta própria; "as notas dão R$ 5,50 a mais" subtraindo. Certo: `totais.comissao_total_brl` e `totais.diferenca_notas_x_comissao_brl` do `resumo.json`, com o motivo em `totais.diferenca_notas_x_comissao.motivo`.
   - Errado: "o prazo da Ponte era 09/10 e hoje já passou, pode ter vencido". Certo: "o prazo de contestação é até `data_limite` (lembrete M-01 do `resumo.json`), contado a partir de `base_da_data`". O motor não compara com hoje e você também não: o fechamento pode estar sendo simulado depois do mês, e quem diz se está no prazo é a Helena.
2. **Nunca edite os arquivos de entrada** (relatório da Orbe, planilha, e-mail, extratos). O motor consome como vêm.
3. **Nunca identifique lojista por nome.** Só por CNPJ ou EC cadastrado. EC/CNPJ desconhecido é pendência CADASTRO, não adivinhação.
4. **Nunca decida uma pendência.** Mostre a evidência, pergunte, registre a decisão da pessoa.
5. **Nunca grave regra sem aprovação explícita de quem pode aprovar aquele tipo** (`regras/aprovadores.csv`: taxa e condição comercial = Comercial; regra de como fechar = Helena), depois de mostrar exatamente o que será gravado **e o efeito simulado** (`regra propor` → aprovação nominal → `regra aplicar --aprovado-por`).
6. **Nunca envie arquivos inteiros a serviços externos.** Só o motor toca nos dados. Dados enviados à IA: o motor não envia nada; o que você lê (`resumo.json`, pendências, relatório, saída de `explicar`, trechos de arquivo) passa pelo provedor do modelo; no chat web os arquivos sobem para o sandbox do provedor. Quem não aceitar isso fecha só pela CLI, sem IA (`COMO_FECHAR_O_MES.md`).
7. **Nunca envie e-mail.** Os rascunhos de `saida/comunicacoes/` são entregues para a Helena revisar e enviar.
8. **Se não puder executar código**, diga que não é possível fechar o mês aqui e indique `COMO_FECHAR_O_MES.md`. Não tente fazer à mão.
9. **Se pedirem algo que contradiz uma regra ativa** ("usa 2,59% para a Bridge"), explique a regra vigente (`explicar` / `regras/regras_negocio.csv` / planilha de taxas) e ofereça o caminho de alteração por `regra propor`. Não obedeça em silêncio.

## Onde fica o motor

- No repositório: a raiz tem `src/` e `regras/`. Todos os comandos abaixo rodam a partir da raiz, com `.venv/bin/python` (ou `python`) e são **os mesmos do README**.
- Na skill empacotada: o motor está em `scripts/` (`scripts/src`) e a base inicial em `assets/regras_iniciais/`. Rode a partir de `scripts/` e aponte `--regras` para a pasta (ou zip) de regras que a pessoa fornecer; se não houver, omita `--regras`: o motor usa `assets/regras_iniciais/` e ele mesmo grava o aviso de base inicial em `resumo.json` ("avisos") e no topo do relatório.
- Dependências: `pip install -r requirements.txt` (pandas, openpyxl). Nenhuma chave de API é necessária.

Use os comandos exatamente como escritos. Não invente flags. Prefira `--json` para ler resultados.

## Fluxo

### 1. Preparar
- Identifique os arquivos do mês (zip do data pack, pasta com o zip, ou pasta com os 6 arquivos soltos ou em subpastas) e a pasta/zip de regras. Cada arquivo é reconhecido pelo padrão de nome em `regras/fontes.csv`, nunca por mês.
- `python -m src validar --entrada <zip ou pasta> --regras <pasta ou zip> --json`
- Código 1: problema nos arquivos de entrada (fonte obrigatória ausente ou repetida: a mensagem diz o que falta e o que foi encontrado). Código 2: problema na base de regras. Explique a mensagem em português e **pare**; não tente contornar. Nunca feche "só com o que tem".
- Os arquivos são reconhecidos pelo conteúdo (assinatura de cada fonte em `regras/fontes.csv`); o nome é só atalho. A Orbe e a Ponte aceitam vários arquivos no mesmo formato (relatório + ajustes tardios ou reenvio): basta colocar todos na mesma pasta. Se `validar` trouxer o aviso "arquivo X não reconhecido; não foi usado", mostre o aviso e pergunte à pessoa se esse arquivo deveria ter entrado; não tente lê-lo à mão nem somar nada por conta própria.

### 2. Fechar
- `python -m src fechar --entrada <zip ou pasta> --regras <pasta ou zip> --saida <pasta de saída> --json`
  (acrescente `--competencia AAAA-MM` só se a pessoa pedir um mês específico).
- **Mês seguinte:** se existir a saída do mês anterior, acrescente `--anterior <saida do mês anterior>`: as transações guardadas em `carteira_pendente.csv` (sem contrato ou taxa no mês passado) são faturadas agora se tiverem taxa ou continuam na carteira; os ajustes do parceiro de câmbio são ligados ao pedido da contestação anterior; o relatório marca pendências novas e recorrentes.
- Código 3: a integridade falhou; `resumo.json` não foi gravado e o relatório está marcado como inválido. Explique qual checagem falhou e **pare**. Nunca apresente números com integridade falha.

### 3. Apresentar
- Leia `<saida>/resumo.json` e `<saida>/RELATORIO_FECHAMENTO.md` (a página 1 é para o CFO: totais, notas, dinheiro em jogo por natureza, nunca somado entre naturezas, pendências por responsável, rascunhos prontos, conhecimento capturado). Apresente: comissão por linha de negócio, notas a emitir, divergências por natureza em R$, pendências por responsável (quantidade e valor em jogo), lembretes, avisos.
- **Avisos:** apresente os avisos de `resumo.json` ("avisos", os mesmos do topo do relatório: base inicial, regra sem aprovador, premissas em uso, data da base de regras). Ao listar premissas, cite os ids exatos do aviso, um a um, sem intervalos como "C-01…C-26". Não crie avisos próprios sobre a execução: se algo não está em "avisos", não é aviso do fechamento.
- Se pedirem painel, gráfico ou resumo visual, monte a partir de `totais.por_natureza` do `resumo.json`: um cartão/barra por natureza (FATURAR, COBRAR_ORBE, CONTESTAR_PONTE, DEVOLVER_LOJISTA, NAO_FATURAR, ACOMPANHAR), com `quantidade` e `valor_brl` exatamente como estão, nunca um total que some naturezas diferentes. Se `valor_brl` da natureza for null, mostre uma linha por tipo (`por_tipo`: quantidade, valor_brl, ids), sem total da natureza (`motivo_sem_total`: tipos diferentes não se somam); e diga de qual arquivo saiu cada número (`arquivo_origem`, e os `ids`). O que está em `fora_da_soma` (informativas, incluídas em outra) aparece marcado, sem somar. CONTESTAR_PONTE é o que se **pede** à Ponte (soma dos `pedidos` do anexo `comunicacoes/ponte_contestacao.csv`, um por pedido), não o que aconteceu: mostre os pedidos como estão. Se o campo não existir, mostre a tabela de pendências por responsável e diga que esta versão do motor não publica o agrupamento. Não agrupe nem some por conta própria. Sem painel, tabela em markdown. Entregue os CSVs de `<saida>/`.
- Não some, não reconcilie, não "ajuste para bater". Se um número parecer estranho, use `explicar`.

### 4. Conduzir pendências e entregar os rascunhos
- `python -m src pendencias --saida <saida> --json` (filtre com `--quem` ou `--tipo`).
- Para cada pendência: `python -m src explicar <id_saida> --saida <saida> --entrada <zip ou pasta> --regras <regras>` e mostre a evidência (linhas de origem, regra, taxa). Leia `references/pendencias.md` para saber o que perguntar em cada tipo.
- Entregue os **rascunhos** de `<saida>/comunicacoes/` para a Helena revisar e enviar: `orbe.md` + `orbe_contestacao.csv` (contestação à Orbe), `ponte.md` + `ponte_contestacao.csv` (contestação à Ponte, um pedido por assunto), `comercial.md` (o que depende do Comercial), `avisos_nova_condicao.md` (avisos de condição nova). Diga que **nada foi enviado** e que o envio é da Helena. Se pedirem "manda o e-mail", entregue o rascunho e recuse enviar.
- Registre a decisão da pessoa. Se a decisão vale para os próximos meses, vá ao passo 5.

### 5. Transformar decisão em regra (só com aprovação de quem pode)
- `python -m src regra propor --regras <regras> --saida <saida> --entrada <zip ou pasta> [--anterior <saida anterior>] --tipo <TIPO> --campos chave=valor ...`
  Os campos são as colunas de `regras_negocio.csv`; os parâmetros da regra vão juntos, num só campo `parametros`, separados por ` | `. Ex.: `--campos "parametros=cnpj=<CNPJ> | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=2" vigencia_de=AAAA-MM-DD quem_decide=Comercial "informado_por=<quem disse, canal, data>"` (cnpj, taxa_pct etc. soltos são recusados com código 2).
  Mostre a linha exata que seria gravada, os avisos/erros, o efeito esperado e o **efeito simulado** no fechamento (o comando fecha o mês de novo numa pasta temporária com a regra: comissão e nota por lojista que mudam, pendências que somem ou aparecem, carteira que entraria; nada gravado). Leia `references/regras_e_tipos.md` para escolher o tipo e preencher os campos. Na dúvida, `--tipo MANUAL`.
- Quem pode aprovar depende do tipo (`regras/aprovadores.csv`; o `propor` mostra "Aprovação: ..."): taxa e condição comercial (TAXA_EXCECAO) = Comercial aprova e a Helena registra; regra de como fechar (demais tipos) = Helena aprova. Pergunte: "Posso gravar esta regra? Quem aprova?" Só com um sim explícito **de quem pode aprovar**:
  `python -m src regra aplicar --regras <regras> --proposta <arquivo gerado> --aprovado-por "<nome> (<papel>)" [--registrado-por "<quem registra>"]`
  O comando imprime quem aprova e quem registra e recusa aprovador de outro papel (ex.: "aprova a taxa da Atlas, sou a Helena" → recusado: taxa é do Comercial); não insista nem troque o nome para passar.
- Se a base veio em zip, o comando gera um zip novo: diga "salve este arquivo na pasta compartilhada; ele substitui o anterior".
- Rode `fechar` de novo e apresente o que mudou.

### 6. Responder dúvidas
- "De onde vem X?" → `python -m src explicar <id_saida> --saida <saida> --entrada <...> --regras <...>` (mostra as linhas de origem, inclusive as de meses anteriores que vieram da carteira).
- "Quanto a Tarvo fatura de tal lojista?" → o id dele em `comissoes_por_lojista.csv` / `notas_a_emitir.csv`, depois `explicar`. Nunca de memória.

## Checklist antes de encerrar
- [ ] `fechar` saiu com código 0 e `resumo.json` existe.
- [ ] Apresentei totais, notas, divergências e pendências por responsável a partir de `resumo.json`/relatório.
- [ ] Entreguei os rascunhos de `saida/comunicacoes/` e deixei claro que o envio é da Helena.
- [ ] Toda regra gravada teve aprovação nominal de quem pode aprovar e está em `historico_alteracoes.csv`.
- [ ] Se a base estava em zip, entreguei o zip novo e pedi para substituir o anterior.
- [ ] Deixei claro o que ficou em aberto (pendências sem decisão).

## Referências (leia quando precisar)
- `references/saidas.md`: o que é cada arquivo e coluna de `saida/`.
- `references/pendencias.md`: por tipo de pendência, o que mostrar, o que perguntar, quem decide, se costuma virar regra.
- `references/regras_e_tipos.md`: os 9 tipos de regra, campos, exemplos reais, prioridade e como propor/aplicar.
- `references/glossario.md`: MDR, antecipação, EC, spread, PTAX, competência, liquidação, conta garantida, ajuste da Ponte, em linguagem de financeiro.
- `evals/cenarios.md` e `evals/teste_ferias.md`: cenários de teste da skill, inclusive o "teste de férias" com o outubro sintético.
