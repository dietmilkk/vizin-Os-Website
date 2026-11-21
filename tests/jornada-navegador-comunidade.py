"""
Jornada real no navegador: duas pessoas usando a Comunidade de verdade.
Ana descobre a página, cria conta, publica e volta depois pra ver os votos.
Bruno entra, vota e comenta. A administração responde com o selo e marca
a proposta como implementada. Ana vê tudo refletido na página.
"""
import http.server
import socketserver
import threading

SITE = "/home/user/Downloads/app/site"
PAGES = {"/comunidade": "comunidade.html", "/": "index.html"}
import sys

API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8820"
CONFIG = """
window.VIZINHANCA_CONFIG = Object.freeze({
  siteUrl: 'http://local',
  apiUrl: '%(api)s',
  androidUrl: '', iosUrl: '', contactEmail: 'a@b.c',
});
"""


def servir(port):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=SITE, **k)

        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path.split("?")[0] == "/assets/config.js":
                corpo = (CONFIG % {"api": API_URL}).encode()
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


httpd = servir(9061)
falhas = []

from playwright.sync_api import sync_playwright


def oculto(page, sel):
    return page.evaluate(f"document.querySelector('{sel}')?.hasAttribute('hidden')")


with sync_playwright() as p:
    browser = p.chromium.launch()

    # ============ ANA: primeira visita ============
    ana = browser.new_page(viewport={"width": 1280, "height": 900})
    erros_ana = []
    ana.on("pageerror", lambda e: erros_ana.append(str(e)[:150]))
    ana.goto("http://127.0.0.1:9061/comunidade", wait_until="networkidle")
    ana.wait_for_selector(".comunidade-empty", timeout=15000)
    if "falta a primeira fala" not in ana.inner_text(".comunidade-empty"):
        falhas.append("Ana não viu o estado vazio")

    # Ana clica em Nova proposta -> cadastro
    ana.click("#comunidade-new-btn")
    ana.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
    # Ana erra o apelido de propósito e vê o erro
    ana.click('.comunidade-auth-switch button[data-auth-mode="register"]')
    ana.fill("#comunidade-auth-user", "a")
    ana.fill("#comunidade-auth-pass", "curta")
    ana.click("#comunidade-auth-submit")
    erro = ana.inner_text("#comunidade-auth-error")
    if "apelido" not in erro.lower() and "inválido" not in erro.lower():
        falhas.append(f"Ana não viu erro de apelido inválido: '{erro}'")
    # Ana digita certo, olha a senha e entra
    ana.fill("#comunidade-auth-user", "ana.souza")
    ana.fill("#comunidade-auth-pass", "senha-segura-123")
    ana.click("#comunidade-pass-toggle")
    if ana.get_attribute("#comunidade-auth-pass", "type") != "text":
        falhas.append("Ana não conseguiu ver a senha")
    ana.click("#comunidade-auth-submit")
    ana.wait_for_function(
        "() => document.querySelector('#comunidade-auth-modal').hasAttribute('hidden')", timeout=15000
    )
    if "@ana.souza" not in ana.inner_text("#comunidade-account-btn"):
        falhas.append("chip da conta não apareceu para a Ana")

    # publica a proposta
    ana.wait_for_selector("#comunidade-new-modal:not([hidden])", timeout=10000)
    ana.fill("#comunidade-new-title", "Bancos com mais sombra na praça")
    ana.select_option("#comunidade-new-tag", "melhoria")
    ana.fill("#comunidade-new-body", "Os bancos da praça central pegam sol o dia todo. Sugestão: mapear com o grupo quais pontos precisam de sombra e sugerir à prefeitura.")
    ana.click("#comunidade-new-submit")
    ana.wait_for_selector(".comunidade-post", timeout=15000)
    if "Bancos com mais sombra" not in ana.inner_text(".comunidade-post-title"):
        falhas.append("Ana não viu a própria proposta na lista")

    # fecha o modal de nova proposta (fica aberto após publicar? não — fecha sozinho)
    ana.keyboard.press("Escape")
    ana.wait_for_timeout(400)

    # ============ BRUNO: descobre e participa ============
    bruno = browser.new_page(viewport={"width": 1280, "height": 900})
    bruno.goto("http://127.0.0.1:9061/comunidade", wait_until="networkidle")
    bruno.wait_for_selector(".comunidade-post", timeout=15000)

    # Bruno vota sem conta -> o modal de conta abre
    bruno.click('.comunidade-post .comunidade-vote-btn[data-vote="1"]')
    bruno.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
    bruno.click('.comunidade-auth-switch button[data-auth-mode="register"]')
    bruno.fill("#comunidade-auth-user", "bruno-lima")
    bruno.fill("#comunidade-auth-pass", "senha-segura-123")
    bruno.click("#comunidade-auth-submit")
    bruno.wait_for_function(
        "() => document.querySelector('#comunidade-auth-modal').hasAttribute('hidden')", timeout=15000
    )
    # o voto pendente é registrado automaticamente após o login
    bruno.wait_for_function(
        "() => document.querySelector('.comunidade-post .comunidade-score')?.textContent === '1'",
        timeout=10000,
    )

    # Bruno abre a proposta e comenta
    bruno.click(".comunidade-post .comunidade-post-title")
    bruno.wait_for_selector("#comunidade-detail-modal:not([hidden])", timeout=10000)
    bruno.fill("#comunidade-comment-input", "Apoio! O ponto em frente ao mercado é o pior.")
    bruno.click('.comunidade-comment-form button[type="submit"]')
    bruno.wait_for_selector(".comunidade-comment", timeout=10000)

    # Bruno filtra por tag e usa o menu de ordenação
    bruno.click("#comunidade-detail-modal button.modal-close")
    bruno.wait_for_function(
        "() => document.querySelector('#comunidade-detail-modal').hasAttribute('hidden')", timeout=5000
    )
    bruno.click('.comunidade-tag-chip[data-tag="melhoria"]')
    bruno.wait_for_timeout(800)
    bruno.click("#comunidade-sort-btn")
    bruno.wait_for_selector("#comunidade-sort-list:not([hidden])", timeout=5000)
    bruno.click('.comunidade-menu-option[data-sort="new"]')
    bruno.wait_for_timeout(500)

    # ============ A ADMINISTRAÇÃO RESPONDE ============
    # o login da administração abre o modal de nova proposta (a ação pendente
    # do clique em "Nova proposta"); fechamos para navegar até a conta
    ana.keyboard.press("Escape")
    ana.wait_for_timeout(400)
    ana.click("#comunidade-account-btn")
    ana.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
    ana.click("#comunidade-logout-btn")
    ana.wait_for_function(
        "() => document.querySelector('#comunidade-auth-modal').hasAttribute('hidden')", timeout=5000
    )
    ana.click("#comunidade-new-btn")
    ana.wait_for_selector("#comunidade-auth-modal:not([hidden])", timeout=5000)
    ana.click('.comunidade-auth-switch button[data-auth-mode="login"]')
    ana.fill("#comunidade-auth-user", "maidsupremacy")
    ana.fill("#comunidade-auth-pass", "maid-supremacia")
    ana.click("#comunidade-auth-submit")
    ana.wait_for_function(
        "() => document.querySelector('#comunidade-auth-modal').hasAttribute('hidden')", timeout=15000
    )
    if not ana.locator("#comunidade-account-btn .comunidade-badge-adm").count():
        falhas.append("selo ADM não apareceu no chip da administração")

    # o login reabriu o modal de nova proposta (ação pendente); fechamos para
    # abrir a proposta da lista
    ana.keyboard.press("Escape")
    ana.wait_for_function(
        "() => document.querySelector('#comunidade-new-modal').hasAttribute('hidden')", timeout=5000
    )

    # a administração abre a proposta e responde; a autoria é da Ana (conta
    # comum), então o selo na autoria não deve aparecer — só no comentário
    ana.click(".comunidade-post .comunidade-post-title")
    ana.wait_for_selector("#comunidade-detail-modal:not([hidden])", timeout=10000)
    if ana.locator("#comunidade-detail-content .comunidade-detail-head .comunidade-badge-adm").count():
        falhas.append("selo ADM indevido na autoria (proposta é da Ana, conta comum)")
    ana.fill("#comunidade-comment-input", "Resposta oficial: entraremos com o pedido à prefeitura e marco como implementada quando houver resposta.")
    ana.click('.comunidade-comment-form button[type="submit"]')
    # o detalhe é re-renderizado após o POST; esperamos o comentário da
    # administração aparecer COM o selo
    ana.wait_for_function(
        "() => { const c = [...document.querySelectorAll('#comunidade-detail-content .comunidade-comment-author')].find(a => a.textContent.includes('maidsupremacy')); return c && c.parentElement.querySelector('.comunidade-badge-adm'); }",
        timeout=10000,
    )
    if not ana.locator("#comunidade-detail-content .comunidade-badge-adm").count():
        falhas.append("selo ADM não apareceu no comentário da administração")
    ana.click("#comunidade-detail-modal button.modal-close")

    # ============ ANA (agora adm) implementa via painel e todos veem ============
    import json
    import urllib.request
    pid = bruno.evaluate("document.querySelector('.comunidade-post').getAttribute('data-id')")
    req = urllib.request.Request(
        (API_URL + "/forum/admin/status"), method="POST",
        data=json.dumps({"post_id": pid, "status": "done", "note": "Pedido encaminhado à prefeitura."}).encode(),
        headers={"content-type": "application/json", "authorization": "Bearer token-de-admin"},
    )
    json.loads(urllib.request.urlopen(req, timeout=10).read())

    # Bruno recarrega e vê a proposta na aba implementadas
    bruno.reload(wait_until="networkidle")
    bruno.click('.comunidade-tab[data-tab="done"]')
    bruno.wait_for_selector(".comunidade-badge-done", timeout=10000)
    if "Bancos com mais sombra" not in bruno.inner_text(".comunidade-post"):
        falhas.append("Bruno não viu a proposta na aba de implementadas")
    # Bruno abre o detalhe e vê a resposta oficial da administração com o selo
    bruno.click(".comunidade-post .comunidade-post-title")
    bruno.wait_for_selector("#comunidade-detail-modal:not([hidden])", timeout=10000)
    bruno.wait_for_selector("#comunidade-detail-content .comunidade-comment", timeout=10000)
    resposta = bruno.locator("#comunidade-detail-content .comunidade-comment").last
    if not resposta.locator(".comunidade-badge-adm").count():
        falhas.append("Bruno não viu o selo ADM na resposta oficial da administração")
    if not bruno.locator("#comunidade-detail-content .comunidade-detail-note").count():
        falhas.append("Bruno não viu a nota de implementada no detalhe")
    bruno.click("#comunidade-detail-modal button.modal-close")

    # Ana (sessão do adm) também vê na aba dela
    ana.click('.comunidade-tab[data-tab="done"]')
    ana.wait_for_selector(".comunidade-badge-done", timeout=10000)

    if erros_ana:
        falhas.append("erros de JS na sessão da Ana: " + " | ".join(erros_ana[:3]))

    browser.close()

httpd.shutdown()
if falhas:
    print("FALHOU:")
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("Jornada real no navegador: 100% OK (Ana, Bruno e a administração)")
