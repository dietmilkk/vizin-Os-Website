#!/usr/bin/env bash
# Prévia local do painel público (/painel) com uma API de verdade.
#
# Sobe uma VPS local (Bun) com o banco de teste populado e serve uma CÓPIA
# do site em /tmp, com o `assets/config.js` apontado para essa API local.
# O repositório não é alterado em nada.
#
# Uso:
#   tools/prever-painel.sh [porta-do-site] [porta-da-api]
#
# Depois é só abrir http://127.0.0.1:8099/painel

set -euo pipefail

SITE_PORT="${1:-8099}"
API_PORT="${2:-8788}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${VIZIN_APP_DIR:-$(cd "$ROOT/.." && pwd)/app}"
VPS_ENTRY="$APP_DIR/vps/src/index.ts"
SEED="$ROOT/tests/lib/seed_stats.py"

BEACONS='[{"id":"vps-br","url":"https://beacon.br.example.com","pubkey":"0000000000000000000000000000000000000000000000000000000000000000","geohash":"g8u4y"},{"id":"vps-global","url":"https://beacon.global.example.com","pubkey":"0000000000000000000000000000000000000000000000000000000000000000","geohash":"*"}]'

if [ ! -f "$VPS_ENTRY" ]; then
  echo "Não encontrei a VPS em $VPS_ENTRY (use VIZIN_APP_DIR)." >&2
  exit 1
fi

if command -v bun >/dev/null 2>&1; then
  BUN=(bun)
elif command -v npx >/dev/null 2>&1; then
  BUN=(npx --yes bun)
else
  echo "É preciso ter \`bun\` (ou \`npx --yes bun\`)." >&2
  exit 1
fi

DATA_DIR="$(mktemp -d /tmp/vizin-previa-XXXXXX)"
COPY_DIR="$(mktemp -d /tmp/vizin-site-XXXXXX)"
API_PID=""
SITE_PID=""

cleanup() {
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "$SITE_PID" ] && kill "$SITE_PID" 2>/dev/null || true
  rm -rf "$DATA_DIR" "$COPY_DIR"
}
trap cleanup EXIT INT TERM

echo "1/4 Subindo a API local na porta $API_PORT…"
(
  cd "$APP_DIR/vps"
  PORT="$API_PORT" \
  DATA_DIR="$DATA_DIR" \
  BEACONS_JSON="$BEACONS" \
  ACCOUNT_INACTIVE_SECONDS=31536000 \
  ACCOUNT_DELETE_SECONDS=31536000 \
  "${BUN[@]}" run "$VPS_ENTRY"
) >"$DATA_DIR/api.log" 2>&1 &
API_PID=$!

for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! curl -fsS --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
  echo "A API local não subiu. Log:" >&2
  cat "$DATA_DIR/api.log" >&2
  exit 1
fi

echo "2/4 Populando o banco com o cenário de teste…"
python3 "$SEED" "$DATA_DIR/vizin.sqlite"

echo "3/4 Copiando o site e apontando o config.js para a API local…"
# Só o que é necessário para a prévia (o resto não muda).
mkdir -p "$COPY_DIR/assets" "$COPY_DIR/painel"
cp "$ROOT/painel/index.html" "$COPY_DIR/painel/"
cp "$ROOT/assets/styles.css" "$ROOT/assets/config.js" "$ROOT/assets/panel.js" \
   "$ROOT/assets/app.js" "$ROOT/assets/favicon.png" "$ROOT/assets/icon-192.png" \
   "$ROOT/assets/apple-touch-icon.png" "$COPY_DIR/assets/"
cp "$ROOT/site.webmanifest" "$COPY_DIR/"
python3 - "$COPY_DIR/assets/config.js" "$API_PORT" <<'PY'
import re, sys
caminho, porta = sys.argv[1], sys.argv[2]
texto = open(caminho, encoding="utf-8").read()
texto = re.sub(r"apiUrl:\s*'[^']*'", f"apiUrl: 'http://127.0.0.1:{porta}'", texto)
open(caminho, "w", encoding="utf-8").write(texto)
PY

echo "4/4 Servindo o site na porta $SITE_PORT…"
python3 -m http.server "$SITE_PORT" --directory "$COPY_DIR" >"$DATA_DIR/site.log" 2>&1 &
SITE_PID=$!

sleep 1
cat <<EOF

  Painel público pronto:

    Site:  http://127.0.0.1:$SITE_PORT/painel
    API:   http://127.0.0.1:$API_PORT/stats/public

  Estes números são do cenário de teste (o banco real fica na VPS).
  Ctrl+C encerra e apaga tudo.

EOF

wait "$SITE_PID"
