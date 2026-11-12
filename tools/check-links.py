#!/usr/bin/env python3
"""Rasteja o site como um usuário e checa se todo link funciona.

Começa em `/`, segue todos os links e recursos internos (`/`, `/documento`,
`/painel`, ...) e abre cada um no navegador. URLs externas (Play Store,
Instagram, etc.) são ignoradas — só o que é servido por nós é verificado.

O navegador é usado de verdade porque a hospedagem pública (InfinityFree /
page.gd) coloca uma verificação de JavaScript antes de mostrar a página: um
`curl` puro veria apenas a tela de verificação e todas as URLs pareceriam
quebradas. Também por isso os redirecionamentos são conferidos no servidor
(`/criadores` -> `/afiliados/`), e não simulados aqui.

Uso:
    python3 tools/check-links.py https://vizin-os.page.gd
    python3 tools/check-links.py http://127.0.0.1:8099
"""

from __future__ import annotations

import sys
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 45_000

# Caminhos que devem responder 404 (página que não existe).
NAO_EXISTE = ["/pagina-que-nao-existe-xyz", "/nao-existe/tampouco"]


class LinkCollector(HTMLParser):
    """Coleta href/src de links, scripts, imagens e formulários."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for attribute in ("href", "src"):
            value = attrs.get(attribute)
            if value:
                self.urls.append(value)


def is_internal(url: str, base: str) -> bool:
    if url.startswith(("mailto:", "tel:", "javascript:", "data:", "#", "/_vercel/")):
        # /_vercel/insights/* só existe quando o site é servido pela Vercel
        # (Web Analytics): no InfinityFree e na VPS o caminho não existe.
        return False
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return True
    return parsed.netloc == urlparse(base).netloc


def normalize(url: str, base: str) -> str | None:
    absolute = urljoin(base, url)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return absolute.split("#")[0]


def main() -> int:
    base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/") + "/"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright é necessário para conferir as páginas (pip install playwright)", file=sys.stderr)
        return 2

    visited: set[str] = set()
    failures: list[tuple[str, str, str]] = []
    checked = 0

    print(f"Rastreando {base}")
    with sync_playwright() as playwright:
        navegador = playwright.chromium.launch(args=["--no-sandbox"])
        contexto = navegador.new_context(locale="pt-BR", viewport={"width": 1366, "height": 900})
        pagina = contexto.new_page()

        # A primeira visita resolve a verificação de JavaScript do host.
        pagina.goto(base, wait_until="domcontentloaded", timeout=60_000)
        pagina.wait_for_timeout(2500)

        queue: deque[str] = deque([base])
        for caminho in NAO_EXISTE:
            queue.append(urljoin(base, caminho))

        while queue:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            try:
                resposta = pagina.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
                pagina.wait_for_timeout(900)
                status = resposta.status if resposta else 0
                final = pagina.url
                tipo = (resposta.headers.get("content-type", "") if resposta else "").lower()
                corpo = pagina.content() if "html" in tipo else ""
            except Exception as erro:  # noqa: BLE001
                status, final, tipo, corpo = 0, url, "", str(erro)

            checked += 1
            caminho = urlparse(url).path or "/"

            if caminho in NAO_EXISTE:
                # Uma página que não existe tem de mostrar a página de erro.
                texto = pagina.inner_text("body") if status else ""
                tem_erro = any(
                    marca in texto.lower()
                    for marca in ("não encontrada", "nao encontrada", "not found", "404", "página não existe")
                )
                if status in (404, 410) or tem_erro:
                    print(f"  ok    {status or '404'}  {caminho} (página de erro)")
                else:
                    failures.append((caminho, str(status), texto[:120]))
                    print(f"  ERRO  {status or 'sem resposta'}  {caminho} (esperava página de erro)")
                continue

            if status != 200:
                failures.append((caminho, str(status), ""))
                print(f"  ERRO  {status or 'sem resposta'}  {caminho}")
                continue

            redirecionou = final.rstrip("/") != url.rstrip("/")
            print(f"  ok    200  {caminho}" + (f"  -> {urlparse(final).path}" if redirecionou else ""))
            pagina.goto(base, wait_until="domcontentloaded", timeout=60_000)
            pagina.wait_for_timeout(1200)

            if "html" not in tipo:
                continue
            collector = LinkCollector()
            try:
                collector.feed(corpo)
            except Exception:  # HTML quebrado não deve derrubar o rastreio.
                pass
            for raw in collector.urls:
                if not is_internal(raw, url):
                    continue
                resolved = normalize(raw, url)
                if resolved and resolved not in visited:
                    queue.append(resolved)

        contexto.close()
        navegador.close()

    print("")
    print(f"{checked} URLs internas verificadas · {len(failures)} falha(s)")
    if failures:
        print("")
        for caminho, status, detalhe in failures:
            print(f"  - {caminho} -> {status} {detalhe}".rstrip())
        return 1
    print("OK: todo link interno responde 200 e as páginas inexistentes mostram o erro.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
