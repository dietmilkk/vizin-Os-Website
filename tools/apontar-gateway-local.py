"""Aponta a API da VPS para o gateway de e-mail que roda no PC do usuario.

A VPS nao sai por SMTP (a rede do datacenter bloqueia as portas 25/465/587),
mas ela sai por HTTPS na 443. O transporte `api` da API e exatamente um POST
no formato do Resend, entao apontamos a VPS para o gateway local do PC, que
fala o mesmo formato e entrega pelo SMTP do Gmail.

O tunel SSH reverso (`ssh -R 8789:127.0.0.1:8789`) faz o endereco
127.0.0.1:8789 da VPS responder para o gateway do PC. O token chega pelo
stdin — nunca por argumento de linha de comando (que fica visivel em `ps`).

Uso na VPS:
    python3 tools/apontar-gateway-local.py < token
"""

import pathlib
import sys

MAIL_ENV = "/etc/vizin/mail.env"
PORTA = 8789

token = sys.stdin.read().strip()
if not token:
    sys.exit("token do gateway nao informado (envie pelo stdin)")
if any(c in token for c in "\r\n"):
    sys.exit("token invalido")

env = """# Gerado por tools/apontar-gateway-local.py: transporte HTTPS (api) apontado
# para o gateway de e-mail que roda no PC do usuario, alcancado pelo tunel SSH
# reverso (ssh -R {porta}:127.0.0.1:{porta}).
#
# A VPS nao sai por SMTP (25/465/587 bloqueadas), entao o gateway no PC e quem
# fala com o Gmail. Se o PC estiver desligado ou o tunel caiu, a API responde
# erro de conexao e a cota do afiliado NAO e consumida (dá para tentar de novo).
#
# Para voltar ao transporte de producao (provedor HTTPS com MAIL_API_KEY):
# python3 tools/restaurar-mail-api.py
MAIL_TRANSPORT=api
MAIL_API_URL=http://127.0.0.1:{porta}/emails
MAIL_API_KEY={token}
MAIL_FROM=vizin.Os <vizin.oos@gmail.com>
MAIL_REPLY_TO=vizin.oos@gmail.com
""".format(porta=PORTA, token=token)

pathlib.Path(MAIL_ENV).write_text(env)
pathlib.Path(MAIL_ENV).chmod(0o600)
print("API apontada para o gateway local do PC (127.0.0.1:%d/emails)." % PORTA)
