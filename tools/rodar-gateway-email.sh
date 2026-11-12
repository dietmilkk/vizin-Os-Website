#!/bin/sh
# Sobe o gateway de e-mail no PC e liga a VPS nele (tunel SSH reverso).
#
# O problema: a VPS nao sai por SMTP (a rede do datacenter bloqueia as portas
# 25/465/587), mas ela sai por HTTPS na 443. O transporte `api` da API e um
# POST no formato do Resend, entao apontamos a VPS para um gateway local do PC
# que fala esse mesmo formato e entrega pelo SMTP do Gmail.
#
# Como funciona:
#   1. o PC sobe tools/gateway-email-local.py em 127.0.0.1:8789;
#   2. o PC abre um tunel SSH reverso (`ssh -R 8789:127.0.0.1:8789`), de modo
#      que na VPS o endereco 127.0.0.1:8789 responde para o gateway do PC;
#   3. a VPS passa a usar MAIL_TRANSPORT=api com
#      MAIL_API_URL=http://127.0.0.1:8789/emails e MAIL_API_KEY=<token>;
#   4. o script fica em primeiro plano segurando o tunel. Ao sair (Ctrl+C),
#      o gateway e fechado.
#
# Nada disso abre porta para a internet: o gateway escuta so em 127.0.0.1 e o
# tunel reverso tambem so escuta em 127.0.0.1 do lado da VPS.
#
# Modo automatico (subida do PC):
#   O serviço do systemd roda este script no boot (ver tools/systemd/). Para
#   isso o script:
#     - espera ATRASO_INICIAL segundos antes de comecar (a rede e o disco
#       ainda podem estar subindo);
#     - usa uma trava (flock) para nunca abrir duas instancias (a segunda
#       sai na hora, sem consumir CPU);
#     - roda o gateway e o tunel com prioridade baixa de CPU (nice);
#     - repete a abertura do tunel enquanto a VPS nao estiver alcancavel.
#
# Uso:
#   tools/rodar-gateway-email.sh                 # espera 60s (padrão)
#   ATRASO_INICIAL=0 tools/rodar-gateway-email.sh   # sem espera
#
# Ajustes de conexao (opcionais):
#   SSH_CONFIG=/caminho/ssh_config HOST=vizin-vps tools/rodar-gateway-email.sh
#
# O script funciona sem o ssh_config: quando ele nao existe, usa a chave
# do projeto do app (app/.local/vps/id_ed25519), que fica sempre no lugar.
#
# O que fica guardado onde:
#   site/.deploy-gmail.env  (600, ignorado pelo git) -> GMAIL_USER, GMAIL_PASS,
#                            GATEWAY_TOKEN. A senha de app nunca passa por argv
#                            de processo nem entra no repositorio.

set -eu

SSH_CONFIG="${SSH_CONFIG:-/tmp/opencode/ssh_config}"
HOST="${HOST:-vizin-vps}"
RAIZ="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
PORTA="${PORTA:-8789}"
ARQ_ENV="$RAIZ/.deploy-gmail.env"
LOG="${GATEWAY_LOG:-/tmp/vizin-gateway.log}"

# Espera antes de comecar (ligar o PC e o inicio do script). 0 desliga.
ATRASO_INICIAL="${ATRASO_INICIAL:-60}"
# Prioridade de CPU: quanto maior o numero, menor a prioridade.
NICE="${NICE:-10}"
# Tentativas de abrir o tunel (cada uma espera ate 20s + 10s de folga).
MAX_TENTATIVAS="${MAX_TENTATIVAS:-30}"
# Trava anti-duplicata: duas instancias nao podem ficar disputando a porta.
LOCK="${LOCK:-/tmp/vizin-gateway-email.lock}"
ARQ_PID="${ARQ_PID:-/tmp/vizin-gateway-email.pid}"

PID_GATEWAY=""
PID_TUNEL=""

# ------------------------------------------------------------- espera inicial
if [ "$ATRASO_INICIAL" -gt 0 ] 2>/dev/null; then
  echo "==> aguardando ${ATRASO_INICIAL}s antes de comecar (a rede ainda pode estar subindo)"
  sleep "$ATRASO_INICIAL"
