#!/usr/bin/env python3
"""Confere o site no ar como uma pessoa usa: abre as paginas no navegador.

Serve para o dominio publico (https://vizin-os.page.gd, hospedagem InfinityFree)
e para qualquer outro endereco. O navegador e usado de verdade porque a
hospedagem gratuita coloca uma verificacao de JavaScript antes de mostrar a
pagina: um `curl` puro veria apenas a tela de verificacao.

O que confere:
  * cada pagina abre (sem erro de rede e sem erro no console);
  * o canonical de cada pagina aponta para o dominio certo;
  * os links internos das paginas respondem;
  * o painel publico mostra numeros da API (sem erro em tela);
  * nada interno fica exposto (README, ferramentas, testes, .git, .env).

Uso:
    python3 tools/conferir-dominio.py
    python3 tools/conferir-dominio.py https://vizin-os.page.gd
    python3 tools/conferir-dominio.py https://site.188.166.156.109.sslip.io

O segundo argumento e o dominio que os canonicals devem apontar (padrao:
vizin-os.page.gd). Ele serve para conferir a copia de trabalho na VPS, que
tem o mesmo conteudo mas outro endereco.

Requer Playwright com Chromium.
"""

from __future__ import annotations

import sys
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://vizin-os.page.gd").rstrip("/")
DOMINIO_CANONICO = (sys.argv[2] if len(sys.argv) > 2 else "vizin-os.page.gd").rstrip("/")

PAGINAS = ["/", "/painel/", "/documento/", "/afiliados/", "/moderacao/"]

# Caminhos que nunca podem responder 200 em um site publico.
INTERNOS = [
    "/README.md",
    "/prompt-afiliados.md",
    "/tools/",
    "/tests/",
    "/deploy/",
    "/dist/",
    "/.git/config",
    "/.gitignore",
    "/.env",
    "/.htaccess",
]

# Apelidos antigos que devem continuar levando para a pagina atual.
ALIAS = {"/criadores": "/afiliados/"}

falhas: list[str] = []
verificacoes = 0


def check(rotulo: str, condicao: bool, detalhe: str = "") -> None:
    global verificacoes
    verificacoes += 1
    if condicao:
        print(f"  OK   {rotulo}")
    else:
        print(f"  FAIL {rotulo}" + (f" -> {detalhe}" if detalhe else ""))
        falhas.append(rotulo)


def navegar(pagina, url: str, tentativas: int = 2) -> int | None:
    """Abre a url no navegador e devolve o status final (None se falhou).

    Navegar de verdade (em vez de fetch) importa: a hospedagem gratuita
    bloqueia leitura de pastas e redireciona erros para outro dominio, e so a
    navegacao mostra o status que o visitante recebe.
    """
    for tentativa in range(tentativas):
        try:
            resposta = pagina.goto(url, wait_until="domcontentloaded", timeout=45_000)
            pagina.wait_for_timeout(1200)
            return resposta.status if resposta else 0
        except Exception:
            if tentativa + 1 < tentativas:
                pagina.wait_for_timeout(2500)
    return None


