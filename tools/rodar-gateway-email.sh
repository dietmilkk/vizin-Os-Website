#!/bin/sh
# ---------------------------------------------------------------------------
# Entrega a fila de e-mail da VPS pelo Gmail, no PC do dono.
#
# Como funciona hoje (modelo de fila):
#   1. o site manda o convite para a API da VPS;
#   2. a API guarda o e-mail na fila (tabela `mail_outbox`) e responde na hora;
#   3. este script pergunta por HTTPS, com token, se ha mensagens;
#   4. cada mensagem sai pelo SMTP do Gmail, com ate 5 tentativas;
#   5. o resultado volta para a VPS (enviado, repetir ou falhou de vez).
#
# O PC nao expoe porta nenhuma: so faz conexoes de saida para a API.
#
# Modo automatico (subida do PC, ver tools/systemd/):
#   - espera 60 s antes de comecar (a rede ainda pode estar subindo);
#   - usa uma trava (flock) para nunca abrir duas instancias;
#   - roda com prioridade baixa de CPU (nice);
#   - se a VPS estiver fora do ar, o puxador tenta de novo com espera
#     crescente (ate 60 s) e nunca desiste sozinho.
#
# Uso:
#   tools/rodar-gateway-email.sh                 # espera 60 s (padrao)
#   ATRASO_INICIAL=0 tools/rodar-gateway-email.sh  # comeca na hora
# ---------------------------------------------------------------------------
set -eu

RAIZ=$(cd "$(dirname "$0")/.." && pwd)
ARQ_ENV="${ARQ_ENV:-$RAIZ/.deploy-gmail.env}"
ATRASO_INICIAL="${ATRASO_INICIAL:-60}"
NICE="${NICE:-10}"
LOCK="${LOCK:-/tmp/vizin-gateway-email.lock}"
ARQ_PID="${ARQ_PID:-/tmp/vizin-gateway-email.pid}"
URL_FILA="${MAIL_QUEUE_URL:-https://api.188.166.156.109.sslip.io}"

# ------------------------------------------------------------- espera inicial
if [ "$ATRASO_INICIAL" -gt 0 ] 2>/dev/null; then
  echo "==> aguardando ${ATRASO_INICIAL}s antes de comecar (a rede ainda pode estar subindo)"
  sleep "$ATRASO_INICIAL"
fi

# ------------------------------------------------------- trava anti-duplicata
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "Ja existe uma instancia rodando (pid $(cat "$ARQ_PID" 2>/dev/null || echo '?')). Saindo."
  exit 0
fi
echo $$ > "$ARQ_PID"

# ------------------------------------------------------- credenciais local
# O arquivo e criado na primeira execucao e nunca vai para o git.
if [ ! -f "$ARQ_ENV" ]; then
  if [ ! -t 0 ]; then
    echo "O arquivo $ARQ_ENV nao existe e nao ha terminal para perguntar a senha." >&2
    echo "Rode o script uma vez no terminal para criar o arquivo." >&2
    exit 1
  fi
  echo "==> criando o arquivo local de credenciais ($ARQ_ENV)"
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
    echo "MAIL_QUEUE_URL=$URL_FILA"
  } > "$ARQ_ENV"
  chmod 600 "$ARQ_ENV"
  unset SENHA
else
  echo "==> usando as credenciais ja salvas em $ARQ_ENV"
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
export GMAIL_USER GMAIL_PASS GATEWAY_TOKEN MAIL_QUEUE_URL="$URL_FILA"

# ------------------------------------------------------------- puxador
echo "==> fila: $URL_FILA"
echo "==> conta: $GMAIL_USER"
echo "==> para encerrar: Ctrl+C"

Fechou() {
  echo
  echo "==> encerrando o entregador"
  [ -n "${PID:-}" ] && kill "$PID" 2>/dev/null || true
  [ -n "${PID:-}" ] && wait "$PID" 2>/dev/null || true
  rm -f "$ARQ_PID"
}
trap Fechou EXIT INT TERM

nice -n "$NICE" python3 "$RAIZ/tools/puxar-fila-email.py" &
PID=$!
wait "$PID" || exit $?