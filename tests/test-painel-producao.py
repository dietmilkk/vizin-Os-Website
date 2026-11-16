#!/usr/bin/env python3
"""Testa o painel público (/painel) contra a API que está no ar.

Sobe o site estático na máquina, abre /painel no Chromium e confere o que uma
pessoa vê quando usa a página de verdade: se o painel consegue números da API
pública, em que modo de coleta está e se há erro em tela.

Duas situations são aceitas (e ambas sãoinformadas):

* "dados completos" — a VPS já publica GET /stats/public: o painel mostra o
  detalhamento do servidor;
* "dados públicos" — a VPS ainda não publica essa rota: o painel mostra só o
  status público real (saúde, latência, versão, módulos, beacons) e avisa que
  o detalhamento completo ainda não está publicado.

Se nem a rota completa nem as rotas públicas responderem, o teste falha: aí o
panel está mesmo sem dados e isso precisa aparecer.

Uso:
    python3 tests/test-painel-producao.py [http://127.0.0.1:8099]

Requer Playwright com Chromium.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = (sys.argv[1] if len(sys.argv) > 1 else "").rstrip("/")

failures: list[str] = []
checks = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}" + (f" -> {detail}" if detail else ""))
        failures.append(label)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, process: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"O servidor do site encerrou (código {process.returncode}).")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return
        except OSError:
            time.sleep(0.3)
    raise SystemExit("O servidor do site não subiu.")


def main() -> int:
    site_process = None
    port = free_port()
    base = BASE or f"http://127.0.0.1:{port}"

    if not BASE:
        site_process = subprocess.Popen(
            [shutil.which("python3") or "python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_for_health(port, site_process)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            console_errors: list[str] = []
            ignorados: list[str] = []

            def registrar_console(message):
                if message.type != "error":
                    return
                texto = message.text
                url = (message.location or {}).get("url", "") or ""
                # No modo público, a sondagem de /stats/public responde 404 de
                # propósito: o navegador registra isso como erro de rede.
                # A rota /_vercel/insights/* (Web Analytics) faz o mesmo fora
                # da Vercel, onde a rota não existe.
                if (
                    "/stats/public" in url
                    or "/stats/public" in texto
                    or "/_vercel/insights/" in url
                    or "/_vercel/insights/" in texto
                ):
                    ignorados.append(texto)
                    return
                console_errors.append(texto)

            page.on("console", registrar_console)
            page.on("pageerror", lambda error: console_errors.append(str(error)))

            print(f"Site: {base}/painel\n")
            page.goto(f"{base}/painel/", wait_until="domcontentloaded")
            page.wait_for_function(
                "() => { const el = document.getElementById('painelStatusTexto');"
                " if (!el) return false;"
                " const t = el.textContent || '';"
                " return t.startsWith('Atualizado') || t === 'Sem dados no momento'; }",
                timeout=30_000,
            )

            status = page.inner_text("#painelStatusTexto").strip()
            erro_visivel = page.locator("#painelErro").is_visible()

            print("Estado visto pelo usuário")
            print(f"  status : {status}")
            print(f"  erro   : {'visível' if erro_visivel else 'oculto'}")
            print()

            check("a página não fica em 'Carregando'", status != "Carregando…", status)
            check("o painel não termina em erro", not erro_visivel, page.inner_text("#painelErro"))
            check("a barra de status é curta", len(status) <= 40, status)
            check(
                "o detalhamento do servidor aparece",
                page.inner_text("#painelCpu").strip() != "—",
                page.inner_text("#painelCpu"),
            )
            check(
                "as contas aparecem",
                page.inner_text("#painelContas").strip() != "—",
                page.inner_text("#painelContas"),
            )

            print("\nCelular (390 px)")
            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
            )
            mobile_page = mobile.new_page()
            mobile_page.goto(f"{base}/painel/", wait_until="domcontentloaded")
            mobile_page.wait_for_function(
                "() => { const el = document.getElementById('painelStatusTexto');"
                " if (!el) return false;"
                " const t = el.textContent || '';"
                " return t.startsWith('Atualizado') || t === 'Sem dados no momento'; }",
                timeout=30_000,
            )
            overflow = mobile_page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            check("não há rolagem horizontal no celular", overflow <= 1, f"excesso de {overflow}px")
            invasores = mobile_page.evaluate(
                """(limite) => {
                    const maus = [];
                    for (const el of document.querySelectorAll('.panel-status *')) {
                      const r = el.getBoundingClientRect();
                      if (r.width === 0 && r.height === 0) continue;
                      if (r.right > limite + 1 || r.left < -1) {
                        maus.push(el.tagName + '.' + (el.className || ''));
                      }
                    }
                    return maus.slice(0, 5);
                }""",
                mobile_page.evaluate("() => document.documentElement.clientWidth"),
            )
            check("a barra de status cabe na tela do celular", not invasores, "; ".join(invasores))
            mobile.close()

            if console_errors:
                print("\nErros de console")
                for error in console_errors:
                    print(f"  - {error}")
            if ignorados:
                print("\nErros esperados (sondagem de /stats/public)")
                for error in ignorados:
                    print(f"  - {error}")
            check("nenhum erro de console", not console_errors, "; ".join(console_errors[:3]))

            context.close()
            browser.close()
    finally:
        if site_process:
            site_process.terminate()
            try:
                site_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                site_process.kill()

    print("")
    print(f"{checks} verificações · {len(failures)} falha(s)")
    if failures:
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("OK: o painel mostra dados reais da API pública.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
