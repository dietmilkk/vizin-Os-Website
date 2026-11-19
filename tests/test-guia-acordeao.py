"""Confere, como quem usa, a pagina de afiliados depois da reformulacao.

O guia em acordeao saiu: a explicacao agora esta em secoes sempre
visiveis (escolha do papel, como funciona, divisao do valor). Este teste
confere o que importa para quem chega na pagina:

- o hero explica o programa em uma frase e tem o botao de criar conta;
- as secoes "Escolha seu papel", "Como funciona" e "Como o valor e dividido"
  existem, sao visiveis e tem textos nao vazios;
- a divisao do valor mostra os quatro percentuais (30/50/10/10) e o exemplo
  em reais (R$ 9,90 -> R$ 6,93), sem letra miuda;
- os botoes de criar conta abrem a janela de cadastro;
- o rodape continua minimalista (icone + titulo ao lado);
- nenhum erro de JavaScript na pagina.

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


def main() -> int:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))

        pagina.goto(f"{BASE}/afiliados", wait_until="load")
        pagina.wait_for_timeout(900)

        # A janela de primeira visita aparece na primeira navegacao: um
        # usuario real fecha antes de continuar.
        if pagina.locator("#firstVisitModal").is_visible():
            pagina.click('.modal-close[data-first-visit-close]')
            pagina.wait_for_timeout(300)

        print("\n[1] O programa se explica na primeira dobra")
        titulo = pagina.locator("h1#aff-title")
        check("titulo principal existe", titulo.count() == 1)
        texto_titulo = titulo.inner_text().strip() if titulo.count() else ""
        check("titulo diz o que a pessoa ganha", len(texto_titulo) > 20, texto_titulo)
        check(
            "hero tem botao para criar conta",
            pagina.locator('[data-open-create="creator"]:visible').count() >= 1,
        )
        lead = pagina.locator(".aff-hero__lead").inner_text().strip()
        check("hero tem um texto de apoio", len(lead) > 40, lead[:60])

        print("\n[2] As secoes que explicam o programa estao visiveis")
        for seletor, rotulo in [
            ('#por-que', "por que esse modelo funciona"),
            ('#how-it-works', "escolha seu papel"),
            ('#divisao', "divisao do valor"),
            ('#participar', "chamada final"),
        ]:
            bloco = pagina.locator(seletor)
            check(f"secao '{rotulo}' existe", bloco.count() == 1)
            if bloco.count():
                texto = bloco.inner_text().strip()
                check(f"secao '{rotulo}' tem conteudo", len(texto) > 80, f"{len(texto)} chars")
                box = bloco.bounding_box()
                check(f"secao '{rotulo}' tem altura", bool(box and box["height"] > 120))

        print("\n[3] A divisao do valor explica os quatro percentuais")
        painel = pagina.locator(".aff-money-panel")
        check("painel de valores existe", painel.count() == 1)
        if painel.count():
            texto = painel.inner_text()
            for pct in ("30%", "50%", "10%"):
                check(f"percentual {pct} aparece", pct in texto)
            check("preco de referencia aparece", "9,90" in texto, texto[:120])
            check("valor pago pelo usuario aparece", "6,93" in texto, texto[:120])
            check(
                "comissao do criador em reais aparece",
                "4,95" in texto,
                texto[:120],
            )
        barra = pagina.locator(".aff-splitbar")
        check("barra da divisao visivel", barra.count() == 1 and barra.first.is_visible())

        print("\n[4] Criar conta abre a janela certa")
        pagina.click('[data-open-create="afiliado"]:visible')
        pagina.wait_for_timeout(500)
        check(
            "janela de criacao abriu",
            pagina.locator("#createModal").is_visible(),
        )
        check(
            "campo de codigo existe",
            pagina.locator("#code").count() == 1,
        )
        pagina.keyboard.press("Escape")
        pagina.wait_for_timeout(400)

        print("\n[5] Rodape minimalista")
        rodape = pagina.locator(".site-footer")
        check("rodape presente", rodape.count() == 1)
        cartoes = pagina.locator(".explore-card")
        check("cartoes de exploracao presentes", cartoes.count() >= 5, str(cartoes.count()))
        icone = pagina.locator(".explore-card__icon").first
        titulo_card = cartoes.first.locator("span").first
        box_i = icone.bounding_box()
        box_t = titulo_card.bounding_box()
        check(
            "icone e titulo ficam lado a lado",
            bool(box_i and box_t and abs(box_i["y"] - box_t["y"]) < 24),
        )

        print("\n[6] Sem erros de JavaScript")
        check("nenhum erro de runtime", not erros, "; ".join(erros[:3]))

        navegador.close()

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("A pagina de afiliados se explica sozinha, do jeito que o usuario precisa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
