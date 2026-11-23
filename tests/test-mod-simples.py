"""Teste de fogo do fluxo simplificado do Mod (Playwright).

Cobre:
  1. painel admin do PC: gerar Mod só com o Handle (sem nome/CPF/e-mail);
  2. painel web do Mod: abrir com o token, preencher o cadastro (Handle),
     salvar e ver o status "cadastro completo";
  3. saque bloqueado enquanto o cadastro estiver incompleto;
  4. aba de e-mail com espaçamento entre métricas e tabela.

Uso: python3 tests/test-mod-simples.py
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


def cpf_valido(base: int) -> str:
    digitos = [int(d) for d in f"{base:09d}"[:9]]

    def dv(dig: list[int], peso_inicial: int) -> int:
        soma = sum(d * (peso_inicial - i) for i, d in enumerate(dig))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    digitos.append(dv(digitos, 10))
    digitos.append(dv(digitos, 11))
    return "".join(str(d) for d in digitos)


def main() -> int:
    marca = str(int(time.time()))[-7:]
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1360, "height": 950})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))

        # ---------- painel admin: só o Handle ----------
        print("\n[admin] gerar Mod com apenas o Handle")
        pagina.goto(ADMIN, wait_until="load")
        check(
            "formulário só pede o Handle",
            pagina.locator("#mod-handle").count() == 1
            and pagina.locator("#mod-name").count() == 0
            and pagina.locator("#mod-cpf").count() == 0
            and pagina.locator("#mod-email").count() == 0,
        )
        pagina.fill("#mod-handle", f"mod_simples_{marca}")
        pagina.click("#mod-create")
        pagina.wait_for_timeout(2500)
        link = pagina.inner_text("#mod-panel-link").strip() if pagina.locator("#mod-panel-link").is_visible() else ""
        token = pagina.inner_text("#mod-token").strip() if pagina.locator("#mod-token").is_visible() else ""
        check("mod criado com link numérico", len(link.rsplit("/", 1)[-1]) == 11, link)
        check("token entregue ao admin", len(token) >= 16, token)
        check(
            "lista mostra cadastro pendente",
            "cadastro pendente" in pagina.inner_text("#mods-list"),
        )

        # ---------- painel web do Mod ----------
        print("\n[site] painel do Mod preenche o próprio cadastro")
        pagina.goto(f"{SITE}/mod", wait_until="load")
        pagina.fill("#mod-token", token)
        pagina.click("#mod-token-submit")
        pagina.wait_for_timeout(2000)
        check("painel abriu", pagina.locator("#mod-dashboard").is_visible())
        check(
            "seção de cadastro visível",
            pagina.locator("#mod-profile-form").is_visible(),
        )
        check(
            "status começa como pendente",
            "informe seu nome" in pagina.inner_text("#mod-profile-status").lower(),
            pagina.inner_text("#mod-profile-status"),
        )

        # saque bloqueado sem cadastro
        pagina.click("#mod-withdraw-button")
        pagina.wait_for_timeout(600)
        check(
            "saque bloqueado sem cadastro",
            "nome" in pagina.inner_text("#mod-withdraw-feedback").lower(),
            pagina.inner_text("#mod-withdraw-feedback"),
        )

        # preenche e salva (sem dado sensível: só nome e e-mail opcional)
        pagina.fill("#mod-profile-name", f"Mod de Teste {marca}")
        pagina.fill("#mod-profile-email", f"mod.simples{marca}@vizinhanca.app")
        pagina.click("#mod-profile-save")
        pagina.wait_for_timeout(2000)
        check("cadastro salvo", "salvo" in pagina.inner_text("#mod-profile-feedback").lower(), pagina.inner_text("#mod-profile-feedback"))
        check(
            "status vira completo",
            "stripe" in pagina.inner_text("#mod-profile-status").lower(),
            pagina.inner_text("#mod-profile-status"),
        )

        # explicar o projeto
        pagina.click(".mod-about summary")
        pagina.wait_for_timeout(300)
        check(
            "explicação do projeto disponível",
            "vizin.Os" in pagina.inner_text(".mod-about"),
        )

        # ---------- aba de e-mail com espaçamento ----------
        print("\n[admin] espaçamento da aba de e-mail")
        pagina.goto(ADMIN, wait_until="load")
        pagina.click("nav button[data-tab='email']")
        pagina.wait_for_timeout(1200)
        gap = pagina.evaluate(
            """() => {
              const cards = document.querySelector('#tab-email .cards');
              const panel = document.querySelector('#tab-email .panel');
              if (!cards || !panel) return -1;
              return Math.round(panel.getBoundingClientRect().top - cards.getBoundingClientRect().bottom);
            }"""
        )
        check("há separação entre métricas e tabela", gap >= 20, f"gap={gap}px")

        check("sem erros de JavaScript", not erros, "; ".join(erros[:3]))
        navegador.close()

    print(f"\n{checks - len(falhas)}/{checks} verificações passaram")
    if falhas:
        print("Falhas: " + ", ".join(falhas))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
