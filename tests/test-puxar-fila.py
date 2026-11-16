#!/usr/bin/env python3
"""Teste do puxador da fila (PC), sem rede e sem Gmail.

Sobe uma API falsa em 127.0.0.1 que implementa `claim` e `result`, importa o
puxador e confere:

1. o lote e pedido com o token certo;
2. cada mensagem e montada com remetente, destinatario, assunto e Reply-To;
3. sucesso vira `sent`, erro permanente vira `failed` e erro transitorio
   esgotado vira `retry`;
4. o modo `--uma-vez` termina sozinho.

Uso:
    python3 tests/test-puxar-fila.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "tools" / "puxar-fila-email.py"

TOKEN = "token-do-teste"
lotes: list[list[dict]] = [
    [
        {
            "id": "aaa111",
            "to": "um@exemplo.com",
            "from": "vizin.Os <vizin.oos@gmail.com>",
            "reply_to": "afiliado@exemplo.com",
            "subject": "Convite",
            "text": "corpo do convite",
            "attempts": 1,
        },
        {
            "id": "bbb222",
            "to": "falha@exemplo.com",
            "from": "vizin.Os <vizin.oos@gmail.com>",
            "subject": "Convite",
            "text": "corpo",
            "attempts": 1,
        },
        {
            "id": "ccc333",
            "to": "rede@exemplo.com",
            "from": "vizin.Os <vizin.oos@gmail.com>",
            "subject": "Convite",
            "text": "corpo",
            "attempts": 1,
        },
    ],
]
claims: list[dict] = []
resultados: list[tuple[str, str, dict]] = []


class FakeQueue(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:  # silencio
        return

    def responder(self, status: int, corpo: dict) -> None:
        dados = json.dumps(corpo).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self) -> None:  # noqa: N802
        tamanho = int(self.headers.get("content-length", "0"))
        corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        autoria = self.headers.get("authorization", "")
        if self.path == "/mail/queue/claim":
            claims.append({"authorization": autoria, "body": corpo})
            lote = lotes.pop(0) if lotes else []
            self.responder(200, {"ok": True, "emails": lote})
            return
        if self.path.startswith("/mail/queue/") and self.path.endswith("/result"):
            identificador = self.path.split("/")[3]
            resultados.append((autoria, identificador, corpo))
            self.responder(200, {"ok": True, "status": corpo.get("status")})
            return
        self.responder(404, {"ok": False, "error": "rota desconhecida"})


servidor = ThreadingHTTPServer(("127.0.0.1", 0), FakeQueue)
porta = servidor.server_address[1]
thread = threading.Thread(target=servidor.serve_forever, daemon=True)
thread.start()

os.environ["MAIL_QUEUE_URL"] = f"http://127.0.0.1:{porta}"
os.environ["MAIL_QUEUE_TOKEN"] = TOKEN
os.environ["GMAIL_USER"] = "vizin.oos@gmail.com"
os.environ["GMAIL_PASS"] = "senha-de-teste-123"
os.environ["ARQ_ENV"] = str(RAIZ / ".nao-existe.env")

especificacao = importlib.util.spec_from_file_location("puxar_fila_email", ORIGEM)
if especificacao is None or especificacao.loader is None:
    print("nao consegui carregar tools/puxar-fila-email.py")
    raise SystemExit(1)
fila = importlib.util.module_from_spec(especificacao)
especificacao.loader.exec_module(fila)

enviadas: list = []
chamadas_envio = {"n": 0}


def envio_falso(mensagem):
    chamadas_envio["n"] += 1
    enviadas.append(mensagem)
    destino = mensagem["To"]
    if destino == "falha@exemplo.com":
        raise fila.FalhaEnvio("SMTPAuthenticationError: 535", 1, permanente=True)
    if destino == "rede@exemplo.com":
        raise fila.FalhaEnvio("TimeoutError: sem resposta", 5, permanente=False)
    return "id-da-mensagem", 2


fila.enviar_com_retry = envio_falso

falhas: list[str] = []
total = 0


def check(nome: str, condicao: bool, detalhe: str = "") -> None:
    global total
    total += 1
    if condicao:
        print(f"  ok    {nome}")
    else:
        sufixo = f" — {detalhe}" if detalhe else ""
        print(f"  FALHOU {nome}{sufixo}")
        falhas.append(nome)


def main() -> int:
    sys.argv = ["puxar-fila-email.py", "--uma-vez"]
    codigo = fila.main()

    check("termina com codigo 0 no --uma-vez", codigo == 0, str(codigo))
    check("pediu o lote uma vez", len(claims) == 1, str(len(claims)))
    check(
        "mandou o token no cabecalho",
        claims and claims[0]["authorization"] == f"Bearer {TOKEN}",
        str(claims[0]["authorization"]) if claims else "sem claim",
    )
    check(
        "pediu o lote padrao",
        claims and claims[0]["body"].get("limit") == fila.LOTE,
        str(claims[0]["body"]) if claims else "",
    )

    check("tentou enviar as 3 mensagens", chamadas_envio["n"] == 3, str(chamadas_envio["n"]))

    primeira = enviadas[0] if enviadas else None
    check("montou o destinatario", primeira is not None and primeira["To"] == "um@exemplo.com")
    check("montou o assunto", primeira is not None and primeira["Subject"] == "Convite")
    check(
        "montou o Reply-To",
        primeira is not None and primeira["Reply-To"] == "afiliado@exemplo.com",
    )
    check(
        "montou o corpo",
        primeira is not None and "corpo do convite" in primeira.get_content(),
    )
    check(
        "manteve o From do servidor",
        primeira is not None and "vizin.Os" in str(primeira["From"]),
    )

    por_id = {identificador: (autoria, corpo) for autoria, identificador, corpo in resultados}
    check("reportou as 3 mensagens", len(resultados) == 3, str(len(resultados)))
    check(
        "sucesso vira sent com provider_id",
        por_id.get("aaa111", (None, {}))[1].get("status") == "sent"
        and por_id.get("aaa111", (None, {}))[1].get("provider_id") == "id-da-mensagem",
        str(por_id.get("aaa111")),
    )
    check(
        "erro permanente vira failed",
        por_id.get("bbb222", (None, {}))[1].get("status") == "failed"
        and "535" in str(por_id.get("bbb222", (None, {}))[1].get("error")),
        str(por_id.get("bbb222")),
    )
    check(
        "erro transitorio esgotado vira retry",
        por_id.get("ccc333", (None, {}))[1].get("status") == "retry"
        and "TimeoutError" in str(por_id.get("ccc333", (None, {}))[1].get("error")),
        str(por_id.get("ccc333")),
    )
    check(
        "todos os resultados usaram o token",
        all(autoria == f"Bearer {TOKEN}" for autoria, _, _ in resultados),
    )

    servidor.shutdown()
    servidor.server_close()

    print()
    if falhas:
        print(f"FALHOU: {len(falhas)} de {total} verificacoes")
        for item in falhas:
            print(f"  - {item}")
        return 1
    print(f"OK: {total}/{total} verificacoes do puxador passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())