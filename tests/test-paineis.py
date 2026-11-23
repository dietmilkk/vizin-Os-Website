"""Teste rápido (Playwright) do painel web do Mod e do painel admin do PC.

- Mod: abre /mod, cola o token do Mod, confere métricas e saldo.
- Admin: abre o painel local (127.0.0.1:8899), cria um Mod, copia os blocos de
  texto com {link} substituído e confere as três abas.

Uso: python3 tests/test-paineis.py [token_mod]
"""
from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright

MOD_TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
API = "https://api.188.166.156.109.sslip.io"
SITE = "https://site.188.166.156.109.sslip.io"
ADMIN = "http://127.0.0.1:8899/"

falhas: list[str] = []
checks = 0


def cpf_valido(base: int) -> str:
    """CPF de 11 dígitos com dígitos verificadores corretos (único por execução)."""
    digitos = [int(d) for d in f"{base:09d}"[:9]]

    def dv(dig: list[int], peso_inicial: int) -> int:
        soma = sum(d * (peso_inicial - i) for i, d in enumerate(dig))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    digitos.append(dv(digitos, 10))
    digitos.append(dv(digitos, 11))
    return "".join(str(d) for d in digitos)


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global checks
    checks += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def main() -> int:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1360, "height": 900})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))

        # ---------------- painel web do Mod ----------------
        print("\n[site] painel do Mod")
        pagina.goto(f"{SITE}/mod", wait_until="load")
        check("abre /mod", pagina.locator("#mod-token-form").count() == 1)
        if MOD_TOKEN:
            pagina.fill("#mod-token", MOD_TOKEN)
            pagina.click("#mod-token-submit")
            pagina.wait_for_timeout(2500)
            check("abre o painel com o token", pagina.locator("#mod-token-form").is_hidden())
            check("dashboard do mod aparece", pagina.locator("#mod-dashboard").is_visible())
            check("mostra volume da rede", pagina.inner_text("#mod-volume").strip() not in ("", "—"))
            check("mostra ganhos", pagina.inner_text("#mod-earnings").strip() not in ("", "—"))
            check("mostra saldo", pagina.inner_text("#mod-available").strip() not in ("", "—"))
            check("mostra número de afiliados", pagina.inner_text("#mod-affiliates").strip() not in ("", "—"))
            check("tem botão de saque", pagina.locator("#mod-withdraw-button").is_visible())

        # ---------------- painel admin do PC ----------------
        print("\n[pc] painel admin unificado")
        pagina.goto(ADMIN, wait_until="load")
        check("carrega o painel", pagina.locator("nav button[data-tab='mods']").count() == 1)
        check("tem 3 abas", pagina.locator("nav button").count() == 3)
        check("aba de moderação existe", pagina.locator("#tab-moderacao").count() == 1)
        check("aba de e-mail existe", pagina.locator("#tab-email").count() == 1)

        # templates: auto-save + {link}
        pagina.fill("#tpl-mod", "Painel do mod: {link}")
        pagina.wait_for_timeout(900)
        pagina.fill("#tpl-share", "Link de afiliado: {link}")
        pagina.wait_for_timeout(900)
        check("template do mod salvo", "Painel do mod" in pagina.input_value("#tpl-mod"))

        # cria um mod (único por execução; o painel admin pede só o Handle)
        marca = str(int(time.time()))[-7:]
        pagina.fill("#mod-handle", f"mod_ui_{marca}")
        pagina.click("#mod-create")
        pagina.wait_for_timeout(2500)
        link_mod = pagina.inner_text("#mod-panel-link").strip() if pagina.locator("#mod-panel-link").is_visible() else ""
        link_share = pagina.inner_text("#mod-share-link").strip() if pagina.locator("#mod-share-link").is_visible() else ""
        codigo_mod = link_mod.rsplit("/", 1)[-1]
        codigo_share = link_share.rsplit("/", 1)[-1]
        check(
            "criou o mod com link numérico",
            len(codigo_mod) == 11 and codigo_mod.isdigit() and codigo_mod.startswith("1"),
            link_mod,
        )
        check(
            "link de afiliado começa com 2",
            len(codigo_share) == 11 and codigo_share.isdigit() and codigo_share.startswith("2")
            and codigo_share[1:] == codigo_mod[1:],
            link_share,
        )

        # copiar substitui {link}
        pagina.evaluate(
            """() => { window.__copied = ''; navigator.clipboard.writeText = async (t) => { window.__copied = t; }; }"""
        )
        pagina.click("#copy-mod")
        pagina.wait_for_timeout(400)
        copiado = pagina.evaluate("() => window.__copied")
        check("copiar substitui {link} pelo link do painel", bool(copiado) and "{link}" not in copiado and link_mod in copiado, copiado)
        pagina.click("#copy-share")
        pagina.wait_for_timeout(400)
        copiado2 = pagina.evaluate("() => window.__copied")
        check("copiar usa o link de compartilhamento", bool(copiado2) and link_share in copiado2, copiado2)

        # aba de e-mail
        pagina.click("nav button[data-tab='email']")
        pagina.wait_for_timeout(1200)
        check("métricas de e-mail carregaram", pagina.inner_text("#mail-week").strip() != "—")

        # aba de moderação
        pagina.click("nav button[data-tab='moderacao']")
        pagina.wait_for_timeout(1200)
        check("moderação carregou", pagina.locator("#mod-list").count() == 1)

        check("sem erros de JavaScript", not erros, "; ".join(erros[:3]))
        navegador.close()

    print(f"\n{checks - len(falhas)}/{checks} verificações passaram")
    if falhas:
        print("Falhas: " + ", ".join(falhas))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
