#!/usr/bin/env python3
"""Tira prints das páginas do site para conference visual do header.

Uso:
    python3 tools/prints-header.py [http://127.0.0.1:8099] [saida]
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
SAIDA = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/prints-header")
SAIDA.mkdir(parents=True, exist_ok=True)

PAGINAS = {
    "home": "/",
    "painel": "/painel",
    "documento": "/documento",
    "moderacao": "/moderacao",
    "afiliados": "/afiliados",
    "404": "/404.html",
}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for nome, rota in PAGINAS.items():
        for largura, sufixo in [(1440, "desktop"), (390, "celular")]:
            context = browser.new_context(viewport={"width": largura, "height": 900})
            page = context.new_page()
            page.goto(f"{BASE}{rota}", wait_until="networkidle")
            page.wait_for_timeout(600)
            destino = SAIDA / f"{nome}-{sufixo}.png"
            page.screenshot(path=str(destino), clip={"x": 0, "y": 0, "width": largura, "height": 260})
            print(destino)
            context.close()
    browser.close()
