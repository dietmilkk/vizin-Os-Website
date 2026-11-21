#!/usr/bin/env python3
"""Puxa a fila de e-mail da VPS e entrega pelo Gmail.

A VPS guarda os convites em uma fila (tabela `mail_outbox`). Este script
pergunta por HTTPS, com token, se ha mensagens; entrega cada uma pelo SMTP do
Gmail (com retentativa) e devolve o resultado. O PC nao expoe porta nenhuma:
so faz conexoes de saida.

Enquanto nao ha nada, dorme. Se a VPS estiver fora do ar, tenta de novo com
espera crescente (ate 60 s) e nunca desiste sozinho.

Configuracao (lida de `.deploy-gmail.env` ou do ambiente):

    GATEWAY_TOKEN ou MAIL_QUEUE_TOKEN   token compartilhado com a VPS
    MAIL_QUEUE_URL                      padrao https://api.188.166.156.109.sslip.io
    FILA_INTERVALO                      segundos entre consultas (padrao 15)
    FILA_LOTE                           mensagens por lote (padrao 5, maximo 20)
    FILA_TIMEOUT                        segundos por requisicao (padrao 25)

Uso:
    python3 tools/puxar-fila-email.py            # fica rodando
    python3 tools/puxar-fila-email.py --uma-vez  # um lote e sai (diagnostico)
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQ_ENV = Path(os.environ.get("ARQ_ENV", RAIZ / ".deploy-gmail.env"))


def carregar_env(caminho: Path) -> None:
    """Le KEY=VALOR sem executar o arquivo como shell."""
    try:
        linhas = caminho.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


if ARQ_ENV.exists():
    carregar_env(ARQ_ENV)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from email_envio import FalhaEnvio, enviar_com_retry

URL_FILA = os.environ.get(
    "MAIL_QUEUE_URL", "https://api.188.166.156.109.sslip.io"
).rstrip("/")
TOKEN = (
    os.environ.get("MAIL_QUEUE_TOKEN")
    or os.environ.get("GATEWAY_TOKEN")
    or ""
).strip()
INTERVALO = float(os.environ.get("FILA_INTERVALO", "15"))
LOTE = max(1, min(int(os.environ.get("FILA_LOTE", "5")), 20))
TIMEOUT = float(os.environ.get("FILA_TIMEOUT", "25"))

PARAR = False


def log(mensagem: str) -> None:
    print("[fila] {} {}".format(time.strftime("%H:%M:%S"), mensagem), flush=True)


def parar(*_argumentos) -> None:
    global PARAR
    PARAR = True


def dormir(segundos: float) -> None:
    """Dorme em fatias de 1 s para atender o SIGTERM na hora."""
    fim = time.monotonic() + max(0.0, segundos)
    while not PARAR and time.monotonic() < fim:
        time.sleep(min(1.0, fim - time.monotonic()))


def postar(url: str, corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo or {}).encode("utf-8")
    pedido = urllib.request.Request(url, data=dados, method="POST")
    pedido.add_header("authorization", "Bearer " + TOKEN)
    pedido.add_header("content-type", "application/json")
    pedido.add_header("accept", "application/json")
    with urllib.request.urlopen(pedido, timeout=TIMEOUT) as resposta:
        texto = resposta.read().decode("utf-8", "replace")
    return json.loads(texto) if texto.strip() else {}


def buscar_lote() -> list[dict]:
    dados = postar(
        URL_FILA + "/mail/queue/claim",
        {"limit": LOTE, "client": "pc"},
    )
    emails = dados.get("emails")
    return emails if isinstance(emails, list) else []


def reportar(item_id: str, status: str, provider_id: str | None = None, erro: str | None = None) -> None:
    corpo: dict = {"status": status}
    if provider_id:
        corpo["provider_id"] = provider_id
    if erro:
        corpo["error"] = erro[:300]
    postar(URL_FILA + "/mail/queue/" + urllib.parse.quote(item_id) + "/result", corpo)


def montar(item: dict) -> EmailMessage:
    usuario = os.environ.get("GMAIL_USER", "").strip()
    remetente = str(item.get("from") or f"vizin.Os <{usuario}>")
    _nome, endereco = parseaddr(remetente)
    if not endereco:
        remetente = f"vizin.Os <{usuario}>"

    destinatario = str(item.get("to") or "").strip()
    if not destinatario:
        raise ValueError("mensagem sem destinatario")

    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem["Subject"] = str(item.get("subject") or "")
    resposta = item.get("reply_to")
    if resposta:
        mensagem["Reply-To"] = str(resposta)
    mensagem.set_content(str(item.get("text") or ""))
    return mensagem


def entregar(item: dict) -> bool:
    """Entrega um item e reporta o resultado. Devolve False se voltou a fila."""
    identificador = str(item.get("id") or "")
    if not identificador:
        return True

    try:
        mensagem = montar(item)
    except Exception as erro:  # noqa: BLE001 - mensagem invalida vira falha reportada
        log(f"mensagem invalida {identificador[:8]}: {erro}")
        try:
            reportar(identificador, "failed", erro=f"{type(erro).__name__}: {erro}")
        except Exception as falha:  # noqa: BLE001 - falha ao reportar a falha: seguir
            log(f"nao consegui reportar a falha: {falha}")
        return False

    try:
        enviado, tentativas = enviar_com_retry(mensagem)
    except FalhaEnvio as erro:
        destino = str(item.get("to") or "?")
        if erro.permanente:
            log(f"falha permanente para {destino}: {erro}")
            try:
                reportar(identificador, "failed", erro=str(erro))
            except Exception as falha:  # noqa: BLE001 - falha ao reportar a falha: seguir
                log(f"nao consegui reportar a falha: {falha}")
            return False
        log(
            f"tentativas esgotadas para {destino} ({erro}); volta para a fila"
        )
        try:
            reportar(identificador, "retry", erro=str(erro))
        except Exception as falha:  # noqa: BLE001 - falha ao reportar a falha: seguir
            log(f"nao consegui devolver para a fila: {falha}")
        return False

    destino = str(item.get("to") or "?")
    try:
        reportar(identificador, "sent", provider_id=enviado)
    except Exception as falha:  # noqa: BLE001 - e-mail enviado; reportar e melhor esforco
        # O e-mail saiu; se o report falhar, o item volta para a fila depois
        # do tempo de reclamacao e pode ser entregue de novo.
        log(f"enviado para {destino}, mas o resultado nao foi reportado: {falha}")
        return False
    log(f"enviado para {destino} em {tentativas} tentativa(s)")
    return True


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--uma-vez", action="store_true", help="processa um lote e sai"
    )
    opcoes = analisador.parse_args()

    if not TOKEN:
        print("GATEWAY_TOKEN/MAIL_QUEUE_TOKEN nao definido", file=sys.stderr)
        return 2
    if not os.environ.get("GMAIL_USER") or not os.environ.get("GMAIL_PASS"):
        print("GMAIL_USER/GMAIL_PASS nao definidos", file=sys.stderr)
        return 2

    signal.signal(signal.SIGTERM, parar)
    signal.signal(signal.SIGINT, parar)
    log("fila ligada em {} (conta {})".format(URL_FILA, os.environ.get("GMAIL_USER")))

    espera = 5.0
    while not PARAR:
        try:
            lote = buscar_lote()
        except urllib.error.HTTPError as erro:
            if erro.code in (401, 403):
                log(f"token recusado pela VPS (HTTP {erro.code}); confira GATEWAY_TOKEN")
            else:
                log(f"VPS respondeu HTTP {erro.code}; nova tentativa em {espera:.0f}s")
            dormir(espera)
            espera = min(espera * 2, 60.0)
            continue
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as erro:
            log(f"VPS nao respondeu ({erro}); nova tentativa em {espera:.0f}s")
            dormir(espera)
            espera = min(espera * 2, 60.0)
            continue

        espera = 5.0
        if not lote:
            if opcoes.uma_vez:
                log("fila vazia")
                return 0
            dormir(INTERVALO)
            continue

        log(f"{len(lote)} e-mail(s) na fila")
        voltou = False
        for item in lote:
            if PARAR:
                break
            if not entregar(item):
                voltou = True
        if opcoes.uma_vez:
            return 0
        if voltou:
            # Evita um laco apertado quando a rede esta ruim: o item volta
            # para a fila e sera reclamado de novo.
            dormir(5)

    log("encerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())