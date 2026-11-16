"""Verificacao dos links curtos do painel (?p=) e da compatibilidade legada.

A API e mockada via page.route: nao ha chamada de rede real.

Cobertura:
  - ?p=<token com prefixo C> abre o painel do criador;
  - ?p=<token com prefixo A> abre o painel do afiliado;
  - os links antigos (?token=, ?afiliado_token=, ?tipo=afiliado&token=) seguem
    funcionando;
  - a atribuicao por ?a=CODE continua registrando o afiliado;
  - a criacao de conta gera o link curto ?p= e atualiza a URL do navegador.

Uso:
    python3 tests/test-links-painel.py
"""

import http.server
import json
import socketserver
import threading
import time

from playwright.sync_api import sync_playwright

PORT = 8123
ROOT = "/home/user/Downloads/site"
API = "https://api.188.166.156.109.sslip.io"

TOKEN_CRIADOR = "C7KQ9XZ2M4P8R3TU"
TOKEN_AFILIADO = "A3R8Y6H1K5N9W2QS"

failures = []
checks = 0


def check(label, condition, detail=""):
    global checks
    checks += 1
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label} -> {detail}")
        failures.append(label)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):
        pass


def serve():
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def responder(page, requests, token_criador=TOKEN_CRIADOR, token_afiliado=TOKEN_AFILIADO):
    """MOCK da API: registra as chamadas e devolve respostas plausiveis."""

    def handler(route):
        url = route.request.url
        method = route.request.method
        requests.append(url)

        if method == "POST" and url.endswith("/creators"):
            body = {
                "ok": True,
                "creator": {"id": "1", "name": "Ana", "handle": "ana10", "code": "ANA10"},
                "token": token_criador,
            }
        elif method == "POST" and url.endswith("/hunters"):
            body = {
                "ok": True,
                "hunter": {"id": "2", "name": "Bia", "handle": "bia99", "code": "BIA99"},
                "afiliado": {"id": "2", "name": "Bia", "handle": "bia99", "code": "BIA99"},
                "token": token_afiliado,
            }
        elif "/creators/me" in url or "/hunters/me" in url:
            body = {"ok": False, "error": "token invalido (mock)"}
        elif url.endswith("/signup-guard"):
            body = {"ok": True, "allowed": True}
        else:
            body = {"ok": True}

        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(body),
        )

    page.route(f"{API}/**", handler)


def api_calls(requests, kind):
    return [u for u in requests if kind in u]


def abrir(page, query):
    requests = []
    responder(page, requests)
    page.goto(
        f"http://127.0.0.1:{PORT}/afiliados/index.html{query}",
        wait_until="domcontentloaded",
    )
    page.wait_for_timeout(900)
    return requests


def main():
    httpd = serve()
    time.sleep(0.4)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()

        print("\n[Link curto do painel]")
        reqs = abrir(page, f"?p={TOKEN_CRIADOR}")
        calls = api_calls(reqs, "/creators/me")
        check(
            "?p=C... abre o painel do criador",
            len(calls) == 1 and calls[0].endswith(f"/creators/me?token={TOKEN_CRIADOR}"),
            str(reqs),
        )
        check("?p=C... nao chama /hunters/me", not api_calls(reqs, "/hunters/me"), str(reqs))

        reqs = abrir(page, f"?p={TOKEN_AFILIADO}")
        calls = api_calls(reqs, "/hunters/me")
        check(
            "?p=A... abre o painel do afiliado",
            len(calls) == 1 and calls[0].endswith(f"/hunters/me?token={TOKEN_AFILIADO}"),
            str(reqs),
        )
        check("?p=A... nao chama /creators/me", not api_calls(reqs, "/creators/me"), str(reqs))

        print("\n[Token sem prefixo (VPS antiga)]")
        reqs = abrir(page, "?p=8f3a9c1d2e4b6a8c")
        calls = api_calls(reqs, "/creators/me")
        check(
            "token sem prefixo tenta primeiro o painel do criador",
            len(calls) == 1,
            str(reqs),
        )

        print("\n[Links antigos continuam funcionando]")
        reqs = abrir(page, "?token=8f3a9c1d2e4b6a8c")
        calls = api_calls(reqs, "/creators/me")
        check(
            "?token= legado abre o painel do criador",
            len(calls) == 1 and calls[0].endswith("/creators/me?token=8f3a9c1d2e4b6a8c"),
            str(reqs),
        )

        reqs = abrir(page, "?afiliado_token=8f3a9c1d2e4b6a8c")
        calls = api_calls(reqs, "/hunters/me")
        check(
            "?afiliado_token= legado abre o painel do afiliado",
            len(calls) == 1 and calls[0].endswith("/hunters/me?token=8f3a9c1d2e4b6a8c"),
            str(reqs),
        )

        reqs = abrir(page, "?tipo=afiliado&token=8f3a9c1d2e4b6a8c")
        calls = api_calls(reqs, "/hunters/me")
        check(
            "?tipo=afiliado&token= legado abre o painel do afiliado",
            len(calls) == 1 and calls[0].endswith("/hunters/me?token=8f3a9c1d2e4b6a8c"),
            str(reqs),
        )

        print("\n[Atribuicao por link de afiliado]")
        abrir(page, "?a=ABC123")
        stored = page.evaluate(
            "() => localStorage.getItem('vizin.os.afiliado.v1')"
            " || localStorage.getItem('vizin-os.afiliado.v1')"
        )
        check("?a=CODE ainda registra a atribuicao", "ABC123" in (stored or ""), str(stored))

        print("\n[Criacao de conta]")
        requests = []
        responder(page, requests)
        page.goto(
            f"http://127.0.0.1:{PORT}/afiliados/index.html",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(700)
        page.click('[data-open-create="creator"]')
        page.wait_for_timeout(400)
        page.fill("#code", "ANA10")
        page.click("#createButton")
        page.wait_for_timeout(900)

        href = page.get_attribute("#dashboardLink", "href") or ""
        check(
            "criacao de criador gera o link curto ?p=",
            href.endswith(f"/afiliados?p={TOKEN_CRIADOR}"),
            href,
        )
        check(
            "URL da barra de enderecos tambem fica curta",
            f"?p={TOKEN_CRIADOR}" in (page.url or ""),
            page.url,
        )
        check(
            "token do link tem 16 caracteres",
            len(href.split("?p=")[-1]) == 16,
            href,
        )

        legado = href.split("?p=")[0] + "?afiliado_token=" + "a" * 48
        check(
            "link curto e bem mais curto que o legado",
            len(href) < len(legado),
            f"novo={len(href)} legado={len(legado)}: {href}",
        )

        browser.close()

    httpd.shutdown()
    print(f"\n{checks - len(failures)}/{checks} verificacoes OK")
    if failures:
        print("FALHAS: " + ", ".join(failures))
        raise SystemExit(1)
    print("Links do painel OK")


if __name__ == "__main__":
    main()
