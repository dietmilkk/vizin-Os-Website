"""Jornada de quem chega na home e decide o que fazer.

Confere o caminho real de uma pessoa, na ordem em que ela encontra:

1. a janela de primeira visita aparece e fecha;
2. o hero diz o que o app e, com o botao de download;
3. as secoes estao em ordem de leitura (o que e -> compromissos ->
   honestidade -> fundamentos -> comunidade -> sustento -> manifesto ->
   escolha) e nenhuma delas fica colada na outra sem separacao visual;
4. o bloco de manifesto expande o texto completo quando pedido;
5. a secao de comunidade tem o atalho para /comunidade;
6. o rodape leva para as paginas principais;
7. em celular nao ha rolagem horizontal.

Uso:
    python3 tests/test-jornada-home.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

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


def main() -> int:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))

        pagina.goto(f"{BASE}/", wait_until="load")
        pagina.wait_for_timeout(900)

        print("\n[1] Primeira visita")
        modal = pagina.locator("#firstVisitModal")
        check("janela de primeira visita aparece", modal.is_visible())
        if modal.is_visible():
            texto = modal.inner_text()
            check("janela fala do projeto", "vizin.Os" in texto, texto[:80])
            check(
                "janela aponta a Comunidade",
                modal.locator('a[href="/comunidade"]').count() == 1,
                texto[:120],
            )
            pagina.click('.modal-close[data-first-visit-close]')
            pagina.wait_for_timeout(400)
            check("janela fecha", not modal.is_visible())

        print("\n[2] O hero diz o que e o que fazer")
        check("um unico h1", pagina.locator("h1").count() == 1)
        h1 = pagina.locator("h1").inner_text().strip()
        check("h1 tem conteudo", len(h1) > 10, h1)
        check(
            "h1 descreve o projeto (nao so a marca)",
            "encontros" in h1.lower() or "gente" in h1.lower(),
            h1,
        )
        check("botao de download no hero", pagina.locator("#android-download").count() == 1)
        download = pagina.locator("#android-download")
        check("download visivel", download.is_visible())
        chips = pagina.locator(".hero-chips .chip").count()
        check("hero lista o que o app nao tem", chips >= 3, str(chips))

        print("\n[3] As secoes estao em ordem e separadas")
        secoes = pagina.evaluate(
            """() => [...document.querySelectorAll('main > section')].map(s => ({
                id: s.id,
                tint: s.classList.contains('section-tint'),
                kicker: (s.querySelector('.home-kicker') || {}).textContent || '',
                h: Math.round(s.getBoundingClientRect().height)
            }))"""
        )
        esperados = [
            "what-it-is", "promessas", "nao-prometemos", "fundamentos",
            "community", "funding", "manifesto", "importa",
        ]
        ids = [s["id"] for s in secoes if s["id"] in esperados]
        check("ordem das secoes", ids == esperados, str(ids))

        numeracao = [s["kicker"].split(" ")[0] for s in secoes if s["kicker"]]
        check(
            "numeracao sequencial sem buracos",
            numeracao == [f"{n:02d}" for n in range(1, len(numeracao) + 1)],
            str(numeracao),
        )

        # Nenhuma secao pode ficar colada na seguinte: o fundo alterna e ha
        # respiro entre elas.
        coladas = []
        for anterior, atual in zip(secoes, secoes[1:]):
            if atual["h"] < 200:
                coladas.append(atual["id"])
            if atual["tint"] == anterior["tint"]:
                coladas.append(f"{anterior['id']}->{atual['id']}")
        check("nenhuma secao colada na seguinte", not coladas, str(coladas))

        print("\n[4] O manifesto abre quando pedido")
        check("bloco do manifesto existe", pagina.locator("#manifestoPreview").count() == 1)
        corpo = pagina.locator("#manifestoPreviewBody")
        check("texto do manifesto vem escondido", not corpo.is_visible())
        pagina.click("#manifestoPreviewToggle")
        pagina.wait_for_timeout(1200)
        check("manifesto expande", corpo.is_visible())
        check(
            "manifesto tem o texto completo",
            len(corpo.inner_text().strip()) > 300,
            str(len(corpo.inner_text().strip())),
        )

        print("\n[5] Caminho para a comunidade")
        check(
            "botao para a comunidade na secao",
            pagina.locator('a.btn[href="/comunidade"]').count() == 1,
        )
        check(
            "comunidade no rodape",
            pagina.locator('a.explore-card[href="/comunidade"]').count() == 1,
        )
        check(
            "manifesto no rodape",
            pagina.locator('a.explore-card[href="/manifesto"]').count() == 1,
        )

        print("\n[6] Celular sem rolagem horizontal")
        celular = navegador.new_page(viewport={"width": 390, "height": 844})
        celular.goto(f"{BASE}/", wait_until="load")
        celular.wait_for_timeout(700)
        excesso = celular.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        check("sem rolagem horizontal", excesso <= 0, str(excesso))
        celular.close()

        print("\n[7] Sem erros de JavaScript")
        check("nenhum erro de runtime", not erros, "; ".join(erros[:3]))

        navegador.close()

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("A home guide quem chega nela do primeiro clique ao ultimo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
