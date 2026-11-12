"""Restaura o transporte de e-mail de producao da VPS.

O transporte ativo e o HTTPS (`MAIL_TRANSPORT=api`), porque a saida SMTP da
VPS esta bloqueada pela rede do datacenter. Para voltar ao SMTP do Gmail, use
`MAIL_TRANSPORT=smtp` com `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` e `SMTP_PASS`
(senha de app de 16 caracteres) — ou apague estas linhas e siga o runbook
`app/docs/email-afiliados.md`.

Uso na VPS:
    python3 tools/restaurar-mail-api.py
"""

import pathlib

MAIL_ENV = "/etc/vizin/mail.env"

env = """# Envio de e-mail do painel de afiliado.
# MAIL_TRANSPORT=smtp usa o SMTP do Gmail (senha de app). Hoje a rede do
# datacenter bloqueia as portas 25/465/587, entao o caminho ativo e o
# transporte HTTPS (api). Para voltar ao SMTP, troque para smtp e preencha
# SMTP_HOST, SMTP_PORT, SMTP_USER e SMTP_PASS (senha de app de 16 caracteres).
#
# CA propria (SMTP_TLS_CA): o PEM tem varias linhas e o EnvironmentFile do
# systemd nao aceita isso. Escreva com \\n entre as linhas; o codigo converte
# de volta para quebras de linha reais antes de abrir a conexao TLS.
MAIL_TRANSPORT=api
MAIL_API_URL=https://api.resend.com/emails
MAIL_FROM=vizin.Os <vizin.oos@gmail.com>
MAIL_REPLY_TO=vizin.oos@gmail.com
# MAIL_API_KEY=re_...   (chave do provedor; preencha aqui, fora do git)
"""

pathlib.Path(MAIL_ENV).write_text(env)
print("Transporte de producao restaurado (MAIL_TRANSPORT=api).")
