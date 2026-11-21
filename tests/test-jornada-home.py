"""Jornada de quem chega na home e decide o que fazer.

Confere o caminho real de uma pessoa, na ordem em que ela encontra:

1. a janela de primeira visita aparece e fecha;
2. o hero diz o que o app e, com o botao de download;
3. as secoes estao em ordem de leitura (o que e -> compromissos ->
   honestidade -> comunidade -> sustento e escolha no mesmo bloco) e nenhuma
   delas fica colada na outra sem separacao visual;
4. a secao de comunidade tem o atalho para /comunidade;
5. o rodape leva para as paginas principais;
6. em celular nao ha rolagem horizontal.

Uso:
    python3 tests/test-jornada-home.py [http://127.0.0.1:8099]
"""

from __future__ import annotations

import sys
from itertools import pairwise

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
            "what-it-is", "promessas", "nao-prometemos", "community", "funding",
        ]
        ids = [s["id"] for s in secoes if s["id"] in esperados]
        check("ordem das secoes", ids == esperados, str(ids))

        numeracao = pagina.locator("main .home-kicker").evaluate_all(
            "els => els.map(el => el.textContent.trim().split(' ')[0])"
        )
        check(
            "numeracao da home preservada",
            numeracao == ["01", "02", "03", "05", "06", "07"],
            str(numeracao),
        )
        check(
            "escolha no mesmo bloco de sustento",
            pagina.locator("#funding > .container > #importa.home-closing").count() == 1,
        )

        aparencia = pagina.evaluate(
            """() => {
                const card = getComputedStyle(document.querySelector('.home-funding'));
                const closing = getComputedStyle(document.querySelector('.home-closing'));
                const propriedades = [
                    'backgroundColor', 'borderTopColor', 'borderTopWidth',
                    'borderRadius', 'boxShadow', 'paddingTop', 'paddingRight',
                    'paddingBottom', 'paddingLeft'
                ];
                return Object.fromEntries(propriedades.map(propriedade => [
                    propriedade,
                    [card[propriedade], closing[propriedade]]
                ]));
            }"""
        )
        check(
            "escolha tem a mesma aparencia dos cards de financiamento",
            all(valores[0] == valores[1] for valores in aparencia.values()),
            str(aparencia),
        )

        hierarquia = pagina.evaluate(
            """() => {
                const grid = getComputedStyle(document.querySelector('.home-funding-grid'));
                const closing = getComputedStyle(document.querySelector('.home-closing'));
                const titulo = getComputedStyle(document.querySelector('.home-closing h2'));
                const texto = getComputedStyle(document.querySelector('.home-closing__body p'));
                return {
                    gap: grid.gap,
                    margem: closing.marginTop,
                    alinhamento: closing.textAlign,
                    titulo: parseFloat(titulo.fontSize),
                    texto: parseFloat(texto.fontSize)
                };
            }"""
        )
        check(
            "escolha continua visualmente os cards de financiamento",
            hierarquia["margem"] == hierarquia["gap"]
            and hierarquia["alinhamento"] == "left"
            and hierarquia["titulo"] <= 20
            and hierarquia["texto"] <= 15.1,
            str(hierarquia),
        )

        # Nenhuma secao pode ficar colada na seguinte: o fundo alterna e ha
        # respiro entre elas.
        coladas = []
        for anterior, atual in pairwise(secoes):
            if atual["h"] < 200:
                coladas.append(atual["id"])
            if atual["tint"] == anterior["tint"]:
                coladas.append(f"{anterior['id']}->{atual['id']}")
        check("nenhuma secao colada na seguinte", not coladas, str(coladas))

        print("\n[4] Caminho para a comunidade")
        check(
            "botao para a comunidade na secao",
            pagina.locator('a.btn[href="/comunidade"]').count() == 1,
        )
        check(
            "comunidade no rodape",
            pagina.locator('a.explore-card[href="/comunidade"]').count() == 1,
        )

        # A "florzinha" que existia sobre a marca foi removida do site:
        # agora a checagem garante que a marca do rodape continua completa
        # (icone e wordmark juntos, alinhados e com tamanho real).
        marca_rodape = pagina.locator(".site-footer .brand").first
        marca_rodape.hover()
        pagina.wait_for_timeout(400)
        marca_info = pagina.evaluate(
            """() => {
                const marca = document.querySelector('.site-footer .brand');
                const icone = marca.querySelector('.brand-mark');
                const palavra = marca.querySelector('.brand-wordmark');
                if (!icone || !palavra) return null;
                const boxI = icone.getBoundingClientRect();
                const boxP = palavra.getBoundingClientRect();
                return {
                    temIcone: boxI.width >= 40 && boxI.height >= 40,
                    temPalavra: boxP.width >= 60 && boxP.height >= 10,
                    alinhados: Math.abs(boxI.top - boxP.top) < 24,
                    sobrepostos: boxP.left >= boxI.right - 1,
                    decoracao: getComputedStyle(marca, '::after').content
                };
            }"""
        )
        check(
            "marca do rodape completa e alinhada",
            bool(marca_info)
            and marca_info["temIcone"]
            and marca_info["temPalavra"]
            and marca_info["alinhados"]
            and marca_info["sobrepostos"]
            and marca_info["decoracao"] == 'none',
            str(marca_info),
        )

        print("\n[5] Celular sem rolagem horizontal")
        celular = navegador.new_page(viewport={"width": 390, "height": 844})
        celular.goto(f"{BASE}/", wait_until="load")
        celular.wait_for_timeout(700)
        excesso = celular.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        check("sem rolagem horizontal", excesso <= 0, str(excesso))
        celular.close()

        print("\n[6] Sem erros de JavaScript")
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
