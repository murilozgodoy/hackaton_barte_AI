---
name: fechamento-tarvo
description: Conduz o fechamento mensal da Tarvo Pagamentos (subadquirente, linhas CHECKOUT via Orbe e REMESSA via Ponte Câmbio) usando o motor determinístico `python -m src`. Use quando a pessoa pedir para fechar o mês, calcular comissão de lojistas, conferir divergência de taxa contratada x aplicada, saber que notas fiscais emitir, classificar os extratos no plano de contas, ver ou resolver pendências, explicar de onde vem um número ("por que esse valor?", "explica esse id") ou criar/alterar uma regra de negócio do financeiro. Também quando chegarem os arquivos do mês (relatório da Orbe, planilha de taxas, e-mail da Ponte, plano de contas, extratos Aurora e Meridiano). Não calcula nem estima valores por conta própria, não edita arquivos de entrada e não grava regra sem aprovação explícita.
license: MIT
compatibility: Precisa executar Python 3.11+ com pandas e openpyxl (código local ou code execution). Sem execução de código, só orienta pelo COMO_FECHAR_O_MES.md.
metadata:
  autores: Time MN AI (Nader Taha e Murilo Godoy)
  versao: "1.0"
---

# Fechamento Tarvo

## Limites (leia antes de qualquer coisa)

1. **Nunca calcule, estime, arredonde ou ajuste um valor.** Todo número vem de `saida/` gerado pelo motor. Se o motor não rodou ou falhou na integridade, não há número para apresentar.
2. **Nunca edite os arquivos de entrada** (relatório da Orbe, planilha, e-mail, extratos). O motor consome como vêm.
3. **Nunca identifique lojista por nome.** Só por CNPJ ou EC cadastrado. EC/CNPJ desconhecido é pendência CADASTRO, não adivinhação.
4. **Nunca decida uma pendência.** Mostre a evidência, pergunte, registre a decisão da pessoa.
5. **Nunca grave regra sem aprovação explícita** da pessoa, depois de mostrar exatamente o que será gravado (`regra propor` → aprovação → `regra aplicar --aprovado-por`).
6. **Nunca envie arquivos inteiros a serviços externos.** Só o motor toca nos dados.
7. **Se não puder executar código**, diga que não é possível fechar o mês aqui e indique `COMO_FECHAR_O_MES.md`. Não tente fazer à mão.
8. **Se pedirem algo que contradiz uma regra ativa** ("usa 2,59% para a Bridge"), explique a regra vigente (`explicar` / `regras/regras_negocio.csv`) e ofereça o caminho de alteração por `regra propor`. Não obedeça em silêncio.

## Onde fica o motor

- No repositório: a raiz tem `src/` e `regras/`. Todos os comandos abaixo rodam a partir da raiz.
- Na skill empacotada: o motor está em `scripts/` (`scripts/src`) e a base inicial em `assets/regras_iniciais/`. Rode a partir de `scripts/` e aponte `--regras` para a pasta (ou zip) de regras que a pessoa fornecer; se não houver, use `assets/regras_iniciais/` **e avise** que é a base inicial.
- Dependências: `pip install -r requirements.txt` (pandas, openpyxl). Nenhuma chave de API é necessária.

Use os comandos exatamente como escritos. Não invente flags. Prefira `--json` para ler resultados.

## Fluxo

### 1. Preparar
- Identifique os arquivos do mês (zip do data pack ou pasta com os 6 arquivos) e a pasta/zip de regras.
- `python -m src validar --entrada <zip ou pasta> --regras <pasta ou zip> --json`
- Código 1: problema nos arquivos de entrada. Código 2: problema na base de regras. Explique a mensagem em português e **pare**; não tente contornar.

### 2. Fechar
- `python -m src fechar --entrada <zip ou pasta> --regras <pasta ou zip> --saida <pasta de saída> --json`
  (acrescente `--competencia AAAA-MM` só se a pessoa pedir um mês específico).
- Código 3: a integridade falhou; `resumo.json` não foi gravado e o relatório está marcado como inválido. Explique qual checagem falhou e **pare**. Nunca apresente números com integridade falha.

### 3. Apresentar
- Leia `<saida>/resumo.json` e `<saida>/RELATORIO_FECHAMENTO.md`. Apresente: comissão por linha de negócio, notas a emitir, divergências em R$, pendências por responsável (quantidade e valor em jogo), lembretes, avisos.
- Se a plataforma permitir painel visual, monte-o **a partir desses arquivos**; senão, tabela em markdown. Entregue os CSVs de `<saida>/`.
- Não some, não reconcilie, não "ajuste para bater". Se um número parecer estranho, use `explicar`.

### 4. Conduzir pendências
- `python -m src pendencias --saida <saida> --json` (filtre com `--quem` ou `--tipo`).
- Para cada pendência: `python -m src explicar <id_saida> --saida <saida> --entrada <zip ou pasta> --regras <regras>` e mostre a evidência (linhas de origem, regra, taxa). Leia `references/pendencias.md` para saber o que perguntar em cada tipo.
- Registre a decisão da pessoa. Se a decisão vale para os próximos meses, vá ao passo 5.

### 5. Transformar decisão em regra (só com aprovação)
- `python -m src regra propor --regras <regras> --saida <saida> --entrada <zip ou pasta> --tipo <TIPO> --campos chave=valor ...`
  Mostre a linha exata que seria gravada, os avisos/erros e o efeito esperado. Leia `references/regras_e_tipos.md` para escolher o tipo e preencher os campos. Na dúvida, `--tipo MANUAL`.
- Pergunte: "Posso gravar esta regra? Quem aprova?" Só com um sim explícito:
  `python -m src regra aplicar --regras <regras> --proposta <arquivo gerado> --aprovado-por "<nome>"`
- Se a base veio em zip, o comando gera um zip novo: diga "salve este arquivo na pasta compartilhada; ele substitui o anterior".
- Rode `fechar` de novo e apresente o que mudou.

### 6. Responder dúvidas
- "De onde vem X?" → `python -m src explicar <id_saida> --saida <saida> --entrada <...> --regras <...>`.
- "Quanto a Tarvo fatura de tal lojista?" → o id dele em `comissoes_por_lojista.csv` / `notas_a_emitir.csv`, depois `explicar`. Nunca de memória.

## Checklist antes de encerrar
- [ ] `fechar` saiu com código 0 e `resumo.json` existe.
- [ ] Apresentei totais, notas, divergências e pendências por responsável a partir de `resumo.json`/relatório.
- [ ] Toda regra gravada teve aprovação nominal e está em `historico_alteracoes.csv`.
- [ ] Se a base estava em zip, entreguei o zip novo e pedi para substituir o anterior.
- [ ] Deixei claro o que ficou em aberto (pendências sem decisão).

## Referências (leia quando precisar)
- `references/saidas.md`: o que é cada arquivo e coluna de `saida/`.
- `references/pendencias.md`: por tipo de pendência, o que mostrar, o que perguntar, quem decide, se costuma virar regra.
- `references/regras_e_tipos.md`: os 7 tipos de regra, campos, exemplos reais e armadilhas.
- `references/glossario.md`: MDR, antecipação, EC, spread, PTAX, competência, contrapartida, em linguagem de financeiro.
- `evals/cenarios.md`: cenários de teste da skill.