fi

# ------------------------------------------------------------------ SSH base
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

# ------------------------------------------------------- trava anti-duplicata
# Se ja existe uma instancia rodando, esta sai sem mexer em nada: evita
# duas portas em disputa e consumo dobrado de CPU/memoria.
exec 9>"$LOCK"
if command -v flock >/dev/null 2>&1; then
  if ! flock -n 9; then
    echo "Ja existe uma instancia rodando (pid $(cat "$ARQ_PID" 2>/dev/null || echo '?')). Saindo."
    exit 0
  fi
fi
echo $$ > "$ARQ_PID"

Fechou() {
  echo
  echo "==> encerrando o gateway local e o tunel"
  [ -n "$PID_TUNEL" ] && kill "$PID_TUNEL" 2>/dev/null || true
  [ -n "$PID_GATEWAY" ] && kill "$PID_GATEWAY" 2>/dev/null || true
  [ -n "$PID_TUNEL" ] && wait "$PID_TUNEL" 2>/dev/null || true
  [ -n "$PID_GATEWAY" ] && wait "$PID_GATEWAY" 2>/dev/null || true
  rm -f "$ARQ_PID"
}
trap Fechou EXIT INT TERM

# ------------------------------------------------------- credenciais local
# O arquivo e criado na primeira execucao e nunca vai para o git.
if [ ! -f "$ARQ_ENV" ]; then
  if [ ! -t 0 ]; then
    echo "O arquivo $ARQ_ENV nao existe e nao ha terminal para perguntar a senha." >&2
    echo "Rode o script uma vez no terminal para criar o arquivo." >&2
    exit 1
  fi
  echo "==> 1/4 preparing o arquivo local de credenciais ($ARQ_ENV)"
  echo "Conta do Gmail que envia (deixe em branco para vizin.oos@gmail.com):"
  read -r CONTA
  [ -n "$CONTA" ] || CONTA="vizin.oos@gmail.com"
  echo "Senha de app do Gmail (16 caracteres, sem espacos; nao aparece na tela):"
  stty -echo 2>/dev/null || true
  read -r SENHA
  stty echo 2>/dev/null || true
  echo
  SENHA=$(printf '%s' "$SENHA" | tr -d '[:space:]')
  if [ "${#SENHA}" -ne 16 ]; then
    echo "A senha de app do Gmail tem 16 caracteres (a informada tem ${#SENHA})." >&2
    exit 1
  fi
  TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
  umask 077
  {
    echo "GMAIL_USER=$CONTA"
    echo "GMAIL_PASS=$SENHA"
    echo "GATEWAY_TOKEN=$TOKEN"
  } > "$ARQ_ENV"
  chmod 600 "$ARQ_ENV"
  unset SENHA
else
  echo "==> 1/4 usando as credenciais ja salvas em $ARQ_ENV"
  chmod 600 "$ARQ_ENV"
fi

# Le as variaveis do arquivo sem executar o conteudo como shell.
GMAIL_USER=$(sed -n 's/^GMAIL_USER=//p' "$ARQ_ENV" | head -1)
GMAIL_PASS=$(sed -n 's/^GMAIL_PASS=//p' "$ARQ_ENV" | head -1)
GATEWAY_TOKEN=$(sed -n 's/^GATEWAY_TOKEN=//p' "$ARQ_ENV" | head -1)
if [ -z "$GMAIL_USER" ] || [ -z "$GMAIL_PASS" ] || [ -z "$GATEWAY_TOKEN" ]; then
  echo "Arquivo $ARQ_ENV incompleto (GMAIL_USER/GMAIL_PASS/GATEWAY_TOKEN)." >&2
  exit 1
fi

