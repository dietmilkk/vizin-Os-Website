"""Teste do bloqueio por IP do programa de parceiros.

Confere o comportamento no navegador:
- IP de datacenter/VPN (ou fora do Brasil): a pagina nao carrega e vai para 404;
- IP que ja criou conta: a pagina abre e o aviso aparece dentro da janela;
- painel ja aberto (com token): nunca redireciona, mesmo com IP bloqueado.

O backend e simulado com `page.route` para nao depender do IP real da maquina.

Uso:
    python3 tests/test-guard-ip.py
"""

import sys

from playwright.sync_api import sync_playwright

from lib.primeiro_acesso import ja_visitou

BASE = "http://localhost:8099"
API = "https://api.188.166.156.109.sslip.io"

failures = []
checks = 0


def check(label, condition, detail=""):
    global checks
    checks += 1
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}" + (f" -> {detail}" if detail else ""))
        failures.append(label)


def mock_guard(page, payload):
    """Intercepta GET /signup-guard e devolve o payload definido."""

    def handler(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=payload,
        )

    page.route(f"{API}/signup-guard", handler)


def test_bloqueio_redireciona_404(page):
    print("\n[IP bloqueado] datacenter/VPN/fora do pais -> 404")
    mock_guard(
        page,
        '{"ok":true,"allowed":false,"blocked":true,"reason":"IP_DENIED",'
        '"message":"Este acesso nao esta disponivel."}',
    )
    page.goto(f"{BASE}/afiliados/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    check("redireciona para 404.html", "/404.html" in page.url, page.url)
    check("nao mostra o conteudo da pagina", not page.locator("#createModal").is_visible())


def test_duplicado_avisa_na_janela(page):
    print("\n[IP duplicado] ja criou conta -> aviso na janela")
    mock_guard(
        page,
        '{"ok":true,"allowed":false,"blocked":false,"reason":"IP_BLOCKED_DUPLICATE",'
        '"message":"Voce ja criou uma conta. Se tentar novamente, ficara sem conta, '
        'sem mais nenhuma conta."}',
    )
    page.goto(f"{BASE}/afiliados/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    check("a pagina continua carregada", "/404.html" not in page.url, page.url)
    check("conteudo visivel", page.locator("main").first.is_visible())

    page.locator("[data-open-create]").first.click()
    page.wait_for_timeout(600)
    warning = page.locator("#createWarning")
    check("janela de criacao abriu", page.locator("#createModal").is_visible())
    check("aviso visivel dentro da janela", warning.is_visible())
    text = warning.inner_text().strip()
    check(
        "aviso com o texto do usuario",
        "já criou uma conta" in text or "ja criou uma conta" in text,
        text,
    )
    check(
        "aviso e pequeno (nao ocupa a janela inteira)",
        warning.bounding_box()["height"] < 160,
        str(warning.bounding_box()),
    )


def test_painel_com_token_nao_e_bloqueado(page):
    print("\n[Painel] com token nunca redireciona")
    mock_guard(
        page,
        '{"ok":true,"allowed":false,"blocked":true,"reason":"IP_DENIED",'
        '"message":"Este acesso nao esta disponivel."}',
    )
    page.goto(f"{BASE}/afiliados/?afiliado_token=token-de-teste", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    check("nao redireciona para 404", "/404.html" not in page.url, page.url)
    check("body visivel com token", page.locator("body").is_visible())


def test_api_sem_resposta_nao_trava(page):
    print("\n[API indisponivel] a pagina abre normalmente")

    def handler(route):
        route.abort()

    page.route(f"{API}/signup-guard", handler)
    page.goto(f"{BASE}/afiliados/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    check("nao redireciona para 404", "/404.html" not in page.url, page.url)
    check("conteudo visivel", page.locator("main").first.is_visible())


def main():
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        for test in (
            test_bloqueio_redireciona_404,
            test_duplicado_avisa_na_janela,
            test_painel_com_token_nao_e_bloqueado,
            test_api_sem_resposta_nao_trava,
        ):
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            ja_visitou(context)
            page = context.new_page()
            try:
                test(page)
            except Exception as error:  # noqa: BLE001
                check(f"{test.__name__} executou sem erro", False, str(error))
            finally:
                context.close()
        browser.close()

    print(f"\n{checks - len(failures)}/{checks} verificacoes passaram")
    if failures:
        print("Falhas:")
        for item in failures:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
