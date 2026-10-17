"""Localiza os arquivos de entrada do mês a partir de regras/fontes.csv.

Aceita o zip do pacote (com qualquer nome), uma pasta com o zip dentro (e arquivos soltos ao
lado, ex.: ajustes que chegaram depois), uma pasta com os arquivos soltos ou em subpastas.
Cada arquivo é reconhecido pela ASSINATURA de conteúdo da fonte (coluna `assinatura` de
fontes.csv: colunas do cabeçalho de um CSV, aba de um xlsx, anexo de um .eml, tag e conta de um
OFX); o padrão de nome (`padrao_arquivo`, alternativas separadas por " OU ") é só um atalho,
usado quando nenhuma assinatura bate. Fontes com `multiplos=sim` aceitam vários arquivos no
mesmo formato (relatório + ajustes tardios + reenvios); as outras exigem exatamente um.
Arquivo que não bate com fonte nenhuma não para o fechamento: vira aviso ("não reconhecido;
não foi usado"). Só arquivos ocultos e de sistema (.DS_Store, __MACOSX, ~$*, Thumbs.db) e o
README do pacote são ignorados sem aviso. Zips são extraídos numa pasta temporária, apagada ao fim.
"""
from __future__ import annotations

import csv
import email
import fnmatch
import io
import shutil
import tempfile
import zipfile
from email import policy
from pathlib import Path, PurePosixPath

from .leitores.comum import ErroLeitura, ler_texto

PASTA_ENTRADA = "entrada"          # pasta da raiz usada quando não se passa --entrada
NAO_RECONHECIDOS = "_nao_reconhecidos"   # chave extra devolvida por `localizar`: nomes dos arquivos não usados
SEPARADOR_ALTERNATIVAS = " OU "
_IGNORAR_PARTES = {"__MACOSX"}
_IGNORAR_NOMES = {"thumbs.db", "desktop.ini"}
_PREFIXOS_DOCUMENTACAO = ("README", "LEIA-ME", "00_LEIA-ME")   # o README do pacote não é dado: ignorado sem aviso
_TEMPORARIOS: list[tempfile.TemporaryDirectory] = []   # mantidos vivos até o fim do processo
_ENCODINGS_ESPIADA = ("utf-8-sig", "cp1252", "latin-1")


def _parametros(texto: str) -> dict[str, str]:
    """'tipo=csv | colunas=a,b' -> {'tipo': 'csv', 'colunas': 'a,b'}."""
    out = {}
    for parte in (texto or "").split("|"):
        if "=" in parte:
            k, v = parte.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def carregar_config_fontes(dir_config: Path) -> dict[str, dict]:
    caminho = Path(dir_config) / "fontes.csv"
    texto, _ = ler_texto(caminho, esperado=["fonte", "padrao_arquivo"])
    linhas = [l for l in texto.splitlines() if l.strip()]
    cfg = {}
    for r in csv.DictReader(linhas, delimiter=";"):
        linha = {k: (v or "").strip() for k, v in r.items() if k}
        linha["multiplos"] = linha.get("multiplos", "").lower() in ("sim", "true", "s", "yes")
        linha["assinatura_params"] = _parametros(linha.get("assinatura", ""))
        linha["alternativas"] = [a.strip() for a in linha["padrao_arquivo"].split(SEPARADOR_ALTERNATIVAS) if a.strip()]
        cfg[linha["fonte"]] = linha
    return cfg


def _extrair_zip(zip_path: Path) -> Path:
    """Extrai o zip numa pasta temporária nova (nunca reaproveita extração antiga). Recusa caminhos que saiam dela."""
    tmp = tempfile.TemporaryDirectory(prefix=f"{zip_path.stem}_")
    _TEMPORARIOS.append(tmp)
    alvo = Path(tmp.name)
    try:
        with zipfile.ZipFile(zip_path) as z:
            for membro in z.infolist():
                p = PurePosixPath(membro.filename)
                if p.is_absolute() or ".." in p.parts:
                    raise ErroLeitura(f"{zip_path.name}: caminho suspeito no zip: {membro.filename}")
            z.extractall(alvo)
    except zipfile.BadZipFile:
        raise ErroLeitura(f"{zip_path.name} não é um zip válido") from None
    return alvo


def _e_sistema_ou_documentacao(p: Path) -> bool:
    if _IGNORAR_PARTES & set(p.parts) or any(parte.startswith(".") for parte in p.parts):
        return True
    if p.name.startswith("~$") or p.name.lower() in _IGNORAR_NOMES:
        return True
    return p.name.upper().startswith(_PREFIXOS_DOCUMENTACAO)