def main() -> int:
    print(f"Conferindo {BASE}\n")

    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(args=["--no-sandbox"])
        contexto = navegador.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900})
        pagina = contexto.new_page()

        erros_console: list[str] = []
        pagina.on("pageerror", lambda erro: erros_console.append(str(erro)))

        def escutar_console(mensagem) -> None:
            # A rota /_vercel/insights/* (Web Analytics) só existe quando o site
            # é servido pela Vercel. Fora dela o <script defer> responde 404 e o
            # navegador registra isso como erro de console — a mensagem de texto
            # não traz a URL; ela está em mensagem.location.
            if mensagem.type != "error":
                return
            local = (mensagem.location or {}).get("url", "") or ""
            if "/_vercel/insights/" in mensagem.text or "/_vercel/insights/" in local:
                return
            erros_console.append(mensagem.text)

        pagina.on("console", escutar_console)

        print("Paginas")
        for caminho in PAGINAS:
            erros_console.clear()
            resposta = pagina.goto(BASE + caminho, wait_until="domcontentloaded", timeout=60_000)
            pagina.wait_for_timeout(2500)
            status = resposta.status if resposta else 0
            titulo = pagina.title()
            canonical = pagina.evaluate(
                "document.querySelector('link[rel=canonical]')?.href || ''"
            )
            robots = pagina.evaluate(
                "document.querySelector('meta[name=robots]')?.content || ''"
            ).lower()
            noindex = "noindex" in robots
            print(f"  {caminho:<14} {status}  {titulo[:52]}")
            check(f"{caminho} abre com 200", status == 200, str(status))
            check(f"{caminho} tem título", bool(titulo.strip()))
            if noindex:
                # Pagina fora do indice (tem token e guarda de IP): canonical
                # seria contraditorio, mas ela precisa se declarar assim.
                check(f"{caminho} se declara noindex", True)
                check(f"{caminho} não tem canonical conflitante", not canonical, canonical)
            else:
                check(f"{caminho} tem canonical", bool(canonical), "canonical ausente")
                if canonical:
                    check(
                        f"{caminho} aponta para o domínio certo",
                        urlparse(canonical).netloc == DOMINIO_CANONICO,
                        canonical,
                    )
            check(f"{caminho} sem erro de JavaScript", not erros_console, "; ".join(erros_console[:2]))

        print("\nPainel público")
        erros_console.clear()
        pagina.goto(BASE + "/painel/", wait_until="domcontentloaded", timeout=60_000)
        try:
            pagina.wait_for_function(
                "() => { const el = document.getElementById('painelStatusTexto');"
                " if (!el) return false;"
                " const t = el.textContent || '';"
                " return t.startsWith('Atualizado') || t === 'Sem dados no momento'; }",
                timeout=30_000,
            )
        except Exception:
            pass
        status_painel = pagina.inner_text("#painelStatusTexto").strip() if pagina.query_selector("#painelStatusTexto") else "(sem elemento)"
        erro_visivel = pagina.locator("#painelErro").is_visible() if pagina.query_selector("#painelErro") else False
        print(f"  estado: {status_painel}")
        check("o painel sai do carregamento", status_painel != "Carregando estatísticas…", status_painel)
        check("o painel não termina em erro", not erro_visivel)
        check(
            "o painel mostra números da API",
            "Atualizado" in status_painel,
            status_painel,
        )

        print("\nLinks internos")
        pagina.goto(BASE + "/", wait_until="domcontentloaded", timeout=60_000)
        pagina.wait_for_timeout(1500)
        links = pagina.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]'))
                 .map(a => a.getAttribute('href'))
                 .filter(h => h && !h.startsWith('#') && !h.startsWith('mailto:')
                             && !h.startsWith('http'))"""
        )
        distintos = sorted(set(links))
        for href in distintos:
            url = urljoin(BASE + "/", href)
            if urlparse(url).netloc != urlparse(BASE).netloc:
                continue
            status = navegar(pagina, url)
            print(f"  {href:<28} {status}")
            check(f"link {href} responde", status is not None and status < 400, str(status))

        print("\nApelidos antigos")
        for antigo, novo in ALIAS.items():
            status = navegar(pagina, BASE + antigo)
            final = pagina.url
            print(f"  {antigo:<14} {status} -> {final}")
            check(
                f"{antigo} leva para {novo}",
                status is not None and status < 400 and final.rstrip("/").endswith(novo.rstrip("/")),
                f"{status} -> {final}",
            )

        print("\nArquivos de SEO")
        for caminho, esperado in (("/robots.txt", DOMINIO_CANONICO), ("/sitemap.xml", DOMINIO_CANONICO)):
            status = navegar(pagina, BASE + caminho)
            texto = pagina.inner_text("body") if status == 200 else ""
            if not texto:
                texto = pagina.content()
            print(f"  {caminho:<14} {status}")
            check(f"{caminho} responde 200", status == 200, str(status))
            check(f"{caminho} fala do domínio certo", esperado in texto, texto[:120])

        print("\nArquivos internos")
        for caminho in INTERNOS:
            status = navegar(pagina, BASE + caminho)
            print(f"  {caminho:<24} {status if status is not None else 'sem resposta'}")
            check(
                f"{caminho} não está exposto",
                status is None or status not in (200, 301, 302),
                str(status),
            )

        contexto.close()
        navegador.close()

    print("")
    print(f"{verificacoes} verificações · {len(falhas)} falha(s)")
    if falhas:
        for falha in falhas:
            print(f"  - {falha}")
        return 1
    print("OK: o site está no ar, com os links funcionando e nada interno exposto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
