#!/usr/bin/env bash
# Publica o site no dominio publico https://vizin-os.page.gd (InfinityFree).
#
# Este script e apenas um atalho: o trabalho real esta em
# tools/deploy-infinityfree.py (espelho via FTP + conferencia no navegador).
#
#   tools/deploy-infinityfree.sh              # publica e confere no ar
#   tools/deploy-infinityfree.sh --dry-run    # mostra o que seria enviado
#
# Credenciais: site/.deploy-infinityfree.env (gitignored) ou variaveis de
# ambiente INFINITYFREE_FTP_USER / INFINITYFREE_FTP_PASS.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/tools/deploy-infinityfree.py" "$@"
