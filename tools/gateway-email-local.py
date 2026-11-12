#!/usr/bin/env python3
"""Gateway de e-mail local: o PC despacha o e-mail que a VPS pede.

Por que existe: a VPS nao sai por SMTP (a rede do datacenter bloqueia as
portas 25/465/587), mas ela fala HTTPS na 443 sem problema. O transporte
`api` da API e exatamente um POST no formato do Resend:

    POST <MAIL_API_URL>
    authorization: Bearer <MAIL_API_KEY>
    {"from": "...", "to": ["..."], "subject": "...", "text": "...", "reply_to": "..."}

Este script e esse endpoint: recebe o POST e entrega a mensagem pelo SMTP do
Gmail, usando a senha de app. A VPS chega ate aqui por um tunel SSH inverso
(`ssh -R`), entao nada e exposto na internet e o PC so escuta em 127.0.0.1.

Configuracao (nada disso vai para o git):

    GATEWAY_TOKEN=...   token que a VPS apresenta (Bearer)
    GMAIL_USER=...      conta que envia (vizin.oos@gmail.com)
    GMAIL_PASS=...      senha de app de 16 caracteres, sem espacos
    GATEWAY_PORT=8789   porta local (padrao)

Retentativa (opcional, os padroes ja servem):

    ENVIO_TENTATIVAS=5           tentativas por mensagem
    ENVIO_ORCAMENTO=19           segundos no total (a VPS desiste em 20 s)
    ENVIO_TIMEOUT_TENTATIVA=2.5  segundos por tentativa

Uso:
    python3 tools/gateway-email-local.py
    python3 tools/gateway-email-local.py --testar   # manda um e-mail de teste
"""

import argparse
import email.utils
import hmac
import json
import os
import sys
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("GATEWAY_TOKEN", "").strip()
GMAIL_USER = os.environ.get("GMAIL_USER", "").strip()
GMAIL_PASS = os.environ.get("GMAIL_PASS", "").strip().replace(" ", "")
HOST = os.environ.get("GATEWAY_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("GATEWAY_PORT", "8789"))
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))

# A entrega (SMTP + retentativa) e compartilhada com tools/puxar-fila-email.py.
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
from email_envio import FalhaEnvio, enviar_com_retry  # noqa: E402,F401


def log(mensagem: str) -> None:
    print("[gateway] %s %s" % (time.strftime("%H:%M:%S"), mensagem), flush=True)


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "vizin-mail-gateway/1"

    # ----------------------------------------------------------- utilidades

    def responder(self, status: int, corpo: dict) -> None:
        dados = json.dumps(corpo).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, formato: str, *args) -> None:  # noqa: A003
        log("http " + (formato % args))

    # ------------------------------------------------------------- handlers

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            self.responder(200, {"ok": True, "smtp": SMTP_HOST, "porta": PORT})
            return
        self.responder(404, {"message": "rota desconhecida"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/emails":
            self.responder(404, {"message": "rota desconhecida"})
            return

        if not TOKEN:
            self.responder(500, {"message": "GATEWAY_TOKEN nao definido no gateway"})
            return

        enviado = self.headers.get("authorization", "")
        token = enviado[7:] if enviado.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(token, TOKEN):
            log("recusado: token invalido")
            self.responder(401, {"message": "token invalido"})
            return

        try:
            tamanho = int(self.headers.get("content-length", "0"))
            carga = json.loads(self.rfile.read(tamanho).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.responder(400, {"message": "corpo invalido"})
            return

        try:
            destinatarios = carga.get("to") or []
            if isinstance(destinatarios, str):
                destinatarios = [destinatarios]
            remetente = carga.get("from") or "vizin.Os <%s>" % GMAIL_USER
            assunto = carga.get("subject") or ""
            texto = carga.get("text") or ""
            resposta = carga.get("reply_to") or carga.get("replyTo")
            identificador, tentativas = self.enviar(
                remetente, destinatarios, assunto, texto, resposta
            )
        except Exception as erro:  # noqa: BLE001
            log("falha no envio: %s: %s" % (type(erro).__name__, erro))
            self.responder(502, {"message": "%s: %s" % (type(erro).__name__, erro)})
            return

        log(
            "enviado para %s (assunto: %s) em %d tentativa(s)"
            % (", ".join(destinatarios), assunto[:60], tentativas)
        )
        self.responder(200, {"id": identificador, "message": "ok", "tentativas": tentativas})

    # --------------------------------------------------------------- envio

    def enviar(
        self,
        remetente: str,
        destinatarios: list,
        assunto: str,
        texto: str,
        resposta: str | None,
    ) -> tuple[str, int]:
        if not destinatarios:
            raise ValueError("nenhum destinatario")
        if not GMAIL_USER or not GMAIL_PASS:
            raise ValueError("GMAIL_USER/GMAIL_PASS nao definidos")

        nome, endereco = email.utils.parseaddr(remetente)
        if not endereco:
            remetente = "vizin.Os <%s>" % GMAIL_USER

        mensagem = EmailMessage()
        mensagem["From"] = remetente
        mensagem["To"] = ", ".join(destinatarios)
        mensagem["Subject"] = assunto
        if resposta:
            mensagem["Reply-To"] = resposta
        mensagem.set_content(texto)

        return enviar_com_retry(mensagem)


def teste() -> int:
    """Manda um e-mail de teste para a propria conta do gateway."""
    if not GMAIL_USER or not GMAIL_PASS:
        print("GMAIL_USER/GMAIL_PASS nao definidos", file=sys.stderr)
        return 2
    mensagem = EmailMessage()
    mensagem["From"] = "vizin.Os <%s>" % GMAIL_USER
    mensagem["To"] = GMAIL_USER
    mensagem["Subject"] = "vizin.Os — teste do gateway de e-mail"
    mensagem.set_content(
        "Teste do gateway local: o PC conseguiu sair pelo SMTP do Gmail.\n"
        "Se voce leu isto, o caminho VPS -> tunel -> PC -> Gmail esta de pe."
    )
    identificador, tentativas = enviar_com_retry(mensagem)
    print(
        "e-mail de teste enviado para %s (id %s, %d tentativa(s))"
        % (GMAIL_USER, identificador, tentativas)
    )
    return 0


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--testar", action="store_true", help="manda um e-mail de teste e sai")
    opcoes = analisador.parse_args()

    if opcoes.testar:
        return teste()

    if not TOKEN:
        print("GATEWAY_TOKEN nao definido", file=sys.stderr)
        return 2
    if not GMAIL_USER or not GMAIL_PASS:
        print("GMAIL_USER/GMAIL_PASS nao definidos", file=sys.stderr)
        return 2

    log("escutando em http://%s:%d/emails (SMTP %s:%d)" % (HOST, PORT, SMTP_HOST, SMTP_PORT))
    servidor = ThreadingHTTPServer((HOST, PORT), GatewayHandler)
    servidor.daemon_threads = True
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        log("encerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
