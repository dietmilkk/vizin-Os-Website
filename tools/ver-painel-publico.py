#!/usr/bin/env python3
"""Mostra o que um visitante REAL vê no painel publicado.

Abre a página no Chromium (o site oficial usa verificação por JavaScript, então
`curl` não serve) e imprime os números principais do painel, do jeito que
estão na tela.
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")

CAMPOS = [
    ("painelOnline", "Dispositivos online agora"),
    ("painelOnlineLegenda", "janela usada"),
    ("painelAtivos1h", "Ativos 1 h"),
    ("painelAtivos24", "Ativos 24 h"),
    ("painelAtivos7", "Ativos 7 dias"),
    ("painelAtivos30", "Ativos 30 dias"),
    ("painelRegioes", "Regioes"),
    ("painelBeacons", "Beacons"),
    ("painelUptime", "Servidor no ar ha"),
    ("painelDesde", "Servico no ar desde"),
    ("painelContas", "Contas"),
    ("painelContaRecente", "Conta mais recente"),
    ("painelNovas24h", "Novas 24 h"),
    ("painelNovas7d", "Novas 7 dias"),
    ("painelTaxa", "Taxa (anel)"),
    ("painelAnelLegenda", "Proporcao sobre o total"),
    ("painelUsernamesLegenda", "Proporcao usernames"),
    ("painelCofresLegenda", "Proporcao cofres"),
    ("painelMemoria", "Memoria"),
    ("painelCpu", "CPU"),
    ("painelBanco", "Banco"),
    ("painelRuntime", "Runtime"),
    ("painelLatencia", "Latencia"),
]


def main() -> int:
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
        pagina.goto(f"{BASE}/painel", wait_until="networkidle")
        pagina.wait_for_function(
            "() => document.getElementById('painelStatusTexto')"
            "?.textContent?.startsWith('Atualizado')",
            timeout=30_000,
        )
        print(f"Painel publicado: {BASE}/painel\n")
        print(f"  status: {pagina.inner_text('#painelStatusTexto').strip()}")
        erro = pagina.locator("#painelErro")
        print(f"  erro visivel: {erro.is_visible()}\n")
        for elemento, rotulo in CAMPOS:
            texto = pagina.inner_text(f"#{elemento}").strip()
            print(f"  {rotulo:.<32} {texto}")
        navegador.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
