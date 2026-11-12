"""Passeio final pelo site publicado, como um visitante.

Abre cada pagina em desktop (1366x900) e celular (390x844), rola a pagina
inteira, coleta erros de JavaScript e mede o espaco usado na tela.
"""
import sys
from playwright.sync_api import sync_playwright

SITE = "https://vizin-os.page.gd"
PAGINAS = ["/", "/afiliados", "/painel", "/documento", "/moderacao"]


def main():
    falhas = []
    with sync_playwright() as p:
        navegador = p.firefox.launch()
        for largura, altura, nome in ((1366, 900, "desktop"), (390, 844, "celular")):
            ctx = navegador.new_context(viewport={"width": largura, "height": altura})
            for rota in PAGINAS:
                pagina = ctx.new_page()
                erros = []
                pagina.on("pageerror", lambda e: erros.append(str(e)))

                def escutar_console(m) -> None:
                    # A rota /_vercel/insights/* (Web Analytics) só existe quando o site
                    # é servido pela Vercel. Fora dela o <script defer> responde 404 e o
                    # navegador registra erro de console — a mensagem de texto não traz a
                    # URL; ela está em m.location.
                    if m.type != "error":
                        return
                    local = (m.location or {}).get("url", "") or ""
                    if "/_vercel/insights/" in m.text or "/_vercel/insights/" in local:
                        return
                    erros.append("console: " + m.text)

                pagina.on("console", escutar_console)
                pagina.goto(SITE + rota, wait_until="domcontentloaded")
                pagina.wait_for_timeout(2500)
                pagina.mouse.wheel(0, 20000)
                pagina.wait_for_timeout(1200)
                altura_total = pagina.evaluate(
                    "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
                )
                erros = [e for e in erros if "favicon" not in e.lower()]
                print(
                    f"{nome:8} {rota:12} altura={altura_total:6}px "
                    f"viewport={altura}px erros={len(erros)}"
                )
                for e in erros:
                    print("      !", e[:160])
                    falhas.append(f"{nome} {rota}: {e[:120]}")
                pagina.close()
            ctx.close()

        # A janela de criacao de conta, como o visitante abriria.
        ctx = navegador.new_context(viewport={"width": 390, "height": 844})
        pagina = ctx.new_page()
        erros = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))
        pagina.goto(SITE + "/afiliados", wait_until="domcontentloaded")
        pagina.wait_for_timeout(2500)
        botao = pagina.locator('[data-open-create="afiliado"]').first
        if botao.count() and botao.is_visible():
            botao.click()
            pagina.wait_for_timeout(900)
            visivel = pagina.locator("#createModal").is_visible()
            print(f"celular  /afiliados   janela de criacao abriu: {visivel}")
            if not visivel:
                falhas.append("janela de criacao nao abriu no celular")
        else:
            print("celular  /afiliados   botao de afiliado nao encontrado")
            falhas.append("botao de afiliado nao encontrado no celular")
        for e in erros:
            print("      !", e[:160])
            falhas.append(e[:120])
        ctx.close()
        navegador.close()

    if falhas:
        print("\nFALHAS:")
        for f in falhas:
            print(" -", f)
        sys.exit(1)
    print("\nPasseio sem erros em todas as paginas.")


if __name__ == "__main__":
    main()
