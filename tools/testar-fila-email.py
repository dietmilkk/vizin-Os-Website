#!/usr/bin/env python3
"""Testa a fila de e-mail de ponta a ponta, sem criar afiliado nem gastar cota.

Insere uma mensagem de teste direto em `mail_outbox` na VPS (sem `hunter_id`,
portanto sem cota e sem contato reservado), espera o PC do dono puxar e
entregar pelo Gmail, e apaga a linha no fim.

O destinatário padrão é o `GMAIL_USER` de `.deploy-gmail.env` (a própria conta
que envia). Para outro endereço: `--para alguem@exemplo.com`.

Uso:
    python3 tools/testar-fila-email.py
    python3 tools/testar-fila-email.py --para outro@exemplo.com
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENV_PC = RAIZ / ".deploy-gmail.env"
CHAVE = Path("/home/user/Downloads/app/.local/vps/id_ed25519")
KNOWN = Path("/home/user/Downloads/app/.local/vps/known_hosts")
VPS = "root@188.166.156.109"
SAUDE = "https://api.188.166.156.109.sslip.io/health"
BANCO = "/var/lib/vizin-api/vizin.sqlite"

INSERIR = r'''
import json
import sqlite3
import sys
import time
import uuid

con = sqlite3.connect("/var/lib/vizin-api/vizin.sqlite", timeout=15)
identificador = str(uuid.uuid4())
agora = int(time.time())
con.execute(
    """INSERT INTO mail_outbox
         (id, kind, hunter_id, hunter_code, outreach_id, recipient, sender,
          reply_to, subject, body, status, attempts, created_at)
       VALUES (?, 'teste', NULL, NULL, NULL, ?, ?, NULL, ?, ?, 'pending', 0, ?)""",
    (
        identificador,
        sys.argv[1],
        "vizin.Os <" + sys.argv[2] + ">",
        "Teste da fila de e-mail",
        "Mensagem de teste do modo fila: se voce recebeu isto, o PC puxou a fila da VPS e entregou pelo Gmail.",
        agora,
    ),
)
con.commit()
print(identificador)
'''

ESTADO = r'''
import json
import sqlite3
import sys

con = sqlite3.connect("/var/lib/vizin-api/vizin.sqlite", timeout=15)
linha = con.execute(
    "SELECT status, attempts, last_error, provider_id FROM mail_outbox WHERE id = ?",
    (sys.argv[1],),
).fetchone()
if linha is None:
    print(json.dumps({"status": None}))
else:
    print(json.dumps({
        "status": linha[0],
        "attempts": linha[1],
        "error": linha[2],
        "provider_id": linha[3],
    }))
'''

APAGAR = r'''
import sqlite3
import sys

con = sqlite3.connect("/var/lib/vizin-api/vizin.sqlite", timeout=15)
con.execute("DELETE FROM mail_outbox WHERE id = ?", (sys.argv[1],))
con.commit()
print("linha de teste apagada")
'''


def ler_conta_padrao() -> str:
    for linha in ENV_PC.read_text(encoding="utf-8").splitlines():
        if linha.startswith("GMAIL_USER="):
            return linha.split("=", 1)[1].strip()
    raise SystemExit("GMAIL_USER nao encontrado em .deploy-gmail.env")


def ssh(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={KNOWN}",
            "-i",
            str(CHAVE),
            VPS,
            *argumentos,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )


def enviar_script(nome: str, conteudo: str) -> None:
    local = Path("/tmp") / nome
    local.write_text(conteudo, encoding="utf-8")
    resultado = subprocess.run(
        [
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            f"UserKnownHostsFile={KNOWN}",
            "-i",
            str(CHAVE),
            str(local),
            f"{VPS}:/tmp/{nome}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if resultado.returncode != 0:
        raise SystemExit(resultado.stderr)


def saude() -> dict:
    with urllib.request.urlopen(SAUDE, timeout=15) as resposta:
        return json.loads(resposta.read().decode())


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--para",
        default=None,
        help="destinatario (padrao: a conta do GMAIL_USER)",
    )
    analisador.add_argument(
        "--espera", type=int, default=120, help="segundos de espera (padrao 120)"
    )
    opcoes = analisador.parse_args()

    if not CHAVE.exists():
        print(f"chave SSH ausente: {CHAVE}", file=sys.stderr)
        return 1

    conta = ler_conta_padrao()
    destino = (opcoes.para or conta).strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", destino):
        print(f"destinatario invalido: {destino}", file=sys.stderr)
        return 2

    enviar_script("teste_fila_inserir.py", INSERIR)
    enviar_script("teste_fila_estado.py", ESTADO)
    enviar_script("teste_fila_apagar.py", APAGAR)

    inserido = ssh(
        "python3 /tmp/teste_fila_inserir.py "
        + shlex.quote(destino)
        + " "
        + shlex.quote(conta)
    )
    if inserido.returncode != 0:
        print(inserido.stderr, file=sys.stderr)
        return 1
    identificador = inserido.stdout.strip()
    print(f"mensagem de teste na fila: {identificador}")
    print(f"destino: {destino}")

    inicio = time.monotonic()
    estado = {"status": "pending"}
    try:
        while time.monotonic() - inicio < opcoes.espera:
            consulta = ssh(f"python3 /tmp/teste_fila_estado.py {identificador}")
            if consulta.returncode == 0 and consulta.stdout.strip():
                estado = json.loads(consulta.stdout)
            if estado.get("status") in ("sent", "failed"):
                break
            fila = saude().get("mail", {}).get("queue", {})
            print(
                "  fila: pendentes=%s enviando=%s enviados=%s falhas=%s"
                % (
                    fila.get("pending"),
                    fila.get("sending"),
                    fila.get("sent"),
                    fila.get("failed"),
                )
            )
            time.sleep(5)
    finally:
        apagado = ssh(f"python3 /tmp/teste_fila_apagar.py {identificador}")
        if apagado.returncode != 0:
            print(apagado.stderr, file=sys.stderr)

    print()
    if estado.get("status") == "sent":
        print(
            "OK: o PC puxou a fila e o Gmail aceitou a mensagem "
            f"(id {estado.get('provider_id')}, {estado.get('attempts')} tentativa(s))."
        )
        return 0
    print(f"FALHOU: estado final {estado.get('status')} — {estado.get('error')}")
    return 1


if __name__ == "__main__":
    sys.exit(main())