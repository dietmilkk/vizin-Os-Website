"""Confere, como quem usa, o guia 'Como funciona por dentro': os botoes
expandem um bloco por vez, o primeiro ja vem aberto e o rodape continua
minimalista (icone + titulo ao lado).

Uso:
    python3 tests/test-guia-acordeao.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

from lib.primeiro_acesso import ja_visitou

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099"

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


def visiveis(page) -> list[str]:
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-guide-panel]')]
            .filter(el => {
              const estilo = getComputedStyle(el);
              return estilo.display !== 'none' && estilo.visibility !== 'hidden'
                && !el.hasAttribute('hidden');
            })
            .map(el => el.id)"""
    )


with sync_playwright() as playwright:
    browser = playwright.firefox.launch()
    contexto = browser.new_context(viewport={"width": 1280, "height": 900})
    ja_visitou(contexto)
    pagina = contexto.new_page()
    erros: list[str] = []
    pagina.on("pageerror", lambda e: erros.append(str(e)))

    print("\n[1] O guia abre na pagina publica e no painel")
    pagina.goto(f"{BASE}/afiliados/", wait_until="networkidle")
    pagina.wait_for_timeout(1200)
    # O guia completo e publico: na pagina ele abre na primeira aba.
    check(
        "guia visivel na pagina publica",
        pagina.locator("#guiaCompleto").is_visible(),
    )
    check(
        "guia com uma unica aba aberta",
        len(visiveis(pagina)) == 1,
        str(visiveis(pagina)),
    )
    check(
        "primeira aba do guia aberta",
        (visiveis(pagina) or [None])[0] == "guiaProjeto",
        str(visiveis(pagina)),
    )

    # Entra pelo painel usando um token ficticio para revelar o guia.
    pagina.goto(f"{BASE}/afiliados/?p=C" + "A" * 15, wait_until="networkidle")
    pagina.wait_for_timeout(2500)
    check("guia visivel no painel", pagina.locator("#guiaCompleto").is_visible())

    print("\n[2] Acordeao: um bloco por vez")
    visiveis_iniciais = visiveis(pagina)
    check("apenas um bloco aberto", len(visiveis_iniciais) == 1, str(visiveis_iniciais))

    botoes = pagina.locator("[data-guide-target]")
    total = botoes.count()
    check("botoes do sumario presentes", total >= 3, str(total))

    for indice in range(total):
        botoes.nth(indice).click()
        pagina.wait_for_timeout(500)
        abertos = visiveis(pagina)
        esperado = botoes.nth(indice).get_attribute("data-guide-target")
        check(
            f"botao {indice + 1} abre so o bloco dele",
            len(abertos) == 1 and esperado in abertos,
            f"esperado {esperado}, abertos {abertos}",
        )

    print("\n[3] Sumario com o bloco aberto marcado")
    marcados = pagina.evaluate(
        """() => [...document.querySelectorAll('[data-guide-target]')]
            .filter(el => el.getAttribute('aria-expanded') === 'true').length"""
    )
    check("apenas um botao marcado como aberto", marcados == 1, str(marcados))

    print("\n[4] Rodape minimalista")
    cards = pagina.locator(".explore-card")
    check("blocos do rodape presentes", cards.count() >= 3, str(cards.count()))
    formato = pagina.evaluate(
        """() => [...document.querySelectorAll('.explore-card')].map(el => {
          const icone = el.querySelector('.explore-card__icon');
          const texto = el.querySelector('span');
          if (!icone || !texto) return null;
          const rIcone = icone.getBoundingClientRect();
          const rTexto = texto.getBoundingClientRect();
          return {
            lado: rIcone.right <= rTexto.left + 2 || rTexto.right <= rIcone.left + 2,
            iconeTop: Math.round(rIcone.top),
            textoTop: Math.round(rTexto.top),
          };
        })"""
    )
    check(
        "icone e titulo ficam lado a lado",
        all(item and item["lado"] for item in formato),
        str(formato),
    )
    check(
        "icone e titulo alinhados na mesma linha",
        all(item and abs(item["iconeTop"] - item["textoTop"]) < 14 for item in formato),
        str(formato),
    )

    print("\n[5] Sem erros de JavaScript")
    check("nenhum erro de runtime", not erros, "; ".join(erros))

    browser.close()

print()
if falhas:
    print(f"{verificacoes - len(falhas)}/{verificacoes} verificacoes passaram")
    sys.exit(1)
print(f"{verificacoes}/{verificacoes} verificacoes passaram")
print("Guia em acordeao OK.")
