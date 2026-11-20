#!/usr/bin/env bash
# Publica a API e o site na VPS, com backup do banco e verificação no fim.
#
#   tools/deploy-vps.sh              # backend + site
#   tools/deploy-vps.sh --so-backend
#   tools/deploy-vps.sh --so-site
#
# A chave SSH é procurada automaticamente (app/docs/operacao/deploy-vps.md):
#   app/.local/vps/id_ed25519  ->  /tmp/opencode/id_deploy_new  ->  ~/.ssh/id_ed25519
# (ou defina SSH_KEY com o caminho de outro arquivo)
#
# Requisitos: rsync, ssh e curl. Nada aqui é destrutivo: o banco é copiado
# antes de qualquer mudança e o serviço só é reiniciado depois do rsync.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Raiz do projeto: normalmente o repo do app fica do lado do site
# (…/app com site/ dentro), mas também pode ser o próprio repo do app
# (site/ dentro dele). Detecta qual layout é este.
PROJ="$(cd "$ROOT/.." && pwd)"
APP_DIR="${VIZIN_APP_DIR:-$PROJ}"
if [ -d "$PROJ/vps" ]; then
  VPS_DIR="${VIZIN_VPS_DIR:-$PROJ/vps}"
else
  VPS_DIR="${VIZIN_VPS_DIR:-$APP_DIR/vps}"
fi
if [ ! -d "$VPS_DIR" ]; then
  echo "Pasta da API (vps/) não encontrada. Use VIZIN_VPS_DIR=/caminho/da/vps" >&2
  exit 1
fi

SSH_KEY="${SSH_KEY:-}"
if [ -z "$SSH_KEY" ]; then
  # A chave da VPS fica fora do versionamento. Lugares procurados:
  # ~/.local/vps (padrão), o .local do projeto, /tmp/opencode e ~/.ssh.
  for candidato in \
    "$HOME/.local/vps/id_ed25519" \
    "$APP_DIR/.local/vps/id_ed25519" \
    "/tmp/opencode/id_deploy_new" \
    "$HOME/.ssh/id_ed25519"; do
    if [ -f "$candidato" ]; then
      SSH_KEY="$candidato"
      break
    fi
  done
fi
SSH_USER="${SSH_USER:-root}"
SSH_HOST="${SSH_HOST:-188.166.156.109}"
SSH_PORT="${SSH_PORT:-22}"
API_HOST="${API_HOST:-api.188.166.156.109.sslip.io}"
SITE_HOST="${SITE_HOST:-site.188.166.156.109.sslip.io}"
REMOTE_API_DIR="${REMOTE_API_DIR:-/opt/vizin-api/}"
REMOTE_SITE_DIR="${REMOTE_SITE_DIR:-/var/www/vizinhanca.app/}"

MODO="tudo"
case "${1:-}" in
  --so-backend) MODO="backend" ;;
  --so-site) MODO="site" ;;
  "") ;;
  *) echo "Uso: tools/deploy-vps.sh [--so-backend|--so-site]" >&2; exit 2 ;;
esac

if [ ! -f "$SSH_KEY" ]; then
  cat >&2 <<EOF
Chave SSH não encontrada.

Procurada em:
  $HOME/.local/vps/id_ed25519
  $APP_DIR/.local/vps/id_ed25519
  /tmp/opencode/id_deploy_new
  $HOME/.ssh/id_ed25519

Se a chave estiver em outro lugar:

  SSH_KEY=/caminho/da/chave tools/deploy-vps.sh

Sem essa chave não é possível publicar: o deploy usa rsync + ssh e a
VPS não tem credencial de git.
EOF
  exit 1
fi

chmod 600 "$SSH_KEY" 2>/dev/null || true

# Chave do host fixada (deploy/known_hosts), com accept-new como reserva.
KNOWN_HOSTS="$ROOT/deploy/known_hosts"
SSH_OPTS=(-i "$SSH_KEY" -p "$SSH_PORT" -o BatchMode=yes -o ConnectTimeout=20)
if [ -f "$KNOWN_HOSTS" ]; then
  SSH_OPTS+=(-o "UserKnownHostsFile=$KNOWN_HOSTS" -o StrictHostKeyChecking=yes)
else
  SSH_OPTS+=(-o StrictHostKeyChecking=accept-new)
fi
SSH=(ssh "${SSH_OPTS[@]}" "$SSH_USER@$SSH_HOST")
# O rsync recebe o comando remoto como uma string ("ssh <opcoes>").
RSYNC_SSH="ssh ${SSH_OPTS[*]}"

