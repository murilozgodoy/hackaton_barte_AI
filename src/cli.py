"""CLI do fechamento Tarvo: python -m src <comando> ...

Comandos: validar, fechar, explicar, pendencias, regra propor, regra aplicar, empacotar-skill.
Sem subcomando, equivale a `fechar`. `--regras` aceita uma pasta ou um .zip da base de regras.
Códigos de saída: 0 ok · 1 entrada · 2 regras · 3 integridade · 4 id inexistente.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from . import carteira as carteira_mod
from . import comandos
from .dinheiro import brl, soma
from .fechamento import Fechamento, escrever, executar, extratos_de
from .fontes import NAO_RECONHECIDOS, carregar_config_fontes, localizar, nome_arquivo, preparar_entrada
from .leitores import carregar_todas
from .leitores.comum import ErroLeitura
from .notas import competencia_texto, primeiro_dia
from .regras import Config, ErroConfig, _Contexto, carregar_config
from . import relatorio
from .relatorio import valor_em_jogo
from .validacao import Checagem, avisos_dos_leitores, checar_competencia_extratos, validar_leitores

RAIZ = Path(__file__).resolve().parents[1]
COMANDOS = ("validar", "fechar", "explicar", "pendencias", "regra", "empacotar-skill")
SAIDA_OK, SAIDA_ENTRADA, SAIDA_REGRAS, SAIDA_INTEGRIDADE, SAIDA_ID = 0, 1, 2, 3, 4
_RE_COMPETENCIA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class Parada(Exception):
    def __init__(self, codigo: int, mensagem: str):
        self.codigo, self.mensagem = codigo, mensagem
        super().__init__(mensagem)


@dataclass
class Contexto:
    pasta: Path
    arquivos: dict[str, Path]
    dados: dict[str, pd.DataFrame]
    config: Config
    competencia: str
    competencia_inferida: bool
    checagens: list[Checagem]


# --------------------------------------------------------------------------- base de regras (pasta ou zip)

@dataclass
class BaseRegras:
    pasta: Path                 # pasta com os CSVs (extraída, se veio de zip)
    zip_origem: Path | None     # zip de onde veio, se veio

    raiz_extracao: Path | None = None   # onde o zip foi extraído (para gravar o novo com o mesmo layout)

    def gravar_zip_novo(self, hoje: date) -> Path:
        """Em modo zip, a base alterada vira um zip novo ao lado do original (o original não é tocado)."""
        destino = self.zip_origem.with_name(f"{self.zip_origem.stem.split('_20')[0]}_{hoje.isoformat()}.zip")
        raiz = self.raiz_extracao or self.pasta
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.pasta.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(raiz).as_posix())
        return destino


def resolver_regras(caminho: Path) -> BaseRegras:
    caminho = Path(caminho)
    if caminho.is_dir():
        return BaseRegras(caminho, None)
    if caminho.is_file() and caminho.suffix.lower() == ".zip":
        pasta = Path(tempfile.mkdtemp(prefix="regras_"))
        with zipfile.ZipFile(caminho) as z:
            for m in z.infolist():
                if m.filename.startswith("/") or ".." in Path(m.filename).parts:
                    raise Parada(SAIDA_REGRAS, f"{caminho.name}: caminho suspeito no zip: {m.filename}")
            z.extractall(pasta)
        candidatos = list(pasta.rglob("regras_negocio.csv"))
        if len(candidatos) != 1:
            raise Parada(SAIDA_REGRAS, f"{caminho.name}: esperava exatamente um regras_negocio.csv no zip, "
                                       f"achei {len(candidatos)}")
        return BaseRegras(candidatos[0].parent, caminho, pasta)
    raise Parada(SAIDA_REGRAS, f"--regras {caminho} não é uma pasta nem um .zip")


# --------------------------------------------------------------------------- carga

def inferir_competencia(dados) -> str:
    """Mês mais frequente nas datas de movimento da Orbe, no formato AAAA-MM."""
    return dados["orbe"]["data_movimento"].dt.strftime("%Y-%m").mode().iloc[0]


def carregar_dados(args, base: BaseRegras):
    try:
        fontes = carregar_config_fontes(base.pasta)
        pasta = preparar_entrada(args.entrada, RAIZ, fontes)
        arquivos = localizar(pasta, fontes)
        dados = carregar_todas(arquivos, fontes)
    except ErroLeitura as e:
        raise Parada(SAIDA_ENTRADA, f"Entrada com problema: {e}") from None
    except ErroConfig as e:
        raise Parada(SAIDA_REGRAS, str(e)) from None
    return fontes, pasta, arquivos, dados


def carregar_contexto(args, base: BaseRegras) -> Contexto:
    """Lê entradas, roda as checagens dos leitores e carrega a base de regras."""
    if getattr(args, "competencia", None) and not _RE_COMPETENCIA.match(args.competencia):
        raise Parada(SAIDA_ENTRADA, f"--competencia '{args.competencia}' inválida: use AAAA-MM (ano com quatro dígitos e mês com dois)")
    fontes, pasta, arquivos, dados = carregar_dados(args, base)
    checagens = validar_leitores(dados)
    # arquivo na entrada que não bate com fonte nenhuma: não para, mas nunca some em silêncio (aviso persistido)
    for nome in arquivos.get(NAO_RECONHECIDOS) or []:
        checagens.append(Checagem("entrada", "arquivo reconhecido", False, f"arquivo {nome} não reconhecido; não foi usado", "AVISO",
                                  acao="se ele deveria entrar no fechamento, confira o formato contra a assinatura da fonte em regras/fontes.csv"))
    falhas = [c for c in checagens if c.nivel == "ERRO" and not c.ok]
    if falhas:
        detalhe = "\n  - ".join(f"{c.fonte}: {c.nome} ({c.detalhe})" for c in falhas)
        raise Parada(SAIDA_ENTRADA, f"Arquivos de entrada não fecham:\n  - {detalhe}")
    try:
        bancos = {f["rotulo"] for f in fontes.values() if f.get("rotulo")}
        config = carregar_config(base.pasta, dados["taxas"], dados["plano_contas"], bancos)
    except ErroConfig as e:
        raise Parada(SAIDA_REGRAS, str(e)) from None
    competencia = getattr(args, "competencia", None) or inferir_competencia(dados)
    primeiro = primeiro_dia(competencia)
    ultimo = (pd.Timestamp(primeiro) + pd.offsets.MonthEnd(0)).date()
    faltas = config.verificar_cobertura([primeiro, ultimo])
    if faltas:
        raise Parada(SAIDA_REGRAS, "Base de regras não cobre a competência " + competencia + ":\n  - " + "\n  - ".join(faltas))
    # extrato de outro mês não pode passar como sucesso: nenhum lançamento na competência é erro de entrada
    extr = checar_competencia_extratos(extratos_de(dados), competencia)
    checagens += extr
    falhas = [c for c in extr if c.nivel == "ERRO" and not c.ok]
    if falhas:
        raise Parada(SAIDA_ENTRADA, "Arquivos de entrada não fecham:\n  - " + "\n  - ".join(f"{c.fonte}: {c.detalhe}" for c in falhas))
    return Contexto(pasta, arquivos, dados, config, competencia, not getattr(args, "competencia", None), checagens)


def contexto_validacao(args, base: BaseRegras) -> tuple[_Contexto | None, Contexto | None]:
    """Para regra propor/aplicar: com --entrada, confere contas e CNPJs contra os arquivos do mês (e permite simular
    o efeito da regra no fechamento desse mês)."""
    if not getattr(args, "entrada", None):
        return None, None
    ctx = carregar_contexto(args, base)
    plano = ctx.dados["plano_contas"]
    bancos = {f["rotulo"] for f in carregar_config_fontes(base.pasta).values() if f.get("rotulo")}
    return _Contexto(contas_ok=set(plano.loc[plano["aceita_lancto"], "cod_conta"]), contas_todas=set(plano["cod_conta"]),
                     cnpjs=set(ctx.config.cadastro["cnpj"]), bancos=bancos), ctx


# --------------------------------------------------------------------------- impressão

def resumo_contexto(ctx: Contexto) -> dict:
    cad = ctx.config.cadastro
    por_tipo = pd.Series([r.tipo for r in ctx.config.regras]).value_counts().to_dict()
    return {
        "competencia": ctx.competencia,
        "competencia_inferida": ctx.competencia_inferida,
        "pasta_entrada": str(ctx.pasta),
        "fontes": {f: {"arquivo": nome_arquivo(ctx.arquivos[f]), "linhas": int(len(df)),
                       "encoding": df.attrs.get("encoding")} for f, df in ctx.dados.items()},
        "checagens": [{"fonte": c.fonte, "nome": c.nome, "ok": c.ok, "nivel": c.nivel, "detalhe": c.detalhe}
                      for c in ctx.checagens],
        "regras": {"lojistas": int(len(cad)),
                   "lojistas_por_origem": {k: int(v) for k, v in cad["origem"].value_counts().items()},
                   "ativas_por_tipo": {k: int(v) for k, v in por_tipo.items()},
                   "nao_ativas": [r.id for r in ctx.config.todas if r.status != "ATIVA"],
                   "ultima_alteracao_historico": str(ctx.config.historico_ultima_alteracao or ""),
                   "avisos": list(ctx.config.avisos)},
    }


def imprimir_contexto(ctx: Contexto) -> None:
    print(f"Pasta de entrada: {ctx.pasta}")
    print(f"Competência: {ctx.competencia}{' (inferida dos dados)' if ctx.competencia_inferida else ''}")
    for fonte, df in ctx.dados.items():
        print(f"  {fonte:<13} {len(df):>5} linhas  {nome_arquivo(ctx.arquivos[fonte])}  "
              f"(encoding: {df.attrs.get('encoding', '-')})")
    print("\nChecagens dos leitores:")
    for c in ctx.checagens:
        marca = "ok" if c.ok else c.nivel.lower()
        print(f"  [{marca:<5}] {c.fonte}: {c.nome} - {c.detalhe}")
    r = resumo_contexto(ctx)["regras"]
    print("\nBase de regras:")
    origem = ", ".join(f"{n} {o}" for o, n in r["lojistas_por_origem"].items())
    print(f"  cadastro: {r['lojistas']} lojistas ({origem})")
    print("  regras ativas: " + ", ".join(f"{t} {n}" for t, n in r["ativas_por_tipo"].items())
          + f"; última alteração registrada: {r['ultima_alteracao_historico'] or 'não informada'}")
    if r["nao_ativas"]:
        print(f"  regras não ativas (ignoradas): {', '.join(r['nao_ativas'])}")
    for aviso in r["avisos"]:
        print(f"  [aviso] {aviso}")


def _tabela_comissoes(df: pd.DataFrame, titulo: str, col_qtd: str, rotulo_qtd: str) -> None:
    print(f"\n{titulo}:")
    print(f"  {'id_saida':<13}{'lojista':<42}{'cnpj':<16}{rotulo_qtd:>10}  {'comissão':>16}")
    for r in df.itertuples(index=False):
        print(f"  {r.id_saida:<13}{str(r.lojista)[:40]:<42}{r.cnpj:<16}{int(getattr(r, col_qtd)):>10}  "
              f"{brl(r.comissao_brl):>16}")
    print(f"  {'TOTAL':<13}{'':<42}{'':<16}{int(df[col_qtd].sum()):>10}  {brl(soma(df['comissao_brl'])):>16}")


def imprimir_fechamento(f: Fechamento) -> None:
    _tabela_comissoes(f.comissoes_checkout, f"Comissão de CHECKOUT por lojista ({f.competencia})",
                      "qtd_transacoes", "transações")
    print("  Destino das linhas da Orbe: " + ", ".join(f"{k} {v}" for k, v in f.destinos_orbe.items()))
    _tabela_comissoes(f.comissoes_remessa, f"Comissão de REMESSA por lojista ({f.competencia})",
                      "qtd_operacoes", "operações")
    print("  Destino das linhas da Ponte: " + ", ".join(f"{k} {v}" for k, v in f.destinos_ponte.items()))

    print("\nDivergências de taxa (contratada x aplicada), por natureza e lojista:")
    if f.divergencias.empty:
        print("  nenhuma")
    for (natureza, linha, _cnpj), g in f.divergencias.groupby(["natureza", "linha_negocio", "cnpj"], sort=False):
        print(f"  {natureza:<19}{linha:<9}{str(g['lojista'].iloc[0])[:40]:<42}{len(g):>5} linhas  "
              f"{brl(soma(g['diferenca_brl'])):>16}")
    for (_cnpj, natureza), g in f.divergencias_fora_contrato.groupby(["cnpj", "natureza"], sort=False):
        print(f"  {natureza} (regra {g['regra_id'].iloc[0]}) fica fora da cobrança da contraparte: "
              f"{str(g['lojista'].iloc[0])[:40]}, {len(g)} linhas, {brl(soma(g['diferenca_brl']))} pela taxa")
    for (_cnpj, tipo), g in f.so_pendencia.groupby(["cnpj", "tipo_pendencia"], sort=False):
        print(f"  fora de divergencias_taxa.csv, por regra {g['regra_id'].iloc[0]}: {str(g['lojista'].iloc[0])[:40]}, "
              f"{len(g)} linhas, {brl(soma(g['cobrado_brl']))} cobrados de fato, só na pendência {tipo}")

    print("\nNotas a emitir:")
    for r in f.notas.itertuples(index=False):
        print(f"  {r.id_saida:<9}{r.linha_negocio:<9}{str(r.tomador)[:40]:<42}{r.tomador_cnpj:<16}{brl(r.valor_brl):>16}")
    print(f"  {'TOTAL':<9}{'':<9}{'':<42}{'':<16}{brl(soma(f.notas['valor_brl'])):>16}")
    for r in f.sem_nota.itertuples(index=False):
        print(f"  sem nota: {r.lojista} ({r.cnpj}) com comissão {brl(r.comissao_brl)} (zero ou negativa)")

    met = f.lancamentos["metodo"].value_counts().to_dict()
    print("\nLançamentos classificados: " + ", ".join(f"{k} {v}" for k, v in met.items())
          + f" (total {len(f.lancamentos)})")

    print(f"\nPendências ({len(f.pendencias)}), por responsável:")
    for quem, g in f.pendencias.groupby("quem_decide", sort=False):
        print(f"  {quem}: {len(g)} pendência(s), {brl(valor_em_jogo(g))} em jogo")
        for r in g.itertuples(index=False):
            valor = brl(r.valor_brl) if r.valor_brl is not None else "sem valor"
            sub = f"/{r.subtipo}" if r.subtipo else ""
            print(f"    {r.id_saida} {r.tipo}{sub:<30} {str(r.ref_origem)[:24]:<24} {valor:>16}  {str(r.lojista or '')[:30]}")

    print("\nChecagens de integridade:")
    for c in f.checagens:
        print(f"  [{'ok' if c.ok else 'ERRO':<5}] {c.nome} - {c.detalhe}")
    for aviso in f.avisos:
        print(f"  [aviso] {aviso}")


def imprimir_conciliacao(f: Fechamento, config: Config) -> None:
    c = f.conciliacao
    print("\nConciliação entre fontes (informativo, não gera pendência):")
    o = c["orbe_banco"]
    print("  Adquirente x banco: não conciliável com os arquivos do mês (ver lembrete no relatório).")
    print(f"    totais informativos, que não se comparam entre si: recebido da adquirente {brl(o['recebido_da_adquirente'])} "
          f"({o['qtd_recebimentos']} créditos); repassado a lojistas {brl(o['repassado_a_lojistas'])} ({o['qtd_repasses']} lançamentos)")
    r = c["remessa_banco"]
    print(f"  Remessa x banco: recursos recebidos de lojistas {brl(r['recursos_recebidos'])} ({r['qtd_recursos']}); "
          f"liquidado no parceiro {brl(r['liquidado_na_ponte'])} ({r['qtd_liquidacoes']}); "
          f"operações do relatório (Valor R$ + IOF) {brl(r['operacoes_valor_mais_iof'])}")
    print(f"    recursos - liquidado = {brl(r['recursos_menos_liquidado'])}; "
          f"liquidado - operações = {brl(r['liquidado_menos_operacoes'])}")
    obs = relatorio.observacao_recursos(f, config)
    if obs:
        print(f"    {obs}")
    p = c["ponte"]
    if p["diferenca"] is None:
        return
    print(f"  Parceiro de câmbio: spread total declarado {brl(p['spread_total_declarado'])} (com repetições e negativos); "
          f"operações únicas {brl(p['spread_operacoes_unicas'])}")
    print(f"    repasse pelo total declarado x participação = {brl(p['repasse_pelo_total_declarado'])}; "
          f"comissão calculada = {brl(p['comissao_calculada'])}; diferença = {brl(p['diferenca'])}")
    partes = [f"{brl(d['efeito'])} de {d['qtd']} {destino}" for destino, d in p["efeitos_por_destino"].items()]
    partes.append(f"{brl(p['residual'])} de " + ("arredondamento por operação" if p["residual_e_arredondamento"]
                                                 else "diferença NÃO explicada por arredondamento"))
    print("    = " + " + ".join(partes))


def imprimir_resumo_final(f: Fechamento, res: dict, arquivos: dict[str, Path], ctx: Contexto) -> None:
    """Bloco curto no fim do `fechar`: o que a pessoa precisa ver sem rolar a tela. Tudo vem de `res` (= resumo.json)."""
    t = res["totais"]
    chk, rem = f.comissoes_checkout, f.comissoes_remessa
    print("\n" + "=" * 24 + " RESUMO DO FECHAMENTO " + "=" * 24)
    print(f"Competência: {competencia_texto(f.competencia)}{' (inferida dos dados)' if ctx.competencia_inferida else ''}"
          f" · Integridade: {'OK' if f.integro else 'FALHOU'}")
    print(f"Comissão CHECKOUT: {brl(soma(chk['comissao_brl'])):>16}  ({len(chk)} lojistas, "
          f"{int(chk['qtd_transacoes'].sum())} transações da Orbe)")
    print(f"Comissão REMESSA:  {brl(soma(rem['comissao_brl'])):>16}  ({len(rem)} lojistas, "
          f"{int(rem['qtd_operacoes'].sum())} operações da Ponte)")
    print(f"Comissão total:    {brl(soma(f.comissoes['comissao_brl'])):>16}")
    print(f"Notas a emitir: {t['notas']['quantidade']}, somando {brl(Decimal(t['notas']['valor_total_brl']))}")
    print(f"Divergências: {relatorio.texto_divergencias(t['divergencias'])}")
    l = res["lancamentos"]
    print(f"Lançamentos classificados: {sum(l.values())} (REGRA {l['REGRA']}, IA {l['IA']}, HUMANO {l['HUMANO']})")
    n_inf = t["pendencias"].get("informativas", 0)
    print(f"Pendências: {t['pendencias']['quantidade']}" + (f" ({n_inf} informativas)" if n_inf else "") + ", por responsável:")
    for quem, g in t["pendencias"]["por_responsavel"].items():
        inf, incl = g.get("informativas", 0), g.get("incluidas_em_outra", 0)
        notas_g = [f"{inf} informativa{'s' if inf > 1 else ''}"] * bool(inf) + [f"{incl} já incluída{'s' if incl > 1 else ''} em outra"] * bool(incl)
        print(f"  {quem}: {g['quantidade']} pendência(s), {brl(Decimal(g['valor_brl']))} em jogo"
              + (f" ({', '.join(notas_g)})" if notas_g else ""))
    familias: dict[str, list[bool]] = {}
    for c in f.checagens:
        familias.setdefault(c.nome.split(".")[0], []).append(c.ok)
    ok = sum(all(v) for v in familias.values())
    print(f"Checagens de integridade: {ok} de {len(familias)} ok ({len(f.checagens)} testes)"
          + ("" if ok == len(familias) else " — veja acima qual falhou; não use os números"))
    cj = res["carteira_pendente"]
    if cj["linhas"] or cj["faturadas_de_meses_anteriores"]:
        print(f"Carteira pendente: {cj['linhas']} transações sem contrato/taxa ({brl(Decimal(cj['valor_bruto_brl']))}) "
              f"guardadas para o próximo mês; {cj['faturadas_de_meses_anteriores']} de meses anteriores faturadas agora")
    pasta = Path(arquivos["relatorio"]).parent
    print(f"Arquivos em {pasta}: " + ", ".join(Path(p).name for k, p in arquivos.items()
                                              if k != "relatorio" and not k.startswith("comunicacoes")))
    if "comunicacoes" in arquivos:
        print(f"Rascunhos de e-mail (não enviados; revisão de quem decide) em {arquivos['comunicacoes']}: "
              + ", ".join(Path(p).name for k, p in arquivos.items() if k.startswith("comunicacoes/")))
    print(f"Relatório: {arquivos['relatorio']}")


def _json(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- comandos

def cmd_validar(args) -> int:
    ctx = carregar_contexto(args, resolver_regras(args.regras))
    if args.json:
        _json({"comando": "validar", "ok": True, "codigo": SAIDA_OK, **resumo_contexto(ctx)})
    else:
        imprimir_contexto(ctx)
        print("\nEntradas e base de regras válidas. Nada foi calculado (use `fechar`).")
    return SAIDA_OK


def cmd_fechar(args) -> int:
    ctx = carregar_contexto(args, resolver_regras(args.regras))
    entrada = {"arquivos": {f: nome_arquivo(p) for f, p in ctx.arquivos.items() if not f.startswith("_")},
               "competencia_inferida": ctx.competencia_inferida}
    carteira, contestacao = None, None
    if getattr(args, "anterior", None):
        try:
            carteira = carteira_mod.ler(args.anterior)
        except ErroLeitura as e:
            raise Parada(SAIDA_ENTRADA, f"Carteira anterior com problema: {e}") from None
        contestacao = carteira_mod.ler_contestacao(args.anterior)
        entrada["carteira_anterior"] = {"pasta": str(args.anterior), "linhas": int(len(carteira)),
                                        "operacoes_contestadas": int(len(contestacao))}
    try:
        fech = executar(ctx.dados, ctx.config, ctx.competencia, usar_ia=not args.sem_ia, carteira=carteira,
                        contestacao_anterior=contestacao)
        # avisos dos leitores (checagens AVISO que falharam) vão para o relatório e o resumo, não só para a tela
        fech.avisos = avisos_dos_leitores(ctx.checagens) + fech.avisos
        arquivos, res = escrever(fech, args.saida, ctx.config, entrada, dir_regras=resolver_regras(args.regras).pasta,
                                 pasta_anterior=getattr(args, "anterior", None))
    except ErroConfig as e:
        raise Parada(SAIDA_REGRAS, str(e)) from None
    codigo = SAIDA_OK if fech.integro else SAIDA_INTEGRIDADE
    if args.json:
        # mesmo formato do resumo.json, mais o contexto de carga
        _json({"comando": "fechar", "ok": fech.integro, "codigo": codigo, **res, "contexto": resumo_contexto(ctx),
               "arquivos_gravados": {k: str(v) for k, v in arquivos.items()}})
        return codigo
    imprimir_contexto(ctx)
    imprimir_fechamento(fech)
    imprimir_conciliacao(fech, ctx.config)
    imprimir_resumo_final(fech, res, arquivos, ctx)
    if not fech.integro:
        print("\nINTEGRIDADE FALHOU: os números acima não podem ser apresentados como válidos.", file=sys.stderr)
    return codigo


def cmd_explicar(args) -> int:
    base = resolver_regras(args.regras)
    dados = carregar_dados(args, base)[3] if args.entrada else None
    try:
        e = comandos.explicar(args.id_saida, args.saida, comandos.regras_cruas(base.pasta), dados)
    except comandos.ErroComando as err:
        raise Parada(err.codigo, err.mensagem) from None
    if args.json:
        _json({"comando": "explicar", "ok": True, "codigo": SAIDA_OK, **e})
    else:
        comandos.imprimir_explicacao(e)
    return SAIDA_OK


def cmd_pendencias(args) -> int:
    try:
        res = comandos.listar_pendencias(args.saida, args.quem, args.tipo)
    except comandos.ErroComando as err:
        raise Parada(err.codigo, err.mensagem) from None
    if args.json:
        _json({"comando": "pendencias", "ok": True, "codigo": SAIDA_OK, **res})
    else:
        comandos.imprimir_pendencias(res)
    return SAIDA_OK


def _campos(lista: list[str]) -> dict[str, str]:
    out = {}
    for item in lista or []:
        if "=" not in item:
            raise Parada(SAIDA_REGRAS, f"--campos espera chave=valor, recebi '{item}'")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def cmd_regra(args) -> int:
    base = resolver_regras(args.regras)
    ctx_val, ctx = contexto_validacao(args, base)
    hoje = date.today()
    if args.acao == "propor":
        try:
            return _cmd_regra_propor(args, base, ctx_val, ctx, hoje)
        except ErroConfig as err:
            raise Parada(SAIDA_REGRAS, str(err)) from None

    # aplicar: antes de tudo, quem pode aprovar aquele tipo (regras/aprovadores.csv)
    try:
        proposta = comandos.ler_proposta(args.proposta)
    except (OSError, ValueError, KeyError) as err:
        raise Parada(SAIDA_REGRAS, f"proposta ilegível: {err}") from None
    tipo = proposta.linha.get("tipo", "COMPLEMENTO") if proposta.alvo == "regras_negocio.csv" else "COMPLEMENTO"
    qa, qr = comandos.quem_aprova(base.pasta, tipo)
    if not args.json:
        print(f"Regra do tipo {tipo}: quem aprova é {qa or 'qualquer pessoa'}, quem registra é {qr or 'quem aprova'} "
              f"(regras/aprovadores.csv). Aprovador informado: {args.aprovado_por}"
              + (f"; registro: {args.registrado_por}" if args.registrado_por else "") + ".")
    try:
        res = comandos.aplicar(base.pasta, proposta, args.aprovado_por, ctx_val, hoje, args.registrado_por)
    except comandos.ErroComando as err:
        raise Parada(err.codigo, err.mensagem) from None
    except ErroConfig as err:
        raise Parada(SAIDA_REGRAS, str(err)) from None
    except (OSError, ValueError, KeyError) as err:
        raise Parada(SAIDA_REGRAS, f"proposta ilegível: {err}") from None
    if base.zip_origem is not None:
        res["zip_novo"] = str(base.gravar_zip_novo(hoje))
    res["aprovacao"] = {"tipo": tipo, "quem_aprova": qa, "quem_registra": qr}
    if args.json:
        _json({"comando": "regra aplicar", "ok": True, "codigo": SAIDA_OK, **res})
    else:
        print(f"Regra {res['id_regra']} gravada em {res['arquivo']} e registrada em {res['historico']} "
              f"(aprovado por {res['aprovado_por']}, registrado por {res['registrado_por']}).")
        if "zip_novo" in res:
            print(f"Base em zip: gravei {res['zip_novo']}. Salve este arquivo na pasta compartilhada; ele substitui o anterior.")
        print("Rode `python -m src fechar` de novo para o fechamento refletir a regra.")
    return SAIDA_OK


def _simular_efeito(args, base: BaseRegras, ctx: Contexto | None, p) -> tuple[dict | None, str | None]:
    """Com --entrada, fecha o mês duas vezes numa pasta temporária (base x base + proposta) e devolve a comparação.
    Nada é gravado. Sem --entrada, devolve o aviso de que não dá para simular."""
    if ctx is None:
        return None, "sem --entrada não dá para simular o efeito no fechamento: passe o zip ou a pasta do mês"
    from . import simulacao
    carteira, contestacao = None, None
    if getattr(args, "anterior", None):
        try:
            carteira = carteira_mod.ler(args.anterior)
            contestacao = carteira_mod.ler_contestacao(args.anterior)
        except ErroLeitura as e:
            raise Parada(SAIDA_ENTRADA, f"Carteira anterior com problema: {e}") from None
    bancos = {f["rotulo"] for f in carregar_config_fontes(base.pasta).values() if f.get("rotulo")}
    try:
        return simulacao.simular(base.pasta, p, ctx.dados, ctx.competencia, bancos, carteira, contestacao), None
    except ErroConfig as e:
        return None, f"a base com a proposta não fecha o mês: {e}"


def _cmd_regra_propor(args, base: BaseRegras, ctx_val, ctx: Contexto | None, hoje: date) -> int:
    if True:
        lanc = None
        caminho_lanc = Path(args.saida) / "lancamentos_classificados.csv"
        if caminho_lanc.exists():
            lanc = pd.read_csv(caminho_lanc, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
        p = comandos.propor(base.pasta, args.tipo, _campos(args.campos), ctx_val, lanc, hoje)
        destino = Path(args.proposta) if args.proposta else Path(args.saida) / "propostas" / f"{p.linha.get('id') or p.linha.get('cnpj') or 'proposta'}.json"
        efeito_sim, aviso_sim = (None, None)
        if p.valida:
            destino.parent.mkdir(parents=True, exist_ok=True)
            comandos.gravar_proposta(p, destino)
            efeito_sim, aviso_sim = _simular_efeito(args, base, ctx, p)
        codigo = SAIDA_OK if p.valida else SAIDA_REGRAS
        if args.json:
            _json({"comando": "regra propor", "ok": p.valida, "codigo": codigo, **p.para_json(),
                   "arquivo_proposta": str(destino) if p.valida else None,
                   "efeito_simulado": efeito_sim, "aviso_simulacao": aviso_sim})
            return codigo
        print(f"Proposta para {p.alvo} ({'VÁLIDA' if p.valida else 'INVÁLIDA'}):")
        print("  " + ";".join(str(p.linha.get(c, "")) for c in p.linha))
        for k, v in p.linha.items():
            if v:
                print(f"  {k:<18} {v}")
        for a in p.avisos:
            print(f"  [aviso] {a}")
        for e in p.erros:
            print(f"  [erro] {e}")
        if p.efeito:
            print("Efeito esperado:")
            for e in p.efeito:
                print(f"  - {e}")
        if efeito_sim is not None:
            print(f"Efeito simulado no fechamento de {competencia_texto(efeito_sim['competencia'])} (fechamento refeito numa pasta "
                  f"temporária com a regra proposta; nada gravado):")
            for e in efeito_sim["texto"]:
                print(f"  - {e}")
        elif aviso_sim:
            print(f"  [aviso] {aviso_sim}")
        if p.aprovacao and p.aprovacao.get("quem_aprova"):
            print(f"Aprovação: {p.aprovacao['quem_aprova']} (registro: {p.aprovacao['quem_registra']}), "
                  f"conforme regras/aprovadores.csv")
        if p.valida:
            qa = (p.aprovacao or {}).get("quem_aprova") or "<nome>"
            print(f"\nNada foi gravado. Para aplicar: python -m src regra aplicar --regras {args.regras} "
                  f"--proposta {destino} --aprovado-por \"<nome> ({qa})\" [--registrado-por \"<quem registra>\"]")
        return codigo


def cmd_empacotar(args) -> int:
    from .empacotar import empacotar
    try:
        zip_path = empacotar(RAIZ, args.destino)
    except FileNotFoundError as e:
        raise Parada(SAIDA_ENTRADA, str(e)) from None
    if args.json:
        _json({"comando": "empacotar-skill", "ok": True, "codigo": SAIDA_OK, "zip": str(zip_path)})
    else:
        print(f"Skill empacotada em {zip_path}")
    return SAIDA_OK


# --------------------------------------------------------------------------- parser

def _comuns(p: argparse.ArgumentParser, entrada=True, saida=True, regras=True, competencia=False):
    if entrada:
        p.add_argument("--entrada", type=Path, help="zip do pacote do mês ou pasta com os arquivos")
    if regras:
        p.add_argument("--regras", type=Path, default=RAIZ / "regras",
                       help="pasta ou .zip da base de regras do financeiro (padrão: regras/)")
    if saida:
        p.add_argument("--saida", type=Path, default=RAIZ / "saida")
    if competencia:
        p.add_argument("--competencia", help="AAAA-MM; se omitido, é inferida dos dados")
    p.add_argument("--json", action="store_true", help="saída em JSON (para agentes)")


def construir_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m src", description="Fechamento mensal Tarvo")
    sub = ap.add_subparsers(dest="comando")

    p = sub.add_parser("validar", help="confere as 6 fontes e a base de regras; não calcula nada")
    _comuns(p, competencia=True)
    p = sub.add_parser("fechar", help="fechamento completo: 6 CSVs, resumo.json e relatório")
    _comuns(p, competencia=True)
    p.add_argument("--sem-ia", action="store_true",
                   help="não consultar a IA para lançamentos sem regra, mesmo com ANTHROPIC_API_KEY")
    p.add_argument("--anterior", type=Path,
                   help="pasta de saída do mês anterior: relê carteira_pendente.csv e fatura o que tiver taxa agora")
    p = sub.add_parser("explicar", help="de onde vem um número: rastro, regra e taxa usadas")
    p.add_argument("id_saida")
    _comuns(p)
    p = sub.add_parser("pendencias", help="lista pendências por responsável")
    p.add_argument("--quem", help="filtra pelo responsável (trecho do nome)")
    p.add_argument("--tipo", help="filtra pelo tipo")
    _comuns(p, entrada=False, regras=False)
    p = sub.add_parser("regra", help="propor e aplicar regras na base do financeiro")
    acao = p.add_subparsers(dest="acao", required=True)
    pp = acao.add_parser("propor", help="monta, valida e mostra o efeito; não grava")
    pp.add_argument("--tipo", required=True, help=f"um de {', '.join(comandos.TIPOS)} ou COMPLEMENTO")
    pp.add_argument("--campos", nargs="+", metavar="chave=valor", required=True)
    pp.add_argument("--proposta", type=Path, help="onde gravar a proposta (padrão: <saida>/propostas/<id>.json)")
    pp.add_argument("--anterior", type=Path, help="pasta de saída do mês anterior, para a simulação considerar a carteira pendente")
    _comuns(pp)
    pa = acao.add_parser("aplicar", help="grava a proposta validada e registra no histórico")
    pa.add_argument("--proposta", type=Path, required=True)
    pa.add_argument("--aprovado-por", required=True, help="nome de quem aprovou (quem pode: regras/aprovadores.csv)")
    pa.add_argument("--registrado-por", help="quem registrou a regra, se não for quem aprovou (ver regras/aprovadores.csv)")
    _comuns(pa)
    p = sub.add_parser("empacotar-skill", help="gera o zip autocontido da skill em dist/")
    p.add_argument("--destino", type=Path, default=RAIZ / "dist")
    p.add_argument("--json", action="store_true")
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in COMANDOS and argv[0] not in ("-h", "--help")):
        argv.insert(0, "fechar")  # sem subcomando = fechar com os padrões
    args = construir_parser().parse_args(argv)
    handlers = {"validar": cmd_validar, "fechar": cmd_fechar, "explicar": cmd_explicar,
                "pendencias": cmd_pendencias, "regra": cmd_regra, "empacotar-skill": cmd_empacotar}
    try:
        return handlers[args.comando](args)
    except Parada as p:
        if getattr(args, "json", False):
            _json({"comando": args.comando, "ok": False, "codigo": p.codigo, "erro": p.mensagem})
        else:
            print(f"ERRO: {p.mensagem}", file=sys.stderr)
        return p.codigo
