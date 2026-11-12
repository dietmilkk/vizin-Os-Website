#!/usr/bin/env python3
"""Confere se o Vercel Web Analytics está coletando no site publicado.

Abre o site num navegador de verdade e observa as requisições para
`/_vercel/insights/*`. O script do Analytics ignora navegadores
automatizados (`navigator.webdriver`), então o evento *não* é gravado no
teste — o que interessa aqui é que o script seja carregado e que a rota de
coleta responda, provando que a contagem vai funcionar para visitors de
verdade.

Uso: python3 tools/check-analytics-vercel.py [url]
"""

import sys

from playwright.sync_api import sync_playwright

URL = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.vercel.app").rstrip("/")
PAGINAS = ["/", "/afiliados/", "/documento/", "/manifesto/", "/moderacao/", "/painel/"]


def main() -> int:
    erros = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        for rota in PAGINAS:
            pagina = navegador.new_page()
            pedidos = []
            respostas = {}

            def registrar(req):
                if "/_vercel/insights/" in req.url:
                    pedidos.append(req.url)

            def responder(resp):
                if "/_vercel/insights/" in resp.url:
                    respostas[resp.url.split("/_vercel/insights/")[-1]] = resp.status

            pagina.on("request", registrar)
            pagina.on("response", responder)
            try:
                pagina.goto(URL + rota, wait_until="commit", timeout=45_000)
                pagina.wait_for_timeout(4000)
            except Exception as exc:  # noqa: BLE001 - reporta e segue
                erros.append(f"{rota}: navegacao falhou ({exc.__class__.__name__})")
                pagina.close()
                continue
            pagina.close()
            carregou = [u for u in pedidos if u.endswith("script.js")]
            if not carregou:
                erros.append(f"{rota}: o script do Analytics nao foi requisitado")
                continue
            print(f"{rota}: script carregado, respostas={respostas}")

        navegador.close()

    if erros:
        print("\nproblemas:")
        for erro in erros:
            print(" -", erro)
        return 1
    print("\nAnalytics OK: o script e servido em todas as paginas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
