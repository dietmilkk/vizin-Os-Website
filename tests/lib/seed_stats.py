#!/usr/bin/env python3
"""Cenário de dados compartilhado pelos testes do painel público.

Cria as tabelas (quando ainda não existem) e popula um banco SQLite com um
cenário determinístico: contas ativas em várias janelas, regiões, parceiros,
indicações, comissões, saques e cofres.

Uso como biblioteca:
    from seed_stats import seed

Uso como comando:
    python3 tests/lib/seed-stats.py /caminho/vizin.sqlite
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

NOW = int(time.time())
DAY = 86_400
# Mesma janela usada pela VPS para "online agora" (ONLINE_WINDOW_SECONDS).
ONLINE_WINDOW = 10 * 60

# Segredos usados só no seed: nenhum deles pode aparecer na resposta pública.
SECRET_PUBKEY = "a" * 64
SECRET_USERNAME = "usuario_privado_x9"
SECRET_PIX = "pix_privado_999@example.com"
SECRET_EMAIL = "criador_privado@example.com"
SECRET_IP = "203.0.113.77"

# @ público de um criador contatado (informação pública, exibida no painel).
PUBLIC_HANDLE = "@contato_um"
PUBLIC_CONTACT_URL = "https://instagram.com/contato_um"

# Contas do cenário, com o instante do último sinal de vida. O painel conta
# as contas ativas por janela (24 h, 7 dias, 30 dias), então o mesmo dado
# serve para popular o banco e para o teste conferir o número na tela.
# Os instantes ficam no meio da janela (nunca no limite exato): a API conta
# alguns segundos depois do seed, e um valor colado na borda mudaria de
# janela a cada execução.
# (pubkey, criado há, visto há)
ACCOUNTS = [
    (SECRET_PUBKEY, 400 * DAY, 1_800),      # visto há 30 min (dentro de 1 h)
    ("b" * 64, 300 * DAY, 5 * DAY),          # visto há 5 dias
    ("c" * 64, 200 * DAY, 40 * DAY),         # visto há 40 dias (fora de 30 dias)
    ("d" * 64, 120 * DAY, 60),               # online agora
    ("e" * 64, 3 * DAY, 30),                 # online agora, cadastro de 3 dias
    ("f" * 64, 1_800, 15),                   # online agora, cadastro de hoje
]


def accounts_ativas(janela: int) -> int:
    """Quantas contas do cenário foram vistas dentro da janela (em segundos).

    É o mesmo cálculo que a VPS faz para o painel público, usado aqui para
    que o número esperado no teste nunca saia de sincronia com o seed.
    """
    return sum(1 for _, _, visto_ha in ACCOUNTS if visto_ha <= janela)


def accounts_novas(janela: int) -> int:
    """Quantas contas do cenário foram criadas dentro da janela (em segundos)."""
    return sum(1 for _, criado_ha, _ in ACCOUNTS if criado_ha <= janela)


CONTAS_TOTAL = len(ACCOUNTS)
CONTAS_ONLINE = accounts_ativas(ONLINE_WINDOW)
CONTAS_ATIVAS_1H = accounts_ativas(3_600)
CONTAS_NOVAS_24H = accounts_novas(DAY)
CONTAS_NOVAS_7D = accounts_novas(7 * DAY)

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  expires_at INTEGER
);
CREATE TABLE IF NOT EXISTS accounts (
  pubkey TEXT PRIMARY KEY,
  username TEXT,
  created_at INTEGER NOT NULL,
  last_seen INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  inactive_at INTEGER,
  delete_at INTEGER
);
CREATE TABLE IF NOT EXISTS account_tombstones (
  pubkey_hash TEXT PRIMARY KEY,
  deleted_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS creators (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  handle TEXT NOT NULL UNIQUE,
  pix_key TEXT,
  code TEXT NOT NULL UNIQUE,
  token_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  available_cents INTEGER NOT NULL DEFAULT 0,
  pending_cents INTEGER NOT NULL DEFAULT 0,
  withdrawn_cents INTEGER NOT NULL DEFAULT 0,
  hunter_id TEXT
);
CREATE TABLE IF NOT EXISTS hunters (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  handle TEXT NOT NULL UNIQUE,
  code TEXT NOT NULL UNIQUE,
  token_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  available_cents INTEGER NOT NULL DEFAULT 0,
  pending_cents INTEGER NOT NULL DEFAULT 0,
  withdrawn_cents INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS outreach_creators (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  handle TEXT NOT NULL,
  handle_normalized TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT 'outro',
  contact_url TEXT,
  notes TEXT,
  hunter_id TEXT NOT NULL,
  hunter_code TEXT NOT NULL,
  contacted_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_outreach_handle
  ON outreach_creators(handle_normalized);
CREATE TABLE IF NOT EXISTS referrals (
  pubkey TEXT PRIMARY KEY,
  creator_id TEXT NOT NULL,
  code TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  discount_percent INTEGER NOT NULL DEFAULT 20,
  commission_percent INTEGER NOT NULL DEFAULT 30,
  expires_at INTEGER
);
CREATE TABLE IF NOT EXISTS referral_earnings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creator_id TEXT NOT NULL,
  hunter_id TEXT,
  pubkey TEXT NOT NULL,
  payment_id TEXT NOT NULL UNIQUE,
  amount_cents INTEGER NOT NULL,
  commission_cents INTEGER NOT NULL,
  hunter_commission_cents INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS withdrawals (
  id TEXT PRIMARY KEY,
  creator_id TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'requested',
  pix_key TEXT,
  payer_email TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER,
  processed_at INTEGER,
  failure_reason TEXT,
  provider_id TEXT,
  provider_status TEXT,
  approved_by TEXT
);
CREATE TABLE IF NOT EXISTS hunter_withdrawals (
  id TEXT PRIMARY KEY,
  hunter_id TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'requested',
  pix_key TEXT,
  payer_email TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER,
  processed_at INTEGER,
  failure_reason TEXT,
  provider_id TEXT,
  provider_status TEXT,
  approved_by TEXT
);
CREATE TABLE IF NOT EXISTS vaults (
  pubkey TEXT PRIMARY KEY,
  ciphertext TEXT NOT NULL,
  version INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
"""