# -------------------------------------------------------------- gateway
# O log cresce devagar, mas pode crescer: quando passa de 1 MB, fica so com
# as ultimas linhas (o historico antigo nao tem valor).
if [ -f "$LOG" ]; then
  TAM=$(wc -c < "$LOG")
  if [ "$TAM" -gt 1048576 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null || true
    mv "$LOG.tmp" "$LOG" 2>/dev/null || true
  fi
fi

echo "==> 2/4 subindo o gateway local em 127.0.0.1:$PORTA"
GMAIL_USER="$GMAIL_USER" \
GMAIL_PASS="$GMAIL_PASS" \
GATEWAY_TOKEN="$GATEWAY_TOKEN" \
GATEWAY_PORT="$PORTA" \
  nohup nice -n "$NICE" python3 "$RAIZ/tools/gateway-email-local.py" > "$LOG" 2>&1 &
PID_GATEWAY=$!

# Espera o gateway responder antes de abrir o tunel.
PRONTO=0
i=0
while [ "$i" -lt 20 ]; do
  if python3 - "$PORTA" <<'EOF' >/dev/null 2>&1
import socket, sys
s = socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1)
s.close()
EOF
  then
    PRONTO=1
    break
  fi
  i=$((i + 1))
  sleep 0.5
done
if [ "$PRONTO" -ne 1 ]; then
  echo "O gateway nao subiu. Log:" >&2
  cat "$LOG" >&2
  exit 1
fi
echo "gateway pronto (log em $LOG)"

# ------------------------------------------------------- tunel + VPS
echo "==> 3/4 abrindo o tunel SSH reverso"
# O tunel e aberto antes do apontamento: assim a VPS nunca fica apontada
# para uma porta que ainda nao responde.
# Se a VPS ainda nao estiver alcancavel (ligar o PC sem internet, por
# exemplo), o script repete em vez de desistir.
TENTATIVA=0
while : ; do
  nice -n "$NICE" $SSH_BASE -N \
    -o ExitOnForwardFailure=yes \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -R "$PORTA:127.0.0.1:$PORTA" \
    "$HOST" &
  PID_TUNEL=$!

  # Espera a VPS enxergar o gateway pelo tunel.
  i=0
  VU=0
  while [ "$i" -lt 20 ]; do
    if $SSH_BASE "curl -s -m 5 http://127.0.0.1:$PORTA/health" 2>/dev/null | grep -q '"ok"'; then
      VU=1
      break
    fi
    kill -0 "$PID_TUNEL" 2>/dev/null || break
    i=$((i + 1))
    sleep 1
  done

  if [ "$VU" -eq 1 ]; then
    break
  fi

  # O tunel nao ficou de pe (ou a VPS nao respondeu): tenta de novo.
  kill "$PID_TUNEL" 2>/dev/null || true
  wait "$PID_TUNEL" 2>/dev/null || true
  PID_TUNEL=""
  TENTATIVA=$((TENTATIVA + 1))
  if [ "$TENTATIVA" -ge "$MAX_TENTATIVAS" ]; then
    echo "Nao consegui falar com a VPS depois de $TENTATIVA tentativas." >&2
    exit 1
  fi
  echo "   VPS ainda nao respondeu (tentativa $TENTATIVA/$MAX_TENTATIVAS); tentando de novo em 10s"
  sleep 10
done
echo "tunel no ar: a VPS enxerga o gateway em 127.0.0.1:$PORTA"

echo "==> 4/4 apontando a VPS para o gateway e segurando o tunel"
$SCP_BASE "$RAIZ/tools/apontar-gateway-local.py" "$HOST:/tmp/apontar-gateway-local.py" >/dev/null
printf '%s' "$GATEWAY_TOKEN" | $SSH_BASE 'python3 /tmp/apontar-gateway-local.py && chmod 600 /etc/vizin/mail.env && systemctl restart vizin-api && sleep 4 && curl -s -m 10 http://127.0.0.1:8788/health; echo'

echo
echo "A VPS ja envia e-mail pelo PC enquanto este comando estiver rodando."
echo "Para desfazer o apontamento: python3 tools/restaurar-mail-api.py na VPS."
echo "Para encerrar: Ctrl+C"

# Segura o tunel em primeiro plano.
wait "$PID_TUNEL"
