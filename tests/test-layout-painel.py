#!/usr/bin/env python3
"""Auditoria de layout do painel público: mede a página real no navegador.

Confere que os cartões de estatística se alinham em grade, que nada estoura
a largura da viewport e que o espaçamento/legibilidade batem com o resto do
site (tipografia, contraste de fundo e estados de foco).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

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
    return ["npx", "--yes", "bun"]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, process: subprocess.Popen, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit("A VPS encerrou antes de ficar pronta.")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                if response.status == 200:
                    return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise SystemExit("A VPS não respondeu /health.")


def main() -> int:
    data_dir = Path(tempfile.mkdtemp(prefix="vizin-layout-"))
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
        subprocess.run(["python3", str(SEED_SCRIPT), str(data_dir / "vizin.sqlite")], check=True, capture_output=True)
        api_url = f"http://127.0.0.1:{port}"

        def apontar_para_api_local(route):
            response = route.fetch()
            corpo = response.text().replace("apiUrl: 'https://api.188.166.156.109.sslip.io'", f"apiUrl: '{api_url}'")
            route.fulfill(response=response, body=corpo, headers={**response.headers, "content-type": "application/javascript; charset=utf-8"})

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            for nome, viewport, mobile in [
                ("desktop", {"width": 1280, "height": 1000}, False),
                ("tablet", {"width": 820, "height": 1100}, False),
                ("celular", {"width": 390, "height": 844}, True),
            ]:
                print(f"\n{nome} ({viewport['width']}px)")
                context = browser.new_context(viewport=viewport, is_mobile=mobile, has_touch=mobile)
                context.route("**/assets/config.js", apontar_para_api_local)
                page = context.new_page()
                page.goto(f"{BASE}/painel", wait_until="networkidle")
                page.wait_for_function(
                    "() => document.getElementById('painelStatusTexto')?.textContent?.startsWith('Atualizado')",
                    timeout=20_000,
                )

                largura = page.evaluate("() => document.documentElement.clientWidth")
                estouro = page.evaluate(
                    "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
                )
                check(f"{nome}: sem rolagem horizontal", estouro <= 1, f"excesso de {estouro}px")

                # Nenhum elemento pode invadir a área do texto.
                invasores = page.evaluate(
                    """(limite) => {
                        const maus = [];
                        for (const el of document.querySelectorAll('main *')) {
                          const r = el.getBoundingClientRect();
                          if (r.width === 0 && r.height === 0) continue;
                          if (r.right > limite + 1 || r.left < -1) {
                            maus.push(el.tagName + '.' + (el.className || '') + ' [' +
                              Math.round(r.left) + '..' + Math.round(r.right) + ']');
                          }
                        }
                        return maus.slice(0, 5);
                    }""",
                    largura,
                )
                check(f"{nome}: nenhum elemento invade a viewport", not invasores, "; ".join(invasores))

                # A página é minimalista: nada de selo de modo, etiquetas ou aviso.
                for ausente in ["#painelModo", "#painelResumo", "#painelAviso"]:
                    check(
                        f"{nome}: {ausente} não existe mais no painel",
                        page.locator(ausente).count() == 0,
                    )

                # Grade de estatísticas: cartões da mesma linha com a mesma altura
                # e colunas consistentes (a última linha pode ser parcial).
                grade = page.evaluate(
                    """() => {
                        const grids = Array.from(document.querySelectorAll('.stats-grid'));
                        return grids.map((g) => {
                            const linhas = new Map();
                            for (const s of g.querySelectorAll('.stat')) {
                                const r = s.getBoundingClientRect();
                                const chave = Math.round(r.top);
                                if (!linhas.has(chave)) linhas.set(chave, []);
                                linhas.get(chave).push({ altura: Math.round(r.height), largura: Math.round(r.width) });
                            }
                            const grupos = Array.from(linhas.values());
                            return {
                                cartoes: g.querySelectorAll('.stat').length,
                                linhas: grupos.map((itens) => itens.length),
                                alturas: grupos.map((itens) => itens.map((i) => i.altura)),
                                larguras: grupos.map((itens) => itens.map((i) => i.largura)),
                            };
                        });
                    }"""
                )
                for indice, info in enumerate(grade):
                    for numero, alturas in enumerate(info["alturas"], start=1):
                        check(
                            f"{nome}: grade {indice + 1}, linha {numero} tem cartões do mesmo tamanho",
                            len(set(alturas)) == 1,
                            str(alturas),
                        )
                    larguras = info["larguras"]
                    if len(larguras) > 1 and all(len(linha) == len(larguras[0]) for linha in larguras):
                        check(
                            f"{nome}: grade {indice + 1} mantém a largura das colunas",
                            len({tuple(sorted(set(linha))) for linha in larguras}) == 1,
                            str(larguras),
                        )

                # Tipografia e legibilidade dos números.
                estilo = page.evaluate(
                    """() => {
                        const valor = document.querySelector('.stat .value');
                        const rotulo = document.querySelector('.stat .label');
                        const pegando = (el) => {
                            const c = getComputedStyle(el);
                            return {
                                tamanho: parseFloat(c.fontSize),
                                peso: parseFloat(c.fontWeight),
                                alturaLinha: c.lineHeight,
                                cor: c.color,
                                fundo: c.backgroundColor,
                            };
                        };
                        return {
                            valor: pegando(valor),
                            rotulo: pegando(rotulo),
                            corpo: pegando(document.body),
                        };
                    }"""
                )
                check(
                    f"{nome}: número do painel tem tamanho de destaque",
                    estilo["valor"]["tamanho"] >= 22,
                    f"{estilo['valor']['tamanho']}px",
                )
                check(
                    f"{nome}: número do painel tem peso de destaque",
                    int(estilo["valor"]["peso"]) >= 600,
                    str(estilo["valor"]["peso"]),
                )
                check(
                    f"{nome}: rótulo é menor que o número",
                    estilo["rotulo"]["tamanho"] < estilo["valor"]["tamanho"],
                    f"rótulo {estilo['rotulo']['tamanho']}px vs valor {estilo['valor']['tamanho']}px",
                )
                check(
                    f"{nome}: corpo usa a fonte do site",
                    "Comfortaa" in page.evaluate("() => getComputedStyle(document.body).fontFamily"),
                    page.evaluate("() => getComputedStyle(document.body).fontFamily"),
                )

                # Foco visível num elemento interativo do conteúdo (o
                # painel não tem mais botão manual de atualizar: ele se
                # atualiza sozinho a cada minuto).
                page.focus("main a.btn[href='/afiliados']")
                contorno = page.evaluate(
                    """() => {
                        const c = getComputedStyle(document.querySelector("main a.btn[href='/afiliados']"));
                        return {
                            contorno: `${c.outlineStyle} ${c.outlineWidth} ${c.outlineColor}`,
                            cor: c.outlineColor,
                            sombra: c.boxShadow,
                        };
                    }"""
                )
                tem_contorno = (
                    contorno["contorno"].split()[0] not in ("none", "")
                    and float(contorno["contorno"].split()[1].replace("px", "") or 0) >= 1
                )
                tem_sombra = contorno["sombra"] not in ("none", "")
                check(
                    f"{nome}: link do conteúdo tem foco visível",
                    tem_contorno or tem_sombra,
                    str(contorno),
                )

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
    print("OK: o layout do painel está consistente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
