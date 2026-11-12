#!/usr/bin/env python3
"""Mostra se a pagina publicada tem o breadcrumb e os blocos do painel."""

from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")


def main() -> int:
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch()
        pagina = navegador.new_page()
        pagina.goto(f"{BASE}/painel/", wait_until="networkidle")
        pagina.wait_for_timeout(2500)

        for rota in ("/", "/painel/", "/afiliados/", "/documento/", "/moderacao/", "/404.html"):
            html = pagina.evaluate(
                "async (u) => { const r = await fetch(u, {cache: 'no-store'}); return await r.text(); }",
                f"{BASE}{rota}",
            )
            tem_breadcrumb = 'class="breadcrumb"' in html
            tem_janela = 'id="painelOnlineLegenda"' in html
            print(
                f"{rota:15} breadcrumb={'sim' if tem_breadcrumb else 'no '}"
                f"  janela-online={'sim' if tem_janela else 'no '}"
            )
        navegador.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
