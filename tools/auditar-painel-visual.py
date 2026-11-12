#!/usr/bin/env python3
"""Checagem final de detalhes visuais no painel publicado."""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")

JS = """
() => {
  const spark = document.getElementById('painelLatenciaGrafo');
  const fill = document.getElementById('painelBarra7');
  const anel = document.getElementById('painelAnelArco');
  const valor = document.getElementById('painelAtivos7');
  const cs = (el) => getComputedStyle(el);
  return {
    sparkHtml: spark ? spark.innerHTML.slice(0, 160) : null,
    sparkAltura: spark ? Math.round(spark.getBoundingClientRect().height) : null,
    sparkLargura: spark ? Math.round(spark.getBoundingClientRect().width) : null,
    fillCor: fill ? cs(fill).backgroundColor : null,
    fillAltura: fill ? Math.round(fill.getBoundingClientRect().height) : null,
    anelCor: anel ? cs(anel).stroke : null,
    anelWidth: anel ? cs(anel).strokeWidth : null,
    valorFonte: valor ? cs(valor).fontSize + ' / ' + cs(valor).fontWeight : null,
    chips: Array.from(document.querySelectorAll('#painelRegioesLista .panel-regiao')).map((c) => c.textContent.trim()),
    contatos: Array.from(document.querySelectorAll('#painelContatosLista .panel-regiao')).map((c) => c.textContent.trim()),
    titulos: Array.from(document.querySelectorAll('main h2')).map((h) => h.textContent.trim()),
    linksInternos: Array.from(new Set(Array.from(document.querySelectorAll('main a[href^="/"]')).map((a) => a.getAttribute('href')))),
  };
}
"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    erros = []

    def escutar_console(m) -> None:
        # A rota /_vercel/insights/* (Web Analytics) só existe quando o site é
        # servido pela Vercel: fora dela o 404 do <script defer> aparece como
        # erro de console e não é falha do painel.
        if m.type != "error":
            return
        local = (m.location or {}).get("url", "") or ""
        if "/_vercel/insights/" in m.text or "/_vercel/insights/" in local:
            return
        erros.append(m.text)

    page.on("console", escutar_console)
    page.on("pageerror", lambda e: erros.append(str(e)))
    page.goto(f"{BASE}/painel", wait_until="networkidle")
    page.wait_for_function(
        "() => document.getElementById('painelStatusTexto')?.textContent?.startsWith('Atualizado')",
        timeout=30_000,
    )
    dados = page.evaluate(JS)
    for chave, valor in dados.items():
        print(f"{chave}: {valor}")
    print(f"erros de console: {erros if erros else 'nenhum'}")
    browser.close()
