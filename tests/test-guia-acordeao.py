"""Confere, como quem usa, a pagina de Membros depois da reformulacao.

O guia em acordeao saiu: a explicacao agora esta em secoes sempre
visiveis (escolha do papel, como funciona, divisao do valor). Este teste
confere o que importa para quem chega na pagina:

- o hero explica o programa em uma frase e tem o botao de criar conta;
- as secoes "Escolha seu papel", "Como funciona" e "Como o valor e dividido"
  existem, sao visiveis e tem textos nao vazios;
- a divisao do valor virou uma planilha com os cinco papeis (50/25/10/5/10),
  alimentada por uma configuracao unica que soma 100%;
- a secao "Por que essa divisao e justa" destaca o merito do criador;
- o efeito multiplicador tem diagrama de fluxo e simulacao ilustrativa;
- os botoes de criar conta abrem a janela de cadastro;
- o rodape continua minimalista (icone + titulo ao lado);
- nenhum erro de JavaScript na pagina.

Uso:
    python3 tests/test-guia-acordeao.py [http://127.0.0.1:8099]
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

        pagina.goto(f"{BASE}/membros", wait_until="load")
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
            ('#justica', "por que essa divisao e justa"),
            ('#efeito-multiplicador', "efeito multiplicador"),
            ('#participar', "chamada final"),
        ]:
            bloco = pagina.locator(seletor)
            check(f"secao '{rotulo}' existe", bloco.count() == 1)
            if bloco.count():
                texto = bloco.inner_text().strip()
                check(f"secao '{rotulo}' tem conteudo", len(texto) > 80, f"{len(texto)} chars")
                box = bloco.bounding_box()
                check(f"secao '{rotulo}' tem altura", bool(box and box["height"] > 120))

        print("\n[3] A divisao do valor virou uma planilha com config unica")
        config = pagina.evaluate("() => window.VIZIN_REVENUE_SPLIT")
        check("configuracao da divisao existe", bool(config), str(config))
        esperado = {
            "creator": 50,
            "user": 25,
            "affiliate": 10,
            "mod": 5,
            "development": 10,
        }
        if config:
            check(
                "configuracao soma 100%",
                config.get("total") == 100,
                str(config.get("total")),
            )
            check(
                "percentuais da config batem com a especificacao",
                config.get("shares") == esperado,
                str(config.get("shares")),
            )

        planilha = pagina.locator(".revenue-sheet")
        check(
            "planilha da divisao existe",
            planilha.count() == 1 and planilha.first.is_visible(),
        )
        linhas = pagina.locator(".revenue-sheet__table tbody tr")
        check("planilha tem os cinco papeis", linhas.count() == 5, str(linhas.count()))
        if planilha.count():
            texto = planilha.inner_text()
            for pct in ("50%", "25%", "10%", "5%"):
                check(f"percentual {pct} aparece na planilha", pct in texto)
            check("total de 100% aparece", "100%" in texto)
            check("funcao do criador aparece", "Produzem e trazem usuários" in texto)
            check("funcao do Mod Parceiro aparece", "Recrutam afiliados" in texto)
        check(
            "barra horizontal antiga removida",
            pagina.locator(".aff-splitbar, .split-bar").count() == 0,
        )

        print("\n[4] A secao de merito e o efeito multiplicador")
        justica = pagina.locator("#justica").inner_text().lower()
        check("secao fala de meritocracia", "meritocracia" in justica, justica[:100])
        check(
            "secao destaca o criador",
            "a base do valor" in justica and "sem criador" in justica,
        )
        check(
            "secao cita o Mod Parceiro e o volume acumulado",
            "mod parceiro" in justica and "volume acumulado" in justica,
        )

        efeito = pagina.locator("#efeito-multiplicador").inner_text()
        check("secao cita o efeito multiplicador", "efeito multiplicador" in efeito.lower())
        check("diagrama de fluxo existe", pagina.locator(".revenue-flow").count() == 1)
        check("simulacao identificada", "Simulação ilustrativa" in efeito)
        check(
            "simulacao mostra 1 Mod, 10 Afiliados e 50 Criadores",
            all(trecho in efeito for trecho in ("1", "10", "50")),
        )
        check("simulacao nao promete ganho", "não é promessa de ganho" in efeito)

        proibidas = (
            "pirâmide",
            "esquema",
            "renda passiva garantida",
            "ganhar sem fazer nada",
        )
        pagina_inteira = pagina.locator("body").inner_text().lower()
        check("sem termos proibidos", not any(t in pagina_inteira for t in proibidas))
        for termo in (
            "rede de afiliados",
            "divisão de receita",
            "efeito multiplicador",
            "meritocracia",
        ):
            check(f"termo obrigatorio '{termo}' presente", termo in pagina_inteira)

        print("\n[5] Criar conta abre a janela certa")
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

        print("\n[6] Rodape minimalista")
        rodape = pagina.locator(".site-footer")
        check("rodape presente", rodape.count() == 1)
        cartoes = pagina.locator(".explore-card")
        check("cartoes de exploracao presentes", cartoes.count() >= 5, str(cartoes.count()))
        icone = cartoes.first.locator(".explore-card__icon")
        titulo_card = cartoes.first.locator("span").first
        box_i = icone.bounding_box()
        box_t = titulo_card.bounding_box()
        check(
            "icone e titulo ficam lado a lado",
            bool(box_i and box_t and abs(box_i["y"] - box_t["y"]) < 24),
        )

        print("\n[7] Sem erros de JavaScript")
        check("nenhum erro de runtime", not erros, "; ".join(erros[:3]))

        navegador.close()

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("A pagina de Membros se explica sozinha, do jeito que o usuario precisa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
