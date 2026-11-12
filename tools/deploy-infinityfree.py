#!/usr/bin/env python3
"""Publica o site publico em https://vizin-os.page.gd (hospedagem InfinityFree).

O InfinityFree nao deixa apontar o dominio para um IP externo: o site e
publicado dentro da conta, em `vizin-os.page.gd/htdocs`. A VPS continua sendo a
copia de trabalho (tools/deploy-vps.sh) e a origem da API.

Este script faz um espelho: sobe todos os arquivos publicos e remove do
servidor tudo que nao faz parte do site (README, ferramentas, testes, sobras
de publicacoes antigas). Nada interno fica acessivel pela web.

Credenciais (nunca vao para o git):
  1) arquivo site/.deploy-infinityfree.env (gitignored), ou
  2) variaveis de ambiente: INFINITYFREE_FTP_USER, INFINITYFREE_FTP_PASS,
     INFINITYFREE_FTP_HOST (padrao ftpupload.net),
     INFINITYFREE_FTP_DIR (padrao vizin-os.page.gd/htdocs).

Uso:
  python3 tools/deploy-infinityfree.py --dry-run    # mostra o que seria feito
  python3 tools/deploy-infinityfree.py              # publica e confere no ar

Requer: python3 (ftplib) e, para a conferencia final, Playwright com Chromium.
"""

from __future__ import annotations

import argparse
import ftplib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".deploy-infinityfree.env"

# Arquivos e pastas que compoem o site publico.
PUBLICOS = [
    "index.html",
    "404.html",
    "robots.txt",
    "sitemap.xml",
    "site.webmanifest",
    "_headers",
    "_redirects",
    ".htaccess",
    "painel/index.html",
    "afiliados/index.html",
    "documento/index.html",
    "moderacao/index.html",
    "manifesto/index.html",
]

# Pastas enviadas inteiras.
PUBLICOS_DIR = ["assets"]

# Coisas que nunca devem ficar no ar (podem ter ficado de publicacoes antigas).
REMOVER = [
    "README.md",
    "prompt-afiliados.md",
    "tools",
    "tests",
    "tmp-vps",
    "deploy",
    "dist",
    ".git",
    ".gitignore",
    ".env",
]


def carregar_credenciais() -> tuple[str, str, str, str]:
    if ENV_FILE.exists():
        for linha in ENV_FILE.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))

    host = os.environ.get("INFINITYFREE_FTP_HOST", "ftpupload.net")
    user = os.environ.get("INFINITYFREE_FTP_USER", "")
    senha = os.environ.get("INFINITYFREE_FTP_PASS", "")
    diretorio = os.environ.get("INFINITYFREE_FTP_DIR", "vizin-os.page.gd/htdocs")
    return host, user, senha, diretorio.rstrip("/")


def manifesto() -> list[str]:
    """Lista de arquivos publicos (relativos a ROOT), em ordem."""
    arquivos: list[str] = []
    for item in PUBLICOS:
        if (ROOT / item).is_file():
            arquivos.append(item)
    for pasta in PUBLICOS_DIR:
        base = ROOT / pasta
        if not base.is_dir():
            continue
        for caminho in sorted(base.rglob("*")):
            if caminho.is_file():
                arquivos.append(caminho.relative_to(ROOT).as_posix())
    return arquivos


def conexao(host: str, user: str, senha: str) -> ftplib.FTP:
    ftp = ftplib.FTP(host, timeout=60)
    ftp.connect()
    ftp.login(user, senha)
    ftp.set_pasv(True)
    return ftp


def caminho_remoto(diretorio: str, relativo: str) -> str:
    return f"{diretorio}/{relativo}" if diretorio else relativo


def criar_pastas(ftp: ftplib.FTP, diretorio: str, relativo: str) -> None:
    """Garante que as pastas do arquivo existam no servidor."""
    partes = Path(relativo).parent.as_posix()
    if partes in (".", "/"):
        return
    atual = diretorio
    for parte in partes.split("/"):
        if not parte:
            continue
        atual = f"{atual}/{parte}" if atual else parte
        try:
            ftp.mkd(atual)
        except ftplib.error_perm:
            pass  # ja existe


def enviar(ftp: ftplib.FTP, diretorio: str, relativo: str) -> None:
    criar_pastas(ftp, diretorio, relativo)
    local = ROOT / relativo
    remoto = caminho_remoto(diretorio, relativo)
    with local.open("rb") as fh:
        ftp.storbinary(f"STOR {remoto}", fh)


def listar_remoto(ftp: ftplib.FTP, caminho: str) -> list[tuple[str, bool]]:
    """Lista (nome, e_pasta) de um diretorio remoto.

    Usa MLSD quando o servidor suporta (diz o tipo de cada item). O fallback
    usa NLST + teste de pasta. Em ambos os casos '.', '..' e o proprio
    diretorio sao ignorados: sem isso a varredura entraria em laco.
    """
    entradas: list[tuple[str, bool]] = []
    try:
        for nome, info in ftp.mlsd(caminho):
            if nome in (".", ".."):
                continue
            tipo = (info.get("type") or "").lower()
            if tipo:
                entradas.append((nome, tipo == "dir"))
            else:
                entradas.append((nome, False))
        if entradas:
            return entradas
    except (ftplib.error_perm, ftplib.error_proto, OSError):
        pass

    try:
        listados = ftp.nlst(caminho)
    except (ftplib.error_perm, OSError):
        return []

    base = caminho.rstrip("/").rsplit("/", 1)[-1]
    for entrada in listados:
        nome = entrada.rsplit("/", 1)[-1]
        if nome in (".", "..", base):
            continue
        pasta = False
        try:
            ftp.cwd(entrada)
            pasta = True
        except (ftplib.error_perm, OSError):
            pasta = False
        finally:
            try:
                ftp.cwd("/")
            except (ftplib.error_perm, OSError):
                pass
        entradas.append((nome, pasta))
    return entradas


