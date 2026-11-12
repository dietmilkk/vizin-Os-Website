"""Teste end-to-end do painel de afiliado do vizin.Os.

Valida o fluxo real no navegador: criacao de conta de afiliado, carregamento
do painel, exibicao do link de afiliado, verificacao simplificada por nome
popular e envio do convite por e-mail (que e o unico canal de contato).

Uso:
    python3 tests/test-painel-afiliado.py
"""

import json
import re
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

from lib.primeiro_acesso import ja_visitou

BASE = "http://localhost:8099"
API = "https://api.188.166.156.109.sslip.io"
TOKEN_CACHE = "/tmp/vizin-teste-afiliado-token.json"

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


def api_post(path, payload):
    request = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def api_get(path):
    with urllib.request.urlopen(API + path, timeout=25) as response:
        return json.loads(response.read())


def cached_token():
    """Token do afiliado de teste criado numa execucao anterior.

    A VPS cria uma conta por IP: repetir o teste do mesmo IP e barrado pelo
    guarda de IP. O token fica em cache local para o teste poder repetir.
    """
    try:
        with open(TOKEN_CACHE, encoding="utf-8") as handle:
            return json.load(handle).get("token", "")
    except Exception:
        return ""


def cache_token(token):
    try:
        with open(TOKEN_CACHE, "w", encoding="utf-8") as handle:
            json.dump({"token": token}, handle)
    except Exception:
        pass


