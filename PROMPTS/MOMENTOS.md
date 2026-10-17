# Momentos que importaram

## 1. A IA queria construir demais (e depois de menos)

**O que pedimos:** uma arquitetura para fechar o mês da Tarvo (Claude.ai, 16/10 à noite).
**O que a IA devolveu:** primeiro Postgres + backend + chatbot; quando recusamos, uma skill só com instruções, em que o próprio modelo calcularia as comissões.
**O que fizemos com isso:** recusamos as duas. A primeira era escopo de um mês, não de um dia; a segunda punha um modelo calculando número auditável. Ficou: motor determinístico em Python, regras em CSV que o financeiro edita, e a IA só conduz o fechamento e explica (`docs/ESPECIFICACAO.md`).

## 2. A IA errou: "a Tarvo repassou mais do que recebeu"

**O que pedimos:** conciliar o que a Orbe depositou no Aurora com o que a Tarvo repassou aos lojistas.
**O que a IA devolveu:** a conclusão de que a Tarvo tinha repassado mais do que recebeu, como se fosse um achado do mês.
**O que fizemos com isso:** barramos. A Orbe liquida crédito parcelado ao longo dos meses, então os totais de um mês não se comparam. Virou limitação declarada (regra M-04), sem número de comparação, e a Helena confirmou depois (16/10 22h34).

## 3. Duas auditorias de IA, nenhuma tratada como verdade

**O que pedimos:** que duas IAs diferentes (Codex e Claude) auditassem o repositório.
**O que a IA devolveu:** 21 achados, misturando bugs reais, coisas já corrigidas e sugestões que piorariam o fechamento (por exemplo, apagar as 4 pendências de spread negativo para resolver uma duplicação).
**O que fizemos com isso:** conferimos cada achado no código e aceitamos 8. O resto foi descartado com o motivo escrito (`docs/PLANO_FINAL_E_AUDITORIAS.md`).

## 4. A IA errou duas vezes no mesmo ponto, e corrigimos a causa

**O que pedimos:** testar a skill num chat limpo do Claude.ai: "feche o mês de setembro".
**O que a IA devolveu:** um fechamento com números certos, mas o modelo somou o total por conta própria e disse que o prazo da Ponte "pode ter passado". Comparou 09/10 com a data de hoje, o mesmo alarme falso que o Claude já tinha dado de manhã e que a Helena tinha desfeito.
**O que fizemos com isso:** em vez de corrigir a frase, mudamos a regra. O motor passou a publicar o total, as datas limite e os avisos, e a skill só pode apresentar o que está em `resumo.json`. No reteste, os erros sumiram. A revisão ainda pegou que o agrupamento "dinheiro em jogo por natureza", que nós mesmos tínhamos especificado, somava tipos que não se somam (um PIX sem dono com um repasse devolvido). Mandamos corrigir antes da entrega.

---

*Redigido com o Claude.ai a partir das sessões listadas em `README.md` e revisado pelo time.*
