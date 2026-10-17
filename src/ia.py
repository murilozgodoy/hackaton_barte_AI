"""Sugestão de conta contábil por IA para lançamentos que nenhuma regra cobre (opcional).

Só roda com ANTHROPIC_API_KEY no ambiente e o pacote `anthropic` instalado. O que
sai da máquina: banco, data, descrição e valor de CADA lançamento sem regra, e a
lista de contas analíticas do plano. Nunca arquivos inteiros, nunca dados da Orbe,
da Ponte ou de lojistas. A IA não calcula nada: devolve uma conta candidata com
confiança menor que 1, e toda sugestão vira pendência de revisão humana.
Para desligar: não defina ANTHROPIC_API_KEY (ou use --sem-ia).
"""
from __future__ import annotations

import json
import os
import re
from decimal import Decimal

MODELO_PADRAO = "claude-opus-5-5"
CONFIANCA_MAXIMA = Decimal("0.9")   # sugestão de IA nunca chega a 1

INSTRUCOES = (
    "Você classifica lançamentos de extrato bancário de uma subadquirente de pagamentos no plano de contas "
    "dela. A conta a indicar é a CONTRAPARTIDA do movimento bancário: se o valor já estava registrado "
    "(provisão, recebível, obrigação), indique a conta onde ele estava; só use receita ou despesa quando o "
    "movimento não tinha registro anterior. Use apenas códigos da lista de contas fornecida. Responda somente "
    "com JSON, no formato {\"sugestoes\": [{\"ref\": ..., \"conta_codigo\": ..., \"confianca\": 0.0-0.9, "
    "\"justificativa\": \"uma frase\"}]}. Se não tiver base para sugerir, use conta_codigo null."
)


def disponivel() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def sugerir_contas(linhas: list[dict], contas: list[dict]) -> dict[str, dict]:
    """linhas: [{ref, banco, data, descricao, valor}]; contas: [{cod_conta, descricao}] -> {ref: sugestão}."""
    import anthropic

    client = anthropic.Anthropic()
    pedido = {"contas": contas, "lancamentos": linhas}
    resposta = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", MODELO_PADRAO),
        max_tokens=4096,
        output_config={"effort": "low"},
        system=INSTRUCOES,
        messages=[{"role": "user", "content": json.dumps(pedido, ensure_ascii=False)}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("a IA recusou a solicitação")
    texto = "".join(b.text for b in resposta.content if b.type == "text")
    return _interpretar(texto, {c["cod_conta"] for c in contas}, {l["ref"] for l in linhas})


def _interpretar(texto: str, contas_validas: set[str], refs: set[str]) -> dict[str, dict]:
    m = re.search(r"\{.*\}", texto, flags=re.S)
    if not m:
        raise ValueError("resposta da IA sem JSON")
    dados = json.loads(m.group(0))
    out = {}
    for s in dados.get("sugestoes", []):
        ref, conta = s.get("ref"), s.get("conta_codigo")
        if ref not in refs or conta not in contas_validas:
            continue
        try:
            confianca = Decimal(str(s.get("confianca", 0))).quantize(Decimal("0.01"))
        except Exception:
            confianca = Decimal("0.5")
        confianca = max(Decimal("0"), min(confianca, CONFIANCA_MAXIMA))
        out[ref] = {"conta_codigo": conta, "confianca": confianca, "justificativa": s.get("justificativa")}
    return out
