#!/usr/bin/env python3
"""Confere se o site publicado e igual ao site do repositorio.

O page.gd pede verificacao de JavaScript, entao a leitura e feita no Chromium
(o que o visitante recebe de verdade). Cada arquivo e buscado DENTRO do
navegador (mesmos cookies da verificacao) e comparado byte a byte com o
arquivo local; a primeira linha divergente e mostrada.

Uso:
    python3 tools/comparar-site-publicado.py [https://vizin-os.page.gd]
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent

# Pagina -> arquivo local correspondente.
PAGINAS = {
    "/": "index.html",
    "/painel/": "painel/index.html",
    "/afiliados/": "afiliados/index.html",
    "/documento/": "documento/index.html",
    "/moderacao/": "moderacao/index.html",
    "/404.html": "404.html",
}
ASSETS = {
    "/assets/panel.js": "assets/panel.js",
    "/assets/styles.css": "assets/styles.css",
    "/assets/app.js": "assets/app.js",
    "/assets/config.js": "assets/config.js",
    "/assets/creators.js": "assets/creators.js",
    "/site.webmanifest": "site.webmanifest",
    "/sitemap.xml": "sitemap.xml",
    "/robots.txt": "robots.txt",
}


def primeira_divergencia(local: str, publicado: str) -> str:
    dif = difflib.unified_diff(
        local.splitlines(),
        publicado.splitlines(),
        fromfile="local",
        tofile="publicado",
        lineterm="",
        n=0,
    )
    linhas = [l for l in dif if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    if not linhas:
        return ""
    return linhas[0][:160]


def main() -> int:
    falhas = 0
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        contexto = navegador.new_context()
        pagina = contexto.new_page()

        # A primeira navegacao passa pela verificacao de JavaScript do page.gd.
        pagina.goto(f"{BASE}/painel/", wait_until="networkidle")
        pagina.wait_for_function(
            "() => document.getElementById('painelStatusTexto')"
            "?.textContent?.startsWith('Atualizado')",
            timeout=30_000,
        )

        for rota, arquivo in {**PAGINAS, **ASSETS}.items():
            url = f"{BASE}{rota}"
            # Busca dentro do navegador: usa os cookies da verificacao e traz
            # o arquivo cru (sem normalizar o HTML).
            publicado = pagina.evaluate(
                "async (u) => { const r = await fetch(u, {cache: 'no-store'});"
                " return await r.text(); }",
                url,
            )

            caminho = ROOT / arquivo
            if not caminho.exists():
                print(f"[ERRO] arquivo local ausente: {arquivo}")
                falhas += 1
                continue

            local = caminho.read_text(encoding="utf-8")
            # Compara linha a linha: ignora diferenca de quebra de linha no
            # fim e espacos a direita (o servidor pode normalizar isso).
            igual = [l.rstrip() for l in local.splitlines()] == [
                l.rstrip() for l in publicado.splitlines()
            ]
            print(f"{'ok  ' if igual else 'DIF '} {rota:26} {arquivo}")
            if not igual:
                falhas += 1
                d = primeira_divergencia(local, publicado)
                if d:
                    print(f"       primeira diferenca: {d}")

        navegador.close()

    if falhas:
        print(f"\n{falhas} arquivo(s) divergem do publicado.")
        return 1
    print("\nOK: o site publicado e identico ao do repositorio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
