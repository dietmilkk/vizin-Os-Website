#!/usr/bin/env python3
"""Monta a pasta de publicação da Vercel.

Recebe a cópia do site que está no ar (o tar do /var/www/vizinhanca.app na VPS)
e injeta o snippet do Vercel Web Analytics nas 7 páginas públicas.

O site é 100% estático: não há build, npm ou framework. A Vercel serve os
arquivos como estão, então basta garantir que o <head> de cada página carregue
o script de /_vercel/insights/script.js (a rota só existe quando o Web
Analytics está habilitado no projeto).

Uso: montar-publicacao-vercel.py <pasta-com-o-site-publicado> <saida>
"""

import sys
from pathlib import Path

# Bloco do Analytics: cria a fila `window.vaq` e carrega o script da Vercel.
BLOCO = """  <!-- Vercel Web Analytics: visitação e page views do site.
       O script vive na rota /_vercel/insights/script.js, que só existe
       quando o site é servido pela Vercel. No InfinityFree ele não existe
       e nada é coletado (ver "Analytics de visitação" no README). -->
  <script>
    window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments) };
  </script>
  <script defer src="/_vercel/insights/script.js"></script>
"""

PAGINAS = [
    "index.html",
    "afiliados/index.html",
    "documento/index.html",
    "manifesto/index.html",
    "moderacao/index.html",
    "painel/index.html",
    "404.html",
]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    origem = Path(sys.argv[1])
    saida = Path(sys.argv[2])

    if saida.exists():
        raise SystemExit(f"a saida ja existe: {saida}")
    saida.mkdir(parents=True)

    # 1) copia tudo o que esta publicado
    for arquivo in sorted(origem.rglob("*")):
        if arquivo.is_dir():
            continue
        destino = saida / arquivo.relative_to(origem)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(arquivo.read_bytes())

    # 2) injeta o snippet nas paginas publicas
    faltando = []
    for pagina in PAGINAS:
        arquivo = saida / pagina
        if not arquivo.exists():
            faltando.append(pagina)
            continue
        html = arquivo.read_text(encoding="utf-8")
        if "/_vercel/insights/script.js" in html:
            continue
        if "</head>" not in html:
            raise SystemExit(f"{pagina}: nao achei </head>")
        html = html.replace("</head>", f"{BLOCO}</head>", 1)
        arquivo.write_text(html, encoding="utf-8")

    if faltando:
        raise SystemExit("paginas ausentes no site publicado: " + ", ".join(faltando))

    # 3) ignora o que nao deve virar arquivo publico na Vercel
    (saida / ".vercelignore").write_text(
        "tools/\n"
        "tests/\n"
        "deploy/\n"
        "dist/\n"
        ".github/\n"
        ".git\n"
        "README.md\n"
        "prompt-afiliados.md\n"
        ".htaccess\n"
        ".deploy-*\n"
        ".env*\n",
        encoding="utf-8",
    )

    print(f"publicacao montada em {saida}")
    for pagina in PAGINAS:
        texto = (saida / pagina).read_text(encoding="utf-8")
        print(f"  {pagina}: snippet={'sim' if '/_vercel/insights/script.js' in texto else 'NAO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
