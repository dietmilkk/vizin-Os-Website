#!/usr/bin/env python3
"""Teste da retentativa de envio, sem rede e sem SMTP.

O modulo `tools/email_envio.py` tenta entregar de novo quando o erro e
transitorio (queda de rede, timeout, resposta 4xx) e desiste na hora quando o
erro e permanente (credencial errada, destinatario inexistente). O tempo total
fica abaixo dos 20 s que o mailer da VPS esperava no modo push.

Uso:
    python3 tests/test-email-retry.py
"""

from __future__ import annotations

import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))

import email_envio as gateway  # noqa: E402

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


def mensagem() -> EmailMessage:
    item = EmailMessage()
    item["From"] = "vizin.Os <vizin.oos@gmail.com>"
    item["To"] = "alguem@example.com"
    item["Subject"] = "teste"
    item.set_content("corpo")
    return item


def sem_espera(_segundos: float) -> None:
    """Nao dorme de verdade nos testes."""


def entregar_sempre_falhando(erro: Exception, registro: list[float]):
    def entregar(_mensagem: EmailMessage, timeout: float) -> str:
        registro.append(timeout)
        raise erro

    return entregar


def main() -> int:
    print("Padroes")
    check("tenta 5 vezes por padrao", gateway.TENTATIVAS == 5, str(gateway.TENTATIVAS))
    check(
        "orcamento total cabe no timeout de 20 s da VPS",
        gateway.ORCAMENTO < 20,
        str(gateway.ORCAMENTO),
    )
    check(
        "timeout por tentativa e menor que o orcamento",
        gateway.TIMEOUT_TENTATIVA < gateway.ORCAMENTO,
    )

    print("\nSucesso na primeira tentativa")
    registro: list[float] = []
    gateway.entregar_smtp = lambda _m, t: (registro.append(t), "id-1")[1]
    identificador, tentativas = gateway.enviar_com_retry(
        mensagem(), dormir=sem_espera, relogio=lambda: 0.0
    )
    check("devolve o id do envio", identificador == "id-1")
    check("usa uma tentativa", tentativas == 1 and len(registro) == 1)

    print("\nFalha transitoria ate dar certo")
    registro = []
    dormidas: list[float] = []

    def falha_duas_vezes(_mensagem: EmailMessage, timeout: float) -> str:
        registro.append(timeout)
        if len(registro) < 3:
            raise TimeoutError("sem resposta do SMTP")
        return "id-3"

    gateway.entregar_smtp = falha_duas_vezes
    identificador, tentativas = gateway.enviar_com_retry(
        mensagem(), dormir=dormidas.append, relogio=lambda: 0.0
    )
    check("insiste ate a terceira tentativa", tentativas == 3 and len(registro) == 3)
    check("devolve o id quando finalmente entrega", identificador == "id-3")
    check(
        "espera crescente entre as tentativas",
        len(dormidas) == 2 and dormidas[0] < dormidas[1],
        str(dormidas),
    )

    print("\nEsgotou as 5 tentativas")
    registro = []
    gateway.entregar_smtp = entregar_sempre_falhando(OSError("rede fora"), registro)
    try:
        gateway.enviar_com_retry(mensagem(), dormir=sem_espera, relogio=lambda: 0.0)
        check("levanta FalhaEnvio", False, "nao levantou nada")
    except gateway.FalhaEnvio as erro:
        check("levanta FalhaEnvio", True)
        check("registra 5 tentativas", erro.tentativas == 5, str(erro.tentativas))
        check("tentou 5 vezes de verdade", len(registro) == 5, str(len(registro)))
        check("marca como transitoria", not erro.permanente)

    print("\nErro permanente nao repete")
    registro = []
    dormidas = []
    gateway.entregar_smtp = entregar_sempre_falhando(
        smtplib.SMTPAuthenticationError(535, b"5.7.8 credenciais invalidas"), registro
    )
    try:
        gateway.enviar_com_retry(mensagem(), dormir=dormidas.append, relogio=lambda: 0.0)
        check("credencial errada falha na hora", False, "nao levantou nada")
    except gateway.FalhaEnvio as erro:
        check("credencial errada falha na hora", erro.tentativas == 1)
        check("marca como permanente", erro.permanente)
        check("nao tentou de novo", len(registro) == 1 and not dormidas)

    print("\nResposta do servidor: 4xx repete, 5xx nao")
    registro = []
    gateway.entregar_smtp = entregar_sempre_falhando(
        smtplib.SMTPResponseException(451, b"4.7.0 tente mais tarde"), registro
    )
    try:
        gateway.enviar_com_retry(mensagem(), dormir=sem_espera, relogio=lambda: 0.0)
    except gateway.FalhaEnvio as erro:
        check("4xx (limite temporario) repete", erro.tentativas == 5, str(erro.tentativas))

    registro = []
    gateway.entregar_smtp = entregar_sempre_falhando(
        smtplib.SMTPResponseException(550, b"5.1.1 destinatario inexistente"), registro
    )
    try:
        gateway.enviar_com_retry(mensagem(), dormir=sem_espera, relogio=lambda: 0.0)
    except gateway.FalhaEnvio as erro:
        check("5xx (destinatario invalido) nao repete", erro.tentativas == 1)

    print("\nDestinatarios recusados")
    temporario = smtplib.SMTPRecipientsRefused(
        {"alguem@example.com": (450, b"4.2.0 caixa cheia")}
    )
    permanente = smtplib.SMTPRecipientsRefused(
        {"alguem@example.com": (550, b"5.1.1 nao existe")}
    )
    check("4xx por destinatario e transitorio", gateway.erro_transitorio(temporario))
    check("5xx por destinatario e permanente", not gateway.erro_transitorio(permanente))

    print("\nOrcamento total manda parar")
    tempo = [0.0]
    registro = []

    def lento(_mensagem: EmailMessage, timeout: float) -> str:
        registro.append(timeout)
        tempo[0] += 10.0
        raise OSError("rede muito lenta")

    gateway.entregar_smtp = lento
    try:
        gateway.enviar_com_retry(
            mensagem(), dormir=sem_espera, relogio=lambda: tempo[0]
        )
        check("para antes de estourar os 20 s", False, "nao levantou nada")
    except gateway.FalhaEnvio as erro:
        check("para antes de estourar os 20 s", erro.tentativas < 5, str(erro.tentativas))
        check("avisa que o orcamento acabou", "orcamento" in str(erro), str(erro))

    print("\nTimeout por tentativa respeita o tempo restante")
    registro = []
    gateway.entregar_smtp = lambda _m, t: (registro.append(t), "id-x")[1]
    gateway.enviar_com_retry(
        mensagem(), orcamento=1.2, timeout_tentativa=2.5, dormir=sem_espera, relogio=lambda: 0.0
    )
    check(
        "usa o menor valor entre tentativa e restante",
        registro == [1.2],
        str(registro),
    )

    print()
    if falhas:
        print(f"FALHOU: {len(falhas)} de {total} verificacoes")
        for item in falhas:
            print(f"  - {item}")
        return 1
    print(f"OK: {total}/{total} verificacoes da retentativa passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())