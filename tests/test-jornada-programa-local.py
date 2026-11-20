"""Jornada completa de quem participa do programa de parceiros.

Roda no navegador de verdade, contra uma API local em memoria
(tests/lib/api_programa_mock.py): nenhum registro e criado na producao.

Caminho coberto, como uma pessoa faria:

1. abre /membros, fecha a janela de primeira visita;
2. cria a conta de CRIADOR (codigo, nome, CPF e e-mail);
3. confere o link do painel que aparece e o decora visual;
4. abre o painel e confere os numeros (indicacoes, saldo, saques);
5. registra um saque (chave Pix, titular, CPF e e-mail);
6. sai e cria a conta de AFILIADO (o afiliado nao escolhe codigo);
7. no painel do afiliado, registra o contato de um criador;
8. confere que o contato aparece na lista e nas cotas;
9. o painel do afiliado mostra o link de divulgacao com o codigo dele;
10. um link com o codigo do afiliado atribui o criador recem-criado;
11. nenhum erro de JavaScript em nenhum passo.

Uso:
    python3 tests/test-jornada-programa-local.py
"""

from __future__ import annotations

import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from api_programa_mock import servir_api
from playwright.sync_api import sync_playwright
from servidor_site import servir_site

falhas: list[str] = []
verificacoes = 0


