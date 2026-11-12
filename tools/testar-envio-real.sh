#!/bin/sh
# Teste real do envio de e-mail pelo painel de afiliado.
#
# A VPS nao consegue sair por SMTP na internet (a rede do datacenter bloqueia
# as portas 465/587), entao este script aponta o transporte SMTP da API para
# um servidor SMTP local na propria VPS -- o mesmo protocolo do Gmail
# (STARTTLS + AUTH PLAIN depois do handshake). O e-mail sai pelo codigo de
# producao e fica gravado em disco, para conferir o MIME.
#
# O roteiro:
#   1. limpa os dados de teste na VPS;
#   2. sobe o servidor SMTP de captura;
#   3. aponta a API para ele (MAIL_TRANSPORT=smtp);
#   4. roda o teste no navegador contra o site publicado;
#   5. mostra as mensagens capturadas;
#   6. restaura o transporte de producao (MAIL_TRANSPORT=api).
#
# Uso:
#   tools/testar-envio-real.sh
#
# Ajustes de conexao (opcionais):
#   SSH_CONFIG=/caminho/ssh_config HOST=vizin-vps tools/testar-envio-real.sh
#
# A conexao tambem funciona sem o ssh_config: quando ele nao existe, o script
# usa a chave do projeto do app (app/.local/vps/id_ed25519), que fica sempre
# no lugar.

set -eu

SSH_CONFIG="${SSH_CONFIG:-/tmp/opencode/ssh_config}"
HOST="${HOST:-vizin-vps}"
RAIZ="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
SINK_PORT=2525
SINK_DIR=/var/lib/vizin-sink
CODIGO=TESTEENVIO

# Mounta o comando ssh conforme o que existe na maquina.
if [ -f "$SSH_CONFIG" ]; then
  SSH_BASE="ssh -F $SSH_CONFIG $HOST"
  SCP_BASE="scp -F $SSH_CONFIG"
else
  CHAVE="${CHAVE:-$(cd "$RAIZ/.." && pwd)/app/.local/vps/id_ed25519}"
  KNOWN_HOSTS="${KNOWN_HOSTS:-$(cd "$RAIZ/.." && pwd)/app/.local/vps/known_hosts}"
  VPS="${VPS:-root@188.166.156.109}"
  if [ ! -f "$CHAVE" ]; then
    echo "SSH config nao encontrado ($SSH_CONFIG) e a chave do app tambem nao ($CHAVE)." >&2
    echo "Defina SSH_CONFIG=/caminho/ssh_config ou CHAVE=/caminho/id_ed25519" >&2
    exit 1
  fi
  SSH_BASE="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KNOWN_HOSTS -i $CHAVE $VPS"
  SCP_BASE="scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=$KNOWN_HOSTS -i $CHAVE"
  HOST="$VPS"
fi

echo "==> 1/6 limpando os dados de teste na VPS"
$SCP_BASE "$RAIZ/tools/limpar-teste-vps.ts" "$HOST:/tmp/limpar-teste-vps.ts" >/dev/null
$SSH_BASE 'sudo -u vizin bun run /tmp/limpar-teste-vps.ts --aplicar | tail -2'
rm -f /tmp/vizin-teste-email-token.json /tmp/vizin-teste-email-token-2.json

echo "==> 2/6 subindo o servidor SMTP de captura (127.0.0.1:$SINK_PORT)"
$SCP_BASE "$RAIZ/../app/vps/tools/smtp-sink.ts" "$HOST:/tmp/smtp-sink.ts" >/dev/null
# O servidor de captura roda como unidade systemd transitoria: assim o SSH
# nao fica esperando o processo em background e a porta fica sempre livre
# (duas instancias nao dividem a porta, e a que fica no lugar teria o
# certificado antigo -- o que quebra a validacao do TLS).
$SSH_BASE "systemctl stop vizin-smtp-sink 2>/dev/null; systemctl reset-failed vizin-smtp-sink 2>/dev/null; mkdir -p $SINK_DIR && chmod 777 $SINK_DIR; systemd-run --unit=vizin-smtp-sink --property=User=vizin --property=WorkingDirectory=/tmp --collect /usr/local/bin/bun run /tmp/smtp-sink.ts --port $SINK_PORT --out $SINK_DIR >/dev/null; sleep 5; journalctl -u vizin-smtp-sink -n 1 --no-pager; ss -ltn | grep -q ':$SINK_PORT ' && echo 'servidor de captura ouvindo' || { echo 'FALHA: o servidor de captura nao subiu'; journalctl -u vizin-smtp-sink -n 20 --no-pager; exit 1; }"

echo "==> 3/6 apontando a API para o servidor de captura"
$SCP_BASE "$RAIZ/tools/apontar-smtp-sink.py" "$HOST:/tmp/apontar-smtp-sink.py" >/dev/null
$SSH_BASE 'python3 /tmp/apontar-smtp-sink.py && chmod 600 /etc/vizin/mail.env && systemctl restart vizin-api && sleep 4 && curl -s -m 10 http://127.0.0.1:8788/health; echo'

echo "==> 4/6 rodando o teste no navegador contra o site publicado"
set +e
python3 "$RAIZ/tests/test-envio-email-real.py"
RESULTADO=$?
set -e

echo "==> 5/6 mensagens capturadas pelo servidor SMTP"
$SSH_BASE "ls -1t $SINK_DIR/*.eml 2>/dev/null | head -3 | while read arq; do echo \"--- \$arq ---\"; cat \"\$arq\"; echo; done"

echo "==> 6/6 restaurando o transporte de producao (MAIL_TRANSPORT=api)"
$SCP_BASE "$RAIZ/tools/restaurar-mail-api.py" "$HOST:/tmp/restaurar-mail-api.py" >/dev/null
$SSH_BASE 'python3 /tmp/restaurar-mail-api.py && chmod 600 /etc/vizin/mail.env && systemctl restart vizin-api && sleep 4 && systemctl stop vizin-smtp-sink 2>/dev/null; systemctl reset-failed vizin-smtp-sink 2>/dev/null; curl -s -m 10 http://127.0.0.1:8788/health; echo'

if [ "$RESULTADO" -ne 0 ]; then
  echo "O teste falhou (saida $RESULTADO)."
  exit "$RESULTADO"
fi

echo "Tudo certo: o envio de e-mail funciona de ponta a ponta."