def seed(database: Path | str) -> None:
    """Cria o schema (se preciso) e popula o banco com o cenário de teste."""
    connection = sqlite3.connect(str(database))
    try:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO accounts (pubkey, username, created_at, last_seen, status) VALUES (?,?,?,?,'active')",
            [
                (
                    pubkey,
                    SECRET_USERNAME if pubkey == SECRET_PUBKEY else None,
                    NOW - criado_ha,
                    NOW - visto_ha,
                )
                for pubkey, criado_ha, visto_ha in ACCOUNTS
            ],
        )
        connection.execute(
            "INSERT INTO account_tombstones (pubkey_hash, deleted_at) VALUES (?,?)",
            ("f" * 64, NOW - 10 * DAY),
        )
        # O servico comecou ha 100 dias: o uptime do painel precisa mostrar
        # esse tempo, e nao o tempo de vida do processo.
        connection.execute(
            "INSERT OR REPLACE INTO kv (key, value, expires_at) VALUES (?,?,NULL)",
            ("meta:server_started_at", str(NOW - 100 * DAY)),
        )
        connection.executemany(
            "INSERT INTO creators (id, name, handle, pix_key, code, token_hash, created_at, hunter_id) VALUES (?,?,?,?,?,?,?,?)",
            [
                ("cr1", "Criadora Um", "criador_um", SECRET_PIX, "CODE1", "h1" * 32, NOW - 90 * DAY, "hu1"),
                ("cr2", "Criador Dois", "criador_dois", None, "CODE2", "h2" * 32, NOW - 20 * DAY, None),
            ],
        )
        connection.execute(
            "INSERT INTO hunters (id, name, handle, code, token_hash, created_at) VALUES (?,?,?,?,?,?)",
            ("hu1", "Afiliado Um", "afiliado_um", "HCODE", "h3" * 32, NOW - 60 * DAY),
        )
        # O handle é gravado sem '@' (como o registro Outreach faz no app).
        connection.executemany(
            """INSERT INTO outreach_creators
               (id, name, handle, handle_normalized, platform, contact_url, notes,
                hunter_id, hunter_code, contacted_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [
                ("ou1", "Contato Um", "contato_um", "contato_um", "instagram", PUBLIC_CONTACT_URL, None, "hu1", "HCODE", NOW - 5 * DAY, NOW - 5 * DAY),
                ("ou2", "Contato Dois", "contato_dois", "contato_dois", "tiktok", None, None, "hu1", "HCODE", NOW - 40 * DAY, NOW - 40 * DAY),
                ("ou3", "Contato Tres", "contato_tres", "contato_tres", "outro", None, None, "hu1", "HCODE", NOW - 120 * DAY, NOW - 120 * DAY),
            ],
        )
        connection.executemany(
            """INSERT INTO referrals
               (pubkey, creator_id, code, created_at, status, discount_percent, commission_percent, expires_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                ("d" * 64, "cr1", "CODE1", NOW - 10 * DAY, "active", 20, 30, None),
                ("e" * 64, "cr1", "CODE1", NOW - 200 * DAY, "active", 20, 30, NOW - 30 * DAY),
            ],
        )
        connection.execute(
            """INSERT INTO referral_earnings
               (creator_id, hunter_id, pubkey, payment_id, amount_cents, commission_cents, hunter_commission_cents, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("cr1", "hu1", "d" * 64, "pay_1", 10_000, 3_000, 1_000, NOW - 3 * DAY),
        )
        connection.execute(
            """INSERT INTO withdrawals
               (id, creator_id, amount_cents, status, pix_key, payer_email, created_at, processed_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("wd1", "cr1", 5_000, "paid", SECRET_PIX, SECRET_EMAIL, NOW - 15 * DAY, NOW - 14 * DAY),
        )
        connection.execute(
            """INSERT INTO hunter_withdrawals
               (id, hunter_id, amount_cents, status, pix_key, payer_email, created_at, processed_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("hwd1", "hu1", 2_500, "paid", SECRET_PIX, SECRET_EMAIL, NOW - 12 * DAY, NOW - 11 * DAY),
        )
        connection.executemany(
            "INSERT INTO vaults (pubkey, ciphertext, version, updated_at) VALUES (?,?,?,?)",
            [
                ("d" * 64, "cipher_a", 1, NOW - 2 * DAY),
                ("e" * 64, "cipher_b", 1, NOW - 1 * DAY),
            ],
        )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("uso: python3 tests/lib/seed-stats.py <caminho-do-banco.sqlite>")
    seed(Path(sys.argv[1]))
    print(f"seed aplicado em {sys.argv[1]}")
