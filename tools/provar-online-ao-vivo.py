#!/usr/bin/env python3
"""Prova que o numero de "dispositivos online agora" e real e ao vivo.

Cria uma conta de teste na VPS de producao (chave aleatoria, heartbeat
assinado como o app faz), confere que o contador publico sobe e depois remove
a conta de teste, deixando o servico como estava.
"""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

API = "https://api.188.166.156.109.sslip.io"
SSH = [
    "ssh",
    "-i",
    "/home/user/Downloads/app/.local/vps/id_ed25519",
    "-o",
    "UserKnownHostsFile=/home/user/Downloads/site/deploy/known_hosts",
    "-o",
    "StrictHostKeyChecking=yes",
    "root@188.166.156.109",
]

SCRIPT = """
import { generateKeyPairSync, sign } from 'node:crypto';

const api = process.argv[2];
const { publicKey, privateKey } = generateKeyPairSync('ed25519');
const raw = publicKey.export({ format: 'der', type: 'spki' }).subarray(-32);
const pubkey = raw.toString('hex');
const timestamp = Math.floor(Date.now() / 1000);
const contexto = `vizinhança/account/heartbeat/v1:${pubkey}:${timestamp}`;
const assinatura = sign(null, Buffer.from(contexto, 'utf8'), privateKey).toString('hex');
const resposta = await fetch(`${api}/account/heartbeat`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ pubkey, timestamp, signature: assinatura }),
});
const texto = await resposta.text();
console.log(JSON.stringify({ pubkey, status: resposta.status, corpo: texto.slice(0, 120) }));
"""


def stats() -> dict:
    with urllib.request.urlopen(f"{API}/stats/public", timeout=20) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def main() -> int:
    antes = stats()["accounts"]
    print(f"antes:  online_now = {antes['online_now']}  (janela de {antes['online_window_seconds']}s)")

    with tempfile.TemporaryDirectory() as pasta:
        script = Path(pasta) / "heartbeat.mjs"
        script.write_text(SCRIPT, encoding="utf-8")
        resultado = subprocess.run(
            ["node", str(script), API], capture_output=True, text=True, timeout=120
        )
    if resultado.returncode != 0:
        print("FALHA no heartbeat:", resultado.stderr.strip()[:300])
        return 1
    dados = json.loads(resultado.stdout.strip().splitlines()[-1])
    print(f"heartbeat: HTTP {dados['status']} · {dados['corpo']}")
    pubkey = dados["pubkey"]

    depois = stats()["accounts"]
    print(f"depois: online_now = {depois['online_now']}")

    subprocess.run(
        SSH
        + [
            "python3 -c "
            + repr(
                "import sqlite3;"
                "c=sqlite3.connect('/var/lib/vizin-api/vizin.sqlite');"
                f"c.execute('DELETE FROM accounts WHERE pubkey=?',('{pubkey}',));"
                "c.commit();print('conta de teste removida')"
            )
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    final = stats()["accounts"]
    print(f"limpo:  online_now = {final['online_now']}")

    problemas = []
    if depois["online_now"] != antes["online_now"] + 1:
        problemas.append("o contador nao subiu com o heartbeat")
    if final["online_now"] != antes["online_now"]:
        problemas.append("o contador nao voltou ao valor inicial")
    if problemas:
        print("FALHA: " + "; ".join(problemas))
        return 1
    print("OK: o contador de dispositivos online e real e sobe e desce com o uso do app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
