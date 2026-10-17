# Pasta `entrada/`: os arquivos do mês

Coloque aqui o que chegou do mês, de um destes jeitos (tanto faz):

- o **zip** do data pack, com qualquer nome; ou
- os **6 arquivos soltos** (relatório da Orbe, planilha de taxas, e-mail da Ponte com o anexo,
  plano de contas, extrato do Aurora, extrato do Meridiano), soltos ou em subpastas.

Depois rode, na raiz do projeto: `./fechar.sh` (macOS/Linux) ou `fechar.bat` (Windows).
Sem argumento, o fechamento usa esta pasta; com argumento (`./fechar.sh caminho/do/zip_ou_pasta`),
usa o que foi indicado.

Cada arquivo é reconhecido pelo padrão de nome em `regras/fontes.csv` (por exemplo `01_orbe_*.csv`),
nunca por nome fixo de um mês. Arquivo faltando ou repetido para o fechamento com uma mensagem
dizendo qual. Nada aqui vai para o git (só este README).