def _arquivos_de_dados(pasta: Path) -> list[Path]:
    """Arquivos sob a pasta (recursivo), fora lixo de sistema, ocultos e o README do pacote."""
    return sorted(p for p in Path(pasta).rglob("*") if p.is_file() and not _e_sistema_ou_documentacao(p))


# --------------------------------------------------------------------------- reconhecimento por conteúdo

def _texto_inicio(p: Path, tamanho: int = 262144) -> str:
    dados = p.read_bytes()[:tamanho]
    for enc in _ENCODINGS_ESPIADA:
        try:
            return dados.decode(enc)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin-1", errors="ignore")


def _abas_xlsx(dados) -> list[str]:
    import openpyxl
    wb = openpyxl.load_workbook(dados, read_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def casa_assinatura(p: Path, assinatura: dict[str, str]) -> bool:
    """O arquivo tem o conteúdo que a fonte declara em fontes.csv? Qualquer falha de leitura = não."""
    tipo = assinatura.get("tipo", "").lower()
    if not tipo:
        return False
    try:
        if tipo == "csv":
            colunas = [c.strip() for c in assinatura.get("colunas", "").split(",") if c.strip()]
            if not colunas:
                return False
            for linha in _texto_inicio(p).splitlines()[:60]:
                campos = [c.strip() for c in linha.split(";")]
                if all(c in campos for c in colunas):
                    return True
            return False
        if tipo == "xlsx":
            if p.suffix.lower() not in (".xlsx", ".xlsm"):
                return False
            aba = assinatura.get("aba")
            return (aba in _abas_xlsx(p)) if aba else True
        if tipo == "eml":
            msg = email.message_from_bytes(p.read_bytes(), policy=policy.default)
            extensao = "." + assinatura.get("anexo", "xlsx").lower().lstrip(".")
            for parte in msg.walk():
                nome = (parte.get_filename() or "").lower()
                if not nome.endswith(extensao):
                    continue
                dados = parte.get_payload(decode=True)
                if not dados:
                    continue
                aba = assinatura.get("aba")
                if not aba or (extensao == ".xlsx" and aba in _abas_xlsx(io.BytesIO(dados))):
                    return True
            return False
        if tipo == "ofx":
            texto = _texto_inicio(p)
            contem = assinatura.get("contem", "<OFX>")
            conta = assinatura.get("conta", "")
            return contem in texto and (not conta or conta in texto)
    except Exception:   # arquivo de outro tipo, corrompido ou ilegível: não é desta fonte
        return False
    return False


def _casa_nome(p: Path, linha: dict) -> bool:
    return any(fnmatch.fnmatchcase(p.name.lower(), alt.lower()) for alt in linha["alternativas"])


def classificar_arquivo(p: Path, cfg: dict) -> str | None:
    """Fonte de um arquivo: pela assinatura de conteúdo; se nenhuma bater, pelo padrão de nome (atalho). None = não reconhecido."""
    fontes = [f for f in cfg if f != "pacote"]
    por_conteudo = [f for f in fontes if cfg[f]["assinatura_params"] and casa_assinatura(p, cfg[f]["assinatura_params"])]
    if len(por_conteudo) == 1:
        return por_conteudo[0]
    if por_conteudo:
        por_nome = [f for f in por_conteudo if _casa_nome(p, cfg[f])]
        return (por_nome or por_conteudo)[0]
    por_nome = [f for f in fontes if _casa_nome(p, cfg[f])]
    return por_nome[0] if por_nome else None


# --------------------------------------------------------------------------- entrada

def preparar_entrada(entrada: Path | None, raiz: Path, cfg: dict) -> Path:
    """Devolve a pasta onde procurar os arquivos do mês.

    entrada = zip -> extraído em pasta temporária; entrada = pasta -> a própria (zips dentro dela
    são abertos por `localizar`, somados aos arquivos soltos). Sem entrada: a pasta entrada/ da raiz,
    se tiver algum arquivo de dados; senão o único zip de pacote na raiz (padrão `pacote` de
    fontes.csv), mais os arquivos de dados soltos ao lado dele (ex.: ajustes que chegaram depois).
    """
    raiz = Path(raiz)
    if entrada is not None:
        entrada = Path(entrada)
        if entrada.is_file() and entrada.suffix.lower() == ".zip":
            return _extrair_zip(entrada)
        if entrada.is_dir():
            return entrada
        if entrada.exists():
            raise ErroLeitura(f"Entrada {entrada} não é um .zip nem uma pasta")
        raise ErroLeitura(f"Entrada {entrada} não existe")
    pasta = raiz / PASTA_ENTRADA
    if pasta.is_dir() and _arquivos_de_dados(pasta):
        return pasta
    padrao = cfg["pacote"]["padrao_arquivo"]
    pacotes = sorted(p for p in raiz.glob(padrao) if p.is_file())
    if len(pacotes) == 1:
        extraida = _extrair_zip(pacotes[0])
        # arquivos de dados soltos na raiz, ao lado do zip (reconhecidos por conteúdo ou nome), entram junto
        for p in sorted(raiz.iterdir()):
            if p.is_file() and p.suffix.lower() != ".zip" and not _e_sistema_ou_documentacao(p) \
                    and classificar_arquivo(p, cfg) is not None:
                shutil.copy(p, extraida / p.name)
        return extraida
    if not pacotes:
        raise ErroLeitura(f"Nenhum arquivo do mês: coloque o zip ou os arquivos em {PASTA_ENTRADA}/ "
                          f"(ou um pacote {padrao} na raiz), ou use --entrada <zip ou pasta>.")
    nomes = ", ".join(p.name for p in pacotes)
    raise ErroLeitura(f"Mais de um pacote encontrado na raiz ({nomes}). Use --entrada para escolher.")


def localizar(pasta: Path, cfg: dict) -> dict:
    """Acha cada fonte pelo conteúdo (assinatura) ou pelo nome, na pasta, em subpastas e dentro de zips.

    Devolve {fonte: Path} para fontes de um arquivo só e {fonte: [Path, ...]} para `multiplos=sim` (o
    principal, que casa com o primeiro padrão de nome, vem primeiro), mais `_nao_reconhecidos`: nomes dos
    arquivos que não batem com fonte nenhuma (não param o fechamento; viram aviso). Fonte obrigatória
    ausente ou repetida (quando não aceita vários) para com mensagem dizendo o que falta e o que foi encontrado.
    """
    pasta = Path(pasta)
    arquivos = _arquivos_de_dados(pasta)
    for z in [p for p in arquivos if p.suffix.lower() == ".zip"]:
        arquivos += _arquivos_de_dados(_extrair_zip(z))
    fontes = [f for f in cfg if f != "pacote"]
    por_fonte: dict[str, list[Path]] = {f: [] for f in fontes}
    nao_reconhecidos: list[str] = []
    for p in arquivos:
        if p.suffix.lower() == ".zip":
            continue   # zips são abertos acima; o conteúdo deles é que se classifica
        fonte = classificar_arquivo(p, cfg)
        if fonte is None:
            nao_reconhecidos.append(p.name)
        else:
            por_fonte[fonte].append(p)

    achados: dict = {}
    faltam, repetidos = [], []
    for fonte in fontes:
        linha = cfg[fonte]
        candidatos = sorted(por_fonte[fonte], key=lambda p: p.name.lower())
        descricao = f" ({linha['descricao']})" if linha.get("descricao") else ""
        if not candidatos:
            faltam.append(f"falta: {fonte}{descricao}; padrão de nome {linha['padrao_arquivo']}")
        elif linha["multiplos"]:
            principal = next((p for p in candidatos if fnmatch.fnmatchcase(p.name.lower(), linha["alternativas"][0].lower())),
                             candidatos[0])
            achados[fonte] = [principal] + [p for p in candidatos if p is not principal]
        elif len(candidatos) == 1:
            achados[fonte] = candidatos[0]
        else:
            repetidos.append(f"Mais de um arquivo para a fonte {fonte}{descricao}: "
                             + ", ".join(p.name for p in candidatos) + "; deixe só um")
    if faltam or repetidos:
        encontrados = ", ".join(sorted(p.name for lst in por_fonte.values() for p in lst))
        detalhe = [f"encontrei: {encontrados or 'nenhum arquivo reconhecido'}"] + faltam + repetidos
        if nao_reconhecidos:
            detalhe.append("não reconhecidos (não usados): " + ", ".join(nao_reconhecidos))
        raise ErroLeitura(f"Arquivos de entrada com problema em {pasta}:\n  " + "\n  ".join(detalhe))
    achados[NAO_RECONHECIDOS] = nao_reconhecidos
    return achados


def nome_arquivo(valor) -> str:
    """Nome de um arquivo de fonte (ou os nomes, separados por vírgula, numa fonte com vários arquivos)."""
    if isinstance(valor, (list, tuple)):
        return ", ".join(Path(v).name for v in valor)
    return Path(valor).name
