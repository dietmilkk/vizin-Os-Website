"""Aponta a API da VPS para o servidor SMTP de captura local.

O `EnvironmentFile` do systemd nao aceita um PEM de varias linhas, entao o
certificado do servidor de captura e escrito com `\\n` entre as linhas. O
cliente SMTP do projeto converte de volta para quebras de linha reais antes
de abrir a conexao TLS (ver `unescapeEnv` em `vps/src/mailer.ts`).

Uso na VPS:
    python3 tools/apontar-smtp-sink.py
"""

import pathlib
import sys

CA_PATH = "/var/lib/vizin-sink/ca.pem"
MAIL_ENV = "/etc/vizin/mail.env"

if not pathlib.Path(CA_PATH).exists():
    sys.exit(
        "certificado do servidor de captura nao encontrado em %s: "
        "suba o smtp-sink antes" % CA_PATH
    )

ca = pathlib.Path(CA_PATH).read_text().strip()
# Dentro de aspas duplas do systemd, \n vira quebra de linha no valor final.
escaped = ca.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

env = f"""# Gerado por tools/apontar-smtp-sink.py: transporte SMTP apontado para o
# servidor de captura local (127.0.0.1:2525). Use tools/restaurar-mail-api.py
# para voltar ao transporte de producao.
MAIL_TRANSPORT=smtp
MAIL_API_URL=https://api.resend.com/emails
MAIL_FROM=vizin.Os <vizin.oos@gmail.com>
MAIL_REPLY_TO=vizin.oos@gmail.com
SMTP_HOST=127.0.0.1
SMTP_PORT=2525
SMTP_SECURE=false
SMTP_USER=vizin.oos@gmail.com
SMTP_PASS=senha-de-app-de-teste-16c
SMTP_TLS_CA="{escaped}"
"""

pathlib.Path(MAIL_ENV).write_text(env)
print("API apontada para o servidor SMTP de captura local.")
