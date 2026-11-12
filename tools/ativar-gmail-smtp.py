"""Liga o transporte SMTP do Gmail na VPS (senha de app de 16 caracteres).

A senha de app chega pelo stdin — nunca por argumento de linha de comando
(que fica visivel em `ps`) e nunca dentro do repositorio. O Gmail mostra a
senha em 4 grupos de 4 caracteres; aqui ela e gravada sem os espacos.

Uso na VPS:
    python3 tools/ativar-gmail-smtp.py < arquivo-com-a-senha

Uso da maquina local (a senha nao passa por argv de processo nem pelo repo):
    printf '%s' 'xxxx xxxx xxxx xxxx' | ssh vps python3 /tmp/ativar-gmail-smtp.py

A rede do datacenter pode bloquear a saida SMTP (25/465/587): se o envio
der timeout, use tools/restaurar-mail-api.py para voltar ao transporte
HTTPS (api) ou abra a saida SMTP com o provedor.
"""

import pathlib
import sys

MAIL_ENV = "/etc/vizin/mail.env"

senha = sys.stdin.read().strip().replace(" ", "")
if not senha:
    sys.exit("senha de app nao informada (envie pelo stdin)")
if len(senha) != 16:
    sys.exit(
        "senha de app do Gmail tem 16 caracteres (a informada tem %d)" % len(senha)
    )

env = """# Envio de e-mail do painel de afiliado.
# Transporte SMTP do Gmail (senha de app de 16 caracteres), ligado por
# tools/ativar-gmail-smtp.py. A rede do datacenter pode bloquear as portas
# 25/465/587 — se o envio der timeout, volte com tools/restaurar-mail-api.py
# (transporte HTTPS/api) ou abra a saida SMTP com o provedor.
#
# CA propria (SMTP_TLS_CA): o PEM tem varias linhas e o EnvironmentFile do
# systemd nao aceita isso. Escreva com \\n entre as linhas; o codigo converte
# de volta para quebras de linha reais antes de abrir a conexao TLS.
MAIL_TRANSPORT=smtp
MAIL_API_URL=https://api.resend.com/emails
MAIL_FROM=vizin.Os <vizin.oos@gmail.com>
MAIL_REPLY_TO=vizin.oos@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_SECURE=true
SMTP_USER=vizin.oos@gmail.com
SMTP_PASS=%s
""" % senha

pathlib.Path(MAIL_ENV).write_text(env)
pathlib.Path(MAIL_ENV).chmod(0o600)
print("Transporte SMTP do Gmail ligado em %s (permissao 600)." % MAIL_ENV)
