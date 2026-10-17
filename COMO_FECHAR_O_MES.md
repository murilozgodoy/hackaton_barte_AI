# Como fechar o mês (sem assistente de IA)

Roteiro para a analista, usando só o terminal. Tempo esperado: minutos, não dias.

## Uma vez (instalação)
Instale o Python 3.10 ou mais novo. O resto o script faz sozinho na primeira vez (`.venv` e
dependências). Se preferir à mão: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

## Todo mês
1. **Receba os arquivos** do mês como eles vêm (relatório da Orbe, planilha de taxas, e-mail da
   Ponte com o anexo, plano de contas, extratos Aurora e Meridiano) e coloque na pasta `entrada/`
   (o zip ou os 6 arquivos, soltos ou em subpastas). Não edite nada.
   **Atalho:** `./fechar.sh` (macOS/Linux) ou `fechar.bat` (Windows) faz os passos 2 e 3 de uma vez
   e imprime o resumo no fim; `./fechar.sh caminho/do/zip_ou_pasta` usa outro lugar.
2. **Confira entradas e regras** (não calcula nada):
   ```bash
   .venv/bin/python -m src validar --entrada <zip ou pasta> --regras regras
   ```
   - Mensagem começando com "Entrada com problema": falta arquivo ou o formato mudou. Veja o nome citado.
   - "Base de regras inválida": a mensagem diz o arquivo, a linha, a regra, o problema e como corrigir. Abra o CSV no Excel, corrija, rode de novo.
3. **Feche**:
   ```bash
   .venv/bin/python -m src fechar --entrada <zip ou pasta> --regras regras --saida saida
   ```
   Lê o que aparece na tela: comissões por lojista, divergências, notas, pendências por
   responsável, checagens de integridade. Se aparecer "INTEGRIDADE FALHOU", **não use os
   números**: leia qual checagem falhou e peça ajuda.
4. **Abra `saida/RELATORIO_FECHAMENTO.md`** (uma página) e os CSVs em `saida/`:
   `comissoes_por_lojista`, `divergencias_taxa`, `notas_a_emitir`, `lancamentos_classificados`,
   `pendencias`, `rastro`. Tudo abre no Excel (separador `;`).
5. **Resolva as pendências** com quem decide (está na coluna `quem_decide`). Para ver de onde
   vem um número:
   ```bash
   .venv/bin/python -m src explicar PEN-0003 --saida saida --entrada <zip ou pasta> --regras regras
   .venv/bin/python -m src pendencias --saida saida --quem Helena
   ```
6. **Decisão que vale para os próximos meses vira regra.** Dois caminhos:
   - No Excel: abra `regras/regras_negocio.csv`, copie uma linha parecida, ajuste, salve, rode
     `validar`. O guia é `regras/COMO_CRIAR_REGRA.md`. Anote em `regras/historico_alteracoes.csv`.
   - No terminal:
     ```bash
     .venv/bin/python -m src regra propor --regras regras --saida saida --entrada <zip ou pasta> \
       --tipo CLASSIFICAR_CONTA --campos "situacao=..." "parametros=banco=AURORA | contem=... | conta=... | prioridade=50" \
       "o_que_fazer=..." "quem_decide=Financeiro" "informado_por=quem disse, onde, quando"
     .venv/bin/python -m src regra aplicar --regras regras --proposta saida/propostas/<id>.json --aprovado-por "Seu nome"
     ```
   Depois rode `fechar` de novo.
7. **Emita as notas** de `saida/notas_a_emitir.csv` e **lance** `saida/lancamentos_classificados.csv` no Fênix.

## O que o sistema nunca faz
- Não casa lojista por nome: EC ou CNPJ desconhecido vira pendência CADASTRO.
- Não chuta taxa: lojista sem taxa na planilha vira pendência.
- Não aceita número que não feche com as linhas de origem: a soma do `rastro.csv` é conferida a cada execução.

## Se algo não fecha
Não ajuste número à mão. Rode `explicar` no id em questão, veja as linhas de origem e a regra
usada, e corrija a **fonte** (planilha de taxas, complemento de cadastro ou regra), nunca a saída.
