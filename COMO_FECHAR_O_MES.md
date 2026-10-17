# Como fechar o mês (sem assistente de IA)

Roteiro para a analista, usando só o terminal. O motor fecha em segundos; o tempo restante do fechamento é o das decisões das pendências. Os comandos são
os mesmos do README e da skill.

## Uma vez (instalação)
Instale o Python 3.10 ou mais novo. O resto o script faz sozinho na primeira vez (`.venv` e
dependências). Se preferir à mão: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
Nenhuma chave de API é necessária.

## Todo mês
1. **Receba os arquivos** do mês como eles vêm (relatório da Orbe, planilha de taxas, e-mail da
   Ponte com o anexo, plano de contas, extratos Aurora e Meridiano) e coloque na pasta `entrada/`
   (o zip ou os 6 arquivos, soltos ou em subpastas). Não edite nada.
   **Atalho:** `./fechar.sh` (macOS/Linux) ou `fechar.bat` (Windows) faz os passos 2 e 3 de uma vez
   e imprime o resumo no fim; `./fechar.sh caminho/do/zip_ou_pasta` usa outro lugar.
   **Mês seguinte:** `./fechar.sh caminho/do/zip_de_outubro saida_outubro --anterior saida` relê a
   carteira pendente e a contestação de setembro (ver o passo 3).
2. **Confira entradas e regras** (não calcula nada):
   ```bash
   .venv/bin/python -m src validar --entrada <zip ou pasta> --regras regras
   ```
   - Mensagem começando com "Entrada com problema": falta arquivo ou o formato mudou. Veja o nome citado.
   - "Base de regras inválida": a mensagem diz o arquivo, a linha, a regra, o problema e como corrigir. Abra o CSV no Excel, corrija, rode de novo.
3. **Feche**:
   ```bash
   .venv/bin/python -m src fechar --entrada <zip ou pasta> --regras regras --saida saida
   .venv/bin/python -m src fechar --entrada <zip de outubro> --regras regras --saida saida_outubro --anterior saida   # mês seguinte
   ```
   Leia o que aparece na tela: comissões por lojista, divergências por natureza, notas, pendências por
   responsável, checagens de integridade. Se aparecer "INTEGRIDADE FALHOU", **não use os
   números**: leia qual checagem falhou e peça ajuda.
   Com `--anterior`, as transações guardadas em `carteira_pendente.csv` (sem contrato ou taxa no mês
   passado) entram na comissão se agora tiverem taxa, os ajustes da Ponte (`AJUSTE REF PC-…`) são ligados
   ao pedido da contestação anterior e o relatório marca pendências novas e recorrentes.
4. **Abra `saida/RELATORIO_FECHAMENTO.md`**: a página 1 é para o CFO (totais, notas, dinheiro em jogo
   por natureza (nunca somado entre naturezas), pendências por responsável, rascunhos prontos, conhecimento capturado) e o anexo tem o
   detalhe. Os CSVs em `saida/` abrem no Excel (separador `;`): `comissoes_por_lojista`,
   `divergencias_taxa` (coluna `natureza`: CONTRATO é cobrança da contraparte; DEVOLUCAO_LOJISTA é
   concessão comercial, devolução por conta da Tarvo), `notas_a_emitir`, `lancamentos_classificados`,
   `pendencias`, `rastro`, `carteira_pendente`.
5. **Revise e envie os rascunhos** de `saida/comunicacoes/`: `orbe.md` + `orbe_contestacao.csv`
   (contestação à Orbe), `ponte.md` + `ponte_contestacao.csv` (contestação à Ponte, um pedido por
   assunto, com os dois valores do spread negativo), `comercial.md` (o que depende do Comercial) e
   `avisos_nova_condicao.md` (avisos de condição nova). Nada é enviado pelo sistema: quem decide
   (`quem_decide`) revisa e envia. Prazo da Ponte: 5 dias úteis do e-mail (regra M-01).
6. **Resolva as pendências** com quem decide (está na coluna `quem_decide`; cadastro e contrato são do
   Comercial). Para ver de onde vem um número:
   ```bash
   .venv/bin/python -m src explicar PEN-0003 --saida saida --entrada <zip ou pasta> --regras regras
   .venv/bin/python -m src pendencias --saida saida --quem Helena
   ```
7. **Decisão que vale para os próximos meses vira regra.** Dois caminhos:
   - No Excel: abra `regras/regras_negocio.csv`, copie uma linha parecida, ajuste, salve, rode
     `validar`. O guia é `regras/COMO_CRIAR_REGRA.md`. Anote em `regras/historico_alteracoes.csv`.
   - No terminal, vendo o efeito antes de gravar:
     ```bash
     .venv/bin/python -m src regra propor --regras regras --saida saida --entrada <zip ou pasta> \
       --tipo TAXA_EXCECAO --campos "situacao=Taxa da Atlas confirmada pelo Comercial" \
       "parametros=cnpj=39566044000119 | linha_negocio=CHECKOUT | produto=TODOS | taxa_pct=2.00" \
       "o_que_fazer=Faturar desde 10/09" "quem_decide=Helena (Financeiro)" "informado_por=quem disse, onde, quando" \
       "vigencia_de=2026-09-10"
     ```
     O comando mostra a linha exata, valida, e **simula o efeito** no fechamento (fecha o mês de novo numa
     pasta temporária com a regra): "Atlas passa a gerar R$ X em 57 transações; nova nota NF-00YY;
     pendência SEM_CONTRATO some; nenhum outro lojista muda". Nada é gravado. Depois:
     ```bash
     .venv/bin/python -m src regra aplicar --regras regras --proposta saida/propostas/<id>.json \
       --aprovado-por "Diego (Comercial)" --registrado-por "Helena (Financeiro)"
     ```
     Quem pode aprovar cada tipo está em `regras/aprovadores.csv` (taxa e condição comercial = Comercial, com a
     Helena registrando; regra de como fechar = Helena). O comando diz quem aprova e recusa aprovador de outro
     papel. Depois rode `fechar` de novo.
8. **Emita as notas** de `saida/notas_a_emitir.csv` (remessa: nota única para a Ponte, ajustes incluídos) e
   **lance** `saida/lancamentos_classificados.csv` no Fênix.

## O que o sistema nunca faz
- Não casa lojista por nome: EC desconhecido vira pendência CADASTRO (Comercial) e fica fora da comissão, na
  carteira pendente; CNPJ da Ponte desconhecido entra na comissão (a Ponte paga) e vira pendência CADASTRO.
- Não chuta taxa: lojista sem taxa na planilha, ou parcelado fora das faixas, vira pendência.
- Não aceita número que não feche com as linhas de origem: a soma do `rastro.csv` é conferida a cada execução.
- Não envia e-mail nem decide pendência: rascunhos e evidências são para quem decide.

## Se algo não fecha
Não ajuste número à mão. Rode `explicar` no id em questão, veja as linhas de origem e a regra
usada, e corrija a **fonte** (planilha de taxas, complemento de cadastro ou regra), nunca a saída.
