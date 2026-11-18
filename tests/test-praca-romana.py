"""
Praça Romana no navegador de verdade: cadastro, publicação, voto,
comentário, a aba de implementadas e o selo 'adm' da conta de
administração — contra a API local.

Uso: python3 site/tests/test-praca-romana.py --api http://127.0.0.1:8797
"""
import argparse
import json
import os
import sys
import time
import threading
import http.server
import functools
import socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = {"api": None}

PAGES = {
    "/praca-romana": "praca-romana.html",
    "/": "index.html",
}

# config.js só aceita override em https:// (por design, em produção). No teste
# local a API roda em http://127.0.0.1, então o servidor de arquivos entrega
# uma config já apontada para ela — o código do site não é alterado.
CONFIG_LOCAL = """
window.VIZINHANCA_CONFIG = Object.freeze({
  siteUrl: 'http://local',
  apiUrl: '%(api)s',
  androidUrl: 'https://play.google.com/store/apps/details?id=dev.vizinhoos.app',
  iosUrl: '',
  contactEmail: 'vizin.oos@gmail.com',
});
"""


def servir_site(port):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=ROOT, **kwargs)

        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.split("?")[0] == "/assets/config.js" and ARGS["api"]:
                corpo = (CONFIG_LOCAL % {"api": ARGS["api"]}).encode("utf-8")
                self.send_response(200)
                self.send_header("content-type", "application/javascript")
                self.send_header("content-length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
                return
            http.server.SimpleHTTPRequestHandler.do_GET(self)

        def translate_path(self, path):
            clean = path.split("?")[0].split("#")[0]
            if clean in PAGES:
                clean = "/" + PAGES[clean]
            return super().translate_path(clean)

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def requests_post(url, corpo, token=None):
    import urllib.request

    dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(url, data=dados, method="POST")
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=15) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8797")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    ARGS["api"] = args.api

    httpd = servir_site(args.port)
    base = f"http://127.0.0.1:{args.port}"
    url = f"{base}/praca-romana"

    from playwright.sync_api import sync_playwright

    falhas = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        erros = []
        page.on("pageerror", lambda e: erros.append(str(e)))

        def esperar_fechado(seletor, ms):
            page.wait_for_function(
                "(sel) => document.querySelector(sel)?.hasAttribute('hidden')",
                arg=seletor,
                timeout=ms,
            )

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(800)
        if os.environ.get("PRACA_DEBUG"):
            print("DEBUG list:", page.eval_on_selector("#praca-list", "e => e.innerHTML")[:500])
            print("DEBUG console erros:", erros)

        # 1. estado vazio: a página explica que a praça espera a primeira fala
        page.wait_for_selector(".praca-empty", timeout=15000)
        if "falta a primeira fala" not in page.inner_text(".praca-empty"):
            falhas.append("estado vazio inesperado")
        if page.locator(".praca-post").count() != 0:
            falhas.append("há cartões de proposta com a lista vazia")

        # 2. criar conta pelo modal (a página abre a conta ao pedir proposta)
        page.click("#praca-new-btn")
        page.wait_for_selector("#praca-auth-modal:not([hidden])", timeout=5000)
        page.click('.praca-auth-switch button[data-auth-mode="register"]')
        apelido = "testadora" + str(int(time.time()))[-6:]
        page.fill("#praca-auth-user", apelido)
        page.fill("#praca-auth-pass", "senha-segura-123")
        # a senha pode ser vista no momento da criação
        page.click("#praca-pass-toggle")
        if page.get_attribute("#praca-auth-pass", "type") != "text":
            falhas.append("o botão mostrar senha não funciona")
        page.click("#praca-pass-toggle")
        if page.get_attribute("#praca-auth-pass", "type") != "password":
            falhas.append("o botão ocultar senha não funciona")
        page.click("#praca-auth-submit")
        esperar_fechado("#praca-auth-modal", 15000)
        page.wait_for_selector("#praca-account-btn:not([hidden])", timeout=5000)
        if "@" + apelido not in page.inner_text("#praca-account-btn"):
            falhas.append("o chip da conta não mostra o apelido")

        # 3. publicar uma proposta
        page.wait_for_selector("#praca-new-modal:not([hidden])", timeout=10000)
        page.fill("#praca-new-title", "Filtro por categoria nos encontros")
        page.select_option("#praca-new-tag", "melhoria")
        page.fill(
            "#praca-new-body",
            "Quero filtrar os encontros por categoria e horário para achar o rolê da semana.",
        )
        page.click("#praca-new-submit")
        page.wait_for_selector(".praca-post", timeout=15000)
        if page.locator(".praca-post").count() != 1:
            falhas.append("esperava 1 proposta na lista")
        if "Filtro por categoria" not in page.inner_text(".praca-post-title"):
            falhas.append("a proposta publicada não apareceu na lista")

        # 4. o menu de ordenação é customizado e troca a lista
        page.click("#praca-sort-btn")
        page.wait_for_selector("#praca-sort-list:not([hidden])", timeout=5000)
        if page.get_attribute("#praca-sort-btn", "aria-expanded") != "true":
            falhas.append("o menu de ordenação não abriu")
        page.click('.praca-menu-option[data-sort="new"]')
        esperar_fechado("#praca-sort-list", 5000)
        if "Mais recentes" not in page.inner_text("#praca-sort-label"):
            falhas.append("o rótulo do menu de ordenação não acompanhou a escolha")

        # 5. votos e comentário
        page.click('.praca-post .praca-vote-btn[data-vote="1"]')
        page.wait_for_function(
            "() => document.querySelector('.praca-post .praca-score')?.textContent === '1'",
            timeout=10000,
        )
        if page.get_attribute('.praca-post [data-vote="1"]', "aria-pressed") != "true":
            falhas.append("o voto não ficou marcado")

        page.click(".praca-post .praca-post-title")
        page.wait_for_selector("#praca-detail-modal:not([hidden])", timeout=10000)
        page.fill("#praca-comment-input", "Concordo demais, isso facilitaria o uso.")
        page.click('.praca-comment-form button[type="submit"]')
        page.wait_for_selector(".praca-comment", timeout=10000)
        if "Concordo demais" not in page.inner_text(".praca-comment-body"):
            falhas.append("o comentário não apareceu")
        page.click("#praca-detail-modal button.modal-close")
        esperar_fechado("#praca-detail-modal", 5000)

        # 6. a aba de implementadas mostra a proposta marcada pelo painel
        resposta = requests_post(
            f"{args.api}/forum/admin/status",
            {
                "post_id": page.locator(".praca-post").first.get_attribute("data-id"),
                "status": "done",
                "note": "Teste automatizado",
            },
            token="token-de-admin",
        )
        if resposta.get("ok") is not True:
            falhas.append(f"o painel não marcou a proposta: {resposta}")
        page.click('.praca-tab[data-tab="done"]')
        page.wait_for_selector(".praca-badge-done", timeout=10000)
        if "Implementada" not in page.inner_text(".praca-badge-done"):
            falhas.append("a aba de implementadas não mostrou o selo")

        # 7. voltar para a aba de discussão: a proposta implementada sai de lá
        page.click('.praca-tab[data-tab="open"]')
        page.wait_for_function(
            "() => !document.querySelector('.praca-post-title')?.textContent.includes('Filtro por categoria')",
            timeout=10000,
        )

        # 7b. conta de administracao: entra e recebe o selo 'adm'
        page.click("#praca-account-btn")
        page.wait_for_selector("#praca-auth-modal:not([hidden])", timeout=5000)
        page.click("#praca-logout-btn")
        esperar_fechado("#praca-auth-modal", 5000)
        page.click("#praca-new-btn")
        page.wait_for_selector("#praca-auth-modal:not([hidden])", timeout=5000)
        page.fill("#praca-auth-user", "maidsupremacy")
        page.fill("#praca-auth-pass", "maid-supremacia")
        page.click("#praca-auth-submit")
        esperar_fechado("#praca-auth-modal", 15000)
        page.wait_for_selector("#praca-account-btn .praca-badge-adm", timeout=5000)
        if "adm" not in page.inner_text("#praca-account-btn"):
            falhas.append("o chip da conta de administracao nao mostra o selo 'adm'")

        # 7c. a administracao publica e o selo aparece na lista e no detalhe
        page.wait_for_selector("#praca-new-modal:not([hidden])", timeout=10000)
        page.fill("#praca-new-title", "Nota oficial da administracao da praca")
        page.select_option("#praca-new-tag", "ideia")
        page.fill(
            "#praca-new-body",
            "Mensagem de teste publicada pela conta de administracao da Praca Romana.",
        )
        page.click("#praca-new-submit")
        page.wait_for_selector(".praca-post", timeout=15000)
        alvo = page.locator(".praca-post", has_text="Nota oficial").first
        if alvo.count() != 1:
            falhas.append("a proposta da administracao nao apareceu na lista")
        else:
            if not alvo.locator(".praca-badge-adm").count():
                falhas.append("o selo 'adm' nao aparece no cartao da proposta")
            alvo.locator(".praca-post-title").click()
            page.wait_for_selector("#praca-detail-modal:not([hidden])", timeout=10000)
            if not page.locator("#praca-detail-content .praca-badge-adm").count():
                falhas.append("o selo 'adm' nao aparece no detalhe da proposta")
            page.click("#praca-detail-modal button.modal-close")
            esperar_fechado("#praca-detail-modal", 5000)

        # 8. rodapé com atalho para a página
        page.goto(f"{base}/", wait_until="domcontentloaded")
        if page.locator('a.explore-card[href="/praca-romana"]').count() != 1:
            falhas.append("o atalho da Praça Romana não está no rodapé da home")
        if page.locator('a[href="/praca-romana"].btn').count() != 1:
            falhas.append("a home não fala da Praça Romana na seção nova")

        browser.close()

    if erros:
        falhas.append("erros de JS no console: " + " | ".join(erros[:5]))

    httpd.shutdown()
    if falhas:
        print("FALHOU:")
        for item in falhas:
            print(" -", item)
        sys.exit(1)
    print("Praça Romana: tudo certo no navegador de verdade.")


if __name__ == "__main__":
    main()
