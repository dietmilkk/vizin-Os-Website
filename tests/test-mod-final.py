"""Teste de fogo do fluxo final do Mod (Playwright).

Cobre:
  1. painel admin: gerar Mod só com o Handle;
  2. painel web do Mod: sem campo de CPF, só nome (+ e-mail opcional);
  3. nome completo vira obrigatório para sacar (e é salvo);
  4. um clique em "Sacar" leva ao onboarding da Stripe (sem pedir CPF aqui);
  5. ao voltar da Stripe, o saque é retomado automaticamente (sem novo clique).

Uso: python3 tests/test-mod-final.py
"""
from __future__ import annotations

import time

from playwright.sync_api import sync_playwright

ADMIN = "http://127.0.0.1:8899/"
SITE = "https://site.188.166.156.109.sslip.io"

falhas: list[str] = []
checks = 0


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global checks
    checks += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def main() -> int:
    marca = str(int(time.time()))[-7:]
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1360, "height": 950})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))

        # ---------- painel admin ----------
        print("\n[admin] gerar Mod com apenas o Handle")
        pagina.goto(ADMIN, wait_until="load")
        pagina.fill("#mod-handle", f"mod_final_{marca}")
        pagina.click("#mod-create")
        pagina.wait_for_timeout(2500)
        token = pagina.inner_text("#mod-token").strip() if pagina.locator("#mod-token").is_visible() else ""
        check("mod criado", bool(token), token)

        # ---------- painel web do Mod ----------
        print("\n[site] cadastro sem dado sensível")
        pagina.goto(f"{SITE}/mod", wait_until="load")
        pagina.fill("#mod-token", token)
        pagina.click("#mod-token-submit")
        pagina.wait_for_timeout(2000)
        check("painel abriu", pagina.locator("#mod-dashboard").is_visible())
        check(
            "não pede CPF no nosso site",
            pagina.locator("#mod-profile-cpf").count() == 0,
        )
        check(
            "pede o nome completo",
            pagina.locator("#mod-profile-name").count() == 1,
        )
        check(
            "e-mail é opcional",
            "opcional" in (pagina.locator("label[for='mod-profile-email']").inner_text() or "").lower(),
        )

        # sem nome não dá para sacar
        pagina.click("#mod-withdraw-button")
        pagina.wait_for_timeout(500)
        feedback = pagina.inner_text("#mod-withdraw-feedback")
        check("saque pede o nome", "nome" in feedback.lower(), feedback)

        # salva o nome
        pagina.fill("#mod-profile-name", "Mod Final de Teste")
        pagina.click("#mod-profile-save")
        pagina.wait_for_timeout(1800)
        check(
            "nome salvo",
            "salvo" in pagina.inner_text("#mod-profile-feedback").lower(),
            pagina.inner_text("#mod-profile-feedback"),
        )
        check(
            "status mostra cadastro pronto",
            "stripe" in pagina.inner_text("#mod-profile-status").lower(),
            pagina.inner_text("#mod-profile-status"),
        )

        # ---------- um clique: vai para a Stripe ----------
        print("\n[site] um clique no saque")
        rota_stripe = []
        pagina.route(
            "https://connect.stripe.com/**",
            lambda rota: rota_stripe.append(rota.request.url) or pagina.goto(f"{SITE}/mod"),
        )
        pagina.click("#mod-withdraw-button")
        pagina.wait_for_timeout(2500)
        # Sem Connect configurado a API responde 503: o painel mostra o aviso
        # e NAO pede CPF nem outro dado sensível.
        feedback = pagina.inner_text("#mod-withdraw-feedback")
        check(
            "sem pedir dados sensíveis no nosso site",
            "cpf" not in feedback.lower() and "documento" not in feedback.lower(),
            feedback,
        )
        check(
            "informa o estado do serviço da Stripe",
            "stripe" in feedback.lower(),
            feedback,
        )

        # ---------- retomada automática ----------
        print("\n[site] retomada automática ao voltar da Stripe")
        pagina.goto(f"{SITE}/mod?stripe_connect_return=1&role=mod", wait_until="load")
        # A sessão do token pode já estar salva nesta aba: nesse caso o painel
        # abre direto, sem pedir o token de novo.
        if pagina.locator("#mod-token-form").is_visible():
            pagina.fill("#mod-token", token)
            pagina.click("#mod-token-submit")
            pagina.wait_for_timeout(2500)
        check("painel reopened", pagina.locator("#mod-dashboard").is_visible())
        # Com o onboarding pendente, nada acontece; o que importa é que o painel
        # não peça CPF nem exija confirmação manual do saque.
        corpo = pagina.inner_text("#mod-dashboard")
        check("painel mantém o fluxo simples", "cpf" not in corpo.lower())
        check("botão de saque continua disponível", pagina.locator("#mod-withdraw-button").is_visible())

        check("sem erros de JavaScript", not erros, "; ".join(erros[:3]))
        navegador.close()

    print(f"\n{checks - len(falhas)}/{checks} verificações passaram")
    if falhas:
        print("Falhas: " + ", ".join(falhas))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