def main():
    code = "TESTPNL" + str(int(__import__("time").time()))[-4:]
    status, created = api_post(
        "/hunters", {"handle": "tpainel" + code[-6:].lower(), "code": code}
    )
    if status == 200:
        token = created["token"]
        cache_token(token)
    elif status == 403 and created.get("code") == "IP_BLOCKED_DUPLICATE":
        token = cached_token()
        if not token:
            print(
                "Este IP ja criou conta e nao ha token em cache: "
                f"teste pulado ({TOKEN_CACHE})."
            )
            return 0
        print("Este IP ja criou conta: reaproveitando o afiliado de teste em cache.")
    else:
        print(f"Falha ao criar afiliado de teste: {status} {created}")
        return 1
    # O codigo vem da API: com token reaproveitado o codigo e o do afiliado
    # em cache, nao o gerado nesta execucao.
    code = (api_get(f"/hunters/me?token={token}").get("hunter") or {}).get("code", code)
    # Nome popular unico por execucao: a base de contatos e compartilhada e
    # real, entao "Ana Souza" puro ja pode existir de uma execucao anterior.
    creator_name = "Ana Souza Teste " + code[-4:]
    # O painel so envia e-mail se a VPS tiver um provedor configurado. Sem
    # provedor, a rota responde 502 e o teste valida esse caminho.
    try:
        health = api_get("/health")
        mail_configured = bool((health.get("mail") or {}).get("configured"))
    except Exception:
        mail_configured = False
    print(f"\nAfiliado de teste criado: code={code}")
    print(f"Provedor de e-mail configurado: {mail_configured}")

    errors = []
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        ja_visitou(page)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def escutar_console(msg) -> None:
            # A rota /_vercel/insights/* (Web Analytics) só existe quando o site
            # é servido pela Vercel. Fora dela o <script defer> responde 404 e o
            # navegador registra isso como erro de console — a mensagem de texto
            # não traz a URL; ela está em msg.location.
            if msg.type != "error":
                return
            local = (msg.location or {}).get("url", "") or ""
            if "/_vercel/insights/" in msg.text or "/_vercel/insights/" in local:
                return
            errors.append(msg.text)

        page.on("console", escutar_console)

        print("\n[1] Carregamento do painel")
        page.goto(f"{BASE}/afiliados/?afiliado_token={token}", wait_until="networkidle")
        page.wait_for_selector("#afiliadoDashboardView:not(.hidden)", timeout=20000)
        check("painel de afiliado visivel", page.is_visible("#afiliadoDashboardView"))
        check(
            "marketing escondido no painel",
            not page.is_visible("#partnerMarketing"),
        )

        print("\n[2] Link de afiliado aparece")
        link_value = page.input_value("#afiliadoLink")
        check("link preenchido", bool(link_value), f"valor='{link_value}'")
        check(
            "link usa o parametro ?a=",
            "?a=" in link_value,
            link_value,
        )
        check(
            "link usa o codigo do afiliado",
            code in link_value,
            link_value,
        )

        print("\n[3] Sem sistema de codigo (copia do painel do criador)")
        check(
            "campo de codigo do afiliado removido",
            page.locator("#afiliadoCode").count() == 0,
        )
        check(
            "botao copiar codigo removido",
            page.locator("#copyAfiliadoCode").count() == 0,
        )
        check(
            "painel do criador escondido",
            not page.is_visible("#dashboardView"),
        )

        print("\n[4] Identidade e stats")
        check(
            "nome do afiliado preenchido",
            page.inner_text("#afiliadoName").strip() != "",
            page.inner_text("#afiliadoName"),
        )
        check(
            "handle do afiliado preenchido",
            page.inner_text("#afiliadoHandle").strip().startswith("@"),
            page.inner_text("#afiliadoHandle"),
        )
        for stat in [
            "afiliadoStatOutreach",
            "afiliadoStatCreators",
            "afiliadoStatReferrals",
            "afiliadoStatCommission",
            "afiliadoStatAvailable",
            "afiliadoStatPending",
            "afiliadoStatWithdrawn",
        ]:
            check(f"stat {stat} renderizado", page.locator(f"#{stat}").count() == 1)

        print("\n[5] Verificacao no mesmo envio do convite")
        check(
            "verificacao separada removida",
            page.locator("#checkHandle").count() == 0
            and page.locator("#checkContactButton").count() == 0
            and page.locator("#checkContactResult").count() == 0,
        )
        check(
            "campo de @ do criador existe e e obrigatorio",
            page.locator("#outreachContact").count() == 1
            and page.get_attribute("#outreachContact", "required") is not None,
        )

        print("\n[6] Envio do convite por e-mail")
        check(
            "campo de e-mail do criador existe",
            page.locator("#outreachEmail").count() == 1,
        )
        check(
            "e-mail do criador e obrigatorio",
            page.get_attribute("#outreachEmail", "required") is not None,
        )
        check(
            "campo de e-mail valida formato de e-mail",
            page.get_attribute("#outreachEmail", "type") == "email",
        )
        check(
            "nome popular e obrigatorio",
            page.get_attribute("#outreachName", "required") is not None,
        )
        check(
            "templates de e-mail e DM removidos",
            page.locator("#emailTemplate").count() == 0
            and page.locator("#dmTemplate").count() == 0
            and page.locator("#copyEmailTemplate").count() == 0
            and page.locator("#copyDmTemplate").count() == 0,
        )
        check(
            "cota de e-mails informada no painel",
            re.match(r"^\d+/3$", page.inner_text("#afiliadoStatEmails").strip()) is not None
            and "3 dias"
            in (page.get_attribute("#afiliadoStatEmailsCard", "title") or ""),
            page.inner_text("#afiliadoStatEmails"),
        )
        check(
            "stat de e-mails enviados renderizado",
            page.locator("#afiliadoStatEmails").count() == 1,
        )
        check(
            "formulario bloqueia e-mail invalido",
            page.eval_on_selector(
                "#outreachEmail",
                "el => !el.checkValidity() || el.validity.typeMismatch",
            ),
        )

        # Endereco de exemplo: nao existe caixa de correio real, entao o
        # envio nao alcanca ninguem mesmo com o provedor configurado.
        emails_before = page.inner_text("#afiliadoStatEmails").strip()
        page.fill("#outreachName", creator_name)
        page.fill("#outreachEmail", "criador.exemplo@example.com")
        page.select_option("#outreachPlatform", "instagram")
        page.fill("#outreachContact", "@anasouza")
        page.click("#outreachButton")
        page.wait_for_function(
            """() => {
              const s = document.querySelector('#outreachStatus');
              const e = document.querySelector('#outreachError');
              const status = s ? s.textContent.trim() : '';
              const error = e ? e.textContent.trim() : '';
              // Wait for final result: success status or error (not just initial loading)
              return (status && (status.includes('enviado') || status.includes('já usou') || status.includes('já foi'))) || error;
            }""",
            timeout=30000,
        )
        status_text = page.inner_text("#outreachStatus")
        error_text = page.inner_text("#outreachError")
        if "já usou os 3 e-mails" in error_text:
            # Token reaproveitado de outra execucao: a cota da janela de 3
            # dias ja acabou. O painel precisa explicar quando libera.
            check("cota esgotada e explicada", "libera" in error_text.lower(), error_text)
        elif mail_configured:
            check("e-mail enviado com sucesso", "enviado" in status_text.lower(), status_text)
            # O painel recarrega os numeros depois do envio. A mensagem de
            # status aparece antes do reload terminar, entao a verificacao
            # espera a lista e o contador refletirem o envio.
            page.wait_for_function(
                r"""() => {
                  const stat = document.querySelector('#afiliadoStatEmails');
                  const rows = document.querySelectorAll('#outreachList .contact-row');
                  return rows.length >= 1 && stat && !/^0\//.test(stat.textContent.trim());
                }""",
                timeout=15000,
            )
            check(
                "contato aparece na lista",
                page.locator("#outreachList .contact-row").count() >= 1,
            )
            used_before = int(emails_before.split("/")[0] or 0)
            used_after = int(page.inner_text("#afiliadoStatEmails").strip().split("/")[0] or 0)
            check(
                "stat de e-mails conta o envio",
                used_after == used_before + 1,
                f"{emails_before} -> {page.inner_text('#afiliadoStatEmails').strip()}",
            )
        else:
            check(
                "sem provedor de e-mail a falha e explicada",
                bool(error_text.strip()),
                error_text,
            )
            check(
                "falha nao registra contato na base",
                page.locator("#outreachList .contact-row").count() == 0,
            )

        print("\n[7] Deduplicacao por nome popular")
        # A base compartilhada e escrita pelo envio do e-mail (unico canal de
        # contato). Sem provedor configurado nao ha como semear um registro,
        # entao a deduplicacao so pode ser verificada de ponta a ponta.
        if mail_configured:
            page.fill("#outreachName", creator_name.lower())
            page.fill("#outreachEmail", "criador.exemplo@example.com")
            page.select_option("#outreachPlatform", "instagram")
            page.fill("#outreachContact", "@anasouza")
            page.click("#outreachButton")
            page.wait_for_function(
                """() => {
                  const e = document.querySelector('#outreachError');
                  return e && e.textContent.trim().length > 0;
                }""",
                timeout=15000,
            )
            result = page.inner_text("#outreachError")
            check(
                "variacao de caixa/espaço detecta o mesmo criador",
                "já" in result.lower() and "contat" in result.lower(),
                result,
            )
            # O segundo envio para o mesmo criador volta com 409.
            # O campo "notes" nao existe mais: a API rejeita observacoes.
            status, duplicated = api_post(
                "/hunters/outreach/email",
                {
                    "token": token,
                    "name": creator_name,
                    "email": "criador.exemplo@example.com",
                    "platform": "instagram",
                    "contact_url": "@anasouza",
                },
            )
            check(
                "segundo envio para o mesmo criador e barrado",
                status == 409,
                f"{status} {duplicated}",
            )
        else:
            print("  SKIP deduplicacao: exige provedor de e-mail configurado")

        print("\n[8] Envio de e-mail e o unico canal")
        check(
            "formulario de e-mail presente no painel",
            page.locator("#outreachForm").count() == 1,
        )
        check(
            "botao diz Enviar e-mail",
            "enviar e-mail" in page.inner_text("#outreachButton").lower(),
            page.inner_text("#outreachButton"),
        )
        check(
            "formulario de registro manual removido",
            page.locator("#outreachHandle").count() == 0,
        )

        print("\n[9] Guia completo acima do rodapé")
        check(
            "guia completo visivel no painel",
            page.is_visible("#guiaCompleto"),
        )
        check(
            "guia completo fica depois do painel",
            page.evaluate(
                "() => { const g = document.querySelector('#guiaCompleto');"
                " const d = document.querySelector('#afiliadoDashboardView');"
                " return g.getBoundingClientRect().top + window.scrollY"
                "   > d.getBoundingClientRect().top + window.scrollY + d.offsetHeight - 5; }"
            ),
        )
        check(
            "guia completo fica antes do rodapé",
            page.evaluate(
                "() => { const g = document.querySelector('#guiaCompleto');"
                " const f = document.querySelector('footer.site-footer');"
                " return g.getBoundingClientRect().top + window.scrollY"
                "   < f.getBoundingClientRect().top + window.scrollY; }"
            ),
        )
        check(
            "bloco do afiliado marcado como atual",
            page.eval_on_selector_all(
                ".guia-bloco.is-current", "els => els.map(e => e.id)"
            )
            == ["guiaAfiliado"],
            str(
                page.eval_on_selector_all(
                    ".guia-bloco.is-current", "els => els.map(e => e.id)"
                )
            ),
        )
        check(
            "bloco do criador não marcado como atual",
            page.eval_on_selector_all(
                ".guia-bloco#guiaCriador.is-current", "els => els.length"
            )
            == 0,
        )
        check(
            "convite cruzado aponta para o outro papel",
            page.eval_on_selector_all(
                ".guia-cross__item:not(.hidden)",
                "els => els.map(e => e.getAttribute('data-guide-cta'))",
            )
            == ["afiliado"],
            str(
                page.eval_on_selector_all(
                    ".guia-cross__item:not(.hidden)",
                    "els => els.map(e => e.getAttribute('data-guide-cta'))",
                )
            ),
        )
        check(
            "nav do painel aponta para o guia",
            page.eval_on_selector_all(
                ".partners-nav a",
                "els => els.map(e => e.getAttribute('href'))",
            )
            == ["#guiaProjeto", "#guiaPrograma", "#guiaDivisao"],
            str(
                page.eval_on_selector_all(
                    ".partners-nav a",
                    "els => els.map(e => e.getAttribute('href'))",
                )
            ),
        )

        print("\n[10] Painel em grupos numerados")
        check(
            "4 grupos no fluxo do painel",
            page.eval_on_selector_all(
                "#afiliadoDashboardView .panel-group", "els => els.length"
            )
            == 4,
        )
        check(
            "numeros dos grupos em ordem (1 a 4)",
            page.eval_on_selector_all(
                "#afiliadoDashboardView .panel-group__num",
                "els => els.map(e => e.textContent.trim())",
            )
            == ["1", "2", "3", "4"],
        )
        check(
            "titulos dos grupos em H2",
            page.eval_on_selector_all(
                "#afiliadoDashboardView .panel-group__title",
                "els => els.map(e => e.tagName)",
            )
            == ["H2", "H2", "H2", "H2"],
        )
        check(
            "cards dentro dos grupos usam H3",
            page.eval_on_selector_all(
                "#afiliadoDashboardView .panel-card__title",
                "els => els.every(e => e.tagName === 'H3')",
            ),
        )
        check(
            "nome do afiliado usa H3 (hierarquia H1 > H2 > H3)",
            page.eval_on_selector("#afiliadoName", "el => el.tagName") == "H3",
        )
        check(
            "grupos com intervalo vertical uniforme (56px)",
            page.evaluate(
                """() => {
                  const g = [...document.querySelectorAll('#afiliadoDashboardView .panel-group')];
                  const gaps = [];
                  for (let i = 1; i < g.length; i++) {
                    gaps.push(Math.round(g[i].getBoundingClientRect().top
                      - g[i - 1].getBoundingClientRect().bottom));
                  }
                  return gaps.every((x) => x === 56);
                }"""
            ),
        )
        check(
            "cards do painel agrupados em duas colunas onde cabe",
            page.evaluate(
                """() => {
                  const cols = [...document.querySelectorAll(
                    '#afiliadoDashboardView .panel-two-col, #afiliadoDashboardView .withdraw-panel')];
                  return cols.length >= 2 && cols.every((c) => {
                    const kids = [...c.children].map((k) => Math.round(k.getBoundingClientRect().top));
                    return new Set(kids).size === 1;
                  });
                }"""
            ),
        )
        check(
            "explicacao do envio fica abaixo do formulario (nao ao lado)",
            page.evaluate(
                """() => {
                  const form = document.querySelector('#outreachForm');
                  const nota = document.querySelector(
                    '#afiliadoDashboardView .panel-subsection');
                  if (!form || !nota) return false;
                  return nota.getBoundingClientRect().top
                    >= form.getBoundingClientRect().bottom - 1;
                }"""
            ),
        )

        print("\n[11] Sumario do guia")
        check(
            "sumario do guia visivel",
            page.is_visible(".guia-sumario"),
        )
        check(
            "sumario com 6 botoes para os 6 blocos",
            page.eval_on_selector_all(
                ".guia-sumario__list button",
                "els => els.map(e => e.getAttribute('data-guide-target'))",
            )
            == [
                "guiaProjeto",
                "guiaPrograma",
                "guiaDivisao",
                "guiaAfiliado",
                "guiaCriador",
                "guiaTransparencia",
            ],
        )
        check(
            "apenas um bloco do guia visivel por vez",
            page.evaluate(
                "() => [...document.querySelectorAll('.guia-grid .guia-bloco')]"
                ".filter((el) => !el.hidden).length === 1"
            ),
        )
        check(
            "todos os blocos do guia existem",
            page.eval_on_selector_all(
                ".guia-grid .guia-bloco", "els => els.length"
            )
            == 6,
        )
        check(
            "subsecoes do guia usam H4 (nao H3)",
            page.eval_on_selector_all(
                ".guia-bloco h4", "els => els.length"
            )
            >= 8,
        )
        check(
            "cada bloco do guia tem um unico H3 (titulo do bloco)",
            page.eval_on_selector_all(
                ".guia-bloco",
                """els => els.every((b) => b.querySelectorAll(':scope > h3').length === 1)""",
            ),
        )

        print("\n[12] Página pública com o guia completo")
        page.goto(f"{BASE}/afiliados/", wait_until="networkidle")
        check(
            "guia completo visível na página pública",
            page.is_visible("#guiaCompleto"),
        )
        check(
            "seção curta #porDentro não existe mais",
            page.locator("#porDentro").count() == 0,
        )
        for section in ["#divisao", "#participar"]:
            check(f"seção pública {section} visível", page.is_visible(section))
        check(
            "guia tem os seis blocos em acordeão",
            page.eval_on_selector_all(
                ".guia-bloco", "els => els.length"
            )
            == 6,
        )
        check(
            "nav pública aponta para as seções públicas",
            page.eval_on_selector_all(
                ".partners-nav a",
                "els => els.map(e => e.getAttribute('href'))",
            )
            == ["#divisao", "#participar", "#guiaCompleto"],
            str(
                page.eval_on_selector_all(
                    ".partners-nav a",
                    "els => els.map(e => e.getAttribute('href'))",
                )
            ),
        )
        check(
            "nav pública visível (atalho para o guia)",
            page.is_visible(".partners-nav"),
        )
        check(
            "nenhum convite cruzado na página pública",
            page.eval_on_selector_all(
                ".guia-cross__item:not(.hidden)", "els => els.length"
            )
            == 0,
        )
        check(
            "sem erros de JavaScript na página pública",
            not errors,
            "; ".join(errors[:3]),
        )
        check(
            "intervalo vertical uniforme entre as seções públicas",
            page.evaluate(
                """() => {
                  const s = [...document.querySelectorAll(
                    '#partnerMarketing > .creators-hero, #partnerMarketing > .creators-guide, #guiaCompleto')];
                  const gaps = [];
                  for (let i = 1; i < s.length; i++) {
                    gaps.push(Math.round(s[i].getBoundingClientRect().top
                      - s[i - 1].getBoundingClientRect().bottom));
                  }
                  return gaps.length === 3 && gaps.every((x) => x === 56);
                }"""
            ),
        )
        check(
            "nenhuma classe eyebrow restante na página",
            page.eval_on_selector_all(".eyebrow", "els => els.length") == 0,
        )
        check(
            "bloco 'leia mais' da página pública sem subtítulo próprio",
            page.eval_on_selector_all(
                "#partnerMarketing .creators-more h3", "els => els.length"
            )
            == 0,
        )

        print("\n[13] Sem erros de JavaScript")
        check(
            "nenhum erro de runtime",
            not errors,
            "; ".join(errors[:3]),
        )

        page.screenshot(path="/tmp/opencode/painel-afiliado.png", full_page=True)
        print("\nScreenshot: /tmp/opencode/painel-afiliado.png")

        browser.close()

    print(f"\n{'=' * 52}")
    print(f"  {checks - len(failures)}/{checks} verificacoes passaram")
    if failures:
        print("  Falhas:")
        for failure in failures:
            print(f"    - {failure}")
        return 1
    print("  Tudo certo!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
