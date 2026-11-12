#!/bin/sh
# Limpa os dados de teste do programa de parceiros na VPS.
#
# Os testes criam contas de afiliado/criador de verdade na API. Como cada conta
# registra o IP que a criou (guarda de IP), o IP da maquina de teste fica
# bloqueado para criar contas ate a limpeza. Este script remove as contas de
# teste e libera os IPs junto.
#
# Uso:
#   tools/limpar-teste.sh            # so mostra o que seria apagado
#   tools/limpar-teste.sh --aplicar  # apaga
#   tools/limpar-teste.sh --ip 1.2.3.4 --aplicar  # apaga as contas deste IP
#
# O filtro por IP existe porque os codigos das contas sao aleatorios: o
# prefixo de teste nem sempre identifica a conta que o teste criou, mas o
# endereco de rede sim (a guarda permite uma conta por papel e IP).
#
# Ajustes de conexao (opcionais, por ambiente):
#   SSH_CONFIG=/caminho/ssh_config HOST=vizin-vps
#
# Sem SSH_CONFIG, o script usa a chave do projeto do app
# (app/.local/vps/id_ed25519) e o known_hosts da propria VPS.

set -eu

SSH_CONFIG="${SSH_CONFIG:-/tmp/opencode/ssh_config}"
HOST="${HOST:-vizin-vps}"
RAIZ="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
LOCAL="/tmp/limpar-teste-vps.ts"

SCP_BASE=""
SSH_BASE=""
if [ -f "$SSH_CONFIG" ]; then
  SCP_BASE="scp -F $SSH_CONFIG"
  SSH_BASE="ssh -F $SSH_CONFIG"
else
  CHAVE="${CHAVE:-$(CDPATH='' cd -- "$RAIZ/.." && pwd)/app/.local/vps/id_ed25519}"
  KNOWN_HOSTS="${KNOWN_HOSTS:-$(CDPATH='' cd -- "$RAIZ/.." && pwd)/app/.local/vps/known_hosts}"
  VPS="${VPS:-root@188.166.156.109}"
  if [ ! -f "$CHAVE" ]; then
    echo "SSH config nao encontrado ($SSH_CONFIG) e a chave do app tambem nao ($CHAVE)." >&2
    echo "Defina SSH_CONFIG=/caminho/ssh_config ou CHAVE=/caminho/id_ed25519" >&2
    exit 1
  fi
  SCP_BASE="scp -i $CHAVE -o UserKnownHostsFile=$KNOWN_HOSTS -o StrictHostKeyChecking=yes"
  SSH_BASE="ssh -i $CHAVE -o UserKnownHostsFile=$KNOWN_HOSTS -o StrictHostKeyChecking=yes"
  HOST="$VPS"
fi

$SCP_BASE "$RAIZ/tools/limpar-teste-vps.ts" "$HOST:/tmp/limpar-teste-vps.ts" >/dev/null

# Monta os argumentos repassados ao script da VPS.
ARGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --aplicar) ARGS="$ARGS --aplicar" ;;
    --ip) ARGS="$ARGS --ip ${2:-}"; shift ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 1 ;;
  esac
  shift
done

if [ -n "$ARGS" ]; then
  $SSH_BASE "$HOST" "sudo -u vizin bun run /tmp/limpar-teste-vps.ts $ARGS"
else
  $SSH_BASE "$HOST" 'sudo -u vizin bun run /tmp/limpar-teste-vps.ts'
fi

$SSH_BASE "$HOST" 'rm -f /tmp/limpar-teste-vps.ts' >/dev/null 2>&1 || true
