#!/usr/bin/env bash
# Monta um pacote (.zip) com o site publico pronto para subir pelo painel do
# InfinityFree (https://client.infinityfree.com -> File Manager -> Upload).
#
# O InfinityFree aceita .zip e extrai no lugar. O pacote contem apenas o que
# deve estar no ar: sem README, sem ferramentas, sem testes, sem documentos
# de trabalho.
#
# Uso:
#   tools/pacote-infinityfree.sh          # cria dist/vizin-os-page-gd.zip
#
# Requisitos: zip (ou python3 com zipfile como reserva).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESTINO_DIR="$ROOT/dist"
DESTINO="$DESTINO_DIR/vizin-os-page-gd.zip"

# Arquivos e pastas que compose o site publico.
PUBLICOS=(
  "index.html"
  "404.html"
  "robots.txt"
  "sitemap.xml"
  "site.webmanifest"
  "_headers"
  "_redirects"
  ".htaccess"
  "assets"
  "painel/index.html"
  "afiliados/index.html"
  "documento/index.html"
  "moderacao/index.html"
)

rm -rf "$DESTINO_DIR"
mkdir -p "$DESTINO_DIR"

if command -v zip >/dev/null 2>&1; then
  ARQUIVOS=()
  for item in "${PUBLICOS[@]}"; do
    [ -e "$ROOT/$item" ] && ARQUIVOS+=("$item")
  done
  # O zip guarda os caminhos relativos a raiz do site.
  ( cd "$ROOT" && zip -q -r "$DESTINO" "${ARQUIVOS[@]}" )
else
  python3 - "$ROOT" "$DESTINO" "${PUBLICOS[@]}" <<'PY'
import os, sys, zipfile

root, destino = sys.argv[1], sys.argv[2]
publicos = sys.argv[3:]
with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
    for item in publicos:
        caminho = os.path.join(root, item)
        if os.path.isfile(caminho):
            z.write(caminho, item)
        elif os.path.isdir(caminho):
            for base, _, arquivos in os.walk(caminho):
                for arquivo in sorted(arquivos):
                    completo = os.path.join(base, arquivo)
                    z.write(completo, os.path.relpath(completo, root))
PY
fi

TAMANHO="$(du -h "$DESTINO" | cut -f1)"
echo "==> Pacote pronto: $DESTINO ($TAMANHO)"
echo
echo "Como publicar (InfinityFree):"
echo "  1. Entre em https://client.infinityfree.com"
echo "  2. Abra a conta do dominio vizin-os.page.gd"
echo "  3. File Manager -> htdocs -> Upload -> envie este .zip"
echo "  4. Extraia o .zip no htdocs"
echo "  5. Apague da pasta htdocs os arquivos que nao devem ficar no ar:"
echo "       README.md, prompt-afiliados.md, pasta tools/, pasta tests/"
echo "  6. Confira: https://vizin-os.page.gd"
