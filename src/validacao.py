"""Checagens de integridade que rodam em toda execução.

ERRO interrompe o fechamento (número não confiável). AVISO aparece no resumo
mas não impede a saída. Nada aqui depende do mês: só invariantes dos arquivos e
das saídas. Numeração das checagens de saída conforme a especificação (1 a 6).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

CENTAVO = Decimal("0.01")


@dataclass
class Checagem:
    fonte: str
    nome: str
    ok: bool
    detalhe: str
    nivel: str = "ERRO"  # ERRO | AVISO | INFO
    acao: str = ""       # o que a pessoa deve fazer quando a checagem AVISO falha (vai para os avisos do fechamento)

    def __post_init__(self):
        self.ok = bool(self.ok)  # numpy.bool_ viraria "True" no JSON


def avisos_dos_leitores(checagens: list[Checagem]) -> list[str]:
    """Checagens de nível AVISO que falharam, em texto para Fechamento.avisos (resumo.json e seção Avisos do
    relatório): fonte, o que não fechou e a ação esperada."""
    return [f"{c.fonte}: {c.nome} ({c.detalhe})" + (f". Ação: {c.acao}" if c.acao else "")
            for c in checagens if c.nivel == "AVISO" and not c.ok]


def checar_competencia_extratos(extratos: list[pd.DataFrame], competencia: str) -> list[Checagem]:
    """Extrato de outro mês não pode passar como sucesso. Nenhum lançamento na competência -> ERRO ("o extrato X é de
    outro mês"); alguns fora -> AVISO com banco, quantidade e período (os lançamentos são classificados normalmente)."""
    c = []
    for df in extratos:
        if not len(df):
            continue
        banco, arquivo = df["banco"].iloc[0], df["arquivo_origem"].iloc[0]
        meses = df["data"].dt.strftime("%Y-%m")
        fora = df[meses != competencia]
        de, ate = df["data"].min().date(), df["data"].max().date()
        if len(fora) == len(df):
            c.append(Checagem(banco, "lançamentos na competência", False,
                              f"o extrato {arquivo} é de outro mês: nenhum dos {len(df)} lançamentos do {banco} está em "
                              f"{competencia} (datas de {de} a {ate}); confira o arquivo ou --competencia"))
        elif len(fora):
            c.append(Checagem(banco, "lançamentos na competência", False,
                              f"{len(fora)} de {len(df)} lançamentos do {banco} ({arquivo}) fora de {competencia}, de "
                              f"{fora['data'].min().date()} a {fora['data'].max().date()}", "AVISO",
                              acao="conferir se o extrato é do mês certo; esses lançamentos foram classificados normalmente"))
        else:
            c.append(Checagem(banco, "lançamentos na competência", True, f"{len(df)} lançamentos em {competencia}"))
    return c


def _soma(serie) -> Decimal:
    return sum((v for v in serie if v is not None), Decimal("0"))


def _hu(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _eh_valor(v) -> bool:
    return v is not None and (isinstance(v, Decimal) or not pd.isna(v))


# --------------------------------------------------------------------------- saídas (1 a 6)

def checar_rastro(saidas: dict[str, tuple[pd.DataFrame, str]], rastro: pd.DataFrame) -> list[Checagem]:
    """Checagem 1: a soma do rastro por id_saida é igual ao valor reportado, para todo id com valor.

    `saidas` = {nome do arquivo: (DataFrame, coluna de valor)}. Também confere que todo
    id do rastro existe em alguma saída (nada órfão).
    """
    c: list[Checagem] = []
    somas = rastro.groupby("id_saida")["valor"].apply(_soma) if len(rastro) else pd.Series(dtype=object)
    ids_saida: set[str] = set()
    for nome, (df, coluna) in saidas.items():
        nao_batem, sem_rastro, conferidos = [], [], 0
        for id_saida, valor in zip(df["id_saida"], df[coluna]):
            ids_saida.add(id_saida)
            if not _eh_valor(valor):
                continue  # linha sem valor (ex.: pendência informativa) não precisa de rastro
            if id_saida not in somas.index:
                sem_rastro.append(id_saida)
                continue
            conferidos += 1
            if somas[id_saida] != valor:
                nao_batem.append(f"{id_saida}: reportado {valor}, rastro {somas[id_saida]}")
        ok = not nao_batem and not sem_rastro
        detalhe = (f"{conferidos} ids conferidos" if ok else
                   f"{len(nao_batem)} não batem {nao_batem[:3]}; {len(sem_rastro)} sem rastro {sem_rastro[:3]}")
        c.append(Checagem("integridade", f"1. soma do rastro = valor reportado ({nome})", ok, detalhe))
    orfaos = sorted(set(somas.index) - ids_saida)
    c.append(Checagem("integridade", "1. todo id do rastro existe nas saídas", not orfaos,
                      f"{len(somas)} ids no rastro" if not orfaos else f"órfãos: {orfaos[:5]}"))
    return c


def checar_notas(com_chk: pd.DataFrame, com_rem: pd.DataFrame, notas: pd.DataFrame) -> list[Checagem]:
    """Checagens 2 e 3: notas de checkout = comissões com saldo > 0; nota de remessa = total da remessa."""
    positivas = _soma(v for v in com_chk["comissao_brl"] if v > 0) if len(com_chk) else Decimal("0")
    nf_chk = notas[notas["linha_negocio"] == "CHECKOUT"] if len(notas) else notas
    soma_nf_chk = _soma(nf_chk["valor_brl"]) if len(nf_chk) else Decimal("0")
    n_pos = int((com_chk["comissao_brl"] > 0).sum()) if len(com_chk) else 0
    c = [Checagem("integridade", "2. comissões de checkout com saldo > 0 = notas CHECKOUT",
                  positivas == soma_nf_chk and n_pos == len(nf_chk),
                  f"{n_pos} lojistas somam {positivas}; {len(nf_chk)} notas somam {soma_nf_chk}")]
    total_rem = _soma(com_rem["comissao_brl"]) if len(com_rem) else Decimal("0")
    nf_rem = notas[notas["linha_negocio"] == "REMESSA"] if len(notas) else notas
    soma_nf_rem = _soma(nf_rem["valor_brl"]) if len(nf_rem) else Decimal("0")
    ok = (soma_nf_rem == total_rem and len(nf_rem) <= 1) if total_rem > 0 else len(nf_rem) == 0
    c.append(Checagem("integridade", "3. nota REMESSA = soma da comissão de remessa", ok,
                      f"comissão {total_rem}; {len(nf_rem)} nota(s) somam {soma_nf_rem}"))
    return c


def checar_destinos(orbe_linhas: pd.DataFrame, n_orbe: int, ponte_linhas: pd.DataFrame, n_ponte: int
                    ) -> list[Checagem]:
    """Checagem 4: toda linha da Orbe e toda operação única da Ponte em exatamente um destino."""
    c = []
    dest_orbe = orbe_linhas["destino"].value_counts().to_dict()
    ok = len(orbe_linhas) == n_orbe and orbe_linhas["destino"].notna().all() and orbe_linhas["ref_origem"].is_unique
    c.append(Checagem("integridade", "4. toda linha da Orbe tem exatamente um destino", ok,
                      f"{n_orbe} linhas -> " + ", ".join(f"{k} {v}" for k, v in dest_orbe.items())))
    c.append(Checagem("integridade", "4. há linhas da Orbe na competência fechada",
                      dest_orbe.get("COMISSAO", 0) + dest_orbe.get("EXCLUIDO", 0) > 0,
                      "nenhuma linha da Orbe entrou no mês: confira --competencia e o arquivo"
                      if dest_orbe.get("COMISSAO", 0) + dest_orbe.get("EXCLUIDO", 0) == 0 else "ok"))
    por_op = ponte_linhas.groupby("num_operacao")["destino"].apply(
        lambda s: tuple(sorted(set(s) - {"DUPLICATA_IGNORADA"})))
    ruins = [op for op, d in por_op.items() if len(d) != 1]
    dest_ponte = ponte_linhas["destino"].value_counts().to_dict()
    ok = len(ponte_linhas) == n_ponte and ponte_linhas["destino"].notna().all() and not ruins
    c.append(Checagem("integridade", "4. toda operação única da Ponte tem exatamente um destino", ok,
                      f"{n_ponte} linhas, {len(por_op)} operações únicas -> "
                      + ", ".join(f"{k} {v}" for k, v in dest_ponte.items())
                      + (f"; operações com destino ambíguo: {ruins[:5]}" if ruins else "")))
    return c


def checar_lancamentos(lancamentos: pd.DataFrame, extratos: list[pd.DataFrame]) -> list[Checagem]:
    """Checagem 5: todo lançamento dos extratos aparece em lancamentos_classificados (e só uma vez)."""
    c = []
    for df in extratos:
        banco = df["banco"].iloc[0] if len(df) else "?"
        esperados = set(df["ref_origem"])
        presentes = set(lancamentos.loc[lancamentos["banco"] == banco, "ref_origem"])
        faltam, sobram = sorted(esperados - presentes), sorted(presentes - esperados)
        repetidos = int(lancamentos.loc[lancamentos["banco"] == banco, "ref_origem"].duplicated().sum())
        ok = not faltam and not sobram and repetidos == 0
        c.append(Checagem("integridade", f"5. todo lançamento do {banco} está classificado", ok,
                          f"{len(esperados)} lançamentos" if ok else
                          f"faltam {faltam[:5]}, sobram {sobram[:5]}, repetidos {repetidos}"))
    sem_conta = lancamentos[(lancamentos["metodo"] == "REGRA") & (lancamentos["conta_codigo"] == "")]
    c.append(Checagem("integridade", "5. lançamento classificado por REGRA tem conta", len(sem_conta) == 0,
                      f"{len(sem_conta)} sem conta"))
    return c


def checar_saldo_extratos(extratos: list[pd.DataFrame]) -> list[Checagem]:
    """Checagem 6: onde o extrato traz saldo (Aurora), ele fecha linha a linha e no total."""
    c = []
    for df in extratos:
        ant, fim = df.attrs.get("saldo_anterior"), df.attrs.get("saldo_final")
        if not ant or "saldo" not in df.columns:
            continue
        banco = df["banco"].iloc[0] if len(df) else "?"
        soma = _soma(df["valor"])
        fecha_total = fim is None or ant["valor"] + soma == fim["valor"]
        corrente, quebras = ant["valor"], []
        for ref, v, s in zip(df["ref_origem"], df["valor"], df["saldo"]):
            corrente += v
            if s is not None and corrente != s:
                quebras.append(ref)
                corrente = s
        c.append(Checagem("integridade", f"6. saldo do {banco} fecha linha a linha", fecha_total and not quebras,
                          f"{ant['valor']} + {soma} = {ant['valor'] + soma}"
                          + (f"; extrato diz {fim['valor']}" if fim else "")
                          + (f"; {len(quebras)} quebras {quebras[:5]}" if quebras else "")))
    return c


# --------------------------------------------------------------------------- leitores

def validar_leitores(d: dict[str, pd.DataFrame]) -> list[Checagem]:
    c: list[Checagem] = []

    # Orbe
    o = d["orbe"]
    dup = o["id_transacao"].duplicated().sum()
    c.append(Checagem("orbe", "id_transacao único", dup == 0, f"{len(o)} linhas, {dup} ids repetidos"))
    ruins = sum(1 for b, t, l in zip(o.valor_bruto, o.valor_taxa, o.valor_liquido) if b - t != l)
    c.append(Checagem("orbe", "valor_liquido = valor_bruto - valor_taxa", ruins == 0,
                      f"{ruins} linhas não fecham"))

    # Taxas
    t = d["taxas"]
    c.append(Checagem("taxas", "CNPJ com 14 dígitos", t["cnpj"].str.fullmatch(r"\d{14}").all(),
                      f"{t['cnpj'].nunique()} CNPJs em {t['linha_planilha'].nunique()} linhas"))
    for ign in t.attrs.get("linhas_ignoradas", []):
        c.append(Checagem("taxas", "linha ignorada", True,
                          f"linha {ign['linha']} ({ign['motivo']}): {ign['conteudo']}", "INFO"))

    # Ponte
    p = d["ponte"]
    tot = p.attrs.get("totais_declarados", {})
    if "TOTAL DE OPERACOES:" in tot:
        n_decl = int(tot["TOTAL DE OPERACOES:"])
        c.append(Checagem("ponte", "linhas lidas = total declarado no relatório", len(p) == n_decl,
                          f"lidas {len(p)}, declarado {n_decl}"))
    if "SPREAD TOTAL R$:" in tot:
        s, s_decl = _soma(p.spread_brl), tot["SPREAD TOTAL R$:"]
        c.append(Checagem("ponte", "soma Spread R$ = total declarado no relatório", s == s_decl,
                          f"soma {s}, declarado {s_decl}"))
    ruins = sum(1 for me, tc, v in zip(p.valor_me, p.taxa_cliente, p.valor_brl) if _hu(me * tc) != v)
    c.append(Checagem("ponte", "Valor R$ = Valor ME x Taxa Cliente", ruins == 0,
                      f"{ruins} operações não fecham", "AVISO",
                      acao="conferir essas operações com o parceiro de câmbio antes de usar a conciliação"))
    ruins = sum(1 for me, tc, px, s in zip(p.valor_me, p.taxa_cliente, p.ptax, p.spread_brl)
                if _hu((tc - px) * me) != s)
    c.append(Checagem("ponte", "Spread R$ = (Taxa Cliente - PTAX) x Valor ME", ruins == 0,
                      f"{ruins} operações não fecham", "AVISO",
                      acao="conferir o Spread R$ dessas operações com o parceiro; a comissão usa o Spread R$ do relatório"))
    for ign in p.attrs.get("linhas_ignoradas", []) or []:
        c.append(Checagem("ponte", "linha ignorada", True,
                          f"linha {ign['linha']} sem Nº Operação ou data de contratação válida: {ign['conteudo']}", "INFO"))
    rep = p["num_operacao"].duplicated(keep=False)
    c.append(Checagem("ponte", "Nº Operação repetido", True,
                      f"{p.loc[rep, 'num_operacao'].nunique()} número(s) aparecem mais de uma vez: "
                      f"{sorted(p.loc[rep, 'num_operacao'].unique())}", "INFO"))

    # Plano de contas
    pc = d["plano_contas"]
    c.append(Checagem("plano_contas", "COD_CONTA único", not pc["cod_conta"].duplicated().any(),
                      f"{len(pc)} contas, {int(pc['aceita_lancto'].sum())} aceitam lançamento"))

    # Aurora
    a = d["aurora"]
    ant, fim = a.attrs.get("saldo_anterior"), a.attrs.get("saldo_final")
    if ant and fim:
        soma = _soma(a.valor)
        c.append(Checagem("aurora", "saldo anterior + lançamentos = saldo final",
                          ant["valor"] + soma == fim["valor"],
                          f"{ant['valor']} + {soma} = {ant['valor'] + soma}; extrato diz {fim['valor']}"))
    else:
        c.append(Checagem("aurora", "saldo anterior e final presentes", False,
                          "não encontrei SALDO ANTERIOR ou SALDO FINAL"))
    if ant:
        corrente, quebras = ant["valor"], []
        for ref, v, s in zip(a.ref_origem, a.valor, a.saldo):
            corrente += v
            if s is not None and corrente != s:
                quebras.append(ref)
                corrente = s
        c.append(Checagem("aurora", "saldo linha a linha", not quebras,
                          f"{len(quebras)} linhas com saldo que não fecha {quebras[:5]}"))

    # Meridiano
    m = d["meridiano"]
    dup = m["ref_origem"].duplicated().sum()
    c.append(Checagem("meridiano", "FITID único", dup == 0, f"{len(m)} transações, {dup} FITIDs repetidos"))
    de, ate = m.attrs.get("periodo_de"), m.attrs.get("periodo_ate")
    if de and ate:
        fora = ((m["data"].dt.date < de) | (m["data"].dt.date > ate)).sum()
        c.append(Checagem("meridiano", "datas dentro do período do extrato", fora == 0,
                          f"{fora} transações fora de {de} a {ate}", "AVISO",
                          acao="conferir com o banco se o extrato está completo e é do mês certo"))
    if m.attrs.get("saldo_final") is not None:
        implicito = m.attrs["saldo_final"] - _soma(m.valor)
        c.append(Checagem("meridiano", "saldo inicial (o OFX não informa)", True,
                          f"saldo final {m.attrs['saldo_final']} - lançamentos {_soma(m.valor)} "
                          f"= saldo inicial implícito {implicito}", "INFO"))
    return c
