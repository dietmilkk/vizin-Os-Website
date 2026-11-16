#!/usr/bin/env python3
"""Gera capturas do painel público (desktop e celular) para conferência visual."""

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
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/vizin-painel-shots")

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
    OUT.mkdir(parents=True, exist_ok=True)
    data_dir = Path(tempfile.mkdtemp(prefix="vizin-shot-"))
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

            desktop = browser.new_context(viewport={"width": 1280, "height": 1000}, device_scale_factor=2)
            desktop.route("**/assets/config.js", apontar_para_api_local)
            page = desktop.new_page()
            page.goto(f"{BASE}/painel", wait_until="networkidle")
            page.wait_for_function(
                "() => document.getElementById('painelStatusTexto')?.textContent?.startsWith('Atualizado')",
                timeout=20_000,
            )
            page.wait_for_timeout(600)
            page.screenshot(path=str(OUT / "painel-desktop.png"), full_page=True)
            print(f"desktop -> {OUT / 'painel-desktop.png'}")

            mobile = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )
            mobile.route("**/assets/config.js", apontar_para_api_local)
            mobile_page = mobile.new_page()
            mobile_page.goto(f"{BASE}/painel", wait_until="networkidle")
            mobile_page.wait_for_function(
                "() => document.getElementById('painelStatusTexto')?.textContent?.startsWith('Atualizado')",
                timeout=20_000,
            )
            mobile_page.wait_for_timeout(600)
            mobile_page.screenshot(path=str(OUT / "painel-mobile.png"), full_page=True)
            print(f"mobile  -> {OUT / 'painel-mobile.png'}")

            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(data_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
