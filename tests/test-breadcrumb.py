"""Confere o breadcrumb onde ele existe.

O breadcrumb é opcional por página: quando a página mostra, tem que ser
exatamente um, correto e legível no celular. Páginas sem breadcrumb passam
tranquilamente (a home e as páginas de conteúdo não precisam dele).

Uso:
    python3 tests/test-breadcrumb.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"

# Rota -> nome da página atual esperado no fim do caminho.
PAGINAS = {
    "/": "vizin.Os",
    "/afiliados/": "Afiliados",
    "/painel/": "Painel público",
    "/documento/": "Documento técnico",
    "/moderacao/": "Moderação",
    "/404.html": "Página não encontrada",
}

falhas: list[str] = []
verificacoes = 0


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global verificacoes
    verificacoes += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def visiveis(pagina) -> list[dict]:
    return pagina.evaluate(
        """() => [...document.querySelectorAll('.breadcrumb')].filter(el => {
          const estilo = getComputedStyle(el);
          if (estilo.display === 'none' || estilo.visibility === 'hidden') return false;
          const r = el.getBoundingClientRect();
          return r.width > 0 && r.height > 0;
        }).map(el => ({
          passos: [...el.querySelectorAll('a, [aria-current="page"]')].map(n => n.textContent.trim()),
          temSeparador: !!el.querySelector('.breadcrumb-sep'),
          rotulo: el.getAttribute('aria-label'),
        }))"""
    )


with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    contexto = browser.new_context(viewport={"width": 1280, "height": 900})
    pagina = contexto.new_page()

    for rota, atual in PAGINAS.items():
        print(f"\n[{rota}]")
        pagina.goto(BASE + rota, wait_until="networkidle")
        pagina.wait_for_timeout(700)

        achados = visiveis(pagina)
        if not achados:
            print("  --   sem breadcrumb (opcional)")
            continue
        check("no maximo um breadcrumb visivel", len(achados) == 1, str(len(achados)))
        if not achados:
            continue
        item = achados[0]
        check("comeca em 'Inicio'", item["passos"][0] == "Início", str(item["passos"]))
        check("termina na pagina atual", item["passos"][-1] == atual, str(item["passos"]))
        check("tem separador", item["temSeparador"])
        check("rotulo acessivel", item["rotulo"] == "Você está aqui", str(item["rotulo"]))
        check("link do inicio aponta para a raiz", pagina.evaluate(
            """() => {
              const a = document.querySelector('.breadcrumb a');
              return a ? new URL(a.getAttribute('href'), location.href).pathname : null;
            }"""
        ) == "/")

    # No celular o breadcrumb continua aparecendo (nao pode sumir com o hero).
    print("\n[celular 390px]")
    contexto2 = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pagina2 = contexto2.new_page()
    for rota in PAGINAS:
        pagina2.goto(BASE + rota, wait_until="networkidle")
        pagina2.wait_for_timeout(600)
        achados = visiveis(pagina2)
        if not achados:
            print(f"  --   sem breadcrumb em {rota} (opcional)")
            continue
        check(f"breadcrumb unico e visivel em {rota}", len(achados) == 1, str(len(achados)))

    browser.close()

print()
if falhas:
    print(f"{verificacoes - len(falhas)}/{verificacoes} verificacoes passaram")
    sys.exit(1)
print(f"{verificacoes}/{verificacoes} verificacoes passaram")
print("Breadcrumb OK nas paginas que o mostram.")
