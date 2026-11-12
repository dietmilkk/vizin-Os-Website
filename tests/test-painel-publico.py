#!/usr/bin/env python3
"""Teste do painel público (/painel) em um navegador de verdade.

Abre a página publicada no Chromium, aponta a API para uma VPS local com
dados de teste e confere o que uma pessoa realmente vê: números preenchidos,
etiquetas de região e de criadores contatados, barra de status atualizada e
nenhum resíduo do placeholder "—".

Também confere o comportamento em tela estreita (celular), porque o painel é
usado no telefone.

Uso:
    python3 tests/test-painel-publico.py [http://127.0.0.1:8099]

Requer `bun` (ou `npx --yes bun`) e Playwright com Chromium.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from seed_stats import (  # noqa: E402
    CONTAS_ATIVAS_1H,
    CONTAS_NOVAS_24H,
    CONTAS_NOVAS_7D,
    CONTAS_ONLINE,
    CONTAS_TOTAL,
    accounts_ativas,
)

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(os.environ.get("VIZIN_APP_DIR", ROOT.parent / "app")).resolve()
VPS_ENTRY = APP_DIR / "vps" / "src" / "index.ts"
SEED_SCRIPT = Path(__file__).resolve().parent / "lib" / "seed_stats.py"
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8099").rstrip("/")

DAY = 86_400
BEACONS = json.dumps(
    [
        {
            "id": "vps-br",
            "url": "https://beacon.br.example.com",
            "pubkey": "0" * 64,
            "geohash": "g8u4y",
        },
        {
            "id": "vps-global",
            "url": "https://beacon.global.example.com",
            "pubkey": "0" * 64,
            "geohash": "*",
        },
    ]
)

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


def bun_command() -> list[str]:
    bun = shutil.which("bun")
    if bun:
        return [bun]
    if shutil.which("npx"):
        return ["npx", "--yes", "bun"]
    raise SystemExit("É preciso ter `bun` (ou `npx --yes bun`) instalado.")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, process: subprocess.Popen, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last = "sem resposta"
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"A VPS encerrou antes de ficar pronta (código {process.returncode}).")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except Exception as error:  # noqa: BLE001 — a API ainda está subindo.
            last = str(error)
        time.sleep(0.5)
    raise SystemExit(f"A VPS não respondeu /health em {timeout:.0f}s ({last}).")


def main() -> int:
    if not VPS_ENTRY.exists():
        raise SystemExit(f"Não encontrei a entrada da VPS em {VPS_ENTRY} (use VIZIN_APP_DIR).")

    def apontar_para_api_local(route):
        """Serve o config.js com a API local, sem editar o repositório."""
        response = route.fetch()
        corpo = response.text()
        corpo = re.sub(r"apiUrl:\s*'[^']*'", f"apiUrl: '{api_url}'", corpo)
        route.fulfill(
            response=response,
            body=corpo,
            headers={**response.headers, "content-type": "application/javascript; charset=utf-8"},
        )

    data_dir = Path(tempfile.mkdtemp(prefix="vizin-painel-web-"))
    port = free_port()
    process = subprocess.Popen(
        bun_command() + ["run", str(VPS_ENTRY)],
        cwd=str(APP_DIR / "vps"),
        env={
            **os.environ,
            "PORT": str(port),
            "DATA_DIR": str(data_dir),
            "BEACONS_JSON": BEACONS,
            "ACCOUNT_INACTIVE_SECONDS": str(365 * DAY),
            "ACCOUNT_DELETE_SECONDS": str(365 * DAY),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        wait_for_health(port, process)
        seed = subprocess.run(
            ["python3", str(SEED_SCRIPT), str(data_dir / "vizin.sqlite")],
            capture_output=True,
            text=True,
        )
        if seed.returncode != 0:
            raise SystemExit(f"Falha ao popular o banco: {seed.stderr}")

        api_url = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{api_url}/stats/public", timeout=15) as response:
            api_data = json.loads(response.read().decode("utf-8"))

        print(f"API de teste: {api_url}")
        print(f"Site: {BASE}\n")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            # Aponta a API do site para a VPS local sem editar o repositório.
            context.route("**/assets/config.js", apontar_para_api_local)
            page = context.new_page()

            console_errors: list[str] = []

            def escutar_console(message) -> None:
                # A rota /_vercel/insights/* (Web Analytics) só existe quando o site
                # é servido pela Vercel. Fora dela o <script defer> responde 404 e o
                # navegador registra isso como erro de console — a mensagem de texto
                # não traz a URL; ela está em message.location.
                if message.type != "error":
                    return
                local = (message.location or {}).get("url", "") or ""
                if "/_vercel/insights/" in message.text or "/_vercel/insights/" in local:
                    return
                console_errors.append(message.text)

            page.on("console", escutar_console)
            page.on("pageerror", lambda error: console_errors.append(str(error)))

            print("Carga da página (navegador de verdade)")
            page.goto(f"{BASE}/painel", wait_until="networkidle")
            page.wait_for_function(
                "() => document.getElementById('painelStatusTexto')"
                "?.textContent?.startsWith('Atualizado')",
                timeout=20_000,
            )

            status = page.inner_text("#painelStatusTexto")
            check("a barra de status anuncia a atualização", status.startswith("Atualizado"), status)

            erro = page.locator("#painelErro")
            check("nenhum aviso de erro na tela", not erro.is_visible())

            print("\nNúmeros na tela")
            for element_id, expected in [
                ("painelOnline", str(CONTAS_ONLINE)),
                ("painelAtivos1h", str(CONTAS_ATIVAS_1H)),
                ("painelAtivos24", str(accounts_ativas(DAY))),
                ("painelAtivos7", str(accounts_ativas(7 * DAY))),
                ("painelAtivos30", str(accounts_ativas(30 * DAY))),
                ("painelRegioes", "2"),
                ("painelBeacons", "2"),
                ("painelContas", str(CONTAS_TOTAL)),
                ("painelUsernames", "1"),
                ("painelApagadas", "1"),
                ("painelCofres", "2"),
                ("painelCriadores", "2"),
                ("painelAfiliados", "1"),
                ("painelContatados", "3"),
                ("painelNovas24h", str(CONTAS_NOVAS_24H)),
                ("painelNovas7d", str(CONTAS_NOVAS_7D)),
            ]:
                text = page.inner_text(f"#{element_id}").strip()
                check(f"#{element_id} mostra {expected}", text == expected, f"veio '{text}'")

            taxa = round(accounts_ativas(7 * DAY) / CONTAS_TOTAL * 100)
            texto_taxa = page.inner_text("#painelTaxa").strip()
            check(f"#painelTaxa mostra {taxa}%", texto_taxa == f"{taxa}%", f"veio '{texto_taxa}'")

            anel = page.inner_text("#painelAnelLegenda").strip()
            check(
                "#painelAnelLegenda explica a proporção",
                anel == f"{accounts_ativas(7 * DAY):,} de {CONTAS_TOTAL:,} contas".replace(",", "."),
                f"veio '{anel}'",
            )

            indicacoes = page.inner_text("#painelIndicacoes").strip()
            check("#painelIndicacoes mostra ativas de total", indicacoes == "1 de 2", f"veio '{indicacoes}'")

            saques = page.inner_text("#painelSaques").strip()
            check("#painelSaques soma criadores e afiliados", saques == "2", f"veio '{saques}'")

            saques_criadores = page.inner_text("#painelSaquesCriadores").strip()
            check("#painelSaquesCriadores mostra 1", saques_criadores == "1", f"veio '{saques_criadores}'")
            saques_afiliados = page.inner_text("#painelSaquesAfiliados").strip()
            check("#painelSaquesAfiliados mostra 1", saques_afiliados == "1", f"veio '{saques_afiliados}'")

            print("\nCampos que precisam de valor real")
            for element_id in [
                "painelUptime",
                "painelMemoria",
                "painelCpu",
                "painelBanco",
                "painelRuntime",
                "painelLatencia",
                "painelContaRecente",
                "painelOnlineLegenda",
                "painelDesde",
                "painelComissoes",
                "painelHeapLegenda",
                "painelUsernamesLegenda",
                "painelCofresLegenda",
                "painelIndicacoesLegenda",
            ]:
                text = page.inner_text(f"#{element_id}").strip()
                check(f"#{element_id} não ficou com '—'", text != "—" and text != "", f"veio '{text}'")

            runtime = page.inner_text("#painelRuntime").strip()
            check("#painelRuntime mostra a versão do Bun", runtime.startswith("Bun "), runtime)

            print("\nEtiquetas")
            regioes = page.locator("#painelRegioesLista .panel-regiao").all_inner_texts()
            check("as regiões aparecem como etiquetas", len(regioes) == 2, str(regioes))
            check("a região global é identificada", any("Global" in item for item in regioes), str(regioes))
            check("a região do beacon aparece", "g8u4y" in regioes, str(regioes))

            contatos = page.locator("#painelContatosLista .panel-regiao").all_inner_texts()
            check("os criadores contatados viram etiquetas", len(contatos) == 3, str(contatos))
            check("as etiquetas mostram o @ e não a URL", all(item.startswith("@") for item in contatos), str(contatos))
            check(
                "o @ público do criador contatado aparece",
                "@contato_um" in contatos,
                str(contatos),
            )

            print("\nAtualização automática")
            botao = page.locator("#painelAtualizar")
            check("não há botão manual de atualizar", botao.count() == 0, f"{botao.count()} botão(ões)")
            estado = page.inner_text("#painelStatusTexto").strip()
            check("a barra de status anuncia a atualização", estado.startswith("Atualizado"), estado)

            print("\nNavegação a partir do painel")
            for href, seletor in [
                ("/documento", "a[href='/documento']"),
                ("/moderacao", "a[href='/moderacao']"),
                ("/afiliados", "a[href='/afiliados']"),
                ("/", "a[href='/']"),
            ]:
                quantidade = page.locator(seletor).count()
                check(f"o painel tem link para {href}", quantidade > 0, f"{quantidade} link(s)")

            links = page.evaluate(
                "() => Array.from(document.querySelectorAll('a[href]'))"
                ".map((a) => a.getAttribute('href'))"
            )
            internos = sorted({link for link in links if link and link.startswith("/")})
            check(
                "o painel alcança todas as páginas internas",
                {"/", "/documento", "/moderacao", "/afiliados"}.issubset(set(internos)),
                str(internos),
            )

            print("\nCelular (390 px)")
            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=3,
                is_mobile=True,
                has_touch=True,
            )
            mobile.route("**/assets/config.js", apontar_para_api_local)
            mobile_page = mobile.new_page()
            mobile_page.goto(f"{BASE}/painel", wait_until="networkidle")
            mobile_page.wait_for_function(
                "() => document.getElementById('painelStatusTexto')"
                "?.textContent?.startsWith('Atualizado')",
                timeout=20_000,
            )
            check(
                "o painel carrega no celular",
                mobile_page.inner_text("#painelContas").strip() == str(CONTAS_TOTAL),
                mobile_page.inner_text("#painelContas"),
            )
            overflow = mobile_page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            check("não há rolagem horizontal no celular", overflow <= 1, f"excesso de {overflow}px")

            if console_errors:
                print("\nErros de console")
                for error in console_errors:
                    print(f"  - {error}")

            check("nenhum erro de console", not console_errors, "; ".join(console_errors[:3]))

            mobile.close()
            context.close()
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(data_dir, ignore_errors=True)

    print("")
    print(f"{checks} verificações · {len(failures)} falha(s)")
    if failures:
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("OK: o painel público funciona no navegador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