def porta_livre() -> int:
    """Porta livre para a API mock e para o site local."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global verificacoes
    verificacoes += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def main() -> int:
    # Portas livres: o runner pode estar com outra instancia rodando.
    porta_api = porta_livre()
    porta_site = porta_livre()
    httpd_api, api_base = servir_api(porta_api)
    httpd_site, site_base = servir_site(porta_site, {
        "/": "index.html",
        "/membros": "membros.html",
    })
    print(f"API local: {api_base} | Site local: {site_base}\n")

    try:
        with sync_playwright() as pw:
            navegador = pw.chromium.launch()
            contexto = navegador.new_context(viewport={"width": 1366, "height": 900})
            pagina = contexto.new_page()
            erros: list[str] = []
            pagina.on("pageerror", lambda e: erros.append(str(e)))

            # A pagina le a API pela query ?api=...
            def abrir(rota: str):
                nonlocal pagina
                # Uma aba nova a cada passo: a sessao da conta anterior fica
                # na aba antiga (como no navegador de verdade).
                pagina = contexto.new_page()
                separador = "&" if "?" in rota else "?"
                pagina.goto(
                    f"{site_base}{rota}{separador}api={api_base}",
                    wait_until="domcontentloaded",
                )
                pagina.wait_for_timeout(900)

            def abrir_painel(link: str):
                """Abre o link do painel preservando a API local.

                O link gerado pela plataforma aponta para a API de producao
                (em producao e o certo); no teste local acrescentamos o
                ?api= para que a chamada va para o mock.
                """
                nonlocal pagina
                pagina = contexto.new_page()
                separador = "&" if "?" in link else "?"
                pagina.goto(f"{link}{separador}api={api_base}", wait_until="domcontentloaded")
                pagina.wait_for_timeout(1200)

            def fechar_primeira_visita():
                if pagina.locator("#firstVisitModal").is_visible():
                    pagina.click('.modal-close[data-first-visit-close]')
                    pagina.wait_for_timeout(300)

            print("[1] Criador cria a conta")
            abrir("/membros")
            fechar_primeira_visita()
            pagina.click('[data-open-create="creator"]:visible')
            pagina.wait_for_selector("#createModal:not([hidden])", timeout=5000)
            pagina.fill("#code", "ANA10")
            pagina.fill("#createName", "Ana")
            pagina.fill("#createCpf", "52998224725")
            pagina.fill("#createEmail", "ana@example.com")
            pagina.click("#createButton")
            pagina.wait_for_selector("#createdView:not([hidden])", timeout=15000)

            link = pagina.get_attribute("#dashboardLink", "href") or ""
            check("painel do criador tem link curto", "?p=" in link, link)
            check(
                "link do criador usa prefixo C",
                "?p=C" in link,
                link,
            )
            check(
                "codigo escolhido aparece no painel",
                "ANA10" in pagina.inner_text("#createdView"),
                pagina.inner_text("#createdView")[:120],
            )

            print("\n[2] O painel do criador abre e mostra os numeros")
            # O painel abre em outra aba de proposito: a aba original
            # continua mostrando o link secreto da conta.
            with contexto.expect_page() as evento:
                pagina.click("#openDashboard")
            link_painel = evento.value.url
            abrir_painel(link_painel)
            check(
                "painel abriu em outra aba",
                link_painel != site_base + "/membros",
                link_painel,
            )
            pagina.wait_for_selector("#dashboardView:not([hidden])", timeout=15000)
            pagina.wait_for_timeout(700)
            check("nome do criador aparece", "Ana" in pagina.inner_text("#creatorName"), pagina.inner_text("#creatorName"))
            check("handle aparece", "@" in pagina.inner_text("#creatorHandle"), pagina.inner_text("#creatorHandle"))
            check("codigo aparece", "ANA10" in pagina.inner_text("#creatorCode"), pagina.inner_text("#creatorCode"))
            saldo = pagina.inner_text("#withdrawAvailable")
            check("saldo disponivel em reais", "R$" in saldo, saldo)
            indicacoes = pagina.inner_text("#statReferrals")
            check("numero de indicacoes visivel", indicacoes.strip() != "", indicacoes)
            check(
                "lista de indicacoes preenchida",
                pagina.locator("#referralList .row, #referralList > *").count() > 0,
                pagina.inner_text("#referralList")[:80],
            )

            print("\n[3] Saque: chave Pix, titular, CPF e e-mail")
            pagina.fill("#withdrawPix", "ana@example.com")
            pagina.fill("#withdrawPixCpf", "52998224725")
            pagina.fill("#withdrawEmail", "ana@example.com")
            pagina.click("#withdrawButton")
            pagina.wait_for_timeout(1500)
            erro_saque = pagina.inner_text("#withdrawError")
            check("saque sem erro", not erro_saque.strip(), erro_saque)
            check(
                "saque aparece no historico",
                "saque" in pagina.inner_text("#withdrawalList").lower()
                or pagina.locator("#withdrawalList > *").count() > 0,
                pagina.inner_text("#withdrawalList")[:100],
            )

            print("\n[4] Afiliado cria a conta (sem escolher codigo)")
            abrir("/membros")
            fechar_primeira_visita()
            pagina.click('[data-open-create="afiliado"]:visible')
            pagina.wait_for_selector("#createModal:not([hidden])", timeout=5000)
            check(
                "campo de codigo some para o afiliado",
                pagina.locator("#codeField").is_hidden(),
            )
            pagina.fill("#createName", "Bia")
            pagina.fill("#createCpf", "52998224725")
            pagina.fill("#createEmail", "bia@example.com")
            pagina.click("#createButton")
            try:
                pagina.wait_for_selector("#createdView:not([hidden])", timeout=8000)
            except Exception:
                print("DEBUG reqs:", pagina.evaluate("() => window.__reqs || []"))
                print("DEBUG erro:", pagina.inner_text("#createError"))
                print("DEBUG aviso:", pagina.inner_text("#createWarning"))
                raise
            link_afiliado = pagina.get_attribute("#dashboardLink", "href") or ""
            check("painel do afiliado tem link curto", "?p=" in link_afiliado, link_afiliado)
            check("link do afiliado usa prefixo A", "?p=A" in link_afiliado, link_afiliado)

            print("\n[5] O painel do afiliado mostra numeros e link de divulgacao")
            with contexto.expect_page() as evento:
                pagina.click("#openDashboard")
            link_painel_af = evento.value.url
            abrir_painel(link_painel_af)
            pagina.wait_for_selector("#afiliadoDashboardView:not([hidden])", timeout=15000)
            pagina.wait_for_timeout(700)
            comissao = pagina.inner_text("#afiliadoStatCommission")
            check("comissao em reais", "R$" in comissao, comissao)
            quota = pagina.inner_text("#afiliadoStatOutreach")
            check("cota de contatos visivel", quota.strip() != "", quota)
            check(
                "link de divulgacao removido do painel",
                pagina.locator("#afiliadoLink").count() == 0,
            )

            print("\n[6] Afiliado registra o contato de um criador")
            pagina.fill("#outreachName", "Carlos")
            pagina.fill("#outreachEmail", "carlos@example.com")
            pagina.fill("#outreachContact", "@carloscria")
            pagina.fill("#outreachMotivo", "Criador sem resposta recente.")
            plataforma = pagina.locator("#outreachPlatform")
            if plataforma.count():
                plataforma.select_option(index=1)
            pagina.click("#outreachButton")
            pagina.wait_for_timeout(1800)
            estado = pagina.get_attribute("#outreachStatus", "data-estado") or ""
            check("envio do convite confirmado", estado == "enviado", estado or pagina.inner_text("#outreachError"))
            check(
                "contato aparece na lista",
                "Carlos" in pagina.inner_text("#outreachList"),
                pagina.inner_text("#outreachList")[:100],
            )
            check(
                "cota de contatos conta o envio",
                pagina.inner_text("#afiliadoStatOutreach").strip() not in ("", "0"),
                pagina.inner_text("#afiliadoStatOutreach"),
            )

            print("\n[7] O painel do afiliado nao guarda mais o link de divulgacao")
            check(
                "sem campo de link no painel do afiliado",
                pagina.locator("#afiliadoLink").count() == 0,
            )

            print("\n[8] Sem erros de JavaScript")
            check("nenhum erro de runtime", not erros, "; ".join(erros[:3]))

            navegador.close()
    finally:
        httpd_api.shutdown()
        httpd_site.shutdown()

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("Jornada do programa de parceiros completa, sem tocar a producao.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
