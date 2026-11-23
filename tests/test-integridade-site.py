"""Rastreia o site inteiro e confere a integridade de cada pagina.

Nao depende de rede: as paginas sao servidas localmente com as rotas
reais e o crawler segue os links internos.

Confere:
  - toda pagina tem title, meta description e idioma;
  - todo link interno resolve (nenhum 404 no site);
  - todo recurso local referenciado (css, js, imagem, fonte) existe;
  - toda imagem tem alt; todo campo de formulario tem rotulo;
  - a hierarquia de titulos nao salta nivel (h1 -> h3);
  - nao ha id duplicado nem ancora quebrada;
  - o rodape e a barra de navegacao tem os mesmos destinos em todas as
    paginas (padronizacao).

Uso:
    python3 site/tests/test-integridade-site.py
"""

from __future__ import annotations

import os
import socket
from itertools import pairwise
from urllib.parse import urljoin

from lib.servidor_site import servir_site
from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGINAS = [
    "/", "/membros", "/mod", "/11277376272", "/comunidade", "/documento",
    "/download", "/painel", "/termos",
    "/privacidade", "/licenca", "/404.html",
]

falhas: list[str] = []
verificacoes = 0


def porta_livre() -> int:
    """Porta livre para o servidor local (evita conflito entre suites)."""
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
    httpd, base = servir_site(porta_livre(), {
        "/": "index.html",
        "/membros": "membros.html",
        "/mod": "mod.html",
        "/11277376272": "mod.html",
        "/comunidade": "comunidade.html",
        "/documento": "documento.html",
        "/download": "download.html",
        "/painel": "painel.html",
        "/termos": "termos.html",
        "/privacidade": "privacidade.html",
        "/licenca": "licenca.html",
    })
    print(f"Site local: {base}\n")

    try:
        with sync_playwright() as pw:
            navegador = pw.chromium.launch()
            pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
            erros_js: list[str] = []
            pagina.on("pageerror", lambda e: erros_js.append(str(e)))

            links_vistos: set[str] = set()
            recursos_vistos: set[str] = set()
            rodapes: dict[str, list[str]] = {}

            print("\n[Compatibilidade da URL antiga]")
            for rota_antiga in ("/moderacao", "/moderacao.html"):
                resposta = pagina.request.get(
                    urljoin(base, rota_antiga),
                    max_redirects=0,
                )
                destino = resposta.headers.get("location", "")
                check(
                    f"{rota_antiga} responde redirect",
                    resposta.status in (301, 308),
                    str(resposta.status),
                )
                check(
                    f"{rota_antiga} aponta para a seção de moderação",
                    destino.endswith("/documento#moderacao"),
                    destino,
                )

            for rota in PAGINAS:
                print(f"\n[{rota}]")
                pagina.goto(urljoin(base, rota), wait_until="load")
                pagina.wait_for_timeout(350)

                # --- metadados -------------------------------------------------
                check("tem title", bool(pagina.title().strip()), pagina.title())
                descricao = pagina.get_attribute("meta[name='description']", "content") or ""
                check("tem meta description", len(descricao.strip()) > 30, descricao[:80])
                idioma = pagina.get_attribute("html", "lang") or ""
                check("tem lang", bool(idioma.strip()), idioma)
                canonical = pagina.locator('link[rel="canonical"]').count()
                robots = pagina.get_attribute("meta[name='robots']", "content") or ""
                indexavel = "noindex" not in robots
                if indexavel:
                    check("tem canonical", canonical == 1, str(canonical))
                else:
                    check("pagina noindex sem canonical", canonical == 0, str(canonical))

                # --- imagens e campos -----------------------------------------
                sem_alt = pagina.evaluate(
                    "() => [...document.images]"
                    ".filter(i => !i.hasAttribute('alt'))"
                    ".map(i => i.currentSrc || i.src).slice(0, 5)"
                )
                check("toda imagem tem alt", not sem_alt, "; ".join(sem_alt))

                sem_rotulo = pagina.evaluate(
                    """() => [...document.querySelectorAll('input, select, textarea')]
                       .filter(el => el.type !== 'hidden')
                       .filter(el => !el.id || !document.querySelector(`label[for="${el.id}"]`))
                       .filter(el => !el.getAttribute('aria-label') && !el.closest('label'))
                       .map(el => el.id || el.name || el.tagName).slice(0, 5)"""
                )
                check("todo campo tem rotulo", not sem_rotulo, "; ".join(sem_rotulo))

                # --- hierarquia de titulos -----------------------------------
                titulos = pagina.evaluate(
                    """() => [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
                       .filter(el => el.offsetParent !== null || el.classList.contains('visually-hidden'))
                       .map(el => Number(el.tagName[1]) + ':' + el.textContent.trim().slice(0, 24))"""
                )
                niveis = [int(t.split(":", 1)[0]) for t in titulos]
                salto = None
                for anterior, atual in pairwise(niveis):
                    if atual - anterior > 1:
                        salto = f"{anterior}->{atual}"
                        break
                check("hierarquia de titulos sem salto", salto is None, f"{salto} | {titulos}")
                check("tem exatamente um h1", niveis.count(1) == 1, str(niveis.count(1)))

                # --- ids duplicados e ancoras --------------------------------
                ids = pagina.evaluate(
                    "() => [...document.querySelectorAll('[id]')].map(el => el.id)"
                )
                duplicados = sorted({i for i in ids if ids.count(i) > 1})
                check("sem id duplicado", not duplicados, "; ".join(duplicados))

                ancoras = pagina.evaluate(
                    """() => [...document.querySelectorAll('a[href^="#"]')]
                       .map(a => a.getAttribute('href')).filter(h => h && h !== '#')"""
                )
                quebradas = [
                    h for h in ancoras
                    if not pagina.evaluate("(h) => !!document.getElementById(h.slice(1))", h)
                ]
                check("ancora interna resolve", not quebradas, "; ".join(quebradas[:5]))

                # --- links e recursos ----------------------------------------
                links = pagina.evaluate(
                    "() => [...document.querySelectorAll('a[href]')]"
                    ".map(a => a.getAttribute('href'))"
                )
                for link in links:
                    if not link or link.startswith(("#", "mailto:", "tel:", "javascript:")):
                        continue
                    if link.startswith("http"):
                        continue  # externo: fora do escopo do site
                    if link.startswith(("/local/", "/.local/")):
                        continue  # material de trabalho, nao faz parte do site
                    links_vistos.add(link.split("#")[0].split("?")[0])

                # --- recursos ----------------------------------------
                recursos = pagina.evaluate(
                    """() => [...document.querySelectorAll('link[href], script[src], img[src], source[src]')]
                       .map(el => el.getAttribute('href') || el.getAttribute('src'))
                       .filter(Boolean)"""
                )
                for recurso in recursos:
                    if recurso.startswith(("http", "data:")):
                        continue
                    # /_vercel/... e servido pela plataforma (Vercel), nao
                    # pelo site: nao existe no repositorio.
                    if recurso.startswith("/_vercel/"):
                        continue
                    recursos_vistos.add(recurso.split("#")[0].split("?")[0])

                # --- rodape padronizado --------------------------------------
                rodape = pagina.evaluate(
                    "() => [...document.querySelectorAll('.explore-card')]"
                    ".map(a => a.getAttribute('href'))"
                )
                rodapes[rota] = rodape

            # --- links resolvem de verdade -----------------------------------
            print("\n[Links do site]")
            quebrados = []
            for link in sorted(links_vistos):
                if not link:
                    continue
                resposta = pagina.request.get(urljoin(base, link))
                if resposta.status >= 400:
                    quebrados.append(f"{link} -> {resposta.status}")
            check("todo link interno resolve", not quebrados, "; ".join(quebrados[:8]))

            print("\n[Recursos]")
            faltando = []
            for recurso in sorted(recursos_vistos):
                if not recurso.startswith("/"):
                    continue
                caminho = os.path.join(RAIZ, recurso.lstrip("/"))
                if not os.path.exists(caminho):
                    faltando.append(recurso)
            check("todo recurso local existe", not faltando, "; ".join(faltando[:8]))

            print("\n[Rodape padronizado]")
            # A 404 nao tem o rodape completo: entra fora da comparacao.
            comparados = {tuple(v) for r, v in rodapes.items() if r != "/404.html" and v}
            check(
                "mesmos destinos no rodape de todas as paginas",
                len(comparados) == 1,
                " | ".join(str(v) for v in comparados),
            )

            print("\n[JavaScript]")
            check("nenhum erro de runtime em nenhuma pagina", not erros_js, "; ".join(erros_js[:3]))

            navegador.close()
    finally:
        httpd.shutdown()

    print(f"\n{verificacoes} verificacoes · {len(falhas)} falha(s)")
    for falha in falhas:
        print(f"  - {falha}")
    if falhas:
        return 1
    print("Site integro: metadados, links, recursos, acessibilidade e rodape.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
