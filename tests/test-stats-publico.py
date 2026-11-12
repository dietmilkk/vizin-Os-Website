#!/usr/bin/env python3
"""Teste fim a fim do endpoint público de estatísticas (GET /stats/public).

Sobe a VPS real (Bun) em uma porta livre com um banco SQLite isolado,
popula o banco com dados realistas e confere:

1. o contrato HTTP e o formato pt-BR que o site consome;
2. as agregações (contas ativas, regiões, parceiros, cofres);
3. a garantia de privacidade — nenhum identificador de usuário, IP, e-mail,
   chave, valor individual ou conteúdo trafega na resposta pública.

Uso:
    python3 tests/test-stats-publico.py

Requer `bun` no PATH ou `npx --yes bun` disponível.
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
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from seed_stats import (  # noqa: E402
    ACCOUNTS,
    CONTAS_ATIVAS_1H,
    CONTAS_NOVAS_24H,
    CONTAS_NOVAS_7D,
    CONTAS_ONLINE,
    CONTAS_TOTAL,
    DAY,
    NOW,
    PUBLIC_CONTACT_URL,
    PUBLIC_HANDLE,
    SECRET_EMAIL,
    SECRET_IP,
    SECRET_PIX,
    SECRET_PUBKEY,
    SECRET_USERNAME,
    accounts_ativas,
    seed,
)

# Data de criação mais antiga e mais recente do cenário: o painel mostra a
# "conta mais recente", então o teste confere contra o mesmo seed.
CONTA_MAIS_ANTIGA = NOW - max(criado_ha for _, criado_ha, _ in ACCOUNTS)
CONTA_MAIS_RECENTE = NOW - min(criado_ha for _, criado_ha, _ in ACCOUNTS)

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(os.environ.get("VIZIN_APP_DIR", ROOT.parent / "app")).resolve()
VPS_ENTRY = APP_DIR / "vps" / "src" / "index.ts"

# Geohash válido (5 caracteres do alfabeto sem a/i/l/o) + beacon global.
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


def log(message: str) -> None:
    print(message, flush=True)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def bun_command() -> list[str]:
    bun = shutil.which("bun")
    if bun:
        return [bun]
    if shutil.which("npx"):
        return ["npx", "--yes", "bun"]
    raise SystemExit("É preciso ter `bun` (ou `npx --yes bun`) instalado para rodar este teste.")


def wait_for_health(port: int, process: subprocess.Popen, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/health"
    last_error = "sem resposta"
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"A VPS encerrou antes de ficar pronta (código {process.returncode}).")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = str(error)
        time.sleep(0.5)
    raise SystemExit(f"A VPS não respondeu /health em {timeout:.0f}s ({last_error}).")


def fetch_json(url: str) -> tuple[int, dict, bytes]:
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read()
        return response.status, json.loads(raw.decode("utf-8")), raw


def main() -> int:
    if not VPS_ENTRY.exists():
        raise SystemExit(f"Não encontrei a entrada da VPS em {VPS_ENTRY} (use VIZIN_APP_DIR).")

    data_dir = Path(tempfile.mkdtemp(prefix="vizin-stats-"))
    database = data_dir / "vizin.sqlite"
    port = free_port()
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if condition:
            log(f"  ok   {message}")
        else:
            failures.append(message)
            log(f"  FALHA {message}")

    log(f"VPS: {VPS_ENTRY}")
    log(f"Porta: {port} · dados em {data_dir}")

    process = subprocess.Popen(
        bun_command() + ["run", str(VPS_ENTRY)],
        cwd=str(APP_DIR / "vps"),
        env={
            **os.environ,
            "PORT": str(port),
            "DATA_DIR": str(data_dir),
            "BEACONS_JSON": BEACONS,
            # Mantém as contas do seed estáveis durante o teste.
            "ACCOUNT_INACTIVE_SECONDS": str(365 * DAY),
            "ACCOUNT_DELETE_SECONDS": str(365 * DAY),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        wait_for_health(port, process)
        log("API no ar (health ok)")

        seed(database)
        log("Banco populado com o cenário de teste")

        status, data, raw = fetch_json(f"http://127.0.0.1:{port}/stats/public")

        log("\nContrato HTTP")
        check(status == 200, f"responde 200 (veio {status})")
        check(data.get("ok") is True, "campo ok = true")
        check(isinstance(data.get("generated_at"), int), "generated_at é inteiro")

        log("\nServidor e consumo")
        server = data.get("server", {})
        check(isinstance(server.get("uptime_seconds"), int) and server["uptime_seconds"] >= 0, "uptime_seconds presente")
        # O uptime vem do inicio do SERVICO (persistido no banco), nao do processo.
        check(
            isinstance(server.get("service_started_at"), int)
            and abs(server["service_started_at"] - (NOW - 100 * DAY)) < 300,
            "service_started_at bate com o inicio do servico no banco",
        )
        check(
            abs(server["uptime_seconds"] - (NOW - server["service_started_at"])) < 300,
            "uptime_seconds mede o servico inteiro",
        )
        check(
            isinstance(server.get("process_uptime_seconds"), int)
            and server["process_uptime_seconds"] < server["uptime_seconds"],
            "process_uptime_seconds mede o processo atual (menor que o do servico)",
        )
        check(server.get("runtime") == "bun", "runtime = bun")
        check(bool(server.get("runtime_version")), "runtime_version presente")
        check(isinstance(server.get("cpu_percent"), (int, float)), "cpu_percent numérico")
        check(isinstance(server.get("memory_rss_bytes"), int) and server["memory_rss_bytes"] > 0, "memory_rss_bytes > 0")
        check(isinstance(server.get("memory_heap_used_bytes"), int), "memory_heap_used_bytes presente")
        check(isinstance(server.get("database_size_bytes"), int) and server["database_size_bytes"] > 0, "database_size_bytes > 0")

        log("\nContas")
        accounts = data.get("accounts", {})
        check(accounts.get("total") == CONTAS_TOTAL, f"total = {CONTAS_TOTAL} (veio {accounts.get('total')})")
        # Online agora: contas que mandaram sinal de vida na janela de 10 min.
        check(accounts.get("online_now") == CONTAS_ONLINE, f"online_now = {CONTAS_ONLINE} (veio {accounts.get('online_now')})")
        check(
            accounts.get("online_window_seconds") == 600,
            f"online_window_seconds = 600 (veio {accounts.get('online_window_seconds')})",
        )
        check(accounts.get("active_1h") == CONTAS_ATIVAS_1H, f"active_1h = {CONTAS_ATIVAS_1H} (veio {accounts.get('active_1h')})")
        check(accounts.get("active_24h") == accounts_ativas(DAY), f"active_24h = {accounts_ativas(DAY)} (veio {accounts.get('active_24h')})")
        check(accounts.get("active_7d") == accounts_ativas(7 * DAY), f"active_7d = {accounts_ativas(7 * DAY)} (veio {accounts.get('active_7d')})")
        check(accounts.get("active_30d") == accounts_ativas(30 * DAY), f"active_30d = {accounts_ativas(30 * DAY)} (veio {accounts.get('active_30d')})")
        check(accounts.get("with_username") == 1, f"with_username = 1 (veio {accounts.get('with_username')})")
        check(accounts.get("deleted_total") == 1, f"deleted_total = 1 (veio {accounts.get('deleted_total')})")
        check(abs(int(accounts.get("oldest_created_at", 0)) - CONTA_MAIS_ANTIGA) < 120, "oldest_created_at bate com a conta mais antiga")
        check(abs(int(accounts.get("newest_created_at", 0)) - CONTA_MAIS_RECENTE) < 120, "newest_created_at bate com a conta mais recente")
        check(accounts.get("new_24h") == CONTAS_NOVAS_24H, f"new_24h = {CONTAS_NOVAS_24H} (veio {accounts.get('new_24h')})")
        check(accounts.get("new_7d") == CONTAS_NOVAS_7D, f"new_7d = {CONTAS_NOVAS_7D} (veio {accounts.get('new_7d')})")

        log("\nRede")
        network = data.get("network", {})
        check(network.get("beacons") == 2, f"beacons = 2 (veio {network.get('beacons')})")
        check(network.get("regions") == ["*", "g8u4y"], f"regions = ['*', 'g8u4y'] (veio {network.get('regions')})")

        log("\nParceiros")
        partners = data.get("partners", {})
        check(partners.get("creators") == 2, f"creators = 2 (veio {partners.get('creators')})")
        check(partners.get("hunters") == 1, f"hunters = 1 (veio {partners.get('hunters')})")
        check(partners.get("creators_contacted") == 3, f"creators_contacted = 3 (veio {partners.get('creators_contacted')})")
        check(partners.get("referrals_total") == 2, f"referrals_total = 2 (veio {partners.get('referrals_total')})")
        check(partners.get("referrals_active") == 1, f"referrals_active = 1 (veio {partners.get('referrals_active')})")
        check(partners.get("earnings") == 1, f"earnings = 1 (veio {partners.get('earnings')})")
        check(partners.get("payouts_paid") == 1, f"payouts_paid = 1 (veio {partners.get('payouts_paid')})")
        check(partners.get("payouts_hunter_paid") == 1, f"payouts_hunter_paid = 1 (veio {partners.get('payouts_hunter_paid')})")
        contacts = partners.get("recent_contacts", [])
        check(isinstance(contacts, list) and len(contacts) == 3, f"recent_contacts = 3 itens (veio {len(contacts) if isinstance(contacts, list) else contacts})")
        if isinstance(contacts, list):
            handles = {str(contact.get("handle", "")) for contact in contacts}
            check(PUBLIC_HANDLE in handles, f"recent_contacts traz o @ público (veio {sorted(handles)})")
            check(all(str(contact.get("handle", "")).startswith("@") for contact in contacts), "todo contato vem com @ no início")
            links = {str(contact.get("contact_url") or "") for contact in contacts}
            check(PUBLIC_CONTACT_URL in links, "contato com link público traz contact_url")
            check(all(set(contact) <= {"handle", "contact_url", "platform", "contacted_at"} for contact in contacts), "recent_contacts só tem handle/contact_url/platform/contacted_at")

        log("\nCofres")
        vaults = data.get("vaults", {})
        check(isinstance(vaults, dict) and vaults.get("backups") == 2, f"vaults.backups = 2 (veio {vaults})")

        log("\nPrivacidade (o endpoint não pode vazar nada sensível)")
        text = raw.decode("utf-8")
        for secret, label in [
            (SECRET_PUBKEY, "chave pública de conta"),
            (SECRET_USERNAME, "username de conta"),
            (SECRET_PIX, "chave PIX"),
            (SECRET_EMAIL, "e-mail"),
            (SECRET_IP, "endereço IP"),
            ("cipher_a", "conteúdo de cofre"),
        ]:
            check(secret not in text, f"não expõe {label}")
        check("pubkey" not in text.lower(), "não expõe campo pubkey")
        check("pix_key" not in text.lower(), "não expõe campo pix_key")
        check("amount_cents" not in text.lower(), "não expõe valores individuais")
        check("203.0.113" not in text, "não expõe prefixo de IP")

        log("\nCache")
        request = urllib.request.Request(f"http://127.0.0.1:{port}/stats/public", method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                cache_control = response.headers.get("cache-control", "")
        except urllib.error.HTTPError:
            cache_control = ""
        check("max-age=30" in cache_control, f"cache-control público com max-age=30 (veio '{cache_control}')")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(data_dir, ignore_errors=True)

    log("")
    if failures:
        log(f"FALHOU: {len(failures)} verificação(ões)")
        for failure in failures:
            log(f"  - {failure}")
        return 1
    log("OK: todas as verificações do /stats/public passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