def remover_remoto(ftp: ftplib.FTP, caminho: str) -> str | None:
    """Apaga um arquivo ou uma pasta remota. Devolve o que foi apagado."""
    try:
        ftp.rmd(caminho)
        return caminho
    except (ftplib.error_perm, OSError):
        pass
    try:
        ftp.delete(caminho)
        return caminho
    except (ftplib.error_perm, OSError):
        return None


def apagar_pasta(ftp: ftplib.FTP, caminho: str) -> bool:
    """Apaga uma pasta remota e tudo que esta dentro dela."""
    apagado = False
    for nome, pasta in listar_remoto(ftp, caminho):
        alvo = f"{caminho}/{nome}"
        if pasta:
            apagado = apagar_pasta(ftp, alvo) or apagado
        else:
            apagado = remover_remoto(ftp, alvo) is not None or apagado
    return remover_remoto(ftp, caminho) is not None or apagado


def limpar_sobras(ftp: ftplib.FTP, diretorio: str, publicos: set[str]) -> list[str]:
    """Remove do servidor o que nao faz parte do site publico."""
    removidos: list[str] = []

    # 1) Apaga na mao o que nunca deve estar no ar.
    for item in REMOVER:
        alvo = f"{diretorio}/{item}" if diretorio else item
        if item in ("tools", "tests", "tmp-vps", "deploy", "dist", ".git"):
            apagado = apagar_pasta(ftp, alvo)
        else:
            apagado = remover_remoto(ftp, alvo) is not None
        if apagado:
            removidos.append(item)

    # 2) Varre o resto: arquivos e pastas que sobraram de publicacoes antigas.
    def varrer(atual_rel: str, prefixo: str, profundidade: int = 0) -> None:
        if profundidade > 6:
            return
        remoto = f"{diretorio}/{atual_rel}" if diretorio else atual_rel
        for nome, pasta in listar_remoto(ftp, remoto):
            rel = f"{prefixo}{nome}"
            if pasta:
                varrer(f"{atual_rel}/{nome}" if atual_rel else nome, f"{rel}/", profundidade + 1)
                alvo = f"{remoto}/{nome}"
            else:
                if rel in publicos:
                    continue
                alvo = f"{remoto}/{nome}"
            if ftp_rmd_ou_delete(ftp, alvo):
                removidos.append(rel + ("/" if pasta else ""))

    varrer("", "")
    return removidos


def ftp_rmd_ou_delete(ftp: ftplib.FTP, caminho: str) -> bool:
    """Tenta remover como pasta e, se falhar, como arquivo."""
    if remover_remoto(ftp, caminho) is not None:
        return True
    return False


def main() -> int:
    analisador = argparse.ArgumentParser(description="Publica o site no InfinityFree.")
    analisador.add_argument("--dry-run", action="store_true", help="apenas mostra o que seria feito")
    analisador.add_argument("--sem-conferir", action="store_true", help="nao roda a verificacao no navegador")
    argumentos = analisador.parse_args()

    host, user, senha, diretorio = carregar_credenciais()
    publicos = manifesto()

    print(f"==> FTP: {host}")
    print(f"==> Pasta remota: {diretorio}/")
    print(f"==> Arquivos publicos: {len(publicos)}")

    if not user or not senha:
        if argumentos.dry_run:
            print("\n==> Sem credenciais: simulacao do que seria enviado.")
            for arquivo in publicos:
                print(f"    {arquivo} -> {caminho_remoto(diretorio, arquivo)}")
            for item in REMOVER:
                print(f"    {item} (seria removido do servidor)")
            return 0
        print(
            "\nFaltam as credenciais do FTP do InfinityFree.\n"
            f"Crie o arquivo {ENV_FILE} com:\n\n"
            "  INFINITYFREE_FTP_HOST=ftpupload.net\n"
            "  INFINITYFREE_FTP_USER=SEU_USUARIO\n"
            "  INFINITYFREE_FTP_PASS=SUA_SENHA\n\n"
            "O usuario e a senha sao os da conta do InfinityFree (client.infinityfree.com).\n"
            "O arquivo esta no .gitignore: nunca sera publicado.",
            file=sys.stderr,
        )
        return 1

    if argumentos.dry_run:
        print("\n==> Simulacao: arquivos que seriam enviados.")
        for arquivo in publicos:
            print(f"    {arquivo} -> {caminho_remoto(diretorio, arquivo)}")
        return 0

    ftp = conexao(host, user, senha)
    print(f"==> Conectado. Enviando {len(publicos)} arquivo(s).")
    for arquivo in publicos:
        enviar(ftp, diretorio, arquivo)
        print(f"    {arquivo}")

    print("\n==> Limpando o que nao faz parte do site.")
    removidos = limpar_sobras(ftp, diretorio, set(publicos))
    if removidos:
        for item in removidos:
            print(f"    removido: {item}")
    else:
        print("    nada a remover")

    ftp.quit()
    print("\n==> Publicado.")

    if argumentos.sem_conferir:
        return 0

    print("\n==> Conferindo no navegador (como um visitante).")
    verificador = ROOT / "tools" / "conferir-dominio.py"
    resultado = subprocess.run(
        [sys.executable, str(verificador), "https://vizin-os.page.gd"],
        cwd=ROOT,
    )
    return resultado.returncode


if __name__ == "__main__":
    sys.exit(main())
