"""Comandos de apoio da CLI: explicar, pendencias, regra propor / regra aplicar.

Nenhum deles recalcula: lêem o que `fechar` gravou em saida/ e a base de regras.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from .dinheiro import brl, soma
from .regras import (COLUNAS_COMPLEMENTO, COLUNAS_REGRAS, STATUS_CADASTRO, TIPOS, Regra, _Contexto, cnpj_config,
                     formatar_parametros, ler_csv_regras, normalizar, parse_parametros, validar_conjunto,
                     validar_linha_regra)
from .saida import COLUNAS_OBRIGATORIAS

ARQUIVOS_COM_ID = {
    "comissoes_por_lojista.csv": "comissao_brl", "divergencias_taxa.csv": "diferenca_brl",
    "notas_a_emitir.csv": "valor_brl", "lancamentos_classificados.csv": "valor", "pendencias.csv": "valor_brl",
}
PREFIXOS = {"PARAMETRO": "P", "TAXA_EXCECAO": "X", "IGNORAR_DUPLICADO": "D", "EXCLUIR_E_PENDENCIA": "E",
            "AJUSTE_PARCEIRO": "J", "CLASSIFICAR_CONTA": "C", "DONO_PENDENCIA": "DP", "ALERTA": "A", "MANUAL": "M"}
_RE_ID_REGRA = re.compile(r"^[A-Z]+-\d+")
COLUNAS_APROVADORES = ["tipo", "quem_aprova", "quem_registra", "informado_por", "data"]
COLUNAS_HISTORICO = ["data", "quem", "id_regra", "acao", "antes", "depois", "motivo", "fonte", "aprovado_por", "registrado_por"]


class ErroComando(Exception):
    def __init__(self, codigo: int, mensagem: str):
        self.codigo, self.mensagem = codigo, mensagem
        super().__init__(mensagem)


def _ler_saida(pasta: Path, nome: str) -> pd.DataFrame:
    caminho = Path(pasta) / nome
    if not caminho.exists():
        raise ErroComando(1, f"{caminho} não existe. Rode `python -m src fechar` antes.")
    return pd.read_csv(caminho, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")


def _dec(texto: str) -> Decimal | None:
    try:
        return Decimal(texto) if texto not in ("", None) else None
    except InvalidOperation:
        return None


# --------------------------------------------------------------------------- explicar

def regras_cruas(dir_regras: Path) -> dict[str, dict]:
    """Texto das regras por id, sem validar (para explicar números mesmo sem os arquivos do mês)."""
    caminho = Path(dir_regras) / "regras_negocio.csv"
    if not caminho.exists():
        return {}
    return {r["id"]: {"tipo": r["tipo"], "situacao": r["situacao"], "o_que_fazer": r["o_que_fazer"],
                      "parametros": r["parametros"], "informado_por": r["informado_por"]}
            for _, r in ler_csv_regras(caminho, COLUNAS_REGRAS)}


def explicar(id_saida: str, pasta_saida: Path, regras: dict[str, dict] | None = None,
             dados: dict | None = None) -> dict:
    """De onde vem um número: a linha da saída, as linhas do rastro e, se houver dados, a origem de cada uma."""
    id_saida = id_saida.strip().upper()
    achado = None
    for nome, col_valor in ARQUIVOS_COM_ID.items():
        df = _ler_saida(pasta_saida, nome)
        sel = df[df["id_saida"] == id_saida]
        if len(sel):
            achado = {"arquivo": nome, "coluna_valor": col_valor, "linha": sel.iloc[0].to_dict()}
            break
    if achado is None:
        raise ErroComando(4, f"id_saida {id_saida} não existe em nenhuma saída de {pasta_saida}")
    rastro = _ler_saida(pasta_saida, "rastro.csv")
    linhas = rastro[rastro["id_saida"] == id_saida].to_dict("records")
    soma_rastro = soma(_dec(l["valor"]) for l in linhas)
    valor = _dec(achado["linha"].get(achado["coluna_valor"], ""))
    envolvidas = {}
    for rid in {l.get("regra_id", "") for l in linhas} | {achado["linha"].get("regra_id", "")}:
        m = _RE_ID_REGRA.match(rid or "")
        chave = m.group(0) if m else ""   # "P-01 (ajuste ref PC-...)" e "X-01" apontam para a regra; "planilha:..." não
        if regras and chave in regras:
            envolvidas[chave] = regras[chave]
    origem = _origens(linhas, dados) if dados else {}
    return {"id_saida": id_saida, **achado, "rastro": linhas, "rastro_linhas": len(linhas),
            "rastro_soma": str(soma_rastro), "bate": valor is not None and soma_rastro == valor,
            "regras": envolvidas, "origem": origem}


def _valor_legivel(v):
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if v is None or v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    return str(v)


def _origens(linhas: list[dict], dados: dict) -> dict:
    """Campos relevantes da linha original de cada ref_origem (quando os arquivos do mês estão disponíveis)."""
    indices = {}
    campos = {
        "orbe": (["data_movimento", "nome_estabelecimento", "tipo_lancamento", "modalidade", "qtd_parcelas", "valor_bruto",
                  "taxa_aplicada_pct", "valor_taxa", "id_referencia", "data_venda_original"], "ref_origem"),
        "ponte": (["data_contratacao", "cliente", "cnpj", "moeda", "valor_me", "taxa_cliente", "ptax", "valor_brl",
                   "spread_brl", "spread_pct", "status_compliance", "observacao"], "ref_origem"),
        "aurora": (["data", "descricao", "documento", "valor", "saldo"], "ref_origem"),
        "meridiano": (["data", "descricao", "valor", "tipo_trn"], "ref_origem"),
    }
    for fonte, (cols, chave) in campos.items():
        df = dados.get(fonte)
        if df is not None:
            indices[df.attrs.get("arquivo", "")] = (df.drop_duplicates(chave).set_index(chave), cols)
    out = {}
    for l in linhas:
        idx = indices.get(l["arquivo_origem"])
        if idx is None or l["ref_origem"] not in idx[0].index:
            continue
        row = idx[0].loc[l["ref_origem"]]
        out[l["ref_origem"]] = {c: _valor_legivel(row[c]) for c in idx[1] if c in row.index}
    return out


def imprimir_explicacao(e: dict) -> None:
    print(f"{e['id_saida']} está em {e['arquivo']}:")
    for k, v in e["linha"].items():
        if v != "":
            print(f"  {k:<22} {v}")
    print(f"\nRastro: {e['rastro_linhas']} linha(s) de origem somando {e['rastro_soma']} "
          f"({'bate' if e['bate'] else 'NÃO BATE'} com {e['coluna_valor']}).")
    for l in e["rastro"][:200]:
        extra = ""
        o = e["origem"].get(l["ref_origem"])
        if o:
            extra = "  <- " + ", ".join(f"{k}={v}" for k, v in o.items() if v not in (None, "", "None"))
        print(f"  {l['arquivo_origem']:<48} {l['ref_origem']:<16} {l['valor']:>14}  {l.get('regra_id', ''):<34} "
              f"{l.get('taxa_pct', '')}{extra}")
    if e["rastro_linhas"] > 200:
        print(f"  ... e mais {e['rastro_linhas'] - 200} linhas (veja rastro.csv)")
    if e["regras"]:
        print("\nRegras envolvidas:")
        for rid, r in e["regras"].items():
            print(f"  {rid} ({r['tipo']}): {r['situacao']}. {r['o_que_fazer']} [{r['parametros']}] — fonte: {r['informado_por']}")


# --------------------------------------------------------------------------- pendencias

def listar_pendencias(pasta_saida: Path, quem: str | None = None, tipo: str | None = None) -> dict:
    p = _ler_saida(pasta_saida, "pendencias.csv")
    if quem:
        p = p[p["quem_decide"].map(normalizar).str.contains(normalizar(quem))]
    if tipo:
        p = p[p["tipo"].map(normalizar) == normalizar(tipo)]
    grupos = []
    for q, g in p.groupby("quem_decide", sort=False):
        inf = g["informativa"].map(normalizar).eq("TRUE") if "informativa" in g.columns else pd.Series(False, index=g.index)
        incl = g["incluida_em"].astype(str).str.strip().ne("") if "incluida_em" in g.columns else pd.Series(False, index=g.index)
        valores = [_dec(v) for v, fora in zip(g["valor_brl"], inf | incl) if not fora]
        grupos.append({"quem_decide": q, "quantidade": int(len(g)), "informativas": int(inf.sum()), "incluidas_em_outra": int(incl.sum()),
                       "valor_em_jogo_brl": str(soma(abs(v) for v in valores if v is not None)),
                       "pendencias": g.to_dict("records")})
    return {"total": int(len(p)), "por_responsavel": grupos}


def imprimir_pendencias(res: dict) -> None:
    print(f"{res['total']} pendência(s)")
    for g in res["por_responsavel"]:
        inf, incl = g.get("informativas", 0), g.get("incluidas_em_outra", 0)
        notas_g = [f"{inf} informativa{'s' if inf > 1 else ''}"] * bool(inf) + [f"{incl} já incluída{'s' if incl > 1 else ''} em outra"] * bool(incl)
        print(f"\n{g['quem_decide']}: {g['quantidade']} pendência(s), {brl(Decimal(g['valor_em_jogo_brl']))} em jogo"
              + (f" ({', '.join(notas_g)})" if notas_g else ""))
        for r in g["pendencias"]:
            valor = brl(Decimal(r["valor_brl"])) if r["valor_brl"] else "sem valor"
            sub = f"/{r['subtipo']}" if r.get("subtipo") else ""
            marca = (" [informativa]" if normalizar(r.get("informativa", "")) == "TRUE"
                     else (f" [já incluída em {r['incluida_em']}]" if r.get("incluida_em") else ""))
            print(f"  {r['id_saida']} {r['tipo']}{sub} ({r['ref_origem']}, {valor}){marca}")
            print(f"      {r['motivo']}")


# --------------------------------------------------------------------------- regra propor / aplicar

@dataclass
class Proposta:
    alvo: str                 # regras_negocio.csv | complemento_cadastro.csv
    linha: dict               # colunas do CSV alvo
    avisos: list[str]
    erros: list[str]
    efeito: list[str]
    aprovacao: dict | None = None   # {"quem_aprova", "quem_registra"} de regras/aprovadores.csv

    @property
    def valida(self) -> bool:
        return not self.erros

    def para_json(self) -> dict:
        return {"alvo": self.alvo, "linha": self.linha, "avisos": self.avisos, "erros": self.erros, "efeito": self.efeito,
                "aprovacao": self.aprovacao}


# --------------------------------------------------------------------------- quem aprova (regras/aprovadores.csv)

def quem_aprova(dir_regras: Path, tipo: str) -> tuple[str, str]:
    """(quem aprova, quem registra) para um tipo de regra (ou COMPLEMENTO), de regras/aprovadores.csv.

    Linha com tipo igual vence; senão vale a linha '*'. Sem arquivo, qualquer pessoa aprova (como antes)."""
    caminho = Path(dir_regras) / "aprovadores.csv"
    if not caminho.exists():
        return ("", "")
    linhas = {normalizar(r["tipo"]): r for _, r in ler_csv_regras(caminho, COLUNAS_APROVADORES)}
    r = linhas.get(normalizar(tipo)) or linhas.get("*")
    if r is None:
        return ("", "")
    return (r["quem_aprova"], r["quem_registra"] or r["quem_aprova"])


def _aprovador_bate(aprovado_por: str, quem_aprova: str) -> bool:
    """O nome dado contém o identificador de quem aprova (primeira palavra de cada alternativa ' OU ')."""
    if not quem_aprova:
        return True
    dado = normalizar(aprovado_por)
    for alternativa in normalizar(quem_aprova).split(" OU "):
        chave = alternativa.replace("(", " ").split()[0] if alternativa.strip() else ""
        if chave and chave in dado:
            return True
    return False


def _proximo_id(regras: list[dict], tipo: str) -> str:
    prefixo = PREFIXOS[tipo]
    usados = [int(r["id"].split("-")[1]) for r in regras
              if r["id"].startswith(prefixo + "-") and r["id"].split("-")[1].isdigit()]
    return f"{prefixo}-{(max(usados) + 1 if usados else 1):02d}"


def _texto_sem_bom(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8").lstrip("﻿")


def propor(dir_regras: Path, tipo: str, campos: dict[str, str], contexto: _Contexto | None,
           lancamentos: pd.DataFrame | None = None, hoje: date | None = None) -> Proposta:
    """Monta a linha, valida como o motor validaria e descreve o efeito. Não grava."""
    hoje = hoje or date.today()
    dir_regras = Path(dir_regras)
    tipo_norm = normalizar(tipo)
    avisos: list[str] = []
    erros: list[str] = []
    if tipo_norm == "COMPLEMENTO":
        return _propor_complemento(dir_regras, campos, hoje)
    if tipo_norm not in TIPOS:
        return Proposta("regras_negocio.csv", {}, [], [f"tipo '{tipo}' desconhecido; use {', '.join(TIPOS)} ou COMPLEMENTO"], [])

    existentes = [r for _, r in ler_csv_regras(dir_regras / "regras_negocio.csv", COLUNAS_REGRAS)]
    linha = {c: "" for c in COLUNAS_REGRAS}
    linha.update({k: v for k, v in campos.items() if k in COLUNAS_REGRAS})
    desconhecidos = sorted(set(campos) - set(COLUNAS_REGRAS))
    if desconhecidos:
        erros.append(f"campos desconhecidos: {desconhecidos}. Use: {', '.join(COLUNAS_REGRAS)}")
    linha["tipo"] = tipo_norm
    linha["id"] = linha["id"] or _proximo_id(existentes, tipo_norm)
    linha["status"] = linha["status"] or "ATIVA"
    linha["data"] = linha["data"] or hoje.isoformat()
    if not linha["informado_por"]:
        erros.append("informado_por vazio: diga quem informou a regra (pessoa, canal, horário)")
    if not linha["situacao"]:
        erros.append("situacao vazia: descreva em uma frase a situação que a regra trata")
    if any(r["id"] == linha["id"] for r in existentes):
        erros.append(f"id {linha['id']} já existe; deixe em branco para numerar automaticamente")

    ctx = contexto or _Contexto(contas_ok=set(), contas_todas=set(), cnpjs=set(), bancos={"AURORA", "MERIDIANO"})
    if contexto is None:
        avisos.append("sem --entrada: conta contábil e CNPJ não foram conferidos contra o plano de contas e o cadastro")
        # sem plano de contas, qualquer conta passa na validação estrutural
        ctx = _Contexto(contas_ok=_contas_mencionadas(existentes) | {_conta_de(campos)} - {None},
                        contas_todas=_contas_mencionadas(existentes) | {_conta_de(campos)} - {None},
                        cnpjs=_cnpjs_mencionados(existentes, dir_regras) | {_cnpj_de(campos)} - {None},
                        bancos={"AURORA", "MERIDIANO"})
    erros_val: list[str] = []
    regra = validar_linha_regra(linha, 0, ctx, erros_val, avisos, "proposta")
    erros += erros_val
    if regra is not None:
        todas = []
        erros_existentes: list[str] = []
        for n, r in ler_csv_regras(dir_regras / "regras_negocio.csv", COLUNAS_REGRAS):
            rr = validar_linha_regra(r, n, ctx, erros_existentes, [], "regras_negocio.csv")
            if rr is not None:
                todas.append(rr)
        conjunto: list[str] = []
        validar_conjunto(todas + [regra], conjunto)
        # só interessam conflitos que envolvem a regra nova
        erros += [e for e in conjunto if regra.id in e]
    efeito = _efeito(regra, lancamentos) if regra is not None and not erros else []
    qa, qr = quem_aprova(dir_regras, tipo_norm)
    return Proposta("regras_negocio.csv", linha, avisos, erros, efeito, {"quem_aprova": qa, "quem_registra": qr})


def _conta_de(campos: dict) -> str | None:
    try:
        return parse_parametros(campos.get("parametros", "")).get("conta")
    except ValueError:
        return None


def _cnpj_de(campos: dict) -> str | None:
    try:
        c = parse_parametros(campos.get("parametros", "")).get("cnpj")
        return cnpj_config(c, [], "proposta") if c else None
    except ValueError:
        return None


def _contas_mencionadas(regras: list[dict]) -> set[str]:
    out = set()
    for r in regras:
        try:
            c = parse_parametros(r["parametros"]).get("conta")
        except ValueError:
            c = None
        if c:
            out.add(c)
    return out


def _cnpjs_mencionados(regras: list[dict], dir_regras: Path) -> set[str]:
    out = set()
    for r in regras:
        try:
            c = parse_parametros(r["parametros"]).get("cnpj")
            if c:
                out.add(cnpj_config(c, [], "x"))
        except ValueError:
            pass
    compl = dir_regras / "complemento_cadastro.csv"
    if compl.exists():
        for _, c in ler_csv_regras(compl, COLUNAS_COMPLEMENTO):
            try:
                out.add(cnpj_config(c["cnpj"], [], "x"))
            except ValueError:
                pass
    return out


def _efeito(regra: Regra, lancamentos: pd.DataFrame | None) -> list[str]:
    p = regra.params
    if regra.tipo == "CLASSIFICAR_CONTA":
        efeito = [f"lançamentos do {p['banco']} cuja descrição contém {' OU '.join(p['contem_alternativas'])}"
                  f"{' (só ' + p['sinal'] + 's)' if p.get('sinal') else ''} vão para a conta {p['conta']} "
                  f"com prioridade {p['prioridade']} (menor vence)"]
        if lancamentos is not None and len(lancamentos):
            texto = lancamentos["descricao"].map(normalizar)
            casa = lancamentos[(lancamentos["banco"] == p["banco"]) | (p["banco"] == "TODOS")]
            casa = casa[texto.loc[casa.index].map(lambda t: any(a in t for a in p["contem_alternativas"]))]
            if p.get("sinal") == "credito":
                casa = casa[casa["valor"].map(Decimal) > 0]
            elif p.get("sinal") == "debito":
                casa = casa[casa["valor"].map(Decimal) < 0]
            efeito.append(f"no último fechamento casaria {len(casa)} lançamento(s): "
                          + ", ".join(f"{r.ref_origem} ({r.conta_codigo or 'sem conta'} hoje)" for r in casa.head(8).itertuples()))
        return efeito
    if regra.tipo == "TAXA_EXCECAO":
        natureza = ("vira divergência de contrato (divergencias_taxa.csv)" if p.get("divergencia", "CONTRATO") == "CONTRATO"
                    else f"fica fora de divergencias_taxa.csv e vira pendência {p.get('tipo_pendencia')} ({p['divergencia'].lower().replace('_', ' ')})")
        return [f"lojista {p['cnpj']}: taxa {p['taxa_pct']}% em {p['linha_negocio']} para "
                f"{'todos os produtos' if p['produto'] == {'TODOS'} else ', '.join(sorted(p['produto']))}, "
                f"de {regra.vigencia_de} até {regra.vigencia_ate or 'sem fim'}; o que for cobrado diferente {natureza}"]
    if regra.tipo == "PARAMETRO":
        nome = next(iter(p))
        return [f"parâmetro {nome} passa a valer {regra.valor} a partir de {regra.vigencia_de or 'sempre'}"]
    if regra.tipo == "EXCLUIR_E_PENDENCIA":
        return [f"linhas da fonte {p['fonte']} que caírem no critério {p['criterio']} saem da comissão e viram "
                f"pendência {p['tipo_pendencia']} para {regra.quem_decide}"]
    if regra.tipo == "DONO_PENDENCIA":
        return [f"pendências do tipo {p['tipo_pendencia']}{' / ' + p['subtipo'] if p.get('subtipo') else ''} "
                f"passam a ser de {regra.quem_decide}"]
    if regra.tipo == "ALERTA":
        return [f"lojistas da fonte {p['fonte']} que caírem no critério {p['criterio']}"
                f"{' (só ' + ', '.join(sorted(p['so_para'])) + ')' if p['so_para'] else ''} geram a pendência "
                f"{p['tipo_pendencia']} para {regra.quem_decide}; nada sai da comissão"]
    if regra.tipo == "IGNORAR_DUPLICADO":
        return [f"linhas repetidas da fonte {p['fonte']} pela chave {p['chave']} contam uma vez"]
    if regra.tipo == "AJUSTE_PARCEIRO":
        como = ("cuja observação traz um dos trechos seguido do Nº da operação original" if p["criterio"] == "observacao_ref"
                else "cuja observação contém um dos trechos")
        return [f"linhas da fonte {p['fonte']} {como} ({' OU '.join(p['contem_alternativas'])}) viram AJUSTE_PONTE: entram na "
                f"comissão do mês pela participação sobre o Spread R$ (com sinal) e geram a pendência {p['tipo_pendencia']} para "
                f"{regra.quem_decide}; prioridade {p['prioridade']} entre as regras de destino (menor vence)"]
    return [f"lembrete para {regra.quem_decide} em todo fechamento: {regra.o_que_fazer}"]


def _propor_complemento(dir_regras: Path, campos: dict[str, str], hoje: date) -> Proposta:
    avisos: list[str] = []
    erros: list[str] = []
    linha = {c: "" for c in COLUNAS_COMPLEMENTO}
    linha.update({k: v for k, v in campos.items() if k in COLUNAS_COMPLEMENTO})
    desconhecidos = sorted(set(campos) - set(COLUNAS_COMPLEMENTO))
    if desconhecidos:
        erros.append(f"campos desconhecidos: {desconhecidos}. Use: {', '.join(COLUNAS_COMPLEMENTO)}")
    linha["data"] = linha["data"] or hoje.isoformat()
    try:
        linha["cnpj"] = cnpj_config(linha["cnpj"], avisos, "proposta")
    except ValueError as e:
        erros.append(str(e))
    if linha["ec_orbe"] and not linha["ec_orbe"].isdigit():
        erros.append(f"ec_orbe '{linha['ec_orbe']}' deve ter só dígitos")
    linha["status"] = normalizar(linha["status"]) or "ATIVO"
    if linha["status"] not in STATUS_CADASTRO:
        erros.append(f"status '{linha['status']}' inválido (use {', '.join(sorted(STATUS_CADASTRO))})")
    if not linha["informado_por"]:
        erros.append("informado_por vazio")
    existentes = [c for _, c in ler_csv_regras(dir_regras / "complemento_cadastro.csv", COLUNAS_COMPLEMENTO)]
    if any(cnpj_config(c["cnpj"], [], "x") == linha["cnpj"] for c in existentes if c["cnpj"]):
        erros.append(f"CNPJ {linha['cnpj']} já está no complemento; edite a linha existente")
    efeito = [f"CNPJ {linha['cnpj']} passa a ter EC {linha['ec_orbe'] or '(sem EC)'} e status {linha['status']}; "
              "se a planilha de taxas trouxer um EC diferente, o fechamento para com erro"] if not erros else []
    qa, qr = quem_aprova(dir_regras, "COMPLEMENTO")
    return Proposta("complemento_cadastro.csv", linha, avisos, erros, efeito, {"quem_aprova": qa, "quem_registra": qr})


def gravar_proposta(p: Proposta, caminho: Path) -> Path:
    Path(caminho).write_text(json.dumps(p.para_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return Path(caminho)


def ler_proposta(caminho: Path) -> Proposta:
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return Proposta(d["alvo"], d["linha"], d.get("avisos", []), d.get("erros", []), d.get("efeito", []), d.get("aprovacao"))


def aplicar(dir_regras: Path, proposta: Proposta, aprovado_por: str, contexto: _Contexto | None,
            hoje: date | None = None, registrado_por: str | None = None) -> dict:
    """Revalida a proposta contra a base atual, confere quem pode aprovar o tipo e grava:
    linha no CSV alvo + linha no histórico (com aprovado_por e registrado_por)."""
    hoje = hoje or date.today()
    dir_regras = Path(dir_regras)
    if not aprovado_por.strip():
        raise ErroComando(2, "--aprovado-por é obrigatório: nenhuma regra é gravada sem aprovação de uma pessoa")
    if proposta.alvo == "regras_negocio.csv":
        campos = {k: v for k, v in proposta.linha.items() if k != "tipo"}
        revalidada = propor(dir_regras, proposta.linha["tipo"], campos, contexto, None, hoje)
    else:
        revalidada = _propor_complemento(dir_regras, proposta.linha, hoje)
    if not revalidada.valida:
        raise ErroComando(2, "Proposta inválida contra a base atual:\n  - " + "\n  - ".join(revalidada.erros))
    tipo = proposta.linha.get("tipo", "COMPLEMENTO") if proposta.alvo == "regras_negocio.csv" else "COMPLEMENTO"
    qa, qr = quem_aprova(dir_regras, tipo)
    if not _aprovador_bate(aprovado_por, qa):
        raise ErroComando(2, f"Regra do tipo {tipo} é aprovada por {qa} e registrada por {qr} (regras/aprovadores.csv). "
                             f"'{aprovado_por}' não pode aprovar. Use --aprovado-por \"<nome> ({qa})\" e, se outra pessoa "
                             f"registrar, --registrado-por \"{qr}\"")
    registrado_por = (registrado_por or "").strip() or aprovado_por
    if not _aprovador_bate(registrado_por, qr):
        raise ErroComando(2, f"Regra do tipo {tipo} é registrada por {qr} (regras/aprovadores.csv); '{registrado_por}' não pode "
                             f"registrar. Use --registrado-por \"{qr}\"")
    alvo = dir_regras / proposta.alvo
    colunas = COLUNAS_REGRAS if proposta.alvo == "regras_negocio.csv" else COLUNAS_COMPLEMENTO
    linha = revalidada.linha
    for c in colunas:
        if ";" in str(linha.get(c, "")):
            raise ErroComando(2, f"o campo {c} contém ';', que é o separador do CSV; troque por vírgula")
    _anexar_csv(alvo, [linha[c] for c in colunas])
    id_regra = linha["id"] if proposta.alvo == "regras_negocio.csv" else f"complemento:{linha['cnpj']}"
    depois = (f"{linha['tipo']}: {linha['parametros']}" if proposta.alvo == "regras_negocio.csv"
              else f"ec_orbe={linha['ec_orbe']}, status={linha['status']}")
    motivo = linha.get("situacao") or linha.get("observacao") or ""
    fonte = linha.get("informado_por", "")
    historico = dir_regras / "historico_alteracoes.csv"
    _garantir_colunas_historico(historico)
    _anexar_csv(historico, [hoje.isoformat(), aprovado_por, id_regra, "CRIOU", "", depois, motivo, fonte,
                            aprovado_por, registrado_por])
    return {"arquivo": str(alvo), "id_regra": id_regra, "linha": linha, "historico": str(historico),
            "aprovado_por": aprovado_por, "registrado_por": registrado_por}


def _garantir_colunas_historico(caminho: Path) -> None:
    """Histórico antigo (sem aprovado_por/registrado_por) ganha as colunas, com as linhas antigas em branco."""
    if not caminho.exists():
        caminho.write_text("\ufeff" + ";".join(COLUNAS_HISTORICO) + "\n", encoding="utf-8")
        return
    texto = caminho.read_text(encoding="utf-8")
    linhas = texto.split("\n")
    cab = [c.strip() for c in linhas[0].lstrip("\ufeff").split(";")]
    faltam = [c for c in COLUNAS_HISTORICO if c not in cab]
    if not faltam:
        return
    bom = "\ufeff" if texto.startswith("\ufeff") else ""
    novas = [bom + ";".join(cab + faltam)] + [l + (";" * len(faltam) if l.strip() else "") for l in linhas[1:]]
    caminho.write_text("\n".join(novas), encoding="utf-8")


def _anexar_csv(caminho: Path, valores: list[str]) -> None:
    texto = caminho.read_text(encoding="utf-8")
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", lineterminator="\n").writerow(valores)
    novo = texto if texto.endswith("\n") else texto + "\n"
    caminho.write_text(novo + buf.getvalue(), encoding="utf-8")
