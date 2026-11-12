#!/usr/bin/env python3
"""Envio pelo SMTP do Gmail com retentativa, compartilhado pelos scripts do PC.

O gateway HTTP (`gateway-email-local.py`) e o puxador da fila
(`puxar-fila-email.py`) usam este mesmo codigo: assim a regra de tentar de
novo e o orcamento de tempo nao divergem.

Configuracao (variaveis de ambiente, nunca no git):

    GMAIL_USER   conta que envia
    GMAIL_PASS   senha de app de 16 caracteres, sem espacos
    SMTP_HOST    padrao smtp.gmail.com
    SMTP_PORT    padrao 465 (TLS implicito)

Retentativa:

    ENVIO_TENTATIVAS=5           tentativas por mensagem
    ENVIO_ORCAMENTO=19           segundos no total
    ENVIO_TIMEOUT_TENTATIVA=2.5  segundos por tentativa
"""

from __future__ import annotations

import os
import smtplib
import time
import uuid
from email.message import EmailMessage

TENTATIVAS = max(1, int(os.environ.get("ENVIO_TENTATIVAS", "5")))
ORCAMENTO = float(os.environ.get("ENVIO_ORCAMENTO", "19"))
TIMEOUT_TENTATIVA = float(os.environ.get("ENVIO_TIMEOUT_TENTATIVA", "2.5"))
ESPERA_INICIAL = 0.3
ESPERA_MAXIMA = 2.0


class FalhaEnvio(Exception):
    """O envio falhou depois de esgotar as tentativas (ou de erro permanente)."""

    def __init__(self, mensagem: str, tentativas: int, permanente: bool = False):
        super().__init__(mensagem)
        self.tentativas = tentativas
        self.permanente = permanente


def erro_transitorio(erro: Exception) -> bool:
    """Vale a pena tentar de novo?

    Credencial errada e recurso nao suportado nao melhoram com repeticao.
    Queda de rede, timeout e resposta 4xx (limite de envio, greylisting)
    melhoram.
    """
    if isinstance(erro, smtplib.SMTPRecipientsRefused):
        # Cada destinatario tem o proprio codigo; 4xx e temporario.
        return any(400 <= codigo < 500 for codigo, _ in erro.recipients.values())
    if isinstance(erro, (smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError)):
        return False
    if isinstance(erro, smtplib.SMTPResponseException):
        return 400 <= erro.smtp_code < 500
    if isinstance(erro, ValueError):
        return False
    # Socket/TLS, desconexao e timeout: vale repetir.
    return isinstance(erro, (OSError, smtplib.SMTPException))


def entregar_smtp(mensagem: EmailMessage, timeout: float) -> str:
    """Uma unica transacao SMTP. Devolve o id do envio."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "465"))
    usuario = os.environ.get("GMAIL_USER", "").strip()
    senha = os.environ.get("GMAIL_PASS", "").strip().replace(" ", "")
    if not usuario or not senha:
        raise ValueError("GMAIL_USER/GMAIL_PASS nao definidos")

    with smtplib.SMTP_SSL(host, port, timeout=timeout) as servidor:
        servidor.login(usuario, senha)
        # O envelope MAIL FROM e a propria conta do Gmail: o servidor SMTP
        # recusa um remetente que nao seja a conta autenticada.
        servidor.send_message(mensagem, from_addr=usuario)
    return str(uuid.uuid4())


def enviar_com_retry(
    mensagem: EmailMessage,
    *,
    tentativas: int | None = None,
    orcamento: float | None = None,
    timeout_tentativa: float | None = None,
    dormir=time.sleep,
    relogio=time.monotonic,
) -> tuple[str, int]:
    """Entrega a mensagem, repetindo enquanto o erro for transitorio.

    Devolve `(id, tentativas_usadas)`. Levanta `FalhaEnvio` quando o erro e
    permanente ou quando esgota as tentativas ou o tempo total.
    """
    limite_tentativas = TENTATIVAS if tentativas is None else tentativas
    limite_tempo = ORCAMENTO if orcamento is None else orcamento
    limite_por_tentativa = (
        TIMEOUT_TENTATIVA if timeout_tentativa is None else timeout_tentativa
    )

    inicio = relogio()
    espera = ESPERA_INICIAL
    ultimo: Exception | None = None
    usadas = 0

    for numero in range(1, limite_tentativas + 1):
        restante = limite_tempo - (relogio() - inicio)
        if restante <= 0.5:
            break
        usadas = numero
        try:
            return entregar_smtp(mensagem, min(limite_por_tentativa, restante)), numero
        except Exception as erro:  # noqa: BLE001
            ultimo = erro
            if not erro_transitorio(erro):
                raise FalhaEnvio(
                    "%s: %s" % (type(erro).__name__, erro), numero, permanente=True
                ) from erro
            if numero >= limite_tentativas:
                break
            pausa = min(espera, max(0.0, limite_tempo - (relogio() - inicio) - 0.5))
            if pausa > 0:
                dormir(pausa)
            espera = min(espera * 2, ESPERA_MAXIMA)

    motivo = "%s: %s" % (type(ultimo).__name__, ultimo) if ultimo else "tempo esgotado"
    if usadas < limite_tentativas and ultimo is not None:
        motivo += " (orcamento de %.0fs esgotado)" % limite_tempo
    raise FalhaEnvio(motivo, usadas, permanente=False)