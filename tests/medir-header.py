#!/usr/bin/env python3
"""Mede a largura real do container do header em todas as páginas.

Serve para conferir que o header tem a MESMA largura em todas as páginas
(desktop e celular), como uma pessoa perceptive nota na hora.

Uso:
    python3 tests/medir-header.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
PAGINAS = ["/", "/painel", "/documento", "/moderacao", "/afiliados", "/404.html"]

TOLERANCIA = 1  # px de diferença aceitável entre as páginas.


def main() -> int:
    largura_esperada: float | None = None
    referencia = ""
    falhas: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for viewport, nome in [
            ({"width": 1440, "height": 900}, "desktop 1440px"),
            ({"width": 390, "height": 844}, "celular 390px"),
        ]:
            # Cada viewport tem sua própria referência: a largura maxima do
            # container depende da tela, mas deve ser igual em todas as
            # paginas dentro da mesma viewport.
            largura_esperada = None
            referencia = ""
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            print(f"\n{nome}")
            for rota in PAGINAS:
                page.goto(f"{BASE}{rota}", wait_until="domcontentloaded")
                medidas = page.evaluate(
                    """() => {
                        const header = document.querySelector('.site-header');
                        const inner = document.querySelector('.site-header .container');
                        if (!header || !inner) return null;
                        const r = inner.getBoundingClientRect();
                        const cs = getComputedStyle(inner);
                        return {
                            width: r.width,
                            left: r.left,
                            right: r.right,
                            maxWidth: cs.maxWidth,
                            padding: cs.paddingLeft,
                            headerWidth: header.getBoundingClientRect().width,
                        };
                    }"""
                )
                if medidas is None:
                    print(f"  {rota}: sem header")
                    falhas.append(f"{nome} {rota}: header ausente")
                    continue
                largura = round(medidas["width"], 1)
                print(
                    f"  {rota}: {largura}px "
                    f"(max-width {medidas['maxWidth']}, "
                    f"left {round(medidas['left'], 1)}, right {round(medidas['right'], 1)})"
                )
                if largura_esperada is None:
                    largura_esperada = largura
                    referencia = f"{nome} {rota}"
                elif abs(largura - largura_esperada) > TOLERANCIA:
                    falhas.append(
                        f"{nome} {rota}: {largura}px (referência {referencia}: {largura_esperada}px)"
                    )
            context.close()
        browser.close()

    print("")
    if falhas:
        print(f"{len(falhas)} falha(s):")
        for falha in falhas:
            print(f"  - {falha}")
        return 1
    print("OK: o header tem a mesma largura em todas as páginas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
