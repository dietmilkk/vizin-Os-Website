"""
Comunidade no navegador de verdade: cadastro, publicação, voto,
comentário e a aba de implementadas — contra a API local.

Uso: python3 site/tests/test-comunidade.py --api http://127.0.0.1:8791
"""
import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGS = {"api": None}

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

PAGES = {
    "/comunidade": "comunidade.html",
    "/": "index.html",
}


def servir_site(port):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=ROOT, **kwargs)

        def log_message(self, format, *args):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8791")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()
    ARGS["api"] = args.api

    httpd = servir_site(args.port)
    base = f"http://127.0.0.1:{args.port}"
    url = f"{base}/comunidade"

    from playwright.sync_api import sync_playwright

    falhas = []

    def esperar_fechado(seletor, ms):
        page.wait_for_function(
            "(sel) => document.querySelector(sel)?.hasAttribute('hidden')",
            arg=seletor,
            timeout=ms,
        )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        erros = []
        page.on("pageerror", lambda e: erros.append(str(e)))

        def erro_de_console(mensagem):
            # 404 local (analytics/_vercel, favicon): o recurso só existe na
            # Vercel; no servidor local não há o que servir. Erro de JS a gente
            # já pega pelo pageerror.
            texto = mensagem.text
            if "http://" in texto and "404" in texto:
                return
            if "Failed to load resource" in texto:
                return
            if mensagem.type == "error" and "ERR_FAILED" in texto:
                erros.append(texto)

        page.on("console", erro_de_console)

        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(800)
        if os.environ.get("COMUNIDADE_DEBUG"):
            print("DEBUG list:", page.eval_on_selector("#comunidade-list", "e => e.innerHTML")[:600])
            print("DEBUG banner:", page.eval_on_selector("#comunidade-banner", "e => e.innerText"))
            print("DEBUG console erros:", erros)

        # 1. estado vazio: a página explica que a comunidade espera a primeira fala
        page.wait_for_selector(".comunidade-empty", timeout=15000)
        vazio = page.inner_text(".comunidade-empty")
        if "falta a primeira fala" not in vazio:
            falhas.append(f"estado vazio inesperado: {vazio[:120]}")
        if page.locator(".comunidade-post").count() != 0:
            falhas.append("há cartões de proposta com a lista vazia")

        # 2. criar conta pelo modal (a página abre a conta ao pedir proposta)
        page.click("#comunidade-new-btn")
        page.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
        page.click('.comunidade-auth-switch button[data-auth-mode="register"]')
        apelido = "testadora" + str(int(time.time()))[-6:]
        page.fill("#comunidade-auth-user", apelido)
        page.fill("#comunidade-auth-pass", "senha-segura-123")
        # a senha pode ser vista no momento da criação
        page.click("#comunidade-pass-toggle")
        tipo = page.get_attribute("#comunidade-auth-pass", "type")
        if tipo != "text":
            falhas.append(f"o botão mostrar senha não funciona (type={tipo})")
        page.click("#comunidade-pass-toggle")
        if page.get_attribute("#comunidade-auth-pass", "type") != "password":
            falhas.append("o botão ocultar senha não funciona")
        page.click("#comunidade-auth-submit")
        esperar_fechado("#comunidade-auth-modal", 15000)
        # conta aberta: o chip da conta aparece
        page.wait_for_selector("#comunidade-account-btn:not([hidden])", timeout=5000)
        if "@" + apelido not in page.inner_text("#comunidade-account-btn"):
            falhas.append("o chip da conta não mostra o apelido")

        # 3. publicar uma proposta
        page.wait_for_selector("#comunidade-new-modal:not([hidden])", timeout=10000)
        page.fill("#comunidade-new-title", "Filtro por categoria nos encontros")
        # O campo de tag e um menu customizado (igual ao de ordenacao): o
        # valor real fica no input escondido e o botao abre a lista.
        page.click("#comunidade-new-tag-btn")
        page.wait_for_selector("#comunidade-new-tag-list:not([hidden])", timeout=5000)
        page.click('#comunidade-new-tag-list .comunidade-menu-option[data-tag="melhoria"]')
        page.wait_for_function(
            "() => document.getElementById('comunidade-new-tag').value === 'melhoria'",
            timeout=5000,
        )
        page.fill(
            "#comunidade-new-body",
            "Quero filtrar os encontros por categoria e horário para achar o rolê da semana.",
        )
        page.click("#comunidade-new-submit")
        page.wait_for_selector(".comunidade-post", timeout=15000)
        cartoes = page.locator(".comunidade-post").count()
        if cartoes != 1:
            falhas.append(f"esperava 1 proposta na lista, achei {cartoes}")
        if "Filtro por categoria" not in page.inner_text(".comunidade-post-title"):
            falhas.append("a proposta publicada não apareceu na lista")

        # 4. o menu de ordenação é customizado e troca a lista
        page.click("#comunidade-sort-btn")
        page.wait_for_selector("#comunidade-sort-list:not([hidden])", timeout=5000)
        if page.get_attribute("#comunidade-sort-btn", "aria-expanded") != "true":
            falhas.append("o menu de ordenação não abriu")
        page.click('.comunidade-menu-option[data-sort="new"]')
        esperar_fechado("#comunidade-sort-list", 5000)
        if "Mais recentes" not in page.inner_text("#comunidade-sort-label"):
            falhas.append("o rótulo do menu de ordenação não acompanhou a escolha")

        # 5. votos e comentário
        page.click('.comunidade-post .comunidade-vote-btn[data-vote="1"]')
        page.wait_for_function(
            "() => document.querySelector('.comunidade-post .comunidade-score')?.textContent === '1'",
            timeout=10000,
        )
        if page.get_attribute('.comunidade-post [data-vote="1"]', "aria-pressed") != "true":
            falhas.append("o voto não ficou marcado")

        page.click(".comunidade-post .comunidade-post-title")
        page.wait_for_selector("#comunidade-detail-modal:not([hidden])", timeout=10000)
        page.fill("#comunidade-comment-input", "Concordo demais, isso facilitaria o uso.")
        page.click('.comunidade-comment-form button[type="submit"]')
        page.wait_for_selector(".comunidade-comment", timeout=10000)
        if "Concordo demais" not in page.inner_text(".comunidade-comment-body"):
            falhas.append("o comentário não apareceu")
        page.click("#comunidade-detail-modal button.modal-close")
        esperar_fechado("#comunidade-detail-modal", 5000)

        # 6. a aba de implementadas mostra a proposta marcada pelo painel
        resposta = requests_post(
            f"{args.api}/forum/admin/status",
            {
                "post_id": page.locator(".comunidade-post").first.get_attribute("data-id"),
                "status": "done",
                "note": "Teste automatizado",
            },
            token="token-de-admin",
        )
        if resposta.get("ok") is not True:
            falhas.append(f"o painel não marcou a proposta: {resposta}")
        page.click('.comunidade-tab[data-tab="done"]')
        page.wait_for_selector(".comunidade-badge-done", timeout=10000)
        if "Implementada" not in page.inner_text(".comunidade-badge-done"):
            falhas.append("a aba de implementadas não mostrou o selo")

        # 7. voltar para a aba de discussão: a proposta implementada sai de lá
        page.click('.comunidade-tab[data-tab="open"]')
        page.wait_for_function(
            "() => !document.querySelector('.comunidade-post-title')?.textContent.includes('Filtro por categoria')",
            timeout=10000,
        )

        # 7b. conta de administração: entra e recebe o selo "adm"
        page.click("#comunidade-account-btn")
        page.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
        page.click("#comunidade-logout-btn")
        esperar_fechado("#comunidade-auth-modal", 5000)
        page.click("#comunidade-new-btn")
        page.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
        # o modal reabre em 'Criar conta' se a ultima visita foi de cadastro:
        # um usuário real clicaria em 'Entrar'. O logout já devolve o modo
        # 'Entrar' — aqui garantimos o clique como dupla proteção.
        if page.locator('.comunidade-auth-switch button[data-auth-mode="login"]').get_attribute("class"):
            pass
        page.click('.comunidade-auth-switch button[data-auth-mode="login"]')
        page.fill("#comunidade-auth-user", "maidsupremacy")
        page.fill("#comunidade-auth-pass", "maid-supremacia")
        page.click("#comunidade-auth-submit")
        try:
            esperar_fechado("#comunidade-auth-modal", 15000)
        except Exception:
            print("DEBUG erro do modal:", page.locator("#comunidade-auth-error").inner_text())
            print("DEBUG chip:", page.evaluate("document.querySelector('#comunidade-account-btn')?.innerText"))
            print("DEBUG localStorage:", page.evaluate("window.localStorage.getItem('vizin.os.comunidade.v1')"))
            raise
        page.wait_for_selector("#comunidade-account-btn .comunidade-badge-adm", timeout=5000)
        if "adm" not in page.inner_text("#comunidade-account-btn").lower():
            falhas.append("o chip da conta de administracao nao mostra o selo 'adm'")

        # 7c. a administração publica e o selo aparece na lista e no detalhe
        page.wait_for_selector("#comunidade-new-modal:not([hidden])", timeout=10000)
        page.fill("#comunidade-new-title", "Nota oficial da administração da comunidade")
        page.click("#comunidade-new-tag-btn")
        page.wait_for_selector("#comunidade-new-tag-list:not([hidden])", timeout=5000)
        page.click('#comunidade-new-tag-list .comunidade-menu-option[data-tag="ideia"]')
        page.wait_for_function(
            "() => document.getElementById('comunidade-new-tag').value === 'ideia'",
            timeout=5000,
        )
        page.fill(
            "#comunidade-new-body",
            "Mensagem de teste publicada pela conta de administração da Comunidade.",
        )
        page.click("#comunidade-new-submit")
        page.wait_for_selector(".comunidade-post", timeout=15000)
        cartao = page.locator('.comunidade-post-title', has_text="Nota oficial").first
        if cartao.count() != 1:
            falhas.append("a proposta da administração não apareceu na lista")
        else:
            alvo = page.locator(".comunidade-post", has_text="Nota oficial").first
            if not alvo.locator(".comunidade-badge-adm").count():
                falhas.append("o selo 'adm' não aparece no cartão da proposta")
            alvo.locator(".comunidade-post-title").click()
            page.wait_for_selector("#comunidade-detail-modal:not([hidden])", timeout=10000)
            if not page.locator("#comunidade-detail-content .comunidade-badge-adm").count():
                falhas.append("o selo 'adm' não aparece no detalhe da proposta")
            page.click("#comunidade-detail-modal button.modal-close")
            esperar_fechado("#comunidade-detail-modal", 5000)

        # 8. rodapé com atalho para a página
        page.goto(f"{base}/", wait_until="domcontentloaded")
        if page.locator('a.explore-card[href="/comunidade"]').count() != 1:
            falhas.append("o atalho da Comunidade não está no rodapé da home")
        if page.locator('a[href="/comunidade"].btn').count() != 1:
            falhas.append("a home não fala da Comunidade na seção nova")

        browser.close()

    if erros:
        falhas.append("erros de JS no console: " + " | ".join(erros[:5]))

    httpd.shutdown()
    if falhas:
        print("FALHOU:")
        for item in falhas:
            print(" -", item)
        sys.exit(1)
    print("Comunidade: tudo certo no navegador de verdade.")


def requests_post(url, corpo, token=None):
    import urllib.request

    dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(url, data=dados, method="POST")
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=15) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


if __name__ == "__main__":
    main()
