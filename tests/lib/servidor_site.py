"""Servidor estático local com rotas sem extensão.

O site em produção é servido por CDN/Caddy, onde `/painel` resolve
`painel.html`. O `http.server` do Python não faz isso, então os testes que
dependem de rotas limpas sobem o próprio servidor por aqui.

Uso:
    from lib.servidor_site import servir_site
    httpd, base = servir_site(PORT, {"/painel": "painel.html"})
"""

import functools
import http.server
import os
import socketserver
import threading

# tests/lib/servidor_site.py -> site/
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Rotas sem extensão -> arquivo real.
PAGES = {
    "/painel": "painel.html",
    "/": "index.html",
    "/moderacao": "moderacao.html",
    "/praca-romana": "praca-romana.html",
    "/afiliados": "afiliados.html",
    "/documento": "documento.html",
}


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, *args):
        pass

    def translate_path(self, path):
        clean = path.split("?")[0].split("#")[0]
        if clean in PAGES:
            clean = "/" + PAGES[clean]
        return super().translate_path(clean)


def servir_site(port, pages=None):
    """Sobe o site local na porta e devolve (httpd, base_url)."""

    class Handler(_Handler):
        def translate_path(self, path):
            clean = path.split("?")[0].split("#")[0]
            if pages and clean in pages:
                clean = "/" + pages[clean]
            elif clean in PAGES:
                clean = "/" + PAGES[clean]
            return http.server.SimpleHTTPRequestHandler.translate_path(self, clean)

    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"
