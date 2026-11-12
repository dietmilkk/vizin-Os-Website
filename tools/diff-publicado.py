#!/usr/bin/env python3
"""Mostra a diferenca real entre o arquivo local e o publicado."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent
ALVO = sys.argv[2] if len(sys.argv) > 2 else "/assets/styles.css"
LOCAL = {
    "/assets/styles.css": "assets/styles.css",
    "/assets/site.webmanifest": "site.webmanifest",
    "/site.webmanifest": "site.webmanifest",
}.get(ALVO, ALVO.lstrip("/"))

with sync_playwright() as pw:
    navegador = pw.chromium.launch()
    pagina = navegador.new_page()
    pagina.goto(f"{BASE}/painel/", wait_until="networkidle")
    publicado = pagina.evaluate(
        "async (u) => { const r = await fetch(u, {cache:'no-store'}); return await r.text(); }",
        f"{BASE}{ALVO}",
    )
    navegador.close()

local = (ROOT / LOCAL).read_text(encoding="utf-8")
print(f"local: {len(local)} chars | publicado: {len(publicado)} chars")
print(f"igual (strip): {local.strip() == publicado.strip()}")
print(f"igual (exato): {local == publicado}")
print(f"local CR: {local.count(chr(13))} | publicado CR: {publicado.count(chr(13))}")
print(f"local termina: {local[-40:]!r}")
print(f"publicado termina: {publicado[-40:]!r}")
print()
for linha in list(difflib.unified_diff(
    local.splitlines(), publicado.splitlines(),
    fromfile="local", tofile="publicado", lineterm="", n=1
))[:60]:
    print(linha)
