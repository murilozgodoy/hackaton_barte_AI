"""Carrega e valida a base de regras do financeiro (pasta regras/).

Cadastro de lojistas: a fonte da verdade é a PLANILHA DE TAXAS do mês (CNPJ,
nome, EC, taxas). regras/complemento_cadastro.csv só preenche lacunas ou marca
situações que a planilha não traz (EC em branco, lojista sem contrato).
Ordem: planilha -> complemento. Mesmo CNPJ com EC diferente nas duas é erro;
linha do complemento que só repete a planilha gera aviso.

regras/regras_negocio.csv: cada regra tem um `tipo` de uma lista fechada. O
motor só executa tipos conhecidos, a partir da coluna `parametros`, no formato
chave=valor separado por " | " (ex.: banco=AURORA | contem=PIX ENVIADO | conta=2.1.01.001).
Alternativas de texto dentro de um valor usam " OU " (ex.: contem=PONTE AEREA OU PONTE AÉREA);
listas usam vírgula (ex.: aceitos=APROVADO,APROVADO C/ RESSALVA). Números aceitam
vírgula ou ponto decimal. Só regras com status ATIVA são executadas. MANUAL nunca é
executada: só gera pendência com o_que_fazer e quem_decide. Colunas de texto livre
(situacao, como_identificar, o_que_fazer...) não são interpretadas pelo código.

Erro de configuração para o fechamento com mensagem em português indicando o
arquivo, a linha, o id da regra, o problema e como corrigir.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from .leitores.comum import ErroLeitura, ler_texto, normalizar, normalizar_ec

SEPARADOR_PARAMETROS = "|"
SEPARADOR_ALTERNATIVAS = " OU "
TIPOS = ("PARAMETRO", "TAXA_EXCECAO", "IGNORAR_DUPLICADO", "EXCLUIR_E_PENDENCIA",
         "CLASSIFICAR_CONTA", "DONO_PENDENCIA", "MANUAL")
STATUS_REGRA = {"ATIVA", "PROPOSTA", "INATIVA"}
STATUS_CADASTRO = {"ATIVO", "SEM_CONTRATO", "INATIVO"}

# Vocabulário que o motor sabe executar (formato, não regra de negócio).
PRODUTOS = {
    "CHECKOUT": {"DEBITO", "CREDITO A VISTA", "CREDITO PARCELADO", "PIX", "ANTECIPACAO"},
    "REMESSA": {"SPREAD REMESSA"},
}
# nome -> (como validar, opções). "fracao" = número entre 0 e 1 (0.50 = 50%).
PARAMETROS = {
    "participacao_spread": ("fracao", None),
    "spread_padrao": ("fracao", None),
    "tolerancia_spread_pp": ("numero", None),
    "tolerancia_taxa_checkout_pp": ("numero", None),
    "incluir_excesso_contestado": ("sim_nao", None),
    "arredondamento": ("escolha", {"HALF_UP", "TRUNCAR"}),
    "nota_remessa_tomador_cnpj": ("cnpj", None),
    "nota_remessa_tomador_nome": ("texto", None),
    "discriminacao_checkout": ("texto", None),
    "discriminacao_remessa": ("texto", None),
}
TIPOS_PENDENCIA = {
    "DIVERGENCIA_TAXA", "TARIFA_ZERO_COBRADA", "SEM_CONTRATO", "SPREAD_NEGATIVO",
    "EXCESSO_SPREAD_CONTESTADO", "SALDO_NEGATIVO_LOJISTA", "CADASTRO", "EXTRATO_NAO_IDENTIFICADO",
    "DEVOLUCAO", "EM_TRANSITO", "REVISAR_IA", "MANUAL", "FORA_COMPETENCIA", "COMPLIANCE",
    "DUPLICATA_DIVERGENTE",
}
# Pendências que o próprio motor gera (sem regra que as origine): precisam de DONO_PENDENCIA.
PENDENCIAS_DO_MOTOR = {
    "DIVERGENCIA_TAXA", "EXCESSO_SPREAD_CONTESTADO", "SALDO_NEGATIVO_LOJISTA", "CADASTRO",
    "EXTRATO_NAO_IDENTIFICADO", "EM_TRANSITO", "REVISAR_IA", "FORA_COMPETENCIA",
    "DUPLICATA_DIVERGENTE",
}
CRITERIOS = {"orbe": {"status_cadastro"},
             "ponte": {"status_cadastro", "spread_negativo", "status_compliance_fora"}}
VALOR_PENDENCIA = {"orbe": {"valor_taxa", "valor_bruto"}, "ponte": {"spread_brl", "valor_brl"}}
AGRUPAR = {"cnpj", "ec", "linha", "tudo"}
CHAVES_DUPLICADO = {"ponte": {"num_operacao"}, "orbe": {"id_transacao"}}
_RE_IDENT = re.compile(r"[A-Z][A-Z0-9_]*")

# chaves obrigatórias e opcionais de `parametros`, por tipo
ESQUEMA = {
    "TAXA_EXCECAO": ({"cnpj", "linha_negocio", "produto", "taxa_pct"}, {"tipo_pendencia", "subtipo"}),
    "IGNORAR_DUPLICADO": ({"fonte", "chave"}, set()),
    "EXCLUIR_E_PENDENCIA": ({"fonte", "criterio", "tipo_pendencia"},
                            {"status", "aceitos", "valor_pendencia", "agrupar", "subtipo"}),
    "CLASSIFICAR_CONTA": ({"banco", "contem", "conta", "prioridade"},
                          {"sinal", "gera_pendencia", "tipo_pendencia", "subtipo"}),
    "DONO_PENDENCIA": ({"tipo_pendencia"}, set()),
    "MANUAL": (set(), {"banco", "contem", "cnpj", "linha_negocio"}),
}

COLUNAS_REGRAS = ["id", "situacao", "como_identificar", "tipo", "parametros", "o_que_fazer",
                  "quem_decide", "exemplo", "vigencia_de", "vigencia_ate", "status",
                  "informado_por", "data"]
COLUNAS_COMPLEMENTO = ["cnpj", "ec_orbe", "status", "informado_por", "data", "observacao"]


class ErroConfig(Exception):
    """Configuração inválida. `erros` lista todos os problemas encontrados."""

    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__("Base de regras inválida:\n  - " + "\n  - ".join(erros))


@dataclass
class Regra:
    id: str
    tipo: str
    params: dict
    situacao: str
    como_identificar: str
    o_que_fazer: str
    quem_decide: str
    exemplo: str
    vigencia_de: date | None
    vigencia_ate: date | None
    status: str
    informado_por: str
    data: date | None
    linha: int
    valor: object = None  # PARAMETRO: valor já convertido

    def vigente_em(self, d: date) -> bool:
        if isinstance(d, pd.Timestamp):
            d = d.date()
        return (self.vigencia_de is None or d >= self.vigencia_de) and (
            self.vigencia_ate is None or d <= self.vigencia_ate)

    @property
    def tipo_pendencia(self) -> str | None:
        return self.params.get("tipo_pendencia")

    @property
    def subtipo(self) -> str | None:
        return self.params.get("subtipo")


@dataclass
class Classificacao:
    regra: Regra | None
    conflito: list = field(default_factory=list)  # regras de mesma prioridade com contas diferentes


# --------------------------------------------------------------------------- conversões

def parse_parametros(texto: str) -> dict[str, str]:
    """'banco=AURORA | contem=PIX ENVIADO' -> {'banco': 'AURORA', 'contem': 'PIX ENVIADO'}."""
    out: dict[str, str] = {}
    for parte in (texto or "").split(SEPARADOR_PARAMETROS):
        parte = parte.strip()
        if not parte:
            continue
        if "=" not in parte:
            raise ValueError(f"o trecho '{parte}' não tem '=' (formato: chave=valor, separados por '|')")
        chave, valor = parte.split("=", 1)
        chave = normalizar(chave).lower().replace(" ", "_")
        if not chave:
            raise ValueError(f"o trecho '{parte}' não tem nome antes do '='")
        if chave in out:
            raise ValueError(f"a chave '{chave}' aparece duas vezes")
        out[chave] = valor.strip()
    return out


def formatar_parametros(params: dict) -> str:
    return f" {SEPARADOR_PARAMETROS} ".join(f"{k}={v}" for k, v in params.items())


def numero_param(valor: str) -> Decimal:
    try:
        return Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"'{valor}' não é um número") from None


def sim_nao(valor: str) -> bool:
    v = normalizar(valor)
    if v in {"S", "SIM", "TRUE", "VERDADEIRO", "1"}:
        return True
    if v in {"N", "NAO", "FALSE", "FALSO", "0"}:
        return False
    raise ValueError(f"'{valor}' não é true/false (nem S/N)")


def lista(valor: str) -> list[str]:
    return [normalizar(v) for v in str(valor).split(",") if v.strip()]


def alternativas(valor: str) -> list[str]:
    """'PONTE AEREA OU PONTE AÉREA' -> ['PONTE AEREA'] (normalizado e sem repetição)."""
    vistos: list[str] = []
    for alt in normalizar(valor).split(SEPARADOR_ALTERNATIVAS):
        alt = alt.strip()
        if alt and alt not in vistos:
            vistos.append(alt)
    return vistos


_RE_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_RE_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def data_config(valor: str, avisos: list[str], onde: str) -> date | None:
    """AAAA-MM-DD. Aceita dd/mm/aaaa com aviso (é o que o Excel faz ao salvar)."""
    s = (valor or "").strip()
    if not s:
        return None
    if _RE_ISO.fullmatch(s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            raise ValueError(f"data '{s}' não existe no calendário") from None
    m = _RE_BR.fullmatch(s)
    if m:
        avisos.append(f"{onde}: data '{s}' em dd/mm/aaaa; entendida como {m.group(3)}-{m.group(2)}-{m.group(1)}")
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    raise ValueError(f"data '{s}' fora do formato AAAA-MM-DD")


def cnpj_config(valor: str, avisos: list[str], onde: str) -> str:
    s = (valor or "").strip()
    if re.search(r"[eE]\+", s):
        raise ValueError(f"CNPJ '{s}' em notação científica (o Excel corrompeu o número). "
                         "Formate a coluna como Texto e digite os 14 dígitos")
    digitos = re.sub(r"\D", "", s)
    if not digitos or len(digitos) > 14:
        raise ValueError(f"CNPJ '{s}' não tem 14 dígitos")
    if len(digitos) < 14:
        avisos.append(f"{onde}: CNPJ '{s}' com {len(digitos)} dígitos (o Excel tira zeros à esquerda); "
                      f"entendido como {digitos.zfill(14)}")
    return digitos.zfill(14)


def ler_csv_regras(caminho: Path, colunas: list[str]) -> list[tuple[int, dict]]:
    """Lê um CSV ';' da pasta regras/ e devolve [(nº da linha, {coluna: valor})]."""
    texto, _ = ler_texto(caminho, esperado=colunas[:2])
    leitor = csv.reader(io.StringIO(texto), delimiter=";")
    cab, linhas = None, []
    for campos in leitor:
        n = leitor.line_num
        if not any(c.strip() for c in campos):
            continue
        if cab is None:
            cab = [c.strip().lstrip("﻿") for c in campos]
            faltando = [c for c in colunas if c not in cab]
            if faltando:
                raise ErroConfig([f"{caminho.name}: colunas ausentes no cabeçalho: {faltando}. "
                                  f"Como corrigir: o cabeçalho deve ser {';'.join(colunas)}"])
            continue
        if len(campos) != len(cab):
            raise ErroConfig([f"{caminho.name} linha {n}: {len(campos)} colunas, esperado {len(cab)}. "
                              "Como corrigir: não use ';' dentro do texto"])
        linhas.append((n, {k: (v or "").strip() for k, v in zip(cab, campos)}))
    return linhas


# --------------------------------------------------------------------------- configuração

class Config:
    """Base de regras carregada e validada. `regras` só tem as ATIVAS; `todas` inclui as demais."""

    def __init__(self, cadastro: pd.DataFrame, regras: list[Regra], avisos: list[str]):
        self.cadastro = cadastro
        self.todas = regras
        self.regras = [r for r in regras if r.status == "ATIVA"]
        self.avisos = avisos
        self._por_ec = {r.ec_orbe: r for r in cadastro.itertuples() if r.ec_orbe}
        self._por_cnpj = {r.cnpj: r for r in cadastro.itertuples()}

    # cadastro
    def lojista_por_ec(self, ec: str):
        try:
            return self._por_ec.get(normalizar_ec(ec))
        except ErroLeitura:
            return None

    def lojista_por_cnpj(self, cnpj: str):
        return self._por_cnpj.get(cnpj)

    # regras
    def por_tipo(self, tipo: str) -> list[Regra]:
        return [r for r in self.regras if r.tipo == tipo]

    def regra(self, id_regra: str) -> Regra | None:
        return next((r for r in self.todas if r.id == id_regra), None)

    def regra_parametro(self, nome: str, em: date) -> Regra:
        r = next((r for r in self.por_tipo("PARAMETRO") if nome in r.params and r.vigente_em(em)), None)
        if r is None:
            raise ErroConfig([f"Nenhuma regra PARAMETRO ativa e vigente em {em} para '{nome}'. "
                              "Como corrigir: crie ou ajuste a vigência em regras_negocio.csv"])
        return r

    def parametro(self, nome: str, em: date):
        return self.regra_parametro(nome, em).valor

    def excecao_taxa(self, cnpj: str, linha_negocio: str, produto: str, em: date) -> Regra | None:
        for r in self.por_tipo("TAXA_EXCECAO"):
            p = r.params
            if (p["cnpj"] == cnpj and p["linha_negocio"] == linha_negocio
                    and (p["produto"] == {"TODOS"} or produto in p["produto"]) and r.vigente_em(em)):
                return r
        return None

    def regras_exclusao(self, fonte: str, em: date) -> list[Regra]:
        return [r for r in self.por_tipo("EXCLUIR_E_PENDENCIA")
                if r.params["fonte"] == fonte and r.vigente_em(em)]

    def regra_duplicado(self, fonte: str, em: date) -> Regra | None:
        return next((r for r in self.por_tipo("IGNORAR_DUPLICADO")
                     if r.params["fonte"] == fonte and r.vigente_em(em)), None)

    def dono(self, tipo_pendencia: str, em: date) -> Regra:
        r = next((r for r in self.por_tipo("DONO_PENDENCIA")
                  if r.params["tipo_pendencia"] == tipo_pendencia and r.vigente_em(em)), None)
        if r is None:
            raise ErroConfig([f"Nenhuma regra DONO_PENDENCIA ativa e vigente em {em} para "
                              f"'{tipo_pendencia}'. Como corrigir: crie a regra em regras_negocio.csv"])
        return r

    def lembretes(self, em: date) -> list[Regra]:
        return [r for r in self.por_tipo("MANUAL") if r.vigente_em(em)]

    def classificar(self, banco: str, descricao: str, valor: Decimal, em: date) -> Classificacao:
        """Regra CLASSIFICAR_CONTA de menor prioridade (número) que casa com o lançamento.

        Texto e padrão são comparados sem acento e em maiúsculas; qualquer alternativa
        (" OU ") basta. Empate de prioridade com contas diferentes volta como conflito.
        """
        texto = normalizar(descricao)
        candidatas = []
        for r in self.por_tipo("CLASSIFICAR_CONTA"):
            p = r.params
            if p["banco"] not in (banco, "TODOS") or not r.vigente_em(em):
                continue
            if p.get("sinal") == "credito" and not valor > 0:
                continue
            if p.get("sinal") == "debito" and not valor < 0:
                continue
            if any(alt in texto for alt in p["contem_alternativas"]):
                candidatas.append(r)
        if not candidatas:
            return Classificacao(None)
        menor = min(r.params["prioridade"] for r in candidatas)
        melhores = [r for r in candidatas if r.params["prioridade"] == menor]
        if len({r.params["conta"] for r in melhores}) > 1:
            return Classificacao(None, conflito=melhores)
        return Classificacao(melhores[0])


def carregar_config(dir_regras: Path, taxas: pd.DataFrame, plano_contas: pd.DataFrame,
                    bancos: set[str]) -> Config:
    dir_regras = Path(dir_regras)
    erros: list[str] = []
    avisos: list[str] = []
    try:
        cadastro = montar_cadastro(taxas, dir_regras / "complemento_cadastro.csv", erros, avisos)
        regras = carregar_regras(dir_regras / "regras_negocio.csv", cadastro, plano_contas,
                                 bancos, erros, avisos)
    except ErroLeitura as e:
        raise ErroConfig([str(e)]) from None
    if erros:
        raise ErroConfig(erros)
    return Config(cadastro, regras, avisos)


def montar_cadastro(taxas: pd.DataFrame, caminho_complemento: Path, erros: list[str],
                    avisos: list[str]) -> pd.DataFrame:
    """Cadastro do mês = planilha de taxas (fonte da verdade) + complemento (só lacunas)."""
    base: dict[str, dict] = {}
    linhas = taxas.drop_duplicates("linha_planilha").sort_values("linha_planilha")
    for r in linhas.itertuples():
        b = base.setdefault(r.cnpj, {
            "cnpj": r.cnpj, "nome": r.lojista_planilha, "ec_orbe": None, "status": "ATIVO",
            "origem": "planilha", "linhas_planilha": [], "linha_complemento": None,
            "informado_por": None, "observacao": None})
        b["linhas_planilha"].append(r.linha_planilha)
        if r.ec_orbe:
            if b["ec_orbe"] and b["ec_orbe"] != r.ec_orbe:
                erros.append(f"planilha de taxas: CNPJ {r.cnpj} com EC {b['ec_orbe']} e {r.ec_orbe} em "
                             f"linhas diferentes ({b['linhas_planilha']}). Como corrigir: deixe um EC só")
            b["ec_orbe"] = r.ec_orbe

    for n, c in ler_csv_regras(caminho_complemento, COLUNAS_COMPLEMENTO):
        onde = f"{caminho_complemento.name} linha {n}"
        try:
            cnpj = cnpj_config(c["cnpj"], avisos, onde)
            try:
                ec = normalizar_ec(c["ec_orbe"])
            except ErroLeitura as e:
                raise ValueError(str(e)) from None
            status = normalizar(c["status"])
            if status not in STATUS_CADASTRO:
                raise ValueError(f"status '{c['status']}' inválido (use {', '.join(sorted(STATUS_CADASTRO))})")
            if not c["informado_por"]:
                raise ValueError("informado_por vazio (registre quem informou)")
            data_config(c["data"], avisos, onde)
        except ValueError as e:
            erros.append(f"{onde}: {e}. Como corrigir: ajuste a célula indicada")
            continue

        b = base.get(cnpj)
        if b is None:
            base[cnpj] = {"cnpj": cnpj, "nome": None, "ec_orbe": ec, "status": status,
                          "origem": "complemento", "linhas_planilha": [], "linha_complemento": n,
                          "informado_por": c["informado_por"], "observacao": c["observacao"]}
            continue
        muda = False
        if ec:
            if b["ec_orbe"] and b["ec_orbe"] != ec:
                erros.append(f"{onde}: CNPJ {cnpj} tem EC {b['ec_orbe']} na planilha de taxas e {ec} no "
                             "complemento. Como corrigir: confirme o EC certo e corrija a planilha ou o complemento")
                continue
            muda |= b["ec_orbe"] is None
            b["ec_orbe"] = ec
        if status != b["status"]:
            b["status"] = status
            muda = True
        if not muda:
            avisos.append(f"{onde}: linha redundante, pode ser removida (a planilha de taxas já traz "
                          f"CNPJ {cnpj}, EC {b['ec_orbe']}, status {b['status']})")
        b.update(origem="planilha + complemento", linha_complemento=n,
                 informado_por=c["informado_por"], observacao=c["observacao"])

    df = pd.DataFrame(list(base.values()))
    rep = df[df["ec_orbe"].notna() & df["ec_orbe"].duplicated(keep=False)]
    for ec, grupo in rep.groupby("ec_orbe"):
        erros.append(f"cadastro (planilha + complemento): EC {ec} ligado a mais de um CNPJ "
                     f"{grupo['cnpj'].tolist()}. Como corrigir: cada EC pertence a um CNPJ só")
    return df


def carregar_regras(caminho: Path, cadastro: pd.DataFrame, plano: pd.DataFrame, bancos: set[str],
                    erros: list[str], avisos: list[str]) -> list[Regra]:
    contexto = _Contexto(
        contas_ok=set(plano.loc[plano["aceita_lancto"], "cod_conta"]),
        contas_todas=set(plano["cod_conta"]),
        cnpjs=set(cadastro["cnpj"]),
        bancos=set(bancos),
    )
    regras: list[Regra] = []
    vistos: dict[str, int] = {}
    for n, r in ler_csv_regras(caminho, COLUNAS_REGRAS):
        regra = validar_linha_regra(r, n, contexto, erros, avisos, caminho.name)
        if regra is None:
            continue
        if regra.id in vistos:
            erros.append(f"{caminho.name} linha {n}, regra {regra.id}: id repetido (já usado na linha "
                         f"{vistos[regra.id]}). Como corrigir: use um id que ainda não existe")
            continue
        vistos[regra.id] = n
        regras.append(regra)
    validar_conjunto(regras, erros)
    return regras


@dataclass
class _Contexto:
    contas_ok: set
    contas_todas: set
    cnpjs: set
    bancos: set


def validar_linha_regra(r: dict, n: int, ctx: _Contexto, erros: list[str], avisos: list[str],
                        arquivo: str = "regras_negocio.csv") -> Regra | None:
    """Valida uma linha (dict com as colunas) e devolve a Regra, ou None se houver erro."""
    rid = r.get("id", "") or f"(sem id, linha {n})"
    onde = f"{arquivo} linha {n}, regra {rid}"
    antes = len(erros)

    def erro(problema: str, dica: str):
        erros.append(f"{onde}: {problema}. Como corrigir: {dica}")

    if not r.get("id"):
        erro("id vazio", "dê um id único, ex.: C-29")
    tipo = normalizar(r.get("tipo"))
    if tipo not in TIPOS:
        erro(f"tipo '{r.get('tipo')}' desconhecido", f"use um destes: {', '.join(TIPOS)}. Na dúvida, MANUAL")
        return None
    status = normalizar(r.get("status")) or "ATIVA"
    if status not in STATUS_REGRA:
        erro(f"status '{r.get('status')}' inválido", f"use {', '.join(sorted(STATUS_REGRA))}")
    try:
        params = parse_parametros(r.get("parametros", ""))
    except ValueError as e:
        erro(f"parametros inválidos: {e}", "escreva chave=valor separados por ' | '")
        return None
    try:
        vig_de = data_config(r.get("vigencia_de", ""), avisos, onde)
        vig_ate = data_config(r.get("vigencia_ate", ""), avisos, onde)
        data_info = data_config(r.get("data", ""), avisos, onde)
    except ValueError as e:
        erro(str(e), "use AAAA-MM-DD, ex.: 2026-01-31")
        return None
    if vig_de and vig_ate and vig_de > vig_ate:
        erro(f"vigencia_de {vig_de} depois de vigencia_ate {vig_ate}", "inverta ou corrija as datas")
    if not r.get("informado_por") or data_info is None:
        erro("informado_por ou data vazio", "registre quem informou a regra e quando")
    if not r.get("quem_decide") and tipo != "PARAMETRO":
        erro("quem_decide vazio", "diga quem decide quando a regra gerar pendência")

    regra = Regra(id=r.get("id", ""), tipo=tipo, params=params, situacao=r.get("situacao", ""),
                  como_identificar=r.get("como_identificar", ""), o_que_fazer=r.get("o_que_fazer", ""),
                  quem_decide=r.get("quem_decide", ""), exemplo=r.get("exemplo", ""),
                  vigencia_de=vig_de, vigencia_ate=vig_ate, status=status,
                  informado_por=r.get("informado_por", ""), data=data_info, linha=n)
    _validar_params(regra, erro, avisos, onde, ctx)
    return regra if len(erros) == antes else None


def _validar_params(regra: Regra, erro, avisos, onde, ctx: _Contexto):
    p, tipo = regra.params, regra.tipo
    if tipo == "PARAMETRO":
        if len(p) != 1:
            return erro("PARAMETRO deve ter exatamente uma chave=valor", "uma regra por parâmetro")
        nome, valor = next(iter(p.items()))
        if nome not in PARAMETROS:
            return erro(f"parâmetro '{nome}' desconhecido", f"use um destes: {', '.join(PARAMETROS)}")
        espec, opcoes = PARAMETROS[nome]
        try:
            if espec == "numero":
                regra.valor = numero_param(valor)
            elif espec == "fracao":
                regra.valor = numero_param(valor)
                if not Decimal(0) <= regra.valor <= Decimal(1):
                    raise ValueError(f"'{valor}' deve ser uma fração entre 0 e 1 (0.50 = 50%, 0.015 = 1,5%)")
            elif espec == "sim_nao":
                regra.valor = sim_nao(valor)
            elif espec == "escolha":
                regra.valor = normalizar(valor)
                if regra.valor not in opcoes:
                    raise ValueError(f"'{valor}' não é opção válida ({', '.join(sorted(opcoes))})")
            elif espec == "cnpj":
                regra.valor = cnpj_config(valor, avisos, onde)
            else:
                if not valor:
                    raise ValueError("valor vazio")
                regra.valor = valor
        except ValueError as e:
            erro(f"valor de '{nome}' inválido: {e}", "corrija o valor depois do '='")
        return

    obrigatorias, opcionais = ESQUEMA[tipo]
    faltando = obrigatorias - p.keys()
    sobrando = p.keys() - obrigatorias - opcionais
    if faltando:
        return erro(f"faltam as chaves {sorted(faltando)} em parametros",
                    f"para {tipo} use: {', '.join(sorted(obrigatorias | opcionais))}")
    if sobrando:
        return erro(f"chaves desconhecidas {sorted(sobrando)} em parametros",
                    f"para {tipo} use só: {', '.join(sorted(obrigatorias | opcionais))}")
    if "tipo_pendencia" in p:
        p["tipo_pendencia"] = normalizar(p["tipo_pendencia"]).replace(" ", "_")
        if p["tipo_pendencia"] not in TIPOS_PENDENCIA:
            erro(f"tipo_pendencia '{p['tipo_pendencia']}' desconhecido",
                 f"use um destes: {', '.join(sorted(TIPOS_PENDENCIA))}")
    if "subtipo" in p:
        p["subtipo"] = normalizar(p["subtipo"]).replace(" ", "_")
        if not _RE_IDENT.fullmatch(p["subtipo"]):
            erro(f"subtipo '{p['subtipo']}' inválido", "use letras, números e _, ex.: EC_ORBE")

    if tipo == "TAXA_EXCECAO":
        try:
            p["cnpj"] = cnpj_config(p["cnpj"], avisos, onde)
            p["taxa_pct"] = numero_param(p["taxa_pct"])
        except ValueError as e:
            return erro(str(e), "corrija o valor em parametros")
        if p["cnpj"] not in ctx.cnpjs:
            erro(f"CNPJ {p['cnpj']} não está na planilha de taxas nem em complemento_cadastro.csv",
                 "confira o CNPJ do lojista")
        linha = normalizar(p["linha_negocio"])
        if linha not in PRODUTOS:
            return erro(f"linha_negocio '{p['linha_negocio']}' inválida", "use CHECKOUT ou REMESSA")
        p["linha_negocio"] = linha
        produtos = set(lista(p["produto"]))
        invalidos = produtos - PRODUTOS[linha] - {"TODOS"}
        if invalidos:
            erro(f"produto(s) {sorted(invalidos)} inválido(s) para {linha}",
                 f"use TODOS ou uma lista com {', '.join(sorted(PRODUTOS[linha]))}")
        p["produto"] = {"TODOS"} if "TODOS" in produtos else produtos
        if p["taxa_pct"] < 0:
            erro("taxa_pct negativa", "use 0 ou um percentual positivo")
        if regra.vigencia_de is None:
            erro("exceção comercial sem vigencia_de", "informe a data de início do acordo")

    elif tipo == "IGNORAR_DUPLICADO":
        fonte = p["fonte"].lower()
        if fonte not in CHAVES_DUPLICADO or p["chave"] not in CHAVES_DUPLICADO[fonte]:
            erro(f"fonte/chave '{p['fonte']}/{p['chave']}' não suportada",
                 "use fonte=ponte | chave=num_operacao ou fonte=orbe | chave=id_transacao")
        p["fonte"] = fonte

    elif tipo == "EXCLUIR_E_PENDENCIA":
        fonte, criterio = p["fonte"].lower(), p["criterio"].lower()
        if fonte not in CRITERIOS:
            return erro(f"fonte '{p['fonte']}' inválida", f"use {' ou '.join(CRITERIOS)}")
        if criterio not in CRITERIOS[fonte]:
            return erro(f"critério '{p['criterio']}' não existe para {fonte}",
                        f"use um destes: {', '.join(sorted(CRITERIOS[fonte]))}. Se não houver, use MANUAL")
        p["fonte"], p["criterio"] = fonte, criterio
        if criterio == "status_cadastro":
            if "status" not in p:
                return erro("critério status_cadastro sem 'status'", "ex.: status=SEM_CONTRATO")
            p["status"] = set(lista(p["status"]))
            if not p["status"] <= STATUS_CADASTRO:
                erro(f"status {sorted(p['status'] - STATUS_CADASTRO)} inválido",
                     f"use {', '.join(sorted(STATUS_CADASTRO))}")
        if criterio == "status_compliance_fora":
            if "aceitos" not in p:
                return erro("critério status_compliance_fora sem 'aceitos'", "ex.: aceitos=APROVADO")
            p["aceitos"] = set(lista(p["aceitos"]))
        p.setdefault("valor_pendencia", "valor_taxa" if fonte == "orbe" else "spread_brl")
        if p["valor_pendencia"] not in VALOR_PENDENCIA[fonte]:
            erro(f"valor_pendencia '{p['valor_pendencia']}' inválido",
                 f"use {', '.join(sorted(VALOR_PENDENCIA[fonte]))}")
        p["agrupar"] = p.get("agrupar", "cnpj").lower()
        if p["agrupar"] not in AGRUPAR:
            erro(f"agrupar '{p['agrupar']}' inválido", f"use {', '.join(sorted(AGRUPAR))}")

    elif tipo == "CLASSIFICAR_CONTA":
        _validar_banco_contem(p, erro, ctx.bancos)
        conta = p["conta"]
        if conta not in ctx.contas_todas:
            erro(f"conta {conta} não existe no plano de contas", "use uma conta analítica do plano do Fênix")
        elif conta not in ctx.contas_ok:
            erro(f"conta {conta} não aceita lançamento (ACEITA_LANCTO=N, conta sintética)",
                 "use uma conta analítica abaixo dela")
        try:
            p["prioridade"] = int(str(p["prioridade"]).strip())
            if not 1 <= p["prioridade"] <= 99:
                raise ValueError
        except ValueError:
            erro(f"prioridade '{p['prioridade']}' inválida",
                 "use um inteiro de 1 a 99 (menor vence; específicas ~10, genéricas ~90)")
        if "sinal" in p:
            p["sinal"] = p["sinal"].lower()
            if p["sinal"] not in {"credito", "debito"}:
                erro(f"sinal '{p['sinal']}' inválido", "use credito ou debito")
        try:
            p["gera_pendencia"] = sim_nao(p.get("gera_pendencia", "false"))
        except ValueError as e:
            erro(f"gera_pendencia: {e}", "use true ou false")
        if p["gera_pendencia"] and "tipo_pendencia" not in p:
            erro("gera_pendencia=true sem tipo_pendencia", "informe tipo_pendencia=... (ex.: DEVOLUCAO)")

    elif tipo == "DONO_PENDENCIA":
        if not regra.quem_decide:
            erro("DONO_PENDENCIA sem quem_decide", "preencha a coluna quem_decide")

    elif tipo == "MANUAL":
        if "contem" in p or "banco" in p:
            if not {"contem", "banco"} <= p.keys():
                return erro("MANUAL com contem precisa de banco (e vice-versa)", "informe os dois")
            _validar_banco_contem(p, erro, ctx.bancos)
        if "cnpj" in p:
            try:
                p["cnpj"] = cnpj_config(p["cnpj"], avisos, onde)
            except ValueError as e:
                erro(str(e), "corrija o CNPJ")
        if "linha_negocio" in p:
            p["linha_negocio"] = normalizar(p["linha_negocio"])
            if p["linha_negocio"] not in PRODUTOS:
                erro(f"linha_negocio '{p['linha_negocio']}' inválida", "use CHECKOUT ou REMESSA")


def _validar_banco_contem(p: dict, erro, bancos: set[str]):
    p["banco"] = normalizar(p["banco"])
    if p["banco"] not in bancos | {"TODOS"}:
        erro(f"banco '{p['banco']}' inválido", f"use {', '.join(sorted(bancos))} ou TODOS")
    p["contem_alternativas"] = alternativas(p["contem"])
    curtas = [a for a in p["contem_alternativas"] if len(a) < 3]
    if not p["contem_alternativas"] or curtas:
        erro(f"contem '{p['contem']}' vazio ou curto demais",
             "use trechos de pelo menos 3 letras do extrato, separados por ' OU '")


def _sobrepoe(a: Regra, b: Regra) -> bool:
    inicio_a, fim_a = a.vigencia_de or date.min, a.vigencia_ate or date.max
    inicio_b, fim_b = b.vigencia_de or date.min, b.vigencia_ate or date.max
    return inicio_a <= fim_b and inicio_b <= fim_a


def _chave_conflito(r: Regra):
    """Regras com a mesma chave não podem estar ativas ao mesmo tempo."""
    p = r.params
    if r.tipo == "PARAMETRO":
        return ("PARAMETRO", next(iter(p)))
    if r.tipo == "TAXA_EXCECAO":
        return ("TAXA_EXCECAO", p["cnpj"], p["linha_negocio"])
    if r.tipo == "IGNORAR_DUPLICADO":
        return ("IGNORAR_DUPLICADO", p["fonte"])
    if r.tipo == "EXCLUIR_E_PENDENCIA":
        extra = tuple(sorted(p.get("status", set()) | p.get("aceitos", set())))
        return ("EXCLUIR_E_PENDENCIA", p["fonte"], p["criterio"], extra)
    if r.tipo == "CLASSIFICAR_CONTA":
        return ("CLASSIFICAR_CONTA", p["banco"], tuple(p["contem_alternativas"]), p.get("sinal"))
    if r.tipo == "DONO_PENDENCIA":
        return ("DONO_PENDENCIA", p["tipo_pendencia"])
    return None


def validar_conjunto(regras: list[Regra], erros: list[str]):
    ativas = [r for r in regras if r.status == "ATIVA"]
    grupos: dict = {}
    for r in ativas:
        chave = _chave_conflito(r)
        if chave:
            grupos.setdefault(chave, []).append(r)
    for chave, grupo in grupos.items():
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                produtos_cruzam = (chave[0] != "TAXA_EXCECAO" or "TODOS" in a.params["produto"]
                                   or "TODOS" in b.params["produto"]
                                   or a.params["produto"] & b.params["produto"])
                if produtos_cruzam and _sobrepoe(a, b):
                    erros.append(f"regras_negocio.csv: as regras {a.id} (linha {a.linha}) e {b.id} "
                                 f"(linha {b.linha}) estão ativas ao mesmo tempo para a mesma situação. "
                                 "Como corrigir: ajuste vigencia_de/vigencia_ate ou inative uma delas")
    nomes = {next(iter(r.params)) for r in ativas if r.tipo == "PARAMETRO"}
    for nome in sorted(set(PARAMETROS) - nomes):
        erros.append(f"regras_negocio.csv: falta a regra PARAMETRO ativa '{nome}'. "
                     f"Como corrigir: crie uma linha tipo PARAMETRO com parametros {nome}=...")
    donos = {r.params["tipo_pendencia"] for r in ativas if r.tipo == "DONO_PENDENCIA"}
    for tp in sorted(PENDENCIAS_DO_MOTOR - donos):
        erros.append(f"regras_negocio.csv: falta a regra DONO_PENDENCIA ativa para '{tp}' (diz quem decide). "
                     f"Como corrigir: crie uma linha tipo DONO_PENDENCIA com parametros tipo_pendencia={tp}")
