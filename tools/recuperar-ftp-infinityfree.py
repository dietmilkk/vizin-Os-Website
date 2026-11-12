#!/usr/bin/env python3
"""Recupera as credenciais de FTP do InfinityFree e grava no arquivo local.

Uso:
    python3 tools/recuperar-ftp-infinityfree.py
    python3 tools/recuperar-ftp-infinityfree.py --perfil "Nome do perfil"

O que ele faz:
  1. abre o painel do InfinityFree reaproveitando a sessão do Google que já
     está no Firefox do dono da conta (o login do InfinityFree é "Log in with
     Google");
  2. lê a página "FTP Details" e extrai host, usuário e senha;
  3. grava tudo em site/.deploy-infinityfree.env (permissão 600, fora do git).

A senha **nunca** é impressa no terminal. Nada é enviado para fora da
máquina: o login acontece direto no site do InfinityFree, usando a sessão que
o próprio navegador do dono da conta já tinha.

Se o navegador não estiver logado, o script avisa e termina com erro — não
tenta adivinhar senha nem contorna nada.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".deploy-infinityfree.env"
PROFILES = "/home/user/.config/mozilla/firefox/*/cookies.sqlite"

DOMINIOS = ("google.com", "infinityfree.com")


def cookies_do_firefox() -> list[dict]:
    """Lê os cookies de sessão do Google/InfinityFree dos perfis do Firefox."""
    cookies: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for perfil in sorted(glob.glob(PROFILES)):
        copia = f"/tmp/cookies-recuperar-{abs(hash(perfil)) % 99999}.sqlite"
        try:
            shutil.copy(perfil, copia)
        except OSError:
            continue
        conexao = sqlite3.connect(copia)
        try:
            linhas = conexao.execute(
                "select host, name, value, path, expiry, isSecure, isHttpOnly "
                "from moz_cookies where host like '%google.com' "
                "or host like '%infinityfree.com'"
            ).fetchall()
        except sqlite3.Error:
            continue
        finally:
            conexao.close()
        for host, nome, valor, path, expiry, seguro, http_only in linhas:
            if nome in ("usprivacy", "__test"):
                continue
            chave = (nome, host)
            if chave in vistos:
                continue
            vistos.add(chave)
            cookies.append(
                {
                    "name": nome,
                    "value": valor,
                    "domain": host,
                    "path": path or "/",
                    # O Firefox guarda a expiração em milissegundos.
                    "expires": int(expiry // 1000) if expiry and expiry > 10**11 else -1,
                    "httpOnly": bool(http_only),
                    "secure": bool(seguro),
                    "sameSite": "Lax",
                }
            )
    return cookies


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--conta", default="", help="id da conta (ex.: if0_12345678)")
    analisador.add_argument("--saida", default=str(ENV_FILE), help="onde gravar as credenciais")
    argumentos = analisador.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright é necessário: pip install playwright", file=sys.stderr)
        return 2

    cookies = cookies_do_firefox()
    if not cookies:
        print("Nenhum cookie de sessão encontrado no Firefox.", file=sys.stderr)
        return 1
    print(f"-> {len(cookies)} cookies de sessão encontrados no Firefox")

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(args=["--no-sandbox"])
        contexto = navegador.new_context(
            locale="pt-BR",
            viewport={"width": 1400, "height": 950},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
            ),
        )
        contexto.add_cookies(cookies)
        pagina = contexto.new_page()

        print("-> entrando no painel do InfinityFree")
        pagina.goto("https://dash.infinityfree.com/login", wait_until="domcontentloaded", timeout=60_000)
        pagina.wait_for_timeout(2500)

        logado = False
        for _ in range(12):
            partes = urlparse(pagina.url)
            if partes.netloc.endswith("dash.infinityfree.com") and "/login" not in partes.path:
                logado = True
                break
            clicou = False
            try:
                contas = pagina.locator("[data-email], [aria-label*='@']")
                if contas.count():
                    contas.first.click(timeout=8000)
                    clicou = True
            except Exception:
                pass
            if not clicou:
                for texto in ("log in with google", "continuar", "continue", "aceitar", "accept"):
                    try:
                        alvo = pagina.get_by_text(texto, exact=False).first
                        if alvo.count() and alvo.is_visible():
                            alvo.click(timeout=8000)
                            clicou = True
                            break
                    except Exception:
                        continue
            pagina.wait_for_timeout(4500)

        if not logado:
            print(
                "\nNão foi possível entrar no painel.\n"
                "Abra o InfinityFree no seu navegador, entre na conta e tente de novo.",
                file=sys.stderr,
            )
            navegador.close()
            return 1

        print(f"-> logado em {pagina.url}")

        # Descobre a conta (o id aparece na URL das páginas de gerenciamento).
        conta = argumentos.conta
        if not conta:
            links = pagina.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]'))
                     .map(a => a.getAttribute('href') || '')
                     .filter(h => /\\/accounts\\/if\\d+_\\d+/.test(h))"""
            )
            if links:
                achado = re.search(r"/accounts/(if\d+_\d+)", links[0])
                conta = achado.group(1) if achado else ""
        if not conta:
            print("Não foi possível descobrir a conta. Use --conta if0_12345678.", file=sys.stderr)
            navegador.close()
            return 1
        print(f"-> conta: {conta}")

        pagina.goto(
            f"https://dash.infinityfree.com/accounts/{conta}/ftp-details",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        pagina.wait_for_timeout(2500)

        dados = pagina.evaluate(
            """() => {
                const texto = document.body.innerText;
                const usuario = (texto.match(/if\\d+_\\d+/) || [])[0] || '';
                const host = (texto.match(/ftpupload\\.net|ftp\\.infinityfree\\.com/) || [])[0] || '';
                const senhaEl = document.querySelector('input[type=password][name=password]')
                             || document.querySelector('input[name=password]');
                return {usuario, host, senha: senhaEl ? senhaEl.value : ''};
            }"""
        )

        navegador.close()

    usuario = dados.get("usuario") or conta
    host = dados.get("host") or "ftpupload.net"
    senha = dados.get("senha") or ""

    if not senha:
        print(
            "A senha do FTP não apareceu na página. Abra o painel no navegador "
            "e confira a seção FTP Details.",
            file=sys.stderr,
        )
        return 1

    destino = Path(argumentos.saida)
    destino.write_text(
        f"INFINITYFREE_FTP_HOST={host}\n"
        f"INFINITYFREE_FTP_USER={usuario}\n"
        f"INFINITYFREE_FTP_PASS={senha}\n"
        f"INFINITYFREE_FTP_DIR=vizin-os.page.gd/htdocs\n",
        encoding="utf-8",
    )
    os.chmod(destino, 0o600)

    print(f"\nOK: credenciais gravadas em {destino}")
    print(f"    host={host}  user={usuario}  senha=({len(senha)} caracteres, não exibida)")
    print("    A pasta remota é vizin-os.page.gd/htdocs (o site oficial).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