echo "==> Alvo: $SSH_USER@$SSH_HOST  (api: $API_HOST, site: $SITE_HOST)"
echo "==> Chave: $SSH_KEY"

if [ "$MODO" = "tudo" ] || [ "$MODO" = "backend" ]; then
  echo
  echo "==> Backup do banco na VPS"
  "${SSH[@]}" "cp -a /var/lib/vizin-api/vizin.sqlite /var/lib/vizin-api/vizin.sqlite.bak-antes-painel-\$(date +%Y%m%d-%H%M%S); [ -f /var/lib/vizin-api/vizin.sqlite-wal ] && cp -a /var/lib/vizin-api/vizin.sqlite-wal /var/lib/vizin-api/vizin.sqlite-wal.bak-antes-painel-\$(date +%Y%m%d-%H%M%S) || true"

  echo "==> Publicando a API (vps/)"
  rsync -az --exclude node_modules --exclude '*.sqlite*' -e "$RSYNC_SSH" "$VPS_DIR/" "$SSH_USER@$SSH_HOST:$REMOTE_API_DIR"

  echo "==> Reiniciando o serviço vizin-api"
  "${SSH[@]}" "systemctl restart vizin-api"

  echo "==> Conferindo a API"
  sleep 2
  curl -fsS --max-time 20 "https://$API_HOST/health" >/dev/null
  echo "    health: ok"
  STATS_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$API_HOST/stats/public")"
  if [ "$STATS_CODE" != "200" ]; then
    echo "    ATENÇÃO: /stats/public respondeu $STATS_CODE (esperado 200)" >&2
  else
    echo "    /stats/public: ok"
    curl -fsS --max-time 20 "https://$API_HOST/stats/public" | head -c 400
    echo
  fi
  # Forum da Comunidade: sem isso a pagina /comunidade mostra "fora do ar".
  FORUM_CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$API_HOST/forum/status")"
  if [ "$FORUM_CODE" != "200" ]; then
    echo "    ATENÇÃO: /forum/status respondeu $FORUM_CODE (esperado 200)" >&2
  else
    echo "    /forum/status: ok"
    curl -fsS --max-time 20 "https://$API_HOST/forum/status" | head -c 200
    echo
  fi
fi

if [ "$MODO" = "tudo" ] || [ "$MODO" = "site" ]; then
  echo
  echo "==> Publicando o site"
  # O que vai para o ar e so o site publico. Documentacao interna, ferramentas,
  # testes e pacotes de upload ficam de fora (o Caddy tambem bloqueia esses
  # caminhos, por seguranca).
  rsync -az --delete \
    --exclude '.git' --exclude '.github' --exclude 'deploy' \
    --exclude 'tmp-vps' --exclude 'tests' --exclude 'tools' \
    --exclude 'dist' --exclude 'README.md' --exclude 'docs' \
    --exclude '.htaccess' --exclude 'tmp-*.py' \
    --exclude '.deploy-*' --exclude '.env*' \
    -e "$RSYNC_SSH" \
    "$ROOT/" "$SSH_USER@$SSH_HOST:$REMOTE_SITE_DIR"
  # Limpa o que sobrou de publicacoes antigas (o rsync nao apaga o que exclui).
  # .deploy-* cobre o .deploy-gmail.env: sem isso, a senha do Gmail e o token
  # do gateway iam para o webroot publico a cada deploy.
  "${SSH[@]}" "rm -f $REMOTE_SITE_DIR/README.md $REMOTE_SITE_DIR/.htaccess; rm -f $REMOTE_SITE_DIR/.deploy-*; rm -rf $REMOTE_SITE_DIR/docs; rm -rf $REMOTE_SITE_DIR/tools $REMOTE_SITE_DIR/tests $REMOTE_SITE_DIR/tmp-vps $REMOTE_SITE_DIR/dist; rm -f $REMOTE_SITE_DIR/tmp-*.py $REMOTE_SITE_DIR/.env*"
  "${SSH[@]}" "chown -R vizin:vizin $REMOTE_SITE_DIR"

  echo "==> Conferindo o site"
  for path in / /painel /documento /moderacao /membros /comunidade /doar /download /essencia /privacidade /termos /licenca; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$SITE_HOST$path")"
    printf '    %-12s %s\n' "$path" "$code"
  done

  echo "==> Conferindo que nada interno ficou exposto"
  for path in /README.md /docs/ /tools/ /tests/ /dist/ /.deploy-gmail.env /.env; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$SITE_HOST$path")"
    printf '    %-24s %s\n' "$path" "$code"
    case "$code" in
      200|301|302) echo "    ATENÇÃO: $path está acessível no ar" >&2 ;;
    esac
  done
fi

echo
echo "==> Pronto."
