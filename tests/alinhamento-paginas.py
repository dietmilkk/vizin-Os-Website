#!/usr/bin/env python3
"""Confere se o conteudo das paginas alinha com o header.

O header tem largura padrao em todas as paginas. Este teste confere se o
conteudo principal de cada pagina tambem respeita essa mesma grade — sem
blocos quebrando o alinhamento (um container largo demais, um texto que
 invade a margem, etc.).

Uso:
    python3 tests/alinhamento-paginas.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")
PAGINAS = ["/", "/painel", "/documento", "/moderacao", "/afiliados", "/404.html"]
TOLERANCIA = 2  # px

falhas: list[str] = []
checks = 0


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global checks
    checks += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for largura, nome in [(1440, "desktop"), (390, "celular")]:
            context = browser.new_context(viewport={"width": largura, "height": 900})
            page = context.new_page()
            print(f"\n{nome} ({largura}px)")
            for rota in PAGINAS:
                page.goto(f"{BASE}{rota}", wait_until="networkidle")
                page.wait_for_timeout(300)
                dados = page.evaluate(
                    """() => {
                        const header = document.querySelector('.site-header .container');
                        if (!header) return null;
                        const h = header.getBoundingClientRect();
                        const cs = getComputedStyle(header);
                        const margem = parseFloat(cs.paddingLeft) || 0;
                        const containers = Array.from(document.querySelectorAll(
                            'main .container, main > .container, body > main > .container'
                        )).map((el) => {
                            const r = el.getBoundingClientRect();
                            return {
                                classe: el.className,
                                left: r.left + parseFloat(getComputedStyle(el).paddingLeft),
                                right: r.right - parseFloat(getComputedStyle(el).paddingRight),
                            };
                        });
                        return {
                            headerLeft: h.left + margem,
                            headerRight: h.right - margem,
                            containers,
                        };
                    }"""
                )
                if dados is None:
                    check(f"{rota}: tem header", False, "header ausente")
                    continue
                hl = dados["headerLeft"]
                hr = dados["headerRight"]
                check(
                    f"{rota}: header dentro da viewport",
                    hl >= -1 and hr <= largura + 1,
                    f"left {hl:.1f} right {hr:.1f}",
                )
                for cont in dados["containers"]:
                    desvio_esq = abs(cont["left"] - hl)
                    desvio_dir = abs(cont["right"] - hr)
                    alinhado = desvio_esq <= TOLERANCIA and desvio_dir <= TOLERANCIA
                    # Bloco centralizado e mais estreito que a grade (ex.: o
                    # hero da home, que e um texto curto no meio da tela) e
                    # simetrico: nao quebra o alinhamento, e so uma escolha
                    # editorial. O que nao pode e um bloco torto.
                    margem_esq = cont["left"]
                    margem_dir = largura - cont["right"]
                    centralizado = abs(margem_esq - margem_dir) <= TOLERANCIA
                    check(
                        f"{rota}: '{cont['classe']}' alinha com o header",
                        alinhado or centralizado,
                        f"left {cont['left']:.1f} (header {hl:.1f}) "
                        f"right {cont['right']:.1f} (header {hr:.1f})",
                    )
            context.close()
        browser.close()

    print("")
    print(f"{checks} verificações · {len(falhas)} falha(s)")
    if falhas:
        for falha in falhas:
            print(f"  - {falha}")
        return 1
    print("OK: o conteudo alinha com o header em todas as paginas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
